import json
from pathlib import Path

from gripprobe.models import CaseLogs, CaseModelInfo, CaseResult, CaseTimings
from gripprobe.results import write_json


def test_case_result_serializes_backend_and_model_hash(tmp_path: Path) -> None:
    payload = CaseResult(
        case_id="gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd",
        run_id="20260419T064337Z",
        shell="gptme",
        model=CaseModelInfo(
            id="local_qwen2_5_7b",
            label="local/qwen2.5:7b",
            family="qwen",
            size_class="small",
            quantization="Q4_K_M",
            backend="ollama",
            model_id="qwen2.5:7b",
            shell_model_id="local/qwen2.5:7b",
            model_hash="845dbda0ea48",
        ),
        format="markdown",
        test="shell_pwd",
        title="Shell PWD",
        status="PASS",
        trajectory="clean",
        invoked="yes",
        match_percent=100,
        timings=CaseTimings(warmup_seconds=1.0, measured_seconds=2.0),
        logs=CaseLogs(
            prompt="prompt.txt",
            warmup_stdout="warmup.stdout",
            warmup_stderr="warmup.stderr",
            measured_stdout="measured.stdout",
            measured_stderr="measured.stderr",
        ),
        metadata={"tool_format": "markdown"},
    )

    out = tmp_path / "case.json"
    write_json(out, payload.model_dump())
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["model"]["backend"] == "ollama"
    assert data["model"]["model_hash"] == "845dbda0ea48"
    assert data["model"]["shell_model_id"] == "local/qwen2.5:7b"
