import os
import re
import shlex
import subprocess
from typing import Any


def _validate_command(command: str, allowed_binaries: list[str], denied_patterns: list[str]) -> None:
    if not command or len(command) > 2000:
        raise ValueError("command must be between 1 and 2000 characters")
    try:
        first = shlex.split(command.split("|", 1)[0])[0]
    except (ValueError, IndexError) as exc:
        raise ValueError("invalid shell syntax") from exc
    if first not in set(allowed_binaries):
        raise ValueError(f"command must start with an approved read-only binary: {sorted(allowed_binaries)}")
    denied = re.compile("|".join(f"(?:{pattern})" for pattern in denied_patterns))
    if denied.search(command):
        raise ValueError("mutating, network, process, or shell-control command is not allowed")


def _execute(command: str, timeout_seconds: int, cwd: str | None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        cwd=cwd,
        env=os.environ.copy(),
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-4000:],
    }


def run_shell(
    command: str,
    timeout_seconds: int = 20,
    cwd: str | None = None,
    allowed_binaries: list[str] | None = None,
    denied_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Execute one bounded, read-only diagnostic shell pipeline."""
    _validate_command(command, allowed_binaries or [], denied_patterns or [])
    return _execute(command, max(1, min(timeout_seconds, 30)), cwd)


def run_approved_action(command: str, timeout_seconds: int = 60, cwd: str | None = None) -> dict[str, Any]:
    return _execute(command, max(1, min(timeout_seconds, 120)), cwd)
