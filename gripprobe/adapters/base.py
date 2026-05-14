from __future__ import annotations

from abc import ABC, abstractmethod
import os
import shlex
from pathlib import Path
import subprocess
import time
from datetime import datetime

from gripprobe.models import CaseDefinition, CaseResult, CliAgentSpec, ModelSpec, TestSpec


class CliAgentAdapter(ABC):
    def __init__(self, cli_agent_spec: CliAgentSpec):
        self.cli_agent_spec = cli_agent_spec

    @property
    def shell_spec(self) -> CliAgentSpec:
        # Legacy alias for adapters/tests not yet migrated to cli_agent_spec naming.
        return self.cli_agent_spec

    @abstractmethod
    def run_case(self, case: CaseDefinition, model_spec: ModelSpec, test_spec: TestSpec) -> CaseResult:
        raise NotImplementedError

    def run_command(
        self,
        case: CaseDefinition,
        args: list[str],
        env: dict[str, str],
        stdout_path: Path,
        stderr_path: Path,
        workspace_dir: Path | None = None,
    ) -> tuple[int, float, str, str]:
        start = time.monotonic()
        active_workspace = workspace_dir or case.workspace_dir
        with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
            started_at = datetime.now().astimezone().isoformat(timespec="seconds")
            out.write(f"[gripprobe] process_started_at={started_at}\n")
            err.write(f"[gripprobe] process_started_at={started_at}\n")
            out.flush()
            err.flush()
            try:
                proc = subprocess.run(
                    self._wrap_command(case, args, env, active_workspace),
                    cwd=str(active_workspace),
                    env=self._wrap_env(case, env),
                    stdout=out,
                    stderr=err,
                    text=True,
                    timeout=self.cli_agent_spec.timeout_seconds,
                )
                finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
                out.write(f"\n[gripprobe] process_finished_at={finished_at} exit_code={proc.returncode}\n")
                err.write(f"\n[gripprobe] process_finished_at={finished_at} exit_code={proc.returncode}\n")
                out.flush()
                err.flush()
                return proc.returncode, time.monotonic() - start, started_at, finished_at
            except subprocess.TimeoutExpired:
                finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
                out.write(f"\n[gripprobe] process_finished_at={finished_at} exit_code=124 timeout=true\n")
                err.write(f"\n[gripprobe] process_finished_at={finished_at} exit_code=124 timeout=true\n")
                out.flush()
                err.flush()
                return 124, time.monotonic() - start, started_at, finished_at

    def _wrap_command(self, case: CaseDefinition, args: list[str], env: dict[str, str], workspace_dir: Path | None = None) -> list[str]:
        if not case.container_image:
            return args
        workspace = str(workspace_dir or case.workspace_dir)
        case_dir = str(case.case_dir)
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{workspace}:{workspace}",
            "-v",
            f"{case_dir}:{case_dir}",
            "-w",
            workspace,
        ]
        for key in (
            "OPENAI_BASE_URL",
            "OPENAI_API_KEY",
            "OLLAMA_HOST",
            "OLLAMA_API_BASE",
            "GRIPPROBE_WORKSPACE",
            "GPTME_LOGS_HOME",
            "HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_STATE_HOME",
            "XDG_CACHE_HOME",
            "TMPDIR",
        ):
            if key in env:
                cmd.extend(["-e", f"{key}={env[key]}"])
        cmd.extend([case.container_image, *args])
        return cmd

    def _wrap_env(self, case: CaseDefinition, env: dict[str, str]) -> dict[str, str]:
        if not case.container_image:
            return env
        # Keep environment minimal when using container runtime.
        passthrough = {
            key: value
            for key, value in env.items()
            if key
            in {
                "OPENAI_BASE_URL",
                "OPENAI_API_KEY",
                "OLLAMA_HOST",
                "OLLAMA_API_BASE",
                "GRIPPROBE_WORKSPACE",
                "GPTME_LOGS_HOME",
                "HOME",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
                "XDG_STATE_HOME",
                "XDG_CACHE_HOME",
                "TMPDIR",
            }
        }
        return {**os.environ, **passthrough}

    def _prepare_runtime_dirs(self, case: CaseDefinition, cli_agent_name: str, phase: str) -> dict[str, str]:
        runtime_root = case.case_dir / "runtime" / cli_agent_name / phase
        home_dir = runtime_root / "home"
        xdg_config_home = runtime_root / "config"
        xdg_data_home = runtime_root / "data"
        xdg_state_home = runtime_root / "state"
        xdg_cache_home = runtime_root / "cache"
        tmp_dir = runtime_root / "tmp"
        for path in (home_dir, xdg_config_home, xdg_data_home, xdg_state_home, xdg_cache_home, tmp_dir):
            path.mkdir(parents=True, exist_ok=True)
        return {
            "HOME": str(home_dir),
            "XDG_CONFIG_HOME": str(xdg_config_home),
            "XDG_DATA_HOME": str(xdg_data_home),
            "XDG_STATE_HOME": str(xdg_state_home),
            "XDG_CACHE_HOME": str(xdg_cache_home),
            "TMPDIR": str(tmp_dir),
        }

    @staticmethod
    def _normalize_http_base(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            raw = "http://127.0.0.1:11434"
        if "://" not in raw:
            raw = f"http://{raw}"
        return raw.rstrip("/")

    def _resolve_case_ollama_host(self, case: CaseDefinition, env: dict[str, str]) -> str:
        metadata = case.run_metadata if isinstance(case.run_metadata, dict) else {}
        for key in ("telemetry_proxy_ollama_host", "ollama_host"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return self._normalize_http_base(value)
        if env.get("OLLAMA_HOST"):
            return self._normalize_http_base(env["OLLAMA_HOST"])
        return self._normalize_http_base(os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))

    def _resolve_case_openai_base_url(self, case: CaseDefinition, env: dict[str, str]) -> str:
        metadata = case.run_metadata if isinstance(case.run_metadata, dict) else {}
        for key in ("telemetry_proxy_openai_base_url", "openai_base_url"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return self._normalize_http_base(value)
        if env.get("OPENAI_BASE_URL"):
            return self._normalize_http_base(env["OPENAI_BASE_URL"])
        return f"{self._resolve_case_ollama_host(case, env)}/v1"

    def _apply_case_backend_env_overrides(self, case: CaseDefinition, env: dict[str, str]) -> None:
        if case.backend_id != "ollama":
            return
        env["OLLAMA_HOST"] = self._resolve_case_ollama_host(case, env)
        env["OPENAI_BASE_URL"] = self._resolve_case_openai_base_url(case, env)

    def _command_text(
        self,
        case: CaseDefinition,
        args: list[str],
        env: dict[str, str],
        workspace_dir: Path | None = None,
    ) -> str:
        wrapped = self._wrap_command(case, args, env, workspace_dir)
        return shlex.join(str(part) for part in wrapped)


class AdapterError(RuntimeError):
    pass


# Legacy compatibility alias.
ShellAdapter = CliAgentAdapter
