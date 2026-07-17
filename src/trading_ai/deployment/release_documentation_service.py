from __future__ import annotations

from pathlib import Path

from .final_readiness_profile import ValidationCheck


class ReleaseDocumentationService:
    REQUIRED_FILES = (
        "PROJECT_STATUS.md",
        "README.md",
    )

    def evaluate(
        self,
        *,
        root: str | Path,
        additional_required: tuple[str, ...] = (),
    ) -> tuple[float, tuple[ValidationCheck, ...]]:
        root_path = Path(root)
        required = self.REQUIRED_FILES + additional_required
        checks: list[ValidationCheck] = []

        for name in required:
            exists = (root_path / name).exists()
            checks.append(
                ValidationCheck(
                    check_id=f"documentation-{name}",
                    category="DOCUMENTATION",
                    required=True,
                    passed=exists,
                    score=1.0 if exists else 0.0,
                    summary=(
                        f"{name} is present."
                        if exists else f"{name} is missing."
                    ),
                    recommendation=(
                        "" if exists else f"Create or restore {name}."
                    ),
                )
            )

        score = (
            sum(item.score for item in checks) / len(checks)
            if checks else 1.0
        )
        return score, tuple(checks)
