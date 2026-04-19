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

    type: Literal["file_equals", "patch_applied"]
    target: str | None = None
    expected: str | None = None
    expected_from: Literal["workspace_path", "today"] | None = None
    target_file: str | None = None
    expected_line: str | None = None

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
        return self


class TestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    category: str
    prompt: str
    allowed_tools: list[str] | None = None
    artifacts: list[ArtifactSpec] = Field(default_factory=list)
    validators: list[ValidatorSpec]
    supported_shells: list[str] = Field(default_factory=list)
    supported_formats: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class BackendSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    model_id: str
    shell_model_id: str
    model_hash: str
    env: dict[str, str] = Field(default_factory=dict)


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


class ShellSpec(BaseModel):
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


class CaseDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    run_id: str
    shell_id: str
    shell_label: str
    model_id: str
    model_label: str
    backend_id: str
    backend_model_id: str
    shell_model_id: str
    model_hash: str
    quantization: str | None = None
    tool_format: str
    test_id: str
    test_title: str
    prompt: str
    workspace_dir: Path
    case_dir: Path
    allowed_tools: list[str] | None = None
    container_image: str | None = None


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
    shell_model_id: str
    model_hash: str


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    run_id: str
    shell: str
    model: CaseModelInfo
    format: str
    test: str
    title: str
    status: Literal["PASS", "FAIL", "TIMEOUT", "NO_TOOL_CALL", "TOOL_UNSUPPORTED", "SHELL_ERROR", "HARNESS_ERROR", "SKIPPED"]
    invoked: Literal["yes", "no", "maybe"]
    match_percent: int
    timings: CaseTimings
    logs: CaseLogs
    metadata: dict[str, Any] = Field(default_factory=dict)
