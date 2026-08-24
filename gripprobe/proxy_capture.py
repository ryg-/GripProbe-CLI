from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from gripprobe.models import CaseDefinition, CliAgentSpec, ModelSpec
from gripprobe.telemetry_proxy import OllamaTelemetryProxy


TelemetryPhase = Literal["warmup", "measured"]
TELEMETRY_PHASES: tuple[TelemetryPhase, ...] = ("warmup", "measured")
ProxyFactory = Callable[..., OllamaTelemetryProxy]


def proxy_artifact_path(phase: TelemetryPhase) -> str:
    return f"artifacts/proxy.{phase}.http.jsonl"


def create_ollama_telemetry_proxy(
    case_dir: Path,
    upstream_base_url: str,
    artifact_relpath: str = "artifacts/proxy.measured.http.jsonl",
    filter_tools: bool = False,
    allowed_tool_names: list[str] | None = None,
    strip_git_context: bool = False,
    strip_permissions_instructions: bool = False,
    strip_skills_instructions: bool = False,
    strip_commit_signature_context: bool = False,
    reasoning_effort: str | None = None,
    temperature_override: float | None = None,
    capture_ollama_usage: bool = False,
    capture_stream_timing: bool = False,
) -> OllamaTelemetryProxy:
    return OllamaTelemetryProxy(
        case_dir=case_dir,
        upstream_base_url=upstream_base_url,
        artifact_relpath=artifact_relpath,
        filter_tools=filter_tools,
        allowed_tool_names=allowed_tool_names,
        strip_git_context=strip_git_context,
        strip_permissions_instructions=strip_permissions_instructions,
        strip_commit_signature_context=strip_commit_signature_context,
        strip_skills_instructions=strip_skills_instructions,
        reasoning_effort=reasoning_effort,
        temperature_override=temperature_override,
        capture_ollama_usage=capture_ollama_usage,
        capture_stream_timing=capture_stream_timing,
    )


@dataclass(frozen=True)
class ProxyCaptureOptions:
    filter_tools: bool = False
    allowed_tool_names: list[str] | None = None
    strip_git_context: bool = False
    strip_permissions_instructions: bool = False
    strip_skills_instructions: bool = False
    strip_commit_signature_context: bool = False
    reasoning_effort: str | None = None
    temperature_override: float | None = None
    capture_ollama_usage: bool = False
    capture_stream_timing: bool = False

    def as_factory_kwargs(self) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if self.filter_tools:
            options.update(
                {
                    "filter_tools": True,
                    "allowed_tool_names": self.allowed_tool_names or [],
                }
            )
        if self.strip_git_context:
            options["strip_git_context"] = True
        if self.strip_permissions_instructions:
            options["strip_permissions_instructions"] = True
        if self.strip_commit_signature_context:
            options["strip_commit_signature_context"] = True
        if self.strip_skills_instructions:
            options["strip_skills_instructions"] = True
        if self.reasoning_effort:
            options["reasoning_effort"] = self.reasoning_effort
        if self.temperature_override is not None:
            options["temperature_override"] = self.temperature_override
        if self.capture_ollama_usage:
            options["capture_ollama_usage"] = True
        if self.capture_stream_timing:
            options["capture_stream_timing"] = True
        return options


@dataclass
class _PhaseState:
    artifact_relpath: str
    status: str = "pending"
    skip_reason: str = ""


class PhaseProxyCapture:
    """Own proxy startup, phase state, artifacts, and idempotent cleanup."""

    def __init__(
        self,
        *,
        case_dir: Path,
        upstream_base_url: str,
        options: ProxyCaptureOptions,
        proxy_factory: ProxyFactory = create_ollama_telemetry_proxy,
    ) -> None:
        self.case_dir = case_dir
        self.upstream_base_url = upstream_base_url
        self.options = options
        self.proxy_factory = proxy_factory
        self._states = {
            phase: _PhaseState(artifact_relpath=proxy_artifact_path(phase))
            for phase in TELEMETRY_PHASES
        }
        self._proxies: dict[TelemetryPhase, OllamaTelemetryProxy] = {}
        self._stopped: set[TelemetryPhase] = set()
        self._runtime_error: str | None = None

    def start(self) -> None:
        for phase in TELEMETRY_PHASES:
            state = self._states[phase]
            try:
                proxy = self.proxy_factory(
                    case_dir=self.case_dir,
                    upstream_base_url=self.upstream_base_url,
                    artifact_relpath=state.artifact_relpath,
                    **self.options.as_factory_kwargs(),
                )
                proxy.start()
                if not proxy.base_url:
                    raise RuntimeError("telemetry proxy failed to publish base URL")
            except Exception as exc:  # noqa: BLE001
                state.status = "error"
                state.skip_reason = "proxy_start_failed"
                self._remember_error(exc)
                continue
            self._proxies[phase] = proxy
            state.status = "collected"
            state.skip_reason = ""

    def proxy_for(self, phase: TelemetryPhase) -> OllamaTelemetryProxy | None:
        return self._proxies.get(phase)

    def mark_unavailable(self, phase: TelemetryPhase) -> None:
        state = self._states[phase]
        state.status = "error"
        state.skip_reason = "proxy_unavailable"

    def finish_phase(self, phase: TelemetryPhase) -> None:
        proxy = self._proxies.get(phase)
        if proxy is None or phase in self._stopped:
            return
        try:
            proxy.stop()
        except Exception as exc:  # noqa: BLE001
            state = self._states[phase]
            state.status = "error"
            state.skip_reason = "proxy_stop_failed"
            self._remember_error(exc)
        finally:
            self._stopped.add(phase)

        state = self._states[phase]
        if state.status == "collected" and not (self.case_dir / state.artifact_relpath).exists():
            state.status = "error"
            state.skip_reason = "capture_missing"

    def stop_all(self) -> None:
        for phase in TELEMETRY_PHASES:
            self.finish_phase(phase)

    def runtime_metadata(self) -> dict[str, str]:
        metadata = {
            "telemetry_proxy_upstream_base_url": self.upstream_base_url,
            "telemetry_proxy_warmup_artifact_path": proxy_artifact_path("warmup"),
            "telemetry_proxy_measured_artifact_path": proxy_artifact_path("measured"),
        }
        for phase, proxy in self._proxies.items():
            if not proxy.base_url:
                continue
            metadata[f"telemetry_proxy_{phase}_ollama_host"] = proxy.base_url
            metadata[f"telemetry_proxy_{phase}_openai_base_url"] = f"{proxy.base_url}/v1"

        default_proxy = self._proxies.get("measured") or self._proxies.get("warmup")
        if default_proxy is not None and default_proxy.base_url:
            metadata.update(
                {
                    "telemetry_proxy_ollama_host": default_proxy.base_url,
                    "telemetry_proxy_openai_base_url": f"{default_proxy.base_url}/v1",
                }
            )
        return metadata

    def artifact_relpaths(self) -> dict[str, str]:
        return {
            phase: state.artifact_relpath
            for phase, state in self._states.items()
            if state.status == "collected"
        }

    @property
    def runtime_error(self) -> str | None:
        return self._runtime_error

    def _remember_error(self, error: Exception) -> None:
        if self._runtime_error is None:
            self._runtime_error = str(error)


_PROXY_TOOL_NAME_MAP = {
    "shell": "Bash",
    "read": "Read",
    "save": "Write",
    "write": "Write",
    "patch": "MultiEdit",
    "fetch": "Fetch",
    "list": "List",
}

_PROXY_TOOL_ROLE_MAP = {
    "shell": "command",
    "read": "read",
    "save": "write",
    "write": "write",
    "patch": "patch",
    "fetch": "fetch",
    "list": "list",
}


def _append_unique_name(target: list[str], name: str) -> None:
    if name and name not in target:
        target.append(name)


def _resolve_proxy_allowed_tool_names_from_dialect(
    requested_tools: list[str],
    cli_agent_spec: CliAgentSpec,
    *,
    include_exit: bool,
) -> list[str]:
    names: list[str] = []
    selected_roles: set[str] = set()
    dialect_entries = cli_agent_spec.tool_dialect

    def add_entry(entry: Any) -> None:
        _append_unique_name(names, entry.raw_name)
        if entry.role:
            selected_roles.add(entry.role)

    for requested in requested_tools:
        matched = False
        requested_role = _PROXY_TOOL_ROLE_MAP.get(requested)
        requested_canonical = _PROXY_TOOL_NAME_MAP.get(requested, requested)
        for entry in dialect_entries:
            if requested in {entry.id, entry.raw_name, entry.canonical_name}:
                add_entry(entry)
                matched = True
                continue
            if requested_role and entry.role == requested_role:
                add_entry(entry)
                matched = True
                continue
            if requested_canonical and entry.canonical_name == requested_canonical:
                add_entry(entry)
                matched = True
        if not matched and requested:
            _append_unique_name(names, requested)

    if include_exit and "command" in selected_roles:
        for entry in dialect_entries:
            if entry.role == "terminate":
                add_entry(entry)

    return names


def resolve_proxy_allowed_tool_names(
    case: CaseDefinition,
    cli_agent_spec: CliAgentSpec,
    model_spec: ModelSpec | None = None,
) -> list[str]:
    raw_tools = case.allowed_tools or cli_agent_spec.default_tools
    requested_tools: list[str] = []
    for tool_name in raw_tools:
        if isinstance(tool_name, str) and tool_name not in requested_tools:
            requested_tools.append(tool_name)

    include_exit = True
    extra_tool_names: list[str] = []
    if model_spec is not None:
        include_exit = _cli_agent_policy_bool_option(
            model_spec,
            cli_agent_spec.id,
            "proxy_include_exit_tool",
            fallback_key="proxy_include_exit_tool",
            default=True,
        )
        overrides = model_spec.policy_overrides or {}
        raw_extra_tool_names = overrides.get("proxy_include_tool_names")
        if isinstance(raw_extra_tool_names, list):
            for tool_name in raw_extra_tool_names:
                if not isinstance(tool_name, str):
                    continue
                resolved = _PROXY_TOOL_NAME_MAP.get(tool_name, tool_name)
                if resolved not in extra_tool_names:
                    extra_tool_names.append(resolved)

    combined_requested_tools = requested_tools + [
        tool_name for tool_name in extra_tool_names if tool_name not in requested_tools
    ]

    if cli_agent_spec.tool_dialect:
        return _resolve_proxy_allowed_tool_names_from_dialect(
            combined_requested_tools,
            cli_agent_spec,
            include_exit=include_exit,
        )

    names: list[str] = []
    for tool_name in combined_requested_tools:
        resolved = _PROXY_TOOL_NAME_MAP.get(tool_name, tool_name)
        if resolved not in names:
            names.append(resolved)
    if include_exit and "Bash" in names and "Exit" not in names:
        names.append("Exit")
    return names


def _cli_agent_policy(model_spec: ModelSpec, cli_agent_id: str) -> dict[str, Any]:
    cli_agent_options = (model_spec.policy_overrides or {}).get("cli_agent_options")
    if not isinstance(cli_agent_options, dict):
        return {}
    options = cli_agent_options.get(cli_agent_id)
    return options if isinstance(options, dict) else {}


def _cli_agent_policy_bool_option(
    model_spec: ModelSpec,
    cli_agent_id: str,
    option_key: str,
    *,
    fallback_key: str | None = None,
    default: bool = False,
) -> bool:
    policy = _cli_agent_policy(model_spec, cli_agent_id)
    value = policy.get(option_key)
    if isinstance(value, bool):
        return value
    if fallback_key:
        fallback_value = (model_spec.policy_overrides or {}).get(fallback_key)
        if isinstance(fallback_value, bool):
            return fallback_value
    return default


def build_proxy_capture_options(
    case: CaseDefinition,
    cli_agent_spec: CliAgentSpec,
    model_spec: ModelSpec,
) -> ProxyCaptureOptions:
    filter_tools = _cli_agent_policy_bool_option(
        model_spec,
        cli_agent_spec.id,
        "telemetry_proxy_filter_tools",
        fallback_key="telemetry_proxy_filter_tools",
        default=False,
    ) or _cli_agent_policy(model_spec, cli_agent_spec.id).get("filter_tools") is True
    raw_reasoning_effort = (model_spec.policy_overrides or {}).get("telemetry_proxy_reasoning_effort")
    raw_temperature_override = (model_spec.policy_overrides or {}).get("telemetry_proxy_temperature_override")
    return ProxyCaptureOptions(
        filter_tools=filter_tools,
        allowed_tool_names=resolve_proxy_allowed_tool_names(case, cli_agent_spec, model_spec) if filter_tools else None,
        strip_git_context=_cli_agent_policy_bool_option(
            model_spec,
            cli_agent_spec.id,
            "telemetry_proxy_strip_git_context",
            fallback_key="telemetry_proxy_strip_git_context",
            default=False,
        ),
        strip_permissions_instructions=_cli_agent_policy_bool_option(
            model_spec,
            cli_agent_spec.id,
            "telemetry_proxy_strip_permissions_instructions",
            default=False,
        ),
        strip_skills_instructions=_cli_agent_policy_bool_option(
            model_spec,
            cli_agent_spec.id,
            "telemetry_proxy_strip_skills_instructions",
            default=False,
        ),
        strip_commit_signature_context=_cli_agent_policy_bool_option(
            model_spec,
            cli_agent_spec.id,
            "telemetry_proxy_strip_commit_signature_context",
            fallback_key="telemetry_proxy_strip_commit_signature_context",
            default=False,
        ),
        reasoning_effort=str(raw_reasoning_effort).strip() if isinstance(raw_reasoning_effort, str) else None,
        temperature_override=float(raw_temperature_override)
        if isinstance(raw_temperature_override, (int, float))
        else None,
        capture_ollama_usage=_cli_agent_policy_bool_option(
            model_spec,
            cli_agent_spec.id,
            "telemetry_proxy_capture_ollama_usage",
            fallback_key="telemetry_proxy_capture_ollama_usage",
            default=False,
        ),
        capture_stream_timing=_cli_agent_policy_bool_option(
            model_spec,
            cli_agent_spec.id,
            "telemetry_proxy_capture_stream_timing",
            fallback_key="telemetry_proxy_capture_stream_timing",
            default=False,
        ),
    )


def should_disable_proxy_for_cli_agent(cli_agent_spec: CliAgentSpec, model_spec: ModelSpec) -> bool:
    return _cli_agent_policy(model_spec, cli_agent_spec.id).get("disable_proxy") is True
