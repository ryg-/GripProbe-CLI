from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from gripprobe.adapters.base import CliAgentAdapter
from gripprobe.command_runner import CommandRunner
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.failure_reason import infer_failure_reason
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.validator_runner import evaluate_validators


class CodexAdapter(CliAgentAdapter):
    _DEFAULT_MODEL_METADATA: dict[str, Any] = {
        "description": "Local Ollama model metadata override",
        "default_reasoning_level": "medium",
        "supported_reasoning_levels": [
            {"effort": "low", "description": "low"},
            {"effort": "medium", "description": "medium"},
            {"effort": "high", "description": "high"},
            {"effort": "xhigh", "description": "xhigh"},
        ],
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 1,
        "additional_speed_tiers": [],
        "availability_nux": None,
        "upgrade": None,
        "base_instructions": "You are a coding assistant.",
        "model_messages": {
            "instructions_template": "{{ personality }}",
            "instructions_variables": {"personality_default": ""},
        },
        "supports_reasoning_summaries": True,
        "default_reasoning_summary": "none",
        "support_verbosity": True,
        "default_verbosity": "low",
        "apply_patch_tool_type": "freeform",
        "web_search_tool_type": "text_and_image",
        "truncation_policy": {"mode": "tokens", "limit": 10000},
        "supports_parallel_tool_calls": True,
        "supports_image_detail_original": False,
        "context_window": 131072,
        "max_context_window": 131072,
        "effective_context_window_percent": 95,
        "experimental_supported_tools": [],
        "input_modalities": ["text"],
        "supports_search_tool": True,
    }

    @staticmethod
    def _normalize_http_base(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            raw = "http://127.0.0.1:11434"
        if "://" not in raw:
            raw = f"http://{raw}"
        return raw.rstrip("/")

    def _apply_oss_base_env_for_phase(
        self,
        case: CaseDefinition,
        env: dict[str, str],
        phase: str,
    ) -> None:
        # Codex OSS provider uses its own env knobs and does not read OLLAMA_HOST directly.
        base = self._resolve_case_ollama_host_for_phase(case, env, phase)
        env["CODEX_OSS_BASE_URL"] = base if base.endswith("/v1") else f"{base}/v1"
        parsed = urlparse(base)
        if parsed.port:
            env["CODEX_OSS_PORT"] = str(parsed.port)

    @staticmethod
    def _infer_invoked(stdout: str, stderr: str) -> ToolInvocation:
        combined = f"{stdout}\n{stderr}"
        yes_markers = (
            '"recipient_name":"functions.exec_command"',
            '"recipient_name":"functions.write_stdin"',
            '"recipient_name":"functions.apply_patch"',
            '"type":"tool_use"',
            '"type":"command_execution"',
            '"type":"function_call"',
            '"type":"tool_call"',
            '"tool_name":"',
            "unsupported call:",
        )
        if any(marker in combined for marker in yes_markers):
            return "yes"
        if "can't directly execute shell commands" in combined.lower():
            return "no"
        maybe_markers = ("```bash", "```sh", "```shell")
        if any(marker in combined for marker in maybe_markers):
            return "maybe"
        return "no"

    def _classify(
        self,
        test_spec: TestSpec,
        workspace: Path,
        stdout: str,
        stderr: str,
    ) -> tuple[CaseStatus, ToolInvocation, int, str, str]:
        combined = f"{stdout}\n{stderr}".lower()
        unsupported_markers = (
            "does not support tools",
            "apply_patch tool is not available",
            "no apply_patch tool available",
            "tool is not available in this environment",
        )
        if any(marker in combined for marker in unsupported_markers):
            return "TOOL_UNSUPPORTED", "no", 0, "", ""
        ok, expected, observed = evaluate_validators(test_spec, workspace)
        if ok:
            return "PASS", "yes", 100, expected, observed
        return "FAIL", self._infer_invoked(stdout, stderr), 0, expected, observed

    @classmethod
    def _build_model_catalog_payload(cls, model_id: str) -> dict[str, object]:
        model_entry = {
            "slug": model_id,
            "display_name": model_id,
            **cls._DEFAULT_MODEL_METADATA,
        }
        return {"models": [model_entry]}

    @classmethod
    def _write_model_catalog(cls, case: CaseDefinition, model_id: str) -> Path:
        model_catalog_path = case.case_dir / "artifacts" / "codex-model-catalog.json"
        payload = cls._build_model_catalog_payload(model_id)
        model_catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return model_catalog_path

    def _resolve_source_config_path(self) -> Path | None:
        explicit = self.cli_agent_spec.config_path or os.environ.get("GRIPPROBE_CODEX_CONFIG")
        if explicit:
            explicit_path = Path(explicit).expanduser()
            return explicit_path if explicit_path.exists() else None
        default_path = Path.home() / ".codex" / "config.toml"
        return default_path if default_path.exists() else None

    @staticmethod
    def _prepare_codex_home(runtime_env: dict[str, str], source_config_path: Path | None) -> Path:
        codex_home = Path(runtime_env["HOME"]) / ".codex"
        codex_home.mkdir(parents=True, exist_ok=True)
        if source_config_path:
            target_path = codex_home / "config.toml"
            target_path.write_text(source_config_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        return codex_home

    def _capture_source_config_artifact(self, case: CaseDefinition, source_config_path: Path | None) -> dict[str, object]:
        if source_config_path is None:
            return {}
        source_text = source_config_path.read_text(encoding="utf-8", errors="replace")
        source_env = {"HOME": str(Path.home())}
        source_text_s = self._sanitize_aux_text(source_text, source_env)
        artifact_rel = "artifacts/codex-config-source.toml"
        (case.case_dir / artifact_rel).write_text(source_text_s, encoding="utf-8")
        return {"codex_config_source_path": artifact_rel}

    @staticmethod
    def _codex_policy(model_spec: ModelSpec) -> dict[str, Any]:
        cli_agent_options = (model_spec.policy_overrides or {}).get("cli_agent_options")
        if not isinstance(cli_agent_options, dict):
            return {}
        policy = cli_agent_options.get("codex")
        return policy if isinstance(policy, dict) else {}

    def _build_args(self, case: CaseDefinition, workspace_dir: Path, model_catalog_path: Path) -> list[str]:
        raise RuntimeError("_build_args requires model_spec")

    def _build_args_for_model(
        self,
        case: CaseDefinition,
        model_spec: ModelSpec,
        workspace_dir: Path,
        model_catalog_path: Path,
    ) -> list[str]:
        policy = self._codex_policy(model_spec)
        args = [
            self.cli_agent_spec.executable,
            "-a",
            "never",
            "exec",
            "--oss",
            "--local-provider",
            case.backend_id,
            "-m",
            case.backend_model_id,
            "--sandbox",
            "danger-full-access",
            "--skip-git-repo-check",
            "--ephemeral",
            "--json",
            "-c",
            f"model_catalog_json={model_catalog_path}",
            "--cd",
            str(workspace_dir),
        ]
        if policy.get("ignore_user_config") is True:
            args.append("--ignore-user-config")
        if policy.get("ignore_rules") is True:
            args.append("--ignore-rules")
        args.append(case.prompt)
        return args

    def _run_aux_command(
        self,
        case: CaseDefinition,
        args: list[str],
        env: dict[str, str],
        workspace_dir: Path,
        timeout_seconds: int = 15,
    ) -> tuple[int, str, str]:
        try:
            proc = subprocess.run(
                self._wrap_command(case, args, env, workspace_dir),
                cwd=str(workspace_dir),
                env=self._wrap_env(case, env),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return 1, "", str(exc)
        return proc.returncode, (proc.stdout or ""), (proc.stderr or "")

    @staticmethod
    def _sanitize_aux_text(text: str, env: dict[str, str]) -> str:
        sanitized = text
        home = env.get("HOME", "")
        codex_home = env.get("CODEX_HOME", "")
        if home:
            sanitized = sanitized.replace(home, "$HOME")
        if codex_home:
            sanitized = sanitized.replace(codex_home, "$CODEX_HOME")
        return sanitized

    def _collect_codex_runtime_artifacts(
        self,
        case: CaseDefinition,
        phase: str,
        env: dict[str, str],
        workspace_dir: Path,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {}
        artifacts_dir = case.case_dir / "artifacts"

        enable_args = [self.cli_agent_spec.executable, "features", "enable", "apply_patch_freeform"]
        enable_rc, enable_stdout, enable_stderr = self._run_aux_command(case, enable_args, env, workspace_dir)
        enable_stdout_s = self._sanitize_aux_text(enable_stdout, env)
        enable_stderr_s = self._sanitize_aux_text(enable_stderr, env)
        (artifacts_dir / f"codex-features-enable-{phase}.stdout").write_text(enable_stdout_s, encoding="utf-8")
        (artifacts_dir / f"codex-features-enable-{phase}.stderr").write_text(enable_stderr_s, encoding="utf-8")
        metadata[f"codex_features_enable_{phase}_exit_code"] = enable_rc

        list_args = [self.cli_agent_spec.executable, "features", "list"]
        list_rc, list_stdout, list_stderr = self._run_aux_command(case, list_args, env, workspace_dir)
        list_stdout_s = self._sanitize_aux_text(list_stdout, env)
        list_stderr_s = self._sanitize_aux_text(list_stderr, env)
        (artifacts_dir / f"codex-features-{phase}.txt").write_text(list_stdout_s, encoding="utf-8")
        (artifacts_dir / f"codex-features-{phase}.stderr").write_text(list_stderr_s, encoding="utf-8")
        metadata[f"codex_features_list_{phase}_exit_code"] = list_rc
        metadata[f"codex_features_list_{phase}"] = list_stdout_s

        codex_config_path = Path(env["CODEX_HOME"]) / "config.toml"
        if codex_config_path.exists():
            config_text = codex_config_path.read_text(encoding="utf-8", errors="replace")
            config_text_s = self._sanitize_aux_text(config_text, env)
            (artifacts_dir / f"codex-config-{phase}.toml").write_text(config_text_s, encoding="utf-8")
            metadata[f"codex_config_{phase}_path"] = f"artifacts/codex-config-{phase}.toml"

        return metadata

    def _prune_runtime_cache(self, case: CaseDefinition) -> None:
        for phase in ("warmup", "measured"):
            plugins_cache = case.case_dir / "runtime" / self.cli_agent_spec.id / phase / "home" / ".codex" / ".tmp" / "plugins"
            if plugins_cache.exists():
                shutil.rmtree(plugins_cache, ignore_errors=True)

    def run_case(
        self,
        case: CaseDefinition,
        model_spec: ModelSpec,
        test_spec: TestSpec,
        command_runner: CommandRunner | None = None,
    ):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "artifacts").mkdir(exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")
        model_catalog_path = self._write_model_catalog(case, case.backend_model_id)
        source_config_path = self._resolve_source_config_path()
        source_config_metadata = self._capture_source_config_artifact(case, source_config_path)

        warmup_stdout = case.case_dir / "warmup.stdout"
        warmup_stderr = case.case_dir / "warmup.stderr"
        measured_stdout = case.case_dir / "measured.stdout"
        measured_stderr = case.case_dir / "measured.stderr"

        env = os.environ.copy()
        env.update(self.cli_agent_spec.env)
        self._apply_case_backend_env_overrides(case, env)

        warmup_runtime_env = self._prepare_runtime_dirs(case, self.cli_agent_spec.id, "warmup")
        measured_runtime_env = self._prepare_runtime_dirs(case, self.cli_agent_spec.id, "measured")
        warmup_codex_home = self._prepare_codex_home(warmup_runtime_env, source_config_path)
        measured_codex_home = self._prepare_codex_home(measured_runtime_env, source_config_path)

        warmup_env = {
            **env,
            **warmup_runtime_env,
            "CODEX_HOME": str(warmup_codex_home),
            "GRIPPROBE_WORKSPACE": str(case.warmup_workspace_dir),
        }
        measured_env = {
            **env,
            **measured_runtime_env,
            "CODEX_HOME": str(measured_codex_home),
            "GRIPPROBE_WORKSPACE": str(case.workspace_dir),
        }
        self._apply_oss_base_env_for_phase(case, warmup_env, "warmup")
        self._apply_oss_base_env_for_phase(case, measured_env, "measured")
        warmup_feature_metadata = self._collect_codex_runtime_artifacts(case, "warmup", warmup_env, case.warmup_workspace_dir)
        measured_feature_metadata = self._collect_codex_runtime_artifacts(case, "measured", measured_env, case.workspace_dir)

        warmup_args = self._build_args_for_model(case, model_spec, case.warmup_workspace_dir, model_catalog_path)
        measured_args = self._build_args_for_model(case, model_spec, case.workspace_dir, model_catalog_path)
        warmup_command = self._command_text(case, warmup_args, warmup_env, workspace_dir=case.warmup_workspace_dir)
        measured_command = self._command_text(case, measured_args, measured_env, workspace_dir=case.workspace_dir)

        warmup_rc, warmup_s, warmup_started_at, warmup_finished_at = self._run_case_command(
            command_runner,
            case=case,
            args=warmup_args,
            env=warmup_env,
            stdout_path=warmup_stdout,
            stderr_path=warmup_stderr,
            workspace_dir=case.warmup_workspace_dir,
        )
        measured_rc, measured_s, measured_started_at, measured_finished_at = self._run_case_command(
            command_runner,
            case=case,
            args=measured_args,
            env=measured_env,
            stdout_path=measured_stdout,
            stderr_path=measured_stderr,
            workspace_dir=case.workspace_dir,
        )

        stdout_text = measured_stdout.read_text(encoding="utf-8", errors="replace") if measured_stdout.exists() else ""
        stderr_text = measured_stderr.read_text(encoding="utf-8", errors="replace") if measured_stderr.exists() else ""
        validators_ok, validators_expected, validators_observed = evaluate_validators(test_spec, case.workspace_dir)
        self._prune_runtime_cache(case)

        artifact_reached_before_timeout = False
        if measured_rc == 124:
            artifact_reached_before_timeout = validators_ok
            status: CaseStatus = "TIMEOUT"
            invoked: ToolInvocation = "yes" if validators_ok else self._infer_invoked(stdout_text, stderr_text)
            match_percent = 100 if validators_ok else 0
            expected = validators_expected
            observed = validators_observed
        else:
            status, invoked, match_percent, expected, observed = self._classify(
                test_spec,
                case.workspace_dir,
                stdout_text,
                stderr_text,
            )
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
                "allowed_tools": case.allowed_tools or self.cli_agent_spec.default_tools,
                "warmup_command": warmup_command,
                "measured_command": measured_command,
                "model_selection": "cli-model",
                "model_hash": case.model_hash,
                "codex_model_catalog_path": "artifacts/codex-model-catalog.json",
                **source_config_metadata,
                **warmup_feature_metadata,
                **measured_feature_metadata,
                "artifact_reached_before_timeout": artifact_reached_before_timeout,
                "failure_reason": failure_reason,
            },
        )
