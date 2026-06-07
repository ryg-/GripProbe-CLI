from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable
import yaml

from gripprobe.adapters.base import CliAgentAdapter
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.failure_reason import infer_failure_reason
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.validator_runner import evaluate_validators


class ContinueCliAdapter(CliAgentAdapter):
    _CONTINUE_TOOL_NAME_MAP = {
        "shell": "Bash",
        "read": "Read",
        "save": "Write",
        "write": "Write",
        "patch": "MultiEdit",
        "fetch": "Fetch",
        "list": "List",
    }

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _runtime_patch_specs_path(self) -> Path:
        return self._repo_root() / "specs" / "cli_agents" / "patches" / f"{self.cli_agent_spec.id}.yaml"

    def _load_runtime_patch_specs(self) -> list[dict[str, Any]]:
        specs_path = self._runtime_patch_specs_path()
        if not specs_path.exists():
            return []
        payload = yaml.safe_load(specs_path.read_text(encoding="utf-8")) or {}
        patches = payload.get("patches")
        if not isinstance(patches, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in patches:
            if isinstance(item, dict):
                normalized.append(item)
        return normalized

    def _apply_runtime_patches(self, patch_root: Path, replacements: dict[str, str]) -> bool:
        patch_specs = self._load_runtime_patch_specs()
        if not patch_specs:
            return False
        applied_any = False
        for patch in patch_specs:
            file_relpath = str(patch.get("file") or "").strip()
            pattern_text = str(patch.get("pattern") or "")
            replacement_template = str(patch.get("replacement") or "")
            if not file_relpath or not pattern_text or not replacement_template:
                return False
            target_file = patch_root / file_relpath
            if not target_file.exists():
                return False
            content = target_file.read_text(encoding="utf-8")
            replacement = replacement_template
            for key, value in replacements.items():
                replacement = replacement.replace(f"{{{{{key}}}}}", value)
            patched, replaced_count = re.subn(pattern_text, replacement, content, count=1, flags=re.MULTILINE)
            if replaced_count != 1:
                return False
            target_file.write_text(patched, encoding="utf-8")
            applied_any = True
        return applied_any

    def _resolve_allowed_continue_tool_names(self, case: CaseDefinition) -> list[str]:
        raw_tools = case.allowed_tools or self.cli_agent_spec.default_tools
        names: list[str] = []
        for tool_name in raw_tools:
            resolved = self._CONTINUE_TOOL_NAME_MAP.get(tool_name, tool_name)
            if resolved not in names:
                names.append(resolved)
        return names

    @staticmethod
    def _continue_policy(model_spec: ModelSpec) -> dict[str, Any]:
        cli_agent_options = (model_spec.policy_overrides or {}).get("cli_agent_options")
        if not isinstance(cli_agent_options, dict):
            return {}
        options = cli_agent_options.get("continue-cli")
        return options if isinstance(options, dict) else {}

    def _resolve_context_length(self, model_spec: ModelSpec) -> int:
        value = self._continue_policy(model_spec).get("context_length")
        return value if isinstance(value, int) and value > 0 else 2048

    def _use_minimal_system_prompt(self, model_spec: ModelSpec) -> bool:
        return self._continue_policy(model_spec).get("minimal_system_prompt") is True

    def _resolve_source_config_path(self) -> Path | None:
        explicit = self.cli_agent_spec.config_path or os.environ.get("GRIPPROBE_CONTINUE_CONFIG")
        if explicit:
            path = Path(explicit).expanduser()
            if path.exists():
                return path
        default_path = Path.home() / ".continue" / "config.yaml"
        if default_path.exists():
            return default_path
        return None

    def _prepare_continue_home(
        self,
        case: CaseDefinition,
        model_spec: ModelSpec,
        runtime_env: dict[str, str],
        base_env: dict[str, str],
        phase: str,
    ) -> tuple[Path, Path]:
        config_path = self._resolve_source_config_path()
        continue_home = Path(runtime_env["HOME"])
        continue_dir = continue_home / ".continue"
        continue_dir.mkdir(parents=True, exist_ok=True)

        api_base = self._resolve_case_ollama_host_for_phase(case, base_env, phase)
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
            if isinstance(model_entry, dict):
                model_entry = dict(model_entry)
                model_entry["apiBase"] = api_base
            payload["models"] = [model_entry]
        else:
            payload = {
                "name": "gripprobe-continue",
                "version": "0.0.1",
                "schema": "v1",
                "defaultCompletionOptions": {"contextLength": self._resolve_context_length(model_spec)},
                "models": [model_entry],
            }
        if self._use_minimal_system_prompt(model_spec):
            chat_options = model_entry.get("chatOptions")
            if not isinstance(chat_options, dict):
                chat_options = {}
            chat_options["baseSystemMessage"] = ""
            chat_options["baseAgentSystemMessage"] = ""
            chat_options["basePlanSystemMessage"] = ""
            model_entry["chatOptions"] = chat_options
            payload["models"] = [model_entry]
            payload["rules"] = []

        isolated_config = continue_dir / "config.yaml"
        isolated_config.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        permissions_path = continue_dir / "permissions.yaml"
        permissions_path.write_text(
            "allow: []\nask: []\nexclude: []\n",
            encoding="utf-8",
        )
        return continue_home, isolated_config

    def _escape_js_template(self, text: str) -> str:
        return text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    def _prepare_patched_continue_cli(
        self,
        case: CaseDefinition,
        model_spec: ModelSpec,
        runtime_env: dict[str, str],
    ) -> tuple[list[str], bool]:
        executable_name = str(self.cli_agent_spec.executable)
        policy = self._continue_policy(model_spec)
        if policy.get("runtime_patches") is not True:
            return [executable_name], False
        resolve_executable: Callable[[str], str | None] = getattr(shutil, "which")
        executable = resolve_executable(executable_name)
        if not executable:
            return [executable_name], False
        resolved = Path(executable).resolve()
        package_root: Path | None = None
        for candidate in [resolved.parent, *resolved.parents]:
            if (candidate / "dist" / "cn.js").exists():
                package_root = candidate
                break
        if package_root is None:
            return [executable_name], False

        patch_root = Path(runtime_env["HOME"]) / ".continue-cli-patched"
        if patch_root.exists():
            shutil.rmtree(patch_root)
        shutil.copytree(package_root, patch_root)
        dist_cli = patch_root / "dist" / "cn.js"
        replacement = policy.get("patch_system_text")
        if not isinstance(replacement, str):
            replacement = ""
        replacement = replacement.strip()
        if not replacement:
            replacement = "Use available tools to answer the user's request concisely."
        escaped = self._escape_js_template(replacement)
        allowed_tool_names = self._resolve_allowed_continue_tool_names(case)
        allowed_tools_js = ",".join(f'"{self._escape_js_template(name)}"' for name in allowed_tool_names)
        patch_applied = self._apply_runtime_patches(
            patch_root,
            replacements={
                "continue_system_prompt": escaped,
                "continue_allowed_tool_names": allowed_tools_js,
            },
        )
        if not patch_applied:
            return [executable_name], False
        if dist_cli.exists():
            return ["node", str(dist_cli)], True
        return [executable_name], False

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
        env.update(self.cli_agent_spec.env)
        self._apply_case_backend_env_overrides(case, env)
        warmup_runtime_env = self._prepare_runtime_dirs(case, self.cli_agent_spec.id, "warmup")
        measured_runtime_env = self._prepare_runtime_dirs(case, self.cli_agent_spec.id, "measured")
        warmup_exec, warmup_patch_applied = self._prepare_patched_continue_cli(
            case,
            model_spec,
            warmup_runtime_env,
        )
        measured_exec, measured_patch_applied = self._prepare_patched_continue_cli(
            case,
            model_spec,
            measured_runtime_env,
        )
        _warmup_home, warmup_config = self._prepare_continue_home(
            case,
            model_spec,
            warmup_runtime_env,
            env,
            "warmup",
        )
        _measured_home, measured_config = self._prepare_continue_home(
            case,
            model_spec,
            measured_runtime_env,
            env,
            "measured",
        )
        warmup_env = {**env, **warmup_runtime_env, "GRIPPROBE_WORKSPACE": str(case.warmup_workspace_dir)}
        measured_env = {**env, **measured_runtime_env, "GRIPPROBE_WORKSPACE": str(case.workspace_dir)}
        allowed_tools = case.allowed_tools or self.cli_agent_spec.default_tools

        warmup_args = [
            *warmup_exec,
            "--config",
            str(warmup_config),
            "-p",
            "--auto",
            "--silent",
            case.prompt,
        ]
        measured_args = [
            *measured_exec,
            "--config",
            str(measured_config),
            "-p",
            "--auto",
            "--silent",
            case.prompt,
        ]
        warmup_tool_insert_at = len(warmup_exec)
        measured_tool_insert_at = len(measured_exec)
        for tool_name in allowed_tools:
            warmup_args[warmup_tool_insert_at:warmup_tool_insert_at] = ["--allow", tool_name]
            warmup_tool_insert_at += 2
            measured_args[measured_tool_insert_at:measured_tool_insert_at] = ["--allow", tool_name]
            measured_tool_insert_at += 2
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
                "allowed_tools": allowed_tools,
                "warmup_command": warmup_command,
                "measured_command": measured_command,
                "model_selection": "isolated-config",
                "model_hash": case.model_hash,
                "artifact_reached_before_timeout": artifact_reached_before_timeout,
                "continue_config_path": str(measured_config),
                "continue_builtin_prompt_patch_applied_warmup": warmup_patch_applied,
                "continue_builtin_prompt_patch_applied_measured": measured_patch_applied,
                "failure_reason": failure_reason,
            },
        )
