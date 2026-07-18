from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import threading
import time
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: list[str]
    started_at: str
    finished_at: str
    duration_seconds: float
    return_code: int
    output: str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["succeeded"] = self.succeeded
        return payload


class CommandRunner:
    """
    Runs allowlisted local project commands and records their output.

    The UI constructs all commands from typed controls. No free-form shell
    input is accepted, and subprocesses are launched without shell=True.
    """

    def __init__(
        self,
        repo_root: str | Path,
        *,
        history_file: str | Path = "reports/ui/command_history.jsonl",
        python_executable: str | Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.python_executable = str(
            python_executable
            or self.repo_root / ".venv/bin/python3"
        )
        self.history_file = self.repo_root / history_file
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def module_command(
        self,
        *args: str,
    ) -> list[str]:
        return [
            self.python_executable,
            "-m",
            "trading_ai",
            *[str(arg) for arg in args],
        ]

    def script_command(
        self,
        script: str,
        *args: str,
    ) -> list[str]:
        script_path = self.repo_root / script
        return [
            self.python_executable,
            str(script_path),
            *[str(arg) for arg in args],
        ]

    @staticmethod
    def display_command(command: Sequence[str]) -> str:
        return " ".join(shlex.quote(str(part)) for part in command)

    def _append_history(self, result: CommandResult) -> None:
        with self.history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result.to_dict(), default=str) + "\n")

    def read_history(self, limit: int = 50) -> list[dict]:
        if not self.history_file.exists():
            return []

        records: list[dict] = []
        with self.history_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records[-limit:][::-1]

    def run(
        self,
        name: str,
        command: Sequence[str],
        *,
        output_callback: Callable[[str], None] | None = None,
        timeout_seconds: float | None = None,
        environment: dict[str, str] | None = None,
    ) -> CommandResult:
        command = [str(part) for part in command]
        started = datetime.now(timezone.utc)
        started_clock = time.monotonic()
        lines: list[str] = []

        process = subprocess.Popen(
            command,
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=environment,
        )

        timed_out = threading.Event()

        def watchdog() -> None:
            if timeout_seconds is None:
                return
            if process.wait(timeout=timeout_seconds) is None:
                return

        watcher: threading.Thread | None = None
        if timeout_seconds is not None:
            def terminate_after_timeout() -> None:
                try:
                    process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out.set()
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()

            watcher = threading.Thread(
                target=terminate_after_timeout,
                daemon=True,
            )
            watcher.start()

        assert process.stdout is not None
        for line in iter(process.stdout.readline, ""):
            lines.append(line)
            if output_callback is not None:
                output_callback("".join(lines))

        process.stdout.close()
        return_code = process.wait()

        if watcher is not None:
            watcher.join(timeout=0.1)

        if timed_out.is_set():
            lines.append(
                f"\n[UI] Command exceeded {timeout_seconds} seconds "
                "and was terminated.\n"
            )
            return_code = 124

        finished = datetime.now(timezone.utc)
        result = CommandResult(
            name=name,
            command=command,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=round(
                time.monotonic() - started_clock,
                3,
            ),
            return_code=return_code,
            output="".join(lines),
        )
        self._append_history(result)
        return result
