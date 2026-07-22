from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class UniverseRefreshPolicy:
    minimum_symbol_count: int = 6000
    maximum_source_age_hours: int = 72
    allow_degraded_publish: bool = True
    require_at_least_one_provider: bool = True

    def validate(self) -> None:
        if self.minimum_symbol_count <= 0:
            raise ValueError("minimum_symbol_count must be greater than zero")
        if self.maximum_source_age_hours <= 0:
            raise ValueError("maximum_source_age_hours must be greater than zero")


@dataclass(frozen=True)
class UniverseArtifactPaths:
    canonical_csv: Path
    manifest_json: Path
    summary_json: Path
    reconciliation_json: Path
    refresh_report_html: Path


@dataclass(frozen=True)
class UniverseRefreshResult:
    generated_at: datetime
    status: str
    published: bool
    symbol_count: int
    added_count: int
    removed_count: int
    unchanged_count: int
    stale_provider_count: int
    failed_provider_count: int
    source_names: tuple[str, ...]
    warnings: tuple[str, ...]
    artifacts: dict[str, str]
    metadata: dict[str, Any] = field(default_factory=dict)
