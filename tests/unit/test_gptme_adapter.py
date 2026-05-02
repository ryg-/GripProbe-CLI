from __future__ import annotations

from pathlib import Path
from types import MethodType

from gripprobe.adapters.gptme import GptmeAdapter
from gripprobe.models import CaseDefinition, ModelSpec, ShellSpec, TestSpec as GripTestSpec
from gripprobe.trace_analysis import analyze_trace, compare_profiles, derive_trajectory, explain_trajectory


def _adapter() -> GptmeAdapter:
    return GptmeAdapter(
        ShellSpec.model_validate(
            {
                "id": "gptme",
                "label": "gptme",
                "executable": "gptme",
                "supported_formats": ["tool"],
            }
        )
    )


def _patch_test_spec() -> GripTestSpec:
    return GripTestSpec.model_validate(
        {
            "id": "patch_file",
            "title": "Patch File",
            "category": "patch",
            "prompt": "patch",
            "validators": [
                {
                    "type": "patch_applied",
                    "target_file": "patch-target.txt",
                    "expected_line": "STATUS=new",
                }
            ],
        }
    )


def _python_test_spec() -> GripTestSpec:
    return GripTestSpec.model_validate(
        {
            "id": "python_file",
            "title": "Python File",
            "category": "python",
            "prompt": (
                "Use the shell tool. Run exactly this command: python3 -c \"from pathlib import Path; "
                "Path('python-output.txt').write_text('PYTHON_OK\\\\n')\".\n"
                "Do not retry on error.\n"
                "If the command fails, reply only with FAIL.\n"
                "If the command succeeds, reply only with DONE.\n"
            ),
            "validators": [
                {
                    "type": "file_equals",
                    "target": "python-output.txt",
                    "expected": "PYTHON_OK",
                }
            ],
            "rules": {"no_retry_on_error": True},
        }
    )


def _model_spec() -> ModelSpec:
    return ModelSpec.model_validate(
        {
            "id": "local_qwen2_5_7b",
            "label": "local/qwen2.5:7b",
            "family": "qwen",
            "size_class": "small",
            "backends": [
                {
                    "id": "ollama",
                    "model_id": "qwen2.5:7b",
                    "shell_model_id": "local/qwen2.5:7b",
                    "model_hash": "845dbda0ea48",
                }
            ],
        }
    )


def test_classify_reports_fail_when_tool_call_happened_but_patch_failed(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = _patch_test_spec()
    (tmp_path / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")

    status, invoked, match_percent, expected, observed = adapter._classify(
        spec,
        tmp_path,
        "@patch(call_1): {}\nSystem: Error during execution: Invalid patch\n"
        "No tool call detected in last message\n",
        "",
    )

    assert status == "FAIL"
    assert invoked == "yes"
    assert match_percent == 0
    assert expected == "STATUS=new"
    assert observed == "STATUS=old"


def test_classify_reports_no_tool_call_when_no_tool_activity_happened(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = _patch_test_spec()
    (tmp_path / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")

    status, invoked, match_percent, expected, observed = adapter._classify(
        spec,
        tmp_path,
        "FAIL\nNo tool call detected in last message\n",
        "",
    )

    assert status == "NO_TOOL_CALL"
    assert invoked == "no"
    assert match_percent == 0
    assert expected == "STATUS=new"
    assert observed == "STATUS=old"


def test_trajectory_marks_retry_after_error_as_violated_when_passed(tmp_path: Path) -> None:
    spec = _python_test_spec()
    (tmp_path / "python-output.txt").write_text("PYTHON_OK\n", encoding="utf-8")

    trajectory = derive_trajectory(
        analyze_trace(
        "@shell(call_1): {\"command\":\"broken\"}\n"
        "System: Error during execution: Shell error: syntax error\n"
        "@shell(call_2): {\"command\":\"fixed\"}\n"
        "System:\nRan command: `fixed`\n",
        "",
        ),
        spec.rules.no_retry_on_error,
        "@shell(call_1): {\"command\":\"broken\"}\n"
        "System: Error during execution: Shell error: syntax error\n"
        "@shell(call_2): {\"command\":\"fixed\"}\n"
        "System:\nRan command: `fixed`\n",
        "",
    )

    assert trajectory == "violated"


def test_trace_analysis_detects_maybe_and_loop() -> None:
    maybe_profile = analyze_trace("```bash\npatch file\n```\n", "")
    assert maybe_profile.invoked == "maybe"
    assert maybe_profile.markdown_tool_imitation is True

    loop_profile = analyze_trace(
        "System: Error during execution: Invalid patch: invalid patch, no `<<<<<<< ORIGINAL`\n"
        "System: Error during execution: Invalid patch: invalid patch, no `<<<<<<< ORIGINAL`\n"
        "System: Error during execution: Invalid patch: invalid patch, no `<<<<<<< ORIGINAL`\n",
        "",
    )
    assert loop_profile.invoked == "yes"
    assert loop_profile.loop_detected is True
    assert loop_profile.repeated_error_count == 3


def test_compare_profiles_detects_strong_divergence() -> None:
    run_1 = analyze_trace("FAIL\nNo tool call detected in last message\n", "")
    run_2 = analyze_trace(
        "System: Error during execution: Invalid patch: invalid patch, no `<<<<<<< ORIGINAL`\n"
        "System: Error during execution: Invalid patch: invalid patch, no `<<<<<<< ORIGINAL`\n"
        "System: Error during execution: Invalid patch: invalid patch, no `<<<<<<< ORIGINAL`\n",
        "",
    )

    assert compare_profiles(run_1, run_2, "NO_TOOL_CALL", "TIMEOUT") == "strongly_diverged"


def test_trajectory_marks_contradictory_done_fail_text_as_recovered() -> None:
    profile = analyze_trace(
        '@shell(call_1): {"command":"ok"}\n'
        "System:\nRan command: `ok`\n"
        "DONE\n"
        "FAIL\n",
        "",
    )

    trajectory = derive_trajectory(profile, False, 'DONE\nFAIL\n', "")
    reasons = explain_trajectory(trajectory, profile, False, 'DONE\nFAIL\n', "")

    assert trajectory == "recovered"
    assert "contradictory completion text detected (both DONE and FAIL)" in reasons


def test_trace_analysis_detects_markdown_tool_imitation_followed_by_completion() -> None:
    profile = analyze_trace(
        "```bash\n"
        "date +%F > date-output.txt\n"
        "```\n"
        "DONE\n"
        "No tool call detected in last message\n",
        "",
    )

    trajectory = derive_trajectory(
        profile,
        False,
        "```bash\n"
        "date +%F > date-output.txt\n"
        "```\n"
        "DONE\n"
        "No tool call detected in last message\n",
        "",
    )
    reasons = explain_trajectory(
        trajectory,
        profile,
        False,
        "```bash\n"
        "date +%F > date-output.txt\n"
        "```\n"
        "DONE\n"
        "No tool call detected in last message\n",
        "",
    )

    assert profile.invoked == "maybe"
    assert profile.markdown_tool_imitation is True
    assert profile.no_tool_call_after_completion is True
    assert trajectory == "recovered"
    assert "markdown tool imitation detected without a real tool execution" in reasons
    assert "completion text was emitted before harness reported that no tool call was detected" in reasons


def test_run_case_keeps_timeout_but_records_artifact_reached(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = GripTestSpec.model_validate(
        {
            "id": "shell_pwd",
            "title": "Shell PWD",
            "category": "shell",
            "prompt": "Use shell",
            "validators": [
                {
                    "type": "file_equals",
                    "target": "pwd-output.txt",
                    "expected_from": "workspace_path",
                }
            ],
            "allowed_tools": ["shell"],
        }
    )
    case = CaseDefinition.model_validate(
        {
            "case_id": "gptme__local_qwen2_5_7b__ollama__tool__shell_pwd",
            "run_id": "run-timeout-artifact",
            "shell_id": "gptme",
            "shell_label": "gptme",
            "model_id": "local_qwen2_5_7b",
            "model_label": "local/qwen2.5:7b",
            "backend_id": "ollama",
            "backend_model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
            "model_hash": "845dbda0ea48",
            "tool_format": "tool",
            "test_id": "shell_pwd",
            "test_title": "Shell PWD",
            "prompt": spec.prompt,
            "warmup_workspace_dir": tmp_path / "workspace-warmup",
            "workspace_dir": tmp_path / "workspace",
            "case_dir": tmp_path / "case",
            "allowed_tools": ["shell"],
        }
    )
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)
    model_spec = _model_spec()

    def _fake_run_command(self, case_arg, args, env, stdout_path, stderr_path, workspace_dir=None):
        active_workspace = workspace_dir or case_arg.workspace_dir
        stdout_path.write_text(
            "[gripprobe] process_started_at=2026-04-20T17:26:39+02:00\n"
            "@shell(call_1): {\"command\":\"pwd > pwd-output.txt\"}\n"
            "System:\nRan command: `pwd > pwd-output.txt`\n"
            "[gripprobe] process_finished_at=2026-04-20T17:28:39+02:00 exit_code=124 timeout=true\n",
            encoding="utf-8",
        )
        stderr_path.write_text("", encoding="utf-8")
        (active_workspace / "pwd-output.txt").write_text(str(active_workspace) + "\n", encoding="utf-8")
        return 124, 120.0, "2026-04-20T17:26:39+02:00", "2026-04-20T17:28:39+02:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)

    result = adapter.run_case(case, model_spec, spec)

    assert result.status == "TIMEOUT"
    assert result.invoked == "yes"
    assert result.match_percent == 100
    assert result.metadata["artifact_reached_before_timeout"] is True
    assert (case.case_dir / "expected.txt").read_text(encoding="utf-8").strip() == str(case.workspace_dir)
    assert (case.case_dir / "observed.txt").read_text(encoding="utf-8").strip() == str(case.workspace_dir)


def test_gptme_uses_separate_runtime_home_and_logs_per_phase(tmp_path: Path) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _patch_test_spec()
    case = CaseDefinition.model_validate(
        {
            "case_id": "gptme__local_qwen2_5_7b__ollama__tool__patch_file",
            "run_id": "run-gptme-runtime-home",
            "shell_id": "gptme",
            "shell_label": "gptme",
            "model_id": "local_qwen2_5_7b",
            "model_label": "local/qwen2.5:7b",
            "backend_id": "ollama",
            "backend_model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
            "model_hash": "845dbda0ea48",
            "tool_format": "tool",
            "test_id": "patch_file",
            "test_title": "Patch File",
            "prompt": test_spec.prompt,
            "warmup_workspace_dir": tmp_path / "workspace-warmup",
            "workspace_dir": tmp_path / "workspace",
            "case_dir": tmp_path / "case",
            "allowed_tools": ["read", "patch"],
        }
    )
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)
    (case.warmup_workspace_dir / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")
    (case.workspace_dir / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")

    captured_envs: list[dict[str, str]] = []

    def _fake_run_command(
        self,
        case_arg,
        args: list[str],
        env: dict[str, str],
        stdout_path,
        stderr_path,
        workspace_dir=None,
    ):
        captured_envs.append(dict(env))
        active_workspace = workspace_dir or case_arg.workspace_dir
        (active_workspace / "patch-target.txt").write_text("STATUS=new\n", encoding="utf-8")
        stdout_path.write_text('@patch(call_1): {}\nSystem:\nApplied patch\n', encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-04-22T10:00:00+02:00", "2026-04-22T10:00:01+02:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)

    result = adapter.run_case(case, model_spec, test_spec)

    assert result.status == "PASS"
    assert str(result.metadata["warmup_command"]).startswith("gptme ")
    assert str(result.metadata["measured_command"]).startswith("gptme ")
    assert len(captured_envs) == 2
    assert captured_envs[0]["HOME"] != captured_envs[1]["HOME"]
    assert captured_envs[0]["GPTME_LOGS_HOME"] != captured_envs[1]["GPTME_LOGS_HOME"]
    for env in captured_envs:
        assert env["XDG_CONFIG_HOME"]
        assert env["XDG_STATE_HOME"]


def test_gptme_populates_openai_env_for_ollama_backend_when_missing(tmp_path: Path, monkeypatch) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _patch_test_spec()
    case = CaseDefinition.model_validate(
        {
            "case_id": "gptme__local_qwen2_5_7b__ollama__tool__patch_file",
            "run_id": "run-gptme-ollama-env",
            "shell_id": "gptme",
            "shell_label": "gptme",
            "model_id": "local_qwen2_5_7b",
            "model_label": "local/qwen2.5:7b",
            "backend_id": "ollama",
            "backend_model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
            "model_hash": "845dbda0ea48",
            "tool_format": "tool",
            "test_id": "patch_file",
            "test_title": "Patch File",
            "prompt": test_spec.prompt,
            "warmup_workspace_dir": tmp_path / "workspace-warmup",
            "workspace_dir": tmp_path / "workspace",
            "case_dir": tmp_path / "case",
            "allowed_tools": ["read", "patch"],
        }
    )
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)
    (case.warmup_workspace_dir / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")
    (case.workspace_dir / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")

    monkeypatch.setenv("OLLAMA_HOST", "http://source-host:11434")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured_envs: list[dict[str, str]] = []

    def _fake_run_command(
        self,
        case_arg,
        args: list[str],
        env: dict[str, str],
        stdout_path,
        stderr_path,
        workspace_dir=None,
    ):
        captured_envs.append(dict(env))
        active_workspace = workspace_dir or case_arg.workspace_dir
        (active_workspace / "patch-target.txt").write_text("STATUS=new\n", encoding="utf-8")
        stdout_path.write_text('@patch(call_1): {}\nSystem:\nApplied patch\n', encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-04-23T12:00:00+00:00", "2026-04-23T12:00:01+00:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)

    result = adapter.run_case(case, model_spec, test_spec)

    assert result.status == "PASS"
    assert len(captured_envs) == 2
    for env in captured_envs:
        assert env["OPENAI_BASE_URL"] == "http://source-host:11434/v1"
        assert env["OPENAI_API_KEY"] == "ollama"
