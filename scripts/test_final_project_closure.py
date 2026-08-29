from __future__ import annotations

from pathlib import Path
import tempfile

from trading_ai.deployment.final_project_closure_report import (
    FinalProjectClosureReportBuilder,
)
from trading_ai.deployment.final_project_closure_service import (
    FinalProjectClosureService,
)
from trading_ai.deployment.final_readiness_profile import (
    BenchmarkResult,
    RegressionResult,
    ReleaseSignOff,
    ValidationCheck,
)


def main() -> None:
    checks = (
        ValidationCheck(
            check_id="deployment-ready",
            category="DEPLOYMENT",
            required=True,
            passed=True,
            score=1.0,
            summary="Deployment automation and rollback validated.",
            evidence={"severity": "CRITICAL"},
        ),
        ValidationCheck(
            check_id="operational-governance-ready",
            category="OPERATIONAL_GOVERNANCE",
            required=True,
            passed=True,
            score=1.0,
            summary="Operational governance passed.",
            evidence={"severity": "CRITICAL"},
        ),
        ValidationCheck(
            check_id="observability-ready",
            category="OBSERVABILITY",
            required=True,
            passed=True,
            score=1.0,
            summary="Observability readiness passed.",
            evidence={"severity": "CRITICAL"},
        ),
    )

    benchmarks = (
        BenchmarkResult(
            benchmark_id="latency",
            category="PERFORMANCE",
            metric_name="latency_ms",
            observed_value=100.0,
            threshold_value=250.0,
            comparison="LESS_THAN_OR_EQUAL",
            passed=True,
            duration_seconds=0.01,
        ),
    )

    regressions = (
        RegressionResult(
            suite_name="full-project",
            total_tests=100,
            passed_tests=100,
            failed_tests=0,
            skipped_tests=0,
            pass_rate=1.0,
            passed=True,
            duration_seconds=1.0,
        ),
    )

    sign_off = ReleaseSignOff(
        release_id="release-1",
        release_version="1.0.0",
        approved_by=(
            "engineering-lead",
            "operations-manager",
            "product-owner",
        ),
        approval_roles=(
            "ENGINEERING",
            "OPERATIONS",
            "BUSINESS",
        ),
        final_decision="APPROVED",
        comments="Approved for production.",
    )

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for name in (
            "PROJECT_STATUS.md",
            "updated_PROJECT_STATUS.md",
            "README.md",
            "INSTALL.md",
        ):
            (root / name).write_text("complete\n", encoding="utf-8")

        result = FinalProjectClosureService().evaluate(
            root=root,
            project_name="Trading AI Platform",
            checks=checks,
            benchmarks=benchmarks,
            regressions=regressions,
            sign_off=sign_off,
        )
        assert result.ready_for_production
        assert result.overall_score == 1.0
        assert result.recommendation == "PROJECT_PRODUCTION_READY"

        builder = FinalProjectClosureReportBuilder()
        html_path = builder.write_html(
            root / "final_project_closure.html",
            result,
        )
        json_path = builder.write_json(
            root / "final_project_closure.json",
            result,
        )
        assert html_path.exists()
        assert json_path.exists()
        html = html_path.read_text(encoding="utf-8")
        for heading in builder.SECTIONS:
            assert heading in html

    print(
        "All final production-readiness, regression, benchmark, "
        "documentation, sign-off, and project-closure assertions passed."
    )


if __name__ == "__main__":
    main()
