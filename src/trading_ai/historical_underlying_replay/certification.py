from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean, median
from typing import Iterable, Sequence

from sqlalchemy import text

from trading_ai.historical_underlying_replay.analytics import (
    DIRECTIONAL,
    HistoricalChampionAnalyticsService,
    _bucket,
    _summarize,
)

CERTIFICATION_VERSION = "M77.2-MULTIYEAR-FROZEN-CHAMPION-1.0"
CERTIFICATION_MODE = "READ_ONLY_MULTIYEAR_FROZEN_CHAMPION_CERTIFICATION"
DEFAULT_START = date(2022, 10, 14)
DEFAULT_END = date(2026, 8, 17)


def _pct(numerator: int, denominator: int):
    return None if not denominator else numerator / denominator * 100.0


def _mean(values):
    values = [float(v) for v in values if v is not None]
    return None if not values else mean(values)


def _median(values):
    values = [float(v) for v in values if v is not None]
    return None if not values else median(values)


class MultiYearFrozenChampionCertificationService:
    """Read-only certification over completed M77.1 frozen-champion replay runs.

    This service never updates production authority, production model weights,
    replay predictions, or replay outcomes. It only reads existing M77 replay
    artifacts and computes cross-year certification evidence.
    """

    def __init__(self, session):
        self.session = session
        self.analytics = HistoricalChampionAnalyticsService(session)

    def _run_rows(self, replay_run_ids: Sequence[str]):
        if not replay_run_ids:
            raise ValueError("At least one replay_run_id is required")
        rows = self.session.execute(
            text(
                """
                SELECT *
                FROM historical_underlying_replay_run
                WHERE replay_run_id = ANY(:ids)
                ORDER BY start_date, started_at
                """
            ),
            {"ids": list(replay_run_ids)},
        ).mappings().all()
        found = {str(row["replay_run_id"]) for row in rows}
        missing = [rid for rid in replay_run_ids if rid not in found]
        if missing:
            raise RuntimeError(f"Replay runs not found: {missing}")
        bad = [
            str(row["replay_run_id"])
            for row in rows
            if str(row["status"]) not in {"READY", "DEGRADED"}
        ]
        if bad:
            raise RuntimeError(f"Replay runs are not reportable: {bad}")
        return [dict(row) for row in rows]

    def _combined_rows(self, replay_run_ids: Sequence[str]):
        rows = []
        for rid in replay_run_ids:
            rows.extend(self.analytics._rows(rid))
        rows.sort(key=lambda r: (r["as_of"], r["symbol"], r["prediction_id"]))
        return rows

    @staticmethod
    def _group(rows, key_fn):
        groups = defaultdict(list)
        for row in rows:
            groups[str(key_fn(row))].append(row)
        return [
            {"group": key, **_summarize(groups[key])}
            for key in sorted(groups)
        ]

    @staticmethod
    def _yearly_group_map(rows, group_fn):
        grouped = defaultdict(lambda: defaultdict(list))
        for row in rows:
            year = str(row["as_of"].year)
            grouped[str(group_fn(row))][year].append(row)
        return grouped

    @staticmethod
    def _persistence(rows, group_fn, horizon: int, min_year_observations: int = 10):
        grouped = MultiYearFrozenChampionCertificationService._yearly_group_map(
            rows, group_fn
        )
        result = []
        return_field = f"thesis_aligned_return_{horizon}d_avg_pct"
        hit_field = f"directional_hit_rate_{horizon}d_pct"

        for group, by_year in sorted(grouped.items()):
            yearly = []
            for year, values in sorted(by_year.items()):
                summary = _summarize(values)
                if summary["directional_observations"] < min_year_observations:
                    continue
                yearly.append(
                    {
                        "year": int(year),
                        "directional_observations": summary["directional_observations"],
                        "thesis_return_avg_pct": summary[return_field],
                        "directional_hit_rate_pct": summary[hit_field],
                    }
                )
            if not yearly:
                continue
            positive_return_years = sum(
                (item["thesis_return_avg_pct"] or 0) > 0 for item in yearly
            )
            above_50_hit_years = sum(
                (item["directional_hit_rate_pct"] or 0) > 50 for item in yearly
            )
            result.append(
                {
                    "group": group,
                    "qualified_years": len(yearly),
                    "positive_return_years": positive_return_years,
                    "positive_return_year_rate_pct": _pct(
                        positive_return_years, len(yearly)
                    ),
                    "above_50_hit_years": above_50_hit_years,
                    "above_50_hit_year_rate_pct": _pct(
                        above_50_hit_years, len(yearly)
                    ),
                    "median_year_thesis_return_pct": _median(
                        item["thesis_return_avg_pct"] for item in yearly
                    ),
                    "median_year_hit_rate_pct": _median(
                        item["directional_hit_rate_pct"] for item in yearly
                    ),
                    "yearly": yearly,
                }
            )
        return result

    def build_report(self, replay_run_ids: Sequence[str]):
        runs = self._run_rows(replay_run_ids)
        rows = self._combined_rows(replay_run_ids)
        if not rows:
            raise RuntimeError("Selected replay runs contain no prediction/outcome rows")

        directional = [row for row in rows if row["direction"] in DIRECTIONAL]
        session_index = self.analytics._session_index()

        by_year = self._group(rows, lambda r: r["as_of"].year)
        by_direction = self._group(rows, lambda r: r["direction"])
        by_category = self._group(
            rows, lambda r: r.get("primary_category") or "UNKNOWN"
        )
        by_confidence = self._group(
            rows,
            lambda r: _bucket(
                float(r["confidence"]), (0, 40, 50, 60, 70, 80, 90, 101)
            ),
        )
        by_score = self._group(
            rows,
            lambda r: _bucket(
                float(r["overall_score"]), (0, 40, 50, 60, 70, 80, 90, 101)
            ),
        )

        structure_groups = defaultdict(list)
        alignment_groups = defaultdict(list)
        timeframe_groups = defaultdict(list)
        regime_counts = defaultdict(int)
        for row in rows:
            profile = row.get("profile_json") or {}
            structure_groups[str(profile.get("structure") or "UNKNOWN")].append(row)
            alignment_groups[
                _bucket(
                    float(profile.get("alignment_score") or 0),
                    (0, 25, 50, 65, 80, 101),
                )
            ].append(row)
            states = profile.get("timeframe_states") or {}
            signature = "/".join(
                str((states.get(tf) or {}).get("direction") or "NA")
                for tf in ("1d", "1w", "1mo")
            )
            timeframe_groups[signature].append(row)
            regime_counts[
                str((profile.get("context") or {}).get("market_regime") or "UNKNOWN")
            ] += 1

        overlap = {}
        for horizon in (20, 60):
            cohort = self.analytics._non_overlapping(
                directional, session_index, horizon
            )
            overlap[f"{horizon}d"] = {
                "all_directional_observations": len(directional),
                "non_overlapping_observations": len(cohort),
                "overlap_fraction_pct": None
                if not directional
                else (1 - len(cohort) / len(directional)) * 100,
                "non_overlapping_summary": _summarize(cohort),
            }

        year_summaries = {
            str(item["group"]): item for item in by_year
        }
        directional_years = [
            {
                "year": int(year),
                "directional_observations": summary["directional_observations"],
                "hit_20d_pct": summary["directional_hit_rate_20d_pct"],
                "thesis_return_20d_avg_pct": summary[
                    "thesis_aligned_return_20d_avg_pct"
                ],
                "hit_60d_pct": summary["directional_hit_rate_60d_pct"],
                "thesis_return_60d_avg_pct": summary[
                    "thesis_aligned_return_60d_avg_pct"
                ],
            }
            for year, summary in sorted(year_summaries.items())
        ]

        positive_20_years = sum(
            (row["thesis_return_20d_avg_pct"] or 0) > 0
            for row in directional_years
        )
        positive_60_years = sum(
            (row["thesis_return_60d_avg_pct"] or 0) > 0
            for row in directional_years
        )

        return {
            "certification_version": CERTIFICATION_VERSION,
            "governance": {
                "mode": CERTIFICATION_MODE,
                "production_authority_effect": False,
                "production_model_mutation": False,
                "prediction_mutation": False,
                "outcome_mutation": False,
                "automatic_champion_promotion": False,
                "champion": "FROZEN_CURRENT_STOCK_INTELLIGENCE_UNDERLYING_ONLY",
                "replay_mode": "CURRENT_UNIVERSE_HISTORICAL_REPLAY",
                "survivorship_bias_free_claim": False,
                "pit_sector_certification_claim": False,
                "confidence_probability_claim": False,
                "market_regime_certification_requires_context": True,
            },
            "runs": runs,
            "coverage": {
                "first_as_of": min(row["as_of"] for row in rows),
                "last_as_of": max(row["as_of"] for row in rows),
                "observations": len(rows),
                "directional_observations": len(directional),
                "symbols": len({row["symbol"] for row in rows}),
                "replay_dates": len({row["as_of"] for row in rows}),
                "years": sorted({row["as_of"].year for row in rows}),
            },
            "overall": {
                **_summarize(rows),
                **self.analytics._target_stats(rows),
            },
            "by_year": by_year,
            "cross_year_directional_summary": {
                "years": directional_years,
                "positive_20d_return_years": positive_20_years,
                "positive_20d_return_year_rate_pct": _pct(
                    positive_20_years, len(directional_years)
                ),
                "positive_60d_return_years": positive_60_years,
                "positive_60d_return_year_rate_pct": _pct(
                    positive_60_years, len(directional_years)
                ),
            },
            "by_direction": by_direction,
            "by_primary_category": by_category,
            "by_confidence_bucket": by_confidence,
            "by_overall_score_bucket": by_score,
            "by_structure": [
                {"group": key, **_summarize(values)}
                for key, values in sorted(structure_groups.items())
            ],
            "by_alignment_bucket": [
                {"group": key, **_summarize(values)}
                for key, values in sorted(alignment_groups.items())
            ],
            "by_timeframe_direction_signature": [
                {"group": key, **_summarize(values)}
                for key, values in sorted(timeframe_groups.items())
            ],
            "context_availability": {
                "market_regime_counts": dict(sorted(regime_counts.items()))
            },
            "overlap_governance": overlap,
            "cluster_robustness": {
                "symbol_clustered_20d": self.analytics._cluster_summary(
                    directional, "symbol", 20
                ),
                "date_clustered_20d": self.analytics._cluster_summary(
                    directional, "as_of", 20
                ),
                "symbol_clustered_60d": self.analytics._cluster_summary(
                    directional, "symbol", 60
                ),
                "date_clustered_60d": self.analytics._cluster_summary(
                    directional, "as_of", 60
                ),
            },
            "cross_year_persistence": {
                "direction_20d": self._persistence(
                    rows, lambda r: r["direction"], 20
                ),
                "direction_60d": self._persistence(
                    rows, lambda r: r["direction"], 60
                ),
                "primary_category_20d": self._persistence(
                    rows,
                    lambda r: r.get("primary_category") or "UNKNOWN",
                    20,
                ),
                "primary_category_60d": self._persistence(
                    rows,
                    lambda r: r.get("primary_category") or "UNKNOWN",
                    60,
                ),
                "overall_score_20d": self._persistence(
                    rows,
                    lambda r: _bucket(
                        float(r["overall_score"]),
                        (0, 40, 50, 60, 70, 80, 90, 101),
                    ),
                    20,
                ),
                "overall_score_60d": self._persistence(
                    rows,
                    lambda r: _bucket(
                        float(r["overall_score"]),
                        (0, 40, 50, 60, 70, 80, 90, 101),
                    ),
                    60,
                ),
                "structure_20d": self._persistence(
                    rows,
                    lambda r: (r.get("profile_json") or {}).get("structure")
                    or "UNKNOWN",
                    20,
                ),
                "structure_60d": self._persistence(
                    rows,
                    lambda r: (r.get("profile_json") or {}).get("structure")
                    or "UNKNOWN",
                    60,
                ),
            },
        }
