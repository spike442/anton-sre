import shutil
import subprocess
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from sensei.domain.models import CheckResult, PullRequest
from sensei.infrastructure.config import RepositoryConfig


def _record_command(
    action_sink: Callable,
    command: list[str],
    exit_code: int | None,
    output: str,
) -> None:
    action_sink("workspace_command", {"command": command, "exit_code": exit_code, "output": output})


class WorkspaceManager:
    """Clone and validate untrusted PR code in a disposable workspace."""

    def __init__(self, root: Path, timeout_seconds: int):
        self.root = root
        self.timeout_seconds = timeout_seconds

    @contextmanager
    def checkout(self, pull_request: PullRequest, repository: RepositoryConfig, action_sink: Callable):
        self.root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix=f"pr-{pull_request.number}-", dir=self.root))
        try:
            self._run(
                [
                    "git",
                    "clone",
                    "--depth",
                    str(repository.clone_depth),
                    "--no-checkout",
                    repository.clone_url,
                    str(workspace),
                ],
                self.root,
                action_sink,
            )
            self._run(["git", "fetch", "origin", f"pull/{pull_request.number}/head"], workspace, action_sink)
            self._run(["git", "fetch", "origin", pull_request.base_sha], workspace, action_sink)
            self._run(["git", "checkout", "--detach", pull_request.head_sha], workspace, action_sink)
            yield workspace
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def run_checks(self, checkout: Path, pull_request: PullRequest, action_sink: Callable) -> list[CheckResult]:
        result = self._run(["git", "diff", "--check"], checkout, action_sink, check=False)
        return [CheckResult(name="git diff --check", passed=result.returncode == 0, output=result.stdout)]

    def diff(self, checkout: Path, pull_request: PullRequest, action_sink: Callable, max_bytes: int = 200_000) -> str:
        result = self._run(
            ["git", "diff", "--no-ext-diff", "--unified=80", pull_request.base_sha, pull_request.head_sha],
            checkout,
            action_sink,
        )
        return result.stdout[:max_bytes]

    def _run(
        self,
        command: list[str],
        cwd: Path,
        action_sink: Callable,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=check,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout_seconds,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "GIT_TERMINAL_PROMPT": "0"},
            )
        except subprocess.CalledProcessError as exc:
            _record_command(action_sink, command, exc.returncode, exc.output or "")
            raise
        except subprocess.TimeoutExpired as exc:
            _record_command(action_sink, command, None, str(exc.output or ""))
            raise
        except OSError as exc:
            _record_command(action_sink, command, None, type(exc).__name__)
            raise
        _record_command(action_sink, command, result.returncode, result.stdout)
        return result
