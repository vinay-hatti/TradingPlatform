from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ArtifactResult:
    source: str
    available: bool
    data: Any
    detail: str
    latency_ms: float
    as_of: datetime
    path: str | None = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _latest(root: Path, patterns: Iterable[str]) -> Path | None:
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(path for path in root.glob(pattern) if path.is_file())
    return max(matches, key=lambda path: path.stat().st_mtime) if matches else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class RepositoryArtifactAdapters:
    """
    Reads the durable artifacts that the current TradingPlatform workflows
    already produce. API requests never start scanners, providers, or brokers.
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        configured = project_root or os.getenv("TRADING_AI_PROJECT_ROOT")
        self.root = Path(configured or Path.cwd()).resolve()

    def _result(
        self,
        source: str,
        callback,
        *,
        missing_detail: str,
    ) -> ArtifactResult:
        started = time.perf_counter()
        try:
            path, data = callback()
            elapsed = (time.perf_counter() - started) * 1000
            if path is None:
                return ArtifactResult(
                    source=source,
                    available=False,
                    data=None,
                    detail=missing_detail,
                    latency_ms=elapsed,
                    as_of=utcnow(),
                    path=None,
                )
            return ArtifactResult(
                source=source,
                available=True,
                data=data,
                detail=f"Loaded {path.relative_to(self.root)}",
                latency_ms=elapsed,
                as_of=_mtime(path),
                path=str(path),
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return ArtifactResult(
                source=source,
                available=False,
                data=None,
                detail=f"{type(exc).__name__}: {exc}",
                latency_ms=elapsed,
                as_of=utcnow(),
                path=None,
            )

    def scanner(self) -> ArtifactResult:
        def load():
            reports = self.root / "reports"
            path = _latest(
                reports,
                (
                    "scanner_results_*.csv",
                    "daily_recommendations/**/*.csv",
                    "daily_recommendations_*.csv",
                    "recommendations/**/*.csv",
                ),
            )
            return path, _read_csv(path) if path else None

        return self._result(
            "scanner_artifact",
            load,
            missing_detail=(
                "No scanner CSV found under reports/. Run generate-signals, "
                "daily-scan, or the scanner workflow first."
            ),
        )

    def optimized_portfolio(self) -> ArtifactResult:
        def load():
            path = _latest(
                self.root / "reports",
                (
                    "optimized_portfolio_*.csv",
                    "portfolio/**/*.csv",
                    "optimization/**/*.csv",
                ),
            )
            return path, _read_csv(path) if path else None

        return self._result(
            "optimized_portfolio_artifact",
            load,
            missing_detail="No optimized portfolio CSV found under reports/.",
        )

    def paper_positions(self) -> ArtifactResult:
        def load():
            candidates = (
                self.root / "data/paper_trading/positions.json",
                self.root / "data/paper/positions.json",
            )
            path = next((item for item in candidates if item.exists()), None)
            if path is None:
                return None, None
            payload = _read_json(path)
            if isinstance(payload, dict) and "positions" in payload:
                positions = list(payload.get("positions", {}).values())
            elif isinstance(payload, list):
                positions = payload
            else:
                positions = []
            return path, positions

        return self._result(
            "paper_positions_artifact",
            load,
            missing_detail=(
                "No paper position state found at data/paper_trading/positions.json "
                "or data/paper/positions.json."
            ),
        )

    def paper_executions(self) -> ArtifactResult:
        def load():
            path = self.root / "data/paper_trading/executions.json"
            if not path.exists():
                return None, None
            payload = _read_json(path)
            records = payload.get("executions", {}) if isinstance(payload, dict) else {}
            return path, list(records.values())

        return self._result(
            "paper_execution_artifact",
            load,
            missing_detail="No paper execution history found.",
        )

    def paper_cash(self) -> ArtifactResult:
        def load():
            path = self.root / "data/paper/cash.json"
            return (
                (path, _read_json(path))
                if path.exists()
                else (None, None)
            )

        return self._result(
            "paper_cash_artifact",
            load,
            missing_detail="No legacy paper cash state found.",
        )

    def runtime_health(self) -> ArtifactResult:
        def load():
            path = self.root / "data/operational_resilience/runtime_health_registry.json"
            return (
                (path, _read_json(path))
                if path.exists()
                else (None, None)
            )

        return self._result(
            "runtime_health_registry",
            load,
            missing_detail="No runtime health registry snapshot found.",
        )

    def freshness(self) -> dict[str, ArtifactResult]:
        return {
            "scanner": self.scanner(),
            "portfolio": self.optimized_portfolio(),
            "positions": self.paper_positions(),
            "executions": self.paper_executions(),
            "cash": self.paper_cash(),
            "runtime_health": self.runtime_health(),
        }
