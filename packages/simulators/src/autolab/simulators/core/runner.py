from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from autolab.core.models import AutolabModel
from pydantic import Field


class BinaryNotAvailableError(RuntimeError):
    pass


class ProcessRunResult(AutolabModel):
    command: list[str]
    cwd: str
    exit_code: int | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    stdout_path: str
    stderr_path: str
    message: str = ""

    @property
    def duration_seconds(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


class ProcessRunner:
    def resolve_command(self, command: list[str], wrapper: str | None = None) -> list[str]:
        if not command:
            msg = "command cannot be empty"
            raise ValueError(msg)
        executable = command[0]
        if Path(executable).exists():
            resolved_executable = str(Path(executable).absolute())
        else:
            resolved = shutil.which(executable)
            if resolved is None:
                msg = f"binary '{executable}' is not available"
                raise BinaryNotAvailableError(msg)
            resolved_executable = resolved
        prefix = shlex.split(wrapper) if wrapper else []
        return [*prefix, resolved_executable, *command[1:]]

    def run(
        self,
        command: list[str],
        cwd: Path,
        stdout_path: Path,
        stderr_path: Path,
        timeout_seconds: int,
        environment: dict[str, str] | None = None,
        wrapper: str | None = None,
    ) -> ProcessRunResult:
        cwd.mkdir(parents=True, exist_ok=True)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_command = self.resolve_command(command, wrapper=wrapper)
        started_at = datetime.now(UTC)
        try:
            completed = subprocess.run(
                resolved_command,
                cwd=cwd,
                env={**os.environ, **(environment or {})},
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text((exc.stderr or "") + "\nProcess timed out.", encoding="utf-8")
            return ProcessRunResult(
                command=resolved_command,
                cwd=str(cwd),
                exit_code=None,
                started_at=started_at,
                ended_at=datetime.now(UTC),
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                message="timed out",
            )

        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        return ProcessRunResult(
            command=resolved_command,
            cwd=str(cwd),
            exit_code=completed.returncode,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            message="completed" if completed.returncode == 0 else "failed",
        )
