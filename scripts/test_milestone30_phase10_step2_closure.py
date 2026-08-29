from __future__ import annotations

from pathlib import Path
import re


REQUIRED = (
    "release_validation_policy.py",
    "release_validation_profile.py",
    "artifact_validation_service.py",
    "dependency_verification_service.py",
    "compatibility_validation_service.py",
    "migration_configuration_validation_service.py",
    "smoke_test_service.py",
    "release_readiness_engine.py",
    "release_validation_service.py",
    "release_readiness_report.py",
    "release_validation_cli.py",
)


def _status_candidates(root: Path) -> tuple[Path, ...]:
    return (
        root / "updated_PROJECT_STATUS.md",
        root / "PROJECT_STATUS.md",
    )


def _select_status(root: Path) -> tuple[Path, str]:
    existing: list[tuple[Path, str]] = []
    for path in _status_candidates(root):
        if path.exists():
            existing.append(
                (path, path.read_text(encoding="utf-8"))
            )

    if not existing:
        raise AssertionError(
            "Neither updated_PROJECT_STATUS.md nor PROJECT_STATUS.md "
            f"exists under {root}"
        )

    # Prefer the document that actually describes the current milestone.
    for path, content in existing:
        normalized = content.lower()
        if (
            "milestone 30" in normalized
            and "phase 10" in normalized
            and "step 2" in normalized
        ):
            return path, content

    names = ", ".join(path.name for path, _ in existing)
    raise AssertionError(
        "No available project status file contains Milestone 30 "
        f"Phase 10 Step 2. Checked: {names}. "
        "Replace PROJECT_STATUS.md with the current status or retain "
        "the generated updated_PROJECT_STATUS.md."
    )


def _step_status(status: str, step: int) -> str | None:
    patterns = (
        # - Step 1 — Description: COMPLETE
        rf"(?im)^.*\bstep\s+{step}\b[^\n]*\b"
        rf"(complete|completed|pending|in\s+progress|not\s+started)\b",
        # Step 1 on one line, Status / COMPLETE on following lines.
        rf"(?ims)^\s*#+?\s*step\s+{step}\s*$"
        rf".{{0,500}}?^\s*(?:status\s*)?$"
        rf".{{0,80}}?^\s*(?:✅\s*)?"
        rf"(complete|completed|pending|in\s+progress|not\s+started)\s*$",
        # Table row: | Milestone 30 Phase 10 Step 1 | ✅ Complete |
        rf"(?im)^\|[^\n]*\bstep\s+{step}\b[^\n]*\|"
        rf"[^\n]*\b(complete|completed|pending|in\s+progress|not\s+started)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, status)
        if match:
            return re.sub(
                r"\s+",
                " ",
                match.group(1).upper(),
            )
    return None


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    package = root / "src/trading_ai/deployment"

    missing = [
        name for name in REQUIRED
        if not (package / name).exists()
    ]
    assert not missing, (
        "Missing Milestone 30 Phase 10 Step 2 modules: "
        + ", ".join(missing)
    )

    status_path, status = _select_status(root)

    step1 = _step_status(status, 1)
    step2 = _step_status(status, 2)
    step3 = _step_status(status, 3)

    complete_values = {"COMPLETE", "COMPLETED"}

    assert step1 in complete_values, (
        f"Step 1 is not marked complete in {status_path.name}; "
        f"detected status: {step1!r}"
    )
    assert step2 in complete_values, (
        f"Step 2 is not marked complete in {status_path.name}; "
        f"detected status: {step2!r}"
    )

    normalized = status.lower()
    required_topics = (
        "release validation",
        "dependency verification",
        "smoke test",
        "readiness",
    )
    missing_topics = [
        topic for topic in required_topics
        if topic not in normalized
    ]
    assert not missing_topics, (
        f"{status_path.name} does not describe the Step 2 scope. "
        "Missing topic text: " + ", ".join(missing_topics)
    )

    allowed_step3 = {
        "PENDING",
        "IN PROGRESS",
        "NOT STARTED",
        "COMPLETE",
        "COMPLETED",
    }
    assert step3 in allowed_step3, (
        f"Step 3 status is missing or invalid in "
        f"{status_path.name}; detected status: {step3!r}"
    )

    print(
        "All Milestone 30 Phase 10 Step 2 closure assertions "
        f"passed using {status_path.name}."
    )


if __name__ == "__main__":
    main()
