from __future__ import annotations

import os
from pathlib import Path
import yaml

from gripprobe.adapters.base import ShellAdapter
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.validator_runner import evaluate_validators


class ContinueCliAdapter(ShellAdapter):
    def _resolve_source_config_path(self) -> Path | None:
        explicit = self.shell_spec.config_path or os.environ.get("GRIPPROBE_CONTINUE_CONFIG")
        if explicit:
            path = Path(explicit).expanduser()
            if path.exists():
                return path
        default_path = Path.home() / ".continue" / "config.yaml"
        if default_path.exists():
            return default_path
        return None

    def _prepare_continue_home(self, case: CaseDefinition) -> tuple[Path, Path]:
        config_path = self._resolve_source_config_path()
        continue_home = case.case_dir / "continue-home"
        continue_dir = continue_home / ".continue"
        continue_dir.mkdir(parents=True, exist_ok=True)

        api_base = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        model_entry: dict[str, object] = {
            "name": case.model_label,
            "provider": "ollama",
            "model": case.backend_model_id,
            "apiBase": api_base,
            "roles": ["chat", "edit", "apply"],
        }

        if config_path:
            payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            models = payload.get("models")
            if isinstance(models, list):
                for item in models:
                    if not isinstance(item, dict):
                        continue
                    if item.get("model") == case.backend_model_id or item.get("name") == case.model_label:
                        model_entry = item
                        break
            payload["models"] = [model_entry]
        else:
            payload = {
                "name": "gripprobe-continue",
                "version": "0.0.1",
                "schema": "v1",
                "defaultCompletionOptions": {"contextLength": 2048},
                "models": [model_entry],
            }

        isolated_config = continue_dir / "config.yaml"
        isolated_config.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        permissions_path = continue_dir / "permissions.yaml"
        permissions_path.write_text(
            "allow: []\nask: []\nexclude: []\n",
            encoding="utf-8",
        )
        return continue_home, isolated_config

    def _classify(self, test_spec: TestSpec, workspace: Path, stdout: str, stderr: str) -> tuple[CaseStatus, ToolInvocation, int, str, str]:
        if "does not support tools" in stdout or "does not support tools" in stderr:
            return "TOOL_UNSUPPORTED", "no", 0, "", ""
        ok, expected, observed = evaluate_validators(test_spec, workspace)
        if ok:
            return "PASS", "yes", 100, expected, observed
        if 'Required parameter "' in stdout or 'Required parameter "' in stderr:
            return "FAIL", "maybe", 0, expected, observed
        return "FAIL", ("maybe" if ("Read(" in stdout or "System:" in stdout) else "no"), 0, expected, observed

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
        continue_home, isolated_config = self._prepare_continue_home(case)
        warmup_env = {**env, "GRIPPROBE_WORKSPACE": str(case.warmup_workspace_dir)}
        measured_env = {**env, "GRIPPROBE_WORKSPACE": str(case.workspace_dir)}
        warmup_env["HOME"] = str(continue_home)
        measured_env["HOME"] = str(continue_home)
        allowed_tools = case.allowed_tools or self.shell_spec.default_tools

        base_args = [
            self.shell_spec.executable,
            "--config",
            str(isolated_config),
            "-p",
            "--auto",
            "--silent",
            case.prompt,
        ]
        for tool_name in allowed_tools:
            base_args[1:1] = ["--allow", tool_name]

        warmup_rc, warmup_s, warmup_started_at, warmup_finished_at = self.run_command(
            case,
            base_args,
            warmup_env,
            warmup_stdout,
            warmup_stderr,
            workspace_dir=case.warmup_workspace_dir,
        )
        measured_rc, measured_s, measured_started_at, measured_finished_at = self.run_command(
            case,
            base_args,
            measured_env,
            measured_stdout,
            measured_stderr,
            workspace_dir=case.workspace_dir,
        )

        stdout_text = measured_stdout.read_text(encoding="utf-8", errors="replace") if measured_stdout.exists() else ""
        stderr_text = measured_stderr.read_text(encoding="utf-8", errors="replace") if measured_stderr.exists() else ""
        validators_ok, validators_expected, validators_observed = evaluate_validators(test_spec, case.workspace_dir)

        status: CaseStatus
        invoked: ToolInvocation
        artifact_reached_before_timeout = False
        if measured_rc == 124:
            artifact_reached_before_timeout = validators_ok
            status = "TIMEOUT"
            invoked = "yes" if validators_ok else "no"
            match_percent = 100 if validators_ok else 0
            expected = validators_expected
            observed = validators_observed
        else:
            status, invoked, match_percent, expected, observed = self._classify(test_spec, case.workspace_dir, stdout_text, stderr_text)

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
                "allowed_tools": allowed_tools,
                "model_selection": "isolated-config",
                "model_hash": case.model_hash,
                "artifact_reached_before_timeout": artifact_reached_before_timeout,
                "continue_config_path": str(isolated_config),
            },
        )
