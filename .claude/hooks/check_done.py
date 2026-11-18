"""Claude Code `Stop` hook: the fast definition-of-done check before Claude ends its turn.

Runs only when Python files have uncommitted changes. On failure it exits with code 2, which
sends stderr back to Claude so it keeps working instead of declaring the task done. The full
test suite (real book + corpus) runs in pre-commit, not here: this check must stay fast.
"""

import json
import subprocess
import sys

CHECKS = [
    ["uv", "run", "ruff", "check", "."],
    ["uv", "run", "ruff", "format", "--check", "."],
    ["uv", "run", "mypy", "src"],
    ["uv", "run", "pytest", "tests/unit", "-q"],
]


def python_files_changed() -> bool:
    """True if `git status` lists a modified, added or untracked `.py` file."""
    status = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    return any(line.rstrip().endswith(".py") for line in status.stdout.splitlines())


def first_failure() -> str | None:
    """Run the checks in order; return the output of the first one that fails."""
    for command in CHECKS:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return f"`{' '.join(command)}` failed:\n{result.stdout}{result.stderr}"
    return None


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    # Second stop in a row: Claude already had one chance to fix things; do not loop.
    if payload.get("stop_hook_active") or not python_files_changed():
        return 0
    failure = first_failure()
    if failure is None:
        return 0
    print(f"Definition of done (fast check) is not green.\n{failure}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
