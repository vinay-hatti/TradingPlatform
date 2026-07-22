from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .contracts import RankingRecord


DEFAULT_SEARCH_ROOTS: tuple[Path, ...] = (
    Path("reports/m35"),
    Path("reports"),
)

CANDIDATE_PATTERNS: tuple[str, ...] = (
    "**/opportunity_rankings.json",
    "**/ranking_snapshot.json",
    "**/*opportunity*ranking*.json",
    "**/*rankings*.json",
)


@dataclass(frozen=True)
class SymbolDataFile:
    path: Path
    record_count: int
    quality_score: int


def discover_ranking_files(
    search_roots: Iterable[Path] = DEFAULT_SEARCH_ROOTS,
) -> list[Path]:
    discovered: dict[str, Path] = {}
    for root in search_roots:
        if not root.exists():
            continue
        for pattern in CANDIDATE_PATTERNS:
            for path in root.glob(pattern):
                if path.is_file():
                    discovered[str(path.resolve())] = path
    return sorted(
        discovered.values(),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _row_quality(row: dict[str, Any]) -> int:
    score = 0
    keys = {str(key).lower() for key in row}

    if "symbol" in keys or "ticker" in keys:
        score += 10

    score_fields = {
        "institutional_score",
        "score",
        "composite_score",
        "probability",
        "probability_score",
        "probability_of_profit",
        "rank",
        "recommendation",
        "signal",
        "strategy",
    }
    score += 8 * len(keys & score_fields)

    operational_fields = {
        "provider",
        "provider_symbol",
        "status",
        "is_active",
        "asset_type",
        "last_refresh",
        "reconciliation_status",
    }
    score -= 3 * len(keys & operational_fields)
    return score


def _path_quality(path: Path) -> int:
    text = str(path).lower()
    score = 0

    positive = {
        "scanner_results": 80,
        "live_trade_candidates": 75,
        "recommendations": 70,
        "opportunity": 60,
        "ranking": 60,
        "candidate": 45,
        "scan": 35,
        "decision": 20,
    }
    negative = {
        "provider_reconciliation": -100,
        "universe_registry": -90,
        "population": -70,
        "coverage": -60,
        "completeness": -60,
        "freshness": -60,
        "quality": -50,
        "diagnostics": -50,
        "manifest": -45,
        "summary": -30,
    }

    for token, value in positive.items():
        if token in text:
            score += value
    for token, value in negative.items():
        if token in text:
            score += value
    return score


def discover_symbol_data_files(
    search_roots: Iterable[Path] = DEFAULT_SEARCH_ROOTS,
) -> list[SymbolDataFile]:
    discovered: dict[str, SymbolDataFile] = {}
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.glob("**/*.json"):
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                rows = _find_symbol_rows(payload)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue

            if not rows:
                continue

            sample = rows[: min(25, len(rows))]
            average_row_quality = int(
                sum(_row_quality(row) for row in sample) / len(sample)
            )
            quality = _path_quality(path) + average_row_quality

            discovered[str(path.resolve())] = SymbolDataFile(
                path=path,
                record_count=len(rows),
                quality_score=quality,
            )

    return sorted(
        discovered.values(),
        key=lambda item: (
            item.quality_score,
            item.path.stat().st_mtime,
            item.record_count,
        ),
        reverse=True,
    )


def resolve_ranking_path(path: Path | None) -> Path:
    if path is not None:
        if path.is_file():
            return path
        raise FileNotFoundError(f"Ranking input file does not exist: {path}")

    candidates = discover_symbol_data_files()
    if candidates:
        return candidates[0].path

    raise FileNotFoundError(
        "No non-empty symbol-bearing opportunity/scanner JSON files were "
        "found under reports/. Run the scanner/ranking producer first."
    )


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    rows = _find_symbol_rows(payload)
    if rows:
        return rows

    if isinstance(payload, list) and not payload:
        return []
    if isinstance(payload, dict):
        for key in ("rankings", "opportunities", "results", "items", "records"):
            if key in payload and payload[key] == []:
                return []

    raise ValueError(
        "JSON does not contain symbol/ticker ranking records in a supported "
        "list or nested report structure"
    )


def _find_symbol_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        direct = [
            row
            for row in payload
            if isinstance(row, dict) and (row.get("symbol") or row.get("ticker"))
        ]
        if direct:
            return direct

        for value in payload:
            nested = _find_symbol_rows(value)
            if nested:
                return nested
        return []

    if isinstance(payload, dict):
        priority_keys = (
            "rankings",
            "opportunities",
            "results",
            "items",
            "records",
            "candidates",
            "recommendations",
            "live_trade_candidates",
            "symbols",
            "rows",
            "data",
        )
        for key in priority_keys:
            if key in payload:
                nested = _find_symbol_rows(payload[key])
                if nested:
                    return nested

        for value in payload.values():
            nested = _find_symbol_rows(value)
            if nested:
                return nested
    return []


def load_ranking_records(path: Path | None) -> tuple[Path, list[RankingRecord]]:
    resolved = resolve_ranking_path(path)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    rows = _extract_rows(payload)

    records: list[RankingRecord] = []
    for index, row in enumerate(rows, start=1):
        symbol = row.get("symbol") or row.get("ticker")
        if not symbol:
            continue

        records.append(
            RankingRecord(
                symbol=str(symbol).upper(),
                rank=int(row.get("rank", index)),
                institutional_score=float(
                    row.get(
                        "institutional_score",
                        row.get("score", row.get("composite_score", 0.0)),
                    )
                ),
                probability_score=float(
                    row.get(
                        "probability_score",
                        row.get(
                            "probability",
                            row.get("probability_of_profit", 0.0),
                        ),
                    )
                ),
                expected_move=_optional_float(row.get("expected_move")),
                regime=_optional_str(
                    row.get("regime", row.get("market_regime"))
                ),
                sector=_optional_str(row.get("sector")),
                exchange=_optional_str(row.get("exchange")),
                optionable=_optional_bool(row.get("optionable")),
                is_etf=_optional_bool(row.get("is_etf")),
                cross_asset_score=_optional_float(row.get("cross_asset_score")),
                metadata=row.get("metadata", {}),
            )
        )

    if not records:
        raise ValueError(
            f"The ranking input contains zero usable symbol/ticker records: "
            f"{resolved}"
        )

    return resolved, records


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)
