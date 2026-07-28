from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .policy import OperationalReadinessPolicy
from .profile import ReadinessCategoryScore, ReadinessControl


class OperationalReadinessEngine:
    def __init__(
        self,
        policy: OperationalReadinessPolicy | None = None,
    ) -> None:
        self.policy = policy or OperationalReadinessPolicy()
        self.policy.validate()

    def category_scores(
        self,
        controls: Iterable[ReadinessControl],
    ) -> tuple[ReadinessCategoryScore, ...]:
        grouped: dict[str, list[ReadinessControl]] = {}
        for control in controls:
            grouped.setdefault(control.category, []).append(control)

        output: list[ReadinessCategoryScore] = []
        for category, rows in sorted(grouped.items()):
            total_weight = sum(row.weight for row in rows) or 1.0
            score = round(
                sum(row.score * row.weight for row in rows) / total_weight,
                2,
            )
            failed = sum(row.status == "FAIL" for row in rows)
            warned = sum(row.status == "WARN" for row in rows)
            passed = sum(row.status == "PASS" for row in rows)
            status = (
                "FAIL"
                if score < self.policy.minimum_category_score or failed
                else "WARN" if warned else "PASS"
            )
            output.append(
                ReadinessCategoryScore(
                    category=category,
                    score=score,
                    status=status,
                    control_count=len(rows),
                    passed=passed,
                    warned=warned,
                    failed=failed,
                )
            )
        return tuple(output)

    def overall_score(
        self,
        controls: Iterable[ReadinessControl],
    ) -> float:
        rows = tuple(controls)
        total_weight = sum(row.weight for row in rows) or 1.0
        return round(
            sum(row.score * row.weight for row in rows) / total_weight,
            2,
        )

    def final_status(
        self,
        controls: Iterable[ReadinessControl],
        categories: Iterable[ReadinessCategoryScore],
        overall_score: float,
    ) -> tuple[str, str]:
        rows = tuple(controls)
        cats = tuple(categories)
        failures = sum(row.status == "FAIL" for row in rows)
        warnings = sum(row.status == "WARN" for row in rows)
        category_failures = sum(row.status == "FAIL" for row in cats)

        if (
            failures > self.policy.maximum_failed_controls
            or category_failures > 0
            or overall_score < self.policy.minimum_overall_score
        ):
            return (
                "PHASE9_NOT_READY_FOR_PRODUCTION_ACCEPTANCE",
                "Do not sign off. Resolve failed controls and rerun Phase 9.",
            )
        if warnings > self.policy.maximum_warning_controls:
            return (
                "PHASE9_CONDITIONALLY_READY",
                "Resolve excessive warnings before final sign-off.",
            )
        if warnings:
            return (
                "PHASE9_READY_WITH_CONDITIONS",
                "Paper-trading operations may continue with documented conditions.",
            )
        return (
            "PHASE9_OPERATIONALLY_READY",
            "Milestone 51 paper-trading automation is ready for formal sign-off.",
        )

    def acceptance_summary(
        self,
        controls: Iterable[ReadinessControl],
    ) -> dict[str, int]:
        rows = tuple(controls)
        return {
            "control_count": len(rows),
            "passed": sum(row.status == "PASS" for row in rows),
            "warned": sum(row.status == "WARN" for row in rows),
            "failed": sum(row.status == "FAIL" for row in rows),
            "error_count": sum(len(row.errors) for row in rows),
            "warning_count": sum(len(row.warnings) for row in rows),
        }
