from __future__ import annotations

from abc import ABC, abstractmethod
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime

from gripprobe.models import CaseDefinition, CaseResult, ModelSpec, ShellSpec, TestSpec


class ShellAdapter(ABC):
    def __init__(self, shell_spec: ShellSpec):
        self.shell_spec = shell_spec

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
                    timeout=self.shell_spec.timeout_seconds,
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
        for key in ("OPENAI_BASE_URL", "OLLAMA_HOST", "GRIPPROBE_WORKSPACE", "GPTME_LOGS_HOME"):
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
            if key in {"OPENAI_BASE_URL", "OLLAMA_HOST", "GRIPPROBE_WORKSPACE", "GPTME_LOGS_HOME"}
        }
        return {**os.environ, **passthrough}


class AdapterError(RuntimeError):
    pass
