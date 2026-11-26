"""Claude Code `UserPromptSubmit` hook: notice when a session's context has grown too long.

A long context makes every turn slower and dearer and the model less precise, and past a
point the session is compacted and loses detail. This hook measures the context of the
session before each user message, from the token counts of the last main-thread answer in
its transcript (input + cache reads + cache writes + output). When the context crosses a
threshold, it adds a note for Claude: propose continuing in a new session, with a hand-over
brief, at the next natural break.

The note is given once per threshold and session, so it never nags. The thresholds are
tokens, not a share of the window, because windows differ by model; override them with
CLAUDE_CONTEXT_SOFT_TOKENS and CLAUDE_CONTEXT_HARD_TOKENS; the last level noted per session is
kept in CLAUDE_CONTEXT_STATE_DIR (default: a folder in the system temp directory).

It never blocks a prompt: it exits with 0 (silent when there is no transcript yet, and
unreadable lines are skipped), or with a non-blocking error that Claude Code shows.
"""

import json
import os
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

SOFT_TOKENS = 150_000
HARD_TOKENS = 300_000
DEFAULT_STATE_DIR = Path(tempfile.gettempdir()) / "claude-context-check"

NOTES = {
    1: (
        "Context check: this session's context is about {tokens:,} tokens (soft threshold "
        "{soft:,}). When the current piece of work reaches a natural break (committed, no "
        "change in progress), propose continuing in a new session with a short hand-over "
        "brief: decisions, open pull requests, next steps. Do not interrupt work in progress."
    ),
    2: (
        "Context check: this session's context is about {tokens:,} tokens (hard threshold "
        "{hard:,}). Answers are getting slower, dearer and less precise. Before starting any "
        "new piece of work, propose moving to a new session with a hand-over brief "
        "(decisions, open pull requests, next steps); hand off the task in progress if there "
        "is one. Say in one line why."
    ),
}


def context_tokens(transcript: Iterable[str]) -> int:
    """Tokens in context at the last main-thread answer of a JSONL transcript, 0 if none."""
    tokens = 0
    for line in transcript:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
        if entry.get("isSidechain") or not isinstance(usage, dict):  # subagents have their own
            continue
        tokens = sum(
            int(usage.get(key) or 0)
            for key in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "output_tokens",
            )
        )
    return tokens


def level(tokens: int, soft: int, hard: int) -> int:
    """0 below the soft threshold, 1 from it, 2 from the hard one."""
    return 2 if tokens >= hard else 1 if tokens >= soft else 0


def note_to_give(tokens: int, soft: int, hard: int, last_level: int) -> tuple[int, str | None]:
    """The level reached and the note for Claude, only if the level rose since the last note.

    A level that fell (after a compaction) is remembered as it is, so crossing the threshold
    again gives the note again.
    """
    now = level(tokens, soft, hard)
    if now <= last_level:
        return now, None
    return now, NOTES[now].format(tokens=tokens, soft=soft, hard=hard)


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    transcript = Path(payload.get("transcript_path") or "")
    session = str(payload.get("session_id") or "unknown")
    if not transcript.is_file():
        return 0
    soft = int(os.environ.get("CLAUDE_CONTEXT_SOFT_TOKENS", SOFT_TOKENS))
    hard = int(os.environ.get("CLAUDE_CONTEXT_HARD_TOKENS", HARD_TOKENS))
    with transcript.open(encoding="utf-8", errors="replace") as lines:
        tokens = context_tokens(lines)
    state_dir = Path(os.environ.get("CLAUDE_CONTEXT_STATE_DIR") or DEFAULT_STATE_DIR)
    state = state_dir / f"{session}.level"
    last_level = int(state.read_text()) if state.is_file() else 0
    now, note = note_to_give(tokens, soft, hard, last_level)
    state_dir.mkdir(parents=True, exist_ok=True)
    state.write_text(str(now))
    if note:
        output = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}
        output["hookSpecificOutput"]["additionalContext"] = note
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
