from __future__ import annotations

from pathlib import Path
import tempfile

from trading_ai.ui.command_runner import CommandRunner
from trading_ai.ui.report_browser import discover_reports


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "reports").mkdir()
        (root / "reports/sample.json").write_text(
            '{"ok": true}',
            encoding="utf-8",
        )

        runner = CommandRunner(
            root,
            python_executable=Path(__import__("sys").executable),
        )

        command = [
            runner.python_executable,
            "-c",
            "print('control-center-ok')",
        ]
        result = runner.run(
            "contract test",
            command,
            timeout_seconds=30,
        )

        assert result.succeeded
        assert result.return_code == 0
        assert "control-center-ok" in result.output
        assert runner.read_history(limit=1)[0]["succeeded"]

        reports = discover_reports(root)
        assert len(reports) == 1
        assert reports[0].relative_path == "reports/sample.json"

    print("All Trading AI Control Center assertions passed.")


if __name__ == "__main__":
    main()
