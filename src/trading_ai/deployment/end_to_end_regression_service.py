from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

from .final_readiness_profile import RegressionResult


class EndToEndRegressionService:
    def run_suite(
        self,
        *,
        suite_name: str,
        test_paths: tuple[str | Path, ...],
        cwd: str | Path,
        env: dict[str, str] | None = None,
    ) -> RegressionResult:
        started = time.perf_counter()
        outputs: list[str] = []
        passed = 0
        failed = 0
        skipped = 0

        for raw in test_paths:
            path = Path(raw)
            if not path.exists():
                skipped += 1
                outputs.append(f"SKIPPED missing: {path}")
                continue
            result = subprocess.run(
                [sys.executable, str(path)],
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
            )
            outputs.append(result.stdout)
            if result.stderr:
                outputs.append(result.stderr)
            if result.returncode == 0:
                passed += 1
            else:
                failed += 1

        total = passed + failed + skipped
        denominator = passed + failed
        pass_rate = passed / denominator if denominator else 0.0
        duration = time.perf_counter() - started
        return RegressionResult(
            suite_name=suite_name,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=skipped,
            pass_rate=pass_rate,
            passed=(failed == 0 and denominator > 0),
            duration_seconds=duration,
            output="\n".join(outputs),
        )
