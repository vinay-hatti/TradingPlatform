from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PhaseClosureResult:
    passed: bool
    assertions: tuple[str, ...]
    failures: tuple[str, ...]


def validate_phase5_artifacts(
    *,
    cross_asset_feature_path: str | Path,
    intermarket_path: str | Path,
    sector_path: str | Path,
    correlation_path: str | Path,
    intelligence_path: str | Path,
) -> PhaseClosureResult:
    required = {
        "Step 1 cross-asset feature store": Path(
            cross_asset_feature_path
        ),
        "Step 2 intermarket profile": Path(intermarket_path),
        "Step 3 sector leadership profile": Path(sector_path),
        "Step 4 correlation-dispersion profile": Path(
            correlation_path
        ),
        "Step 5 intelligence profile": Path(intelligence_path),
    }

    assertions: list[str] = []
    failures: list[str] = []

    for label, path in required.items():
        if path.exists() and path.stat().st_size > 0:
            assertions.append(f"{label}: present")
        else:
            failures.append(f"{label}: missing or empty at {path}")

    return PhaseClosureResult(
        passed=not failures,
        assertions=tuple(assertions),
        failures=tuple(failures),
    )
