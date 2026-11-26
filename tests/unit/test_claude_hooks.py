"""The Claude Code hooks in .claude/hooks/, loaded from their files: they are scripts, not
part of the homerag package. Transcripts here are synthetic."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

HOOK = Path(".claude/hooks/context_check.py")


def load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


context_check = load(HOOK)


def answer(cache_read: int, sidechain: bool = False) -> str:
    usage = {
        "input_tokens": 2,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": cache_read,
        "output_tokens": 50,
    }
    entry = {"type": "assistant", "isSidechain": sidechain, "message": {"usage": usage}}
    return json.dumps(entry)


def test_context_is_the_last_main_answer_with_every_kind_of_input() -> None:
    lines = [
        answer(1_000),
        json.dumps({"type": "user", "message": {"content": "hi"}}),
        answer(5_000),
        answer(900_000, sidechain=True),  # a subagent's own context
        "not json",
        "[1, 2]",
    ]

    assert context_check.context_tokens(lines) == 2 + 100 + 5_000 + 50


def test_no_answer_yet_means_no_context() -> None:
    assert context_check.context_tokens([]) == 0


@pytest.mark.parametrize(
    ("tokens", "last", "expected_level", "noted"),
    [
        (10_000, 0, 0, False),  # below both thresholds
        (160_000, 0, 1, True),  # crosses the soft one: one note
        (170_000, 1, 1, False),  # still soft: no repeat
        (310_000, 1, 2, True),  # crosses the hard one: a stronger note
        (320_000, 2, 2, False),
        (20_000, 2, 0, False),  # compacted: back to 0, so a later crossing notes again
    ],
)
def test_a_note_only_when_the_level_rises(
    tokens: int, last: int, expected_level: int, noted: bool
) -> None:
    now, note = context_check.note_to_give(tokens, 150_000, 300_000, last)

    assert now == expected_level
    assert (note is not None) == noted


def test_the_hook_prints_a_note_for_claude_once(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(answer(200_000) + "\n", encoding="utf-8")
    payload = json.dumps({"transcript_path": str(transcript), "session_id": "session-1"})
    env = {**os.environ, "CLAUDE_CONTEXT_STATE_DIR": str(tmp_path / "state")}

    def run() -> str:
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return result.stdout

    first, second = run(), run()

    note = json.loads(first)["hookSpecificOutput"]
    assert note["hookEventName"] == "UserPromptSubmit"
    assert "200,152 tokens" in note["additionalContext"]
    assert second == ""
