from __future__ import annotations

import json
import os
from pathlib import Path

from gripprobe.adapters.base import ShellAdapter
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.failure_reason import infer_failure_reason
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.validator_runner import evaluate_validators


class OpencodeAdapter(ShellAdapter):
    def _resolve_source_config_path(self) -> Path | None:
        explicit = self.shell_spec.config_path or os.environ.get("GRIPPROBE_OPENCODE_CONFIG")
        if explicit:
            path = Path(explicit).expanduser()
            if path.exists():
                return path
        default_path = Path.home() / ".config" / "opencode" / "opencode.json"
        if default_path.exists():
            return default_path
        return None

    def _prepare_opencode_home(self, case: CaseDefinition, runtime_env: dict[str, str]) -> tuple[Path, Path]:
        config_path = self._resolve_source_config_path()
        opencode_home = Path(runtime_env["HOME"])
        config_dir = Path(runtime_env["XDG_CONFIG_HOME"]) / "opencode"
        config_dir.mkdir(parents=True, exist_ok=True)

        api_base = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        if not api_base.endswith("/v1"):
            api_base = f"{api_base}/v1"
        model_key = case.backend_model_id
        source_payload: dict[str, object] = {}
        if config_path:
            source_payload = json.loads(config_path.read_text(encoding="utf-8"))

        provider_payload = (
            source_payload.get("provider", {}) if isinstance(source_payload.get("provider", {}), dict) else {}
        )
        ollama_payload = provider_payload.get("ollama", {}) if isinstance(provider_payload, dict) else {}
        if not isinstance(ollama_payload, dict):
            ollama_payload = {}

        options = ollama_payload.get("options", {}) if isinstance(ollama_payload.get("options", {}), dict) else {}
        models = ollama_payload.get("models", {}) if isinstance(ollama_payload.get("models", {}), dict) else {}

        payload = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "ollama": {
                    "npm": ollama_payload.get("npm", "@ai-sdk/openai-compatible"),
                    "name": ollama_payload.get("name", "Ollama"),
                    "options": {
                        "baseURL": options.get("baseURL", api_base),
                        "apiKey": options.get("apiKey", "dummy"),
                        "timeout": options.get("timeout", 600000),
                        "chunkTimeout": options.get("chunkTimeout", 30000),
                    },
                    "models": {
                        model_key: models.get(model_key, {"name": case.model_label}),
                    },
                }
            },
            "model": f"ollama/{model_key}",
            "small_model": f"ollama/{model_key}",
            "autoupdate": False,
        }

        isolated_config = config_dir / "opencode.json"
        isolated_config.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return opencode_home, isolated_config

    def _classify(self, test_spec: TestSpec, workspace: Path, stdout: str, stderr: str) -> tuple[CaseStatus, ToolInvocation, int, str, str]:
        if "does not support tools" in stdout or "does not support tools" in stderr:
            return "TOOL_UNSUPPORTED", "no", 0, "", ""
        ok, expected, observed = evaluate_validators(test_spec, workspace)
        if ok:
            return "PASS", "yes", 100, expected, observed
        combined = f"{stdout}\n{stderr}"
        if any(marker in combined for marker in ('"tool"', '"call"', '"bash"', '"read"', '"edit"', '"write"')):
            return "FAIL", "maybe", 0, expected, observed
        if "DONE" in combined or "FAIL" in combined:
            return "FAIL", "no", 0, expected, observed
        return "FAIL", "maybe", 0, expected, observed

    def run_case(self, case: CaseDefinition, model_spec: ModelSpec, test_spec: TestSpec):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "artifacts").mkdir(exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")

        warmup_stdout = case.case_dir / "warmup.stdout"
        warmup_stderr = case.case_dir / "warmup.stderr"
        measured_stdout = case.case_dir / "measured.stdout"
        measured_stderr = case.case_dir / "measured.stderr"

        env = os.environ.copy()
        env.update(self.shell_spec.env)
        warmup_runtime_env = self._prepare_runtime_dirs(case, self.shell_spec.id, "warmup")
        measured_runtime_env = self._prepare_runtime_dirs(case, self.shell_spec.id, "measured")
        _warmup_home, warmup_config = self._prepare_opencode_home(case, warmup_runtime_env)
        _measured_home, measured_config = self._prepare_opencode_home(case, measured_runtime_env)
        shared_env = {
            **env,
        }
        warmup_env = {**shared_env, **warmup_runtime_env, "GRIPPROBE_WORKSPACE": str(case.warmup_workspace_dir)}
        measured_env = {**shared_env, **measured_runtime_env, "GRIPPROBE_WORKSPACE": str(case.workspace_dir)}

        warmup_args = [
            self.shell_spec.executable,
            "run",
            "--format",
            "json",
            "--dir",
            str(case.warmup_workspace_dir),
            "--model",
            f"{case.backend_id}/{case.backend_model_id}",
            "--dangerously-skip-permissions",
            case.prompt,
        ]
        measured_args = [
            self.shell_spec.executable,
            "run",
            "--format",
            "json",
            "--dir",
            str(case.workspace_dir),
            "--model",
            f"{case.backend_id}/{case.backend_model_id}",
            "--dangerously-skip-permissions",
            case.prompt,
        ]
        warmup_command = self._command_text(case, warmup_args, warmup_env, workspace_dir=case.warmup_workspace_dir)
        measured_command = self._command_text(case, measured_args, measured_env, workspace_dir=case.workspace_dir)

        warmup_rc, warmup_s, warmup_started_at, warmup_finished_at = self.run_command(
            case,
            warmup_args,
            warmup_env,
            warmup_stdout,
            warmup_stderr,
            workspace_dir=case.warmup_workspace_dir,
        )
        measured_rc, measured_s, measured_started_at, measured_finished_at = self.run_command(
            case,
            measured_args,
            measured_env,
            measured_stdout,
            measured_stderr,
            workspace_dir=case.workspace_dir,
        )

        stdout_text = measured_stdout.read_text(encoding="utf-8", errors="replace") if measured_stdout.exists() else ""
        stderr_text = measured_stderr.read_text(encoding="utf-8", errors="replace") if measured_stderr.exists() else ""
        validators_ok, validators_expected, validators_observed = evaluate_validators(test_spec, case.workspace_dir)

        artifact_reached_before_timeout = False
        if measured_rc == 124:
            artifact_reached_before_timeout = validators_ok
            status: CaseStatus = "TIMEOUT"
            invoked: ToolInvocation = "yes" if validators_ok else "no"
            match_percent = 100 if validators_ok else 0
            expected = validators_expected
            observed = validators_observed
        else:
            status, invoked, match_percent, expected, observed = self._classify(test_spec, case.workspace_dir, stdout_text, stderr_text)
        failure_reason = infer_failure_reason(status, invoked, stdout_text, stderr_text)

        (case.case_dir / "expected.txt").write_text(expected + ("\n" if expected else ""), encoding="utf-8")
        (case.case_dir / "observed.txt").write_text(observed + ("\n" if observed else ""), encoding="utf-8")

        return build_case_result(
            case=case,
            model_spec=model_spec,
            test_spec=test_spec,
            status=status,
            invoked=invoked,
            match_percent=match_percent,
            warmup_seconds=warmup_s,
            measured_seconds=measured_s,
            metadata={
                "warmup_exit_code": warmup_rc,
                "warmup_started_at": warmup_started_at,
                "warmup_finished_at": warmup_finished_at,
                "measured_exit_code": measured_rc,
                "measured_started_at": measured_started_at,
                "measured_finished_at": measured_finished_at,
                "tool_format": case.tool_format,
                "allowed_tools": case.allowed_tools or self.shell_spec.default_tools,
                "warmup_command": warmup_command,
                "measured_command": measured_command,
                "model_selection": "isolated-config",
                "model_hash": case.model_hash,
                "artifact_reached_before_timeout": artifact_reached_before_timeout,
                "opencode_config_path": str(measured_config),
                "failure_reason": failure_reason,
            },
        )
