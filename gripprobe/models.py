from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArtifactSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    kind: Literal["text"] = "text"


class ValidatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["file_equals", "patch_applied", "web_nonce_proof", "weekly_plan_task", "web_search_result"]
    target: str | None = None
    expected: str | None = None
    expected_from: Literal["workspace_path", "today"] | None = None
    target_file: str | None = None
    expected_line: str | None = None
    nonce: str | None = None
    payload: str | None = None
    proof: str | None = None
    request_log: str | None = None
    request_path: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "ValidatorSpec":
        if self.type == "file_equals":
            if not self.target:
                raise ValueError("file_equals validator requires target")
            if not (self.expected or self.expected_from):
                raise ValueError("file_equals validator requires expected or expected_from")
        if self.type == "patch_applied":
            if not (self.target_file and self.expected_line):
                raise ValueError("patch_applied validator requires target_file and expected_line")
        if self.type == "web_nonce_proof":
            if not self.target:
                raise ValueError("web_nonce_proof validator requires target")
        if self.type == "weekly_plan_task":
            if not self.target:
                raise ValueError("weekly_plan_task validator requires target")
            if not self.expected:
                raise ValueError("weekly_plan_task validator requires expected")
        if self.type == "web_search_result":
            if not self.target:
                raise ValueError("web_search_result validator requires target")
            if not self.expected:
                raise ValueError("web_search_result validator requires expected")
            if (self.request_log and not self.request_path) or (self.request_path and not self.request_log):
                raise ValueError("web_search_result validator requires request_log and request_path together")
        return self


class RuleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    no_retry_on_error: bool = False
    require_exact_command: bool = False


class TestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    category: str
    prompt: str
    language: Literal["en", "de", "ru"] = "en"
    allowed_tools: list[str] | None = None
    artifacts: list[ArtifactSpec] = Field(default_factory=list)
    rules: RuleSpec = Field(default_factory=RuleSpec)
    validators: list[ValidatorSpec]
    supported_cli_agents: list[str] = Field(default_factory=list)
    supported_formats: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_supported_cli_agents(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        legacy_supported_shells = payload.pop("supported_shells", None)
        if "supported_cli_agents" not in payload and isinstance(legacy_supported_shells, list):
            payload["supported_cli_agents"] = legacy_supported_shells
        return payload

    @property
    def supported_shells(self) -> list[str]:
        return self.supported_cli_agents


class BackendSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    model_id: str
    cli_agent_model_id: str
    model_hash: str | None = None
    env: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_cli_agent_model_id(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        legacy_shell_model_id = payload.pop("shell_model_id", None)
        if "cli_agent_model_id" not in payload and isinstance(legacy_shell_model_id, str):
            payload["cli_agent_model_id"] = legacy_shell_model_id
        return payload

    @property
    def shell_model_id(self) -> str:
        return self.cli_agent_model_id


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    family: str
    size_class: str
    parameters_b: float | int | None = None
    quantization: str | None = None
    backends: list[BackendSpec]
    tags: list[str] = Field(default_factory=list)
    supported_formats: list[str] = Field(default_factory=list)
    policy_overrides: dict[str, Any] = Field(default_factory=dict)


class CliAgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    executable: str
    default_args: list[str] = Field(default_factory=list)
    supported_formats: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    default_tools: list[str] = Field(default_factory=list)
    config_path: str | None = None
    container_image: str | None = None
    timeout_seconds: int = 120


ShellSpec = CliAgentSpec


class HardwareProfileSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    cpu: str
    gpu: str
    ram: str
    notes: str | None = None


class SuiteMatrixEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cli_agent: str
    model: str
    backend: str | None = None
    format: str | None = None
    tests: list[str] = Field(default_factory=list)
    test_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_cli_agent(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        legacy_shell = payload.pop("shell", None)
        if "cli_agent" not in payload and isinstance(legacy_shell, str):
            payload["cli_agent"] = legacy_shell
        return payload

    @property
    def shell(self) -> str:
        return self.cli_agent


class SuiteSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str | None = None
    backend: str = "ollama"
    cli_agents: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    test_tags: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    matrix: list[SuiteMatrixEntry] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_cli_agents(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        legacy_shells = payload.pop("shells", None)
        if "cli_agents" not in payload and isinstance(legacy_shells, list):
            payload["cli_agents"] = legacy_shells
        return payload

    @property
    def shells(self) -> list[str]:
        return self.cli_agents


class CaseDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    run_id: str
    cli_agent_id: str
    cli_agent_label: str
    model_id: str
    model_label: str
    backend_id: str
    backend_model_id: str
    cli_agent_model_id: str
    model_hash: str
    quantization: str | None = None
    tool_format: str
    test_id: str
    test_title: str
    prompt: str
    warmup_workspace_dir: Path
    workspace_dir: Path
    case_dir: Path
    allowed_tools: list[str] | None = None
    container_image: str | None = None
    keep_system_messages: bool = False
    run_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_cli_agent_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        legacy_shell_id = payload.pop("shell_id", None)
        legacy_shell_label = payload.pop("shell_label", None)
        legacy_shell_model_id = payload.pop("shell_model_id", None)
        if "cli_agent_id" not in payload and isinstance(legacy_shell_id, str):
            payload["cli_agent_id"] = legacy_shell_id
        if "cli_agent_label" not in payload and isinstance(legacy_shell_label, str):
            payload["cli_agent_label"] = legacy_shell_label
        if "cli_agent_model_id" not in payload and isinstance(legacy_shell_model_id, str):
            payload["cli_agent_model_id"] = legacy_shell_model_id
        return payload

    @property
    def shell_id(self) -> str:
        return self.cli_agent_id

    @property
    def shell_label(self) -> str:
        return self.cli_agent_label

    @property
    def shell_model_id(self) -> str:
        return self.cli_agent_model_id


class CaseTimings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warmup_seconds: float
    measured_seconds: float


class CaseLogs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    warmup_stdout: str
    warmup_stderr: str
    measured_stdout: str
    measured_stderr: str


class CaseModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    family: str
    size_class: str
    quantization: str | None = None
    backend: str
    model_id: str
    cli_agent_model_id: str
    model_hash: str

    @model_validator(mode="before")
    @classmethod
    def _normalize_cli_agent_model_id(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        legacy_shell_model_id = payload.pop("shell_model_id", None)
        if "cli_agent_model_id" not in payload and isinstance(legacy_shell_model_id, str):
            payload["cli_agent_model_id"] = legacy_shell_model_id
        return payload

    @property
    def shell_model_id(self) -> str:
        return self.cli_agent_model_id


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    run_id: str
    cli_agent_id: str
    cli_agent: str
    model: CaseModelInfo
    format: str
    test: str
    title: str
    status: Literal["PASS", "FAIL", "TIMEOUT", "NO_TOOL_CALL", "TOOL_UNSUPPORTED", "SHELL_ERROR", "HARNESS_ERROR", "SKIPPED"]
    trajectory: Literal["clean", "recovered", "violated"] = "clean"
    invoked: Literal["yes", "no", "maybe"]
    match_percent: int
    timings: CaseTimings
    logs: CaseLogs
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_cli_agent_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        legacy_shell = payload.pop("shell", None)
        raw_cli_agent_id = payload.get("cli_agent_id")
        raw_cli_agent = payload.get("cli_agent")

        cli_agent_id: str | None = None
        if isinstance(raw_cli_agent_id, str) and raw_cli_agent_id.strip():
            cli_agent_id = raw_cli_agent_id.strip()
        elif isinstance(legacy_shell, str) and legacy_shell.strip():
            cli_agent_id = legacy_shell.strip()
        elif isinstance(raw_cli_agent, str) and raw_cli_agent.strip():
            cli_agent_id = raw_cli_agent.strip()

        cli_agent: str | None = None
        if isinstance(raw_cli_agent, str) and raw_cli_agent.strip():
            cli_agent = raw_cli_agent.strip()
        elif cli_agent_id:
            cli_agent = cli_agent_id
        elif isinstance(legacy_shell, str) and legacy_shell.strip():
            cli_agent = legacy_shell.strip()

        if cli_agent_id is not None:
            payload["cli_agent_id"] = cli_agent_id
        if cli_agent is not None:
            payload["cli_agent"] = cli_agent
        return payload

    @property
    def shell(self) -> str:
        # Legacy compatibility for code paths still using `item.shell`.
        return self.cli_agent
