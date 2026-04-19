from __future__ import annotations

from abc import ABC, abstractmethod
import os
from pathlib import Path
import subprocess
import time

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
    ) -> tuple[int, float]:
        start = time.monotonic()
        with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
            try:
                proc = subprocess.run(
                    self._wrap_command(case, args, env),
                    cwd=str(case.workspace_dir),
                    env=self._wrap_env(case, env),
                    stdout=out,
                    stderr=err,
                    text=True,
                    timeout=self.shell_spec.timeout_seconds,
                )
                return proc.returncode, time.monotonic() - start
            except subprocess.TimeoutExpired:
                return 124, time.monotonic() - start

    def _wrap_command(self, case: CaseDefinition, args: list[str], env: dict[str, str]) -> list[str]:
        if not case.container_image:
            return args
        workspace = str(case.workspace_dir)
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
