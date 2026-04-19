from __future__ import annotations

import json
from pathlib import Path

from gripprobe.results import strip_system_messages_from_transcripts


def test_strip_system_messages_from_transcripts_removes_system_rows(tmp_path: Path) -> None:
    convo_path = tmp_path / "gptme-logs" / "session" / "conversation.jsonl"
    convo_path.parent.mkdir(parents=True)
    convo_path.write_text(
        "\n".join(
            [
                json.dumps({"role": "system", "content": "secret system prompt"}),
                json.dumps({"role": "user", "content": "hello"}),
                json.dumps({"role": "assistant", "content": "DONE"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    strip_system_messages_from_transcripts(tmp_path)

    lines = convo_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["role"] != "system" for line in lines)


def test_strip_system_messages_from_transcripts_keeps_invalid_json_lines(tmp_path: Path) -> None:
    convo_path = tmp_path / "conversation.jsonl"
    convo_path.write_text("not-json\n", encoding="utf-8")

    strip_system_messages_from_transcripts(tmp_path)

    assert convo_path.read_text(encoding="utf-8") == "not-json\n"
