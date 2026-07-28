from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from .profile import ScheduledPhaseCommand, ScheduledPhaseExecution


class SubprocessPhaseRunner:
    def execute(
        self,
        command: ScheduledPhaseCommand,
    ) -> ScheduledPhaseExecution:
        if not command.enabled:
            now = datetime.now(timezone.utc).isoformat()
            return ScheduledPhaseExecution(
                phase=command.phase,
                name=command.name,
                status="SKIPPED",
                attempt_count=0,
                exit_code=None,
                started_at=now,
                completed_at=now,
                duration_seconds=0.0,
                warnings=("PHASE_DISABLED",),
                metadata={"required": command.required},
            )

        started = datetime.now(timezone.utc)
        attempts = 0
        last = None
        errors: list[str] = []
        max_attempts = max(1, command.retry_limit + 1)
        while attempts < max_attempts:
            attempts += 1
            try:
                last = subprocess.run(
                    list(command.command),
                    capture_output=True,
                    text=True,
                    timeout=command.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                errors.append("PHASE_TIMEOUT")
                last = exc
                if attempts >= max_attempts:
                    break
                continue
            if last.returncode == 0:
                break
            errors.append(f"EXIT_CODE_{last.returncode}")

        completed = datetime.now(timezone.utc)
        success = (
            isinstance(last, subprocess.CompletedProcess)
            and last.returncode == 0
        )
        stdout = getattr(last, "stdout", "") or ""
        stderr = getattr(last, "stderr", "") or ""
        exit_code = getattr(last, "returncode", None)
        return ScheduledPhaseExecution(
            phase=command.phase,
            name=command.name,
            status="COMPLETED" if success else "FAILED",
            attempt_count=attempts,
            exit_code=exit_code,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            duration_seconds=round(
                (completed - started).total_seconds(), 6
            ),
            stdout_tail=stdout[-4000:],
            stderr_tail=stderr[-4000:],
            warnings=(),
            errors=tuple(dict.fromkeys(errors)) if not success else (),
            metadata={
                "required": command.required,
                "command": list(command.command),
                "timeout_seconds": command.timeout_seconds,
                "retry_limit": command.retry_limit,
            },
        )
