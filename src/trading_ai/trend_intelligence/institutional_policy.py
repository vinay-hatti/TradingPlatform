from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstitutionalTrendPolicy:
    minimum_history_rows: int = 126
    volume_window: int = 20
    short_return_window: int = 20
    long_return_window: int = 60
    persistence_window: int = 20
    maximum_snapshot_age_days: int = 3

    @staticmethod
    def grade(score: float) -> str:
        if score >= 80.0:
            return "A"
        if score >= 65.0:
            return "B"
        if score >= 50.0:
            return "C"
        if score >= 35.0:
            return "D"
        return "F"
