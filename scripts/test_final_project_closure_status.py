from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    status_candidates = (
        root / "updated_PROJECT_STATUS.md",
        root / "PROJECT_STATUS.md",
    )
    status_path = next(
        (
            path for path in status_candidates
            if path.exists()
            and "Milestone 30" in path.read_text(encoding="utf-8")
            and "Phase 10" in path.read_text(encoding="utf-8")
            and "Step 5" in path.read_text(encoding="utf-8")
        ),
        None,
    )
    assert status_path is not None, (
        "No current project status contains Milestone 30 Phase 10 Step 5."
    )

    status = status_path.read_text(encoding="utf-8")
    required = (
        "Milestone 29",
        "Milestone 30",
        "Phase 10",
        "Step 5",
        "COMPLETE",
        "PROJECT COMPLETE",
    )
    for text in required:
        assert text in status, (
            f"{text!r} is missing from {status_path.name}"
        )

    print(
        "All final project-status and closure assertions passed "
        f"using {status_path.name}."
    )


if __name__ == "__main__":
    main()
