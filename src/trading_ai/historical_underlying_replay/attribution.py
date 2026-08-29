from __future__ import annotations

from collections import defaultdict
from statistics import mean, median
from typing import Sequence

from trading_ai.historical_underlying_replay.analytics import (
    BEARISH,
    BULLISH,
    DIRECTIONAL,
    HistoricalChampionAnalyticsService,
    _bucket,
    _raw_return_from_stored,
    _summarize,
    _thesis_return_from_stored,
)
from trading_ai.historical_underlying_replay.regime import (
    HistoricalRegimeAuthorityService,
    REGIME_AUTHORITY_VERSION,
)

ATTRIBUTION_VERSION = "M77.3-CONDITIONAL-EDGE-ATTRIBUTION-1.0"
SCORE_EDGES = (0, 40, 50, 60, 70, 80, 90, 101)
MIN_YEAR_OBS = 30
MIN_RAW_OBS = 200
MIN_NONOVERLAP_20 = 75
MIN_NONOVERLAP_60 = 30
MIN_SYMBOLS = 30


def _pct(n, d):
    return None if not d else n / d * 100.0


def _avg(values):
    values = [float(v) for v in values if v is not None]
    return None if not values else mean(values)


def _median(values):
    values = [float(v) for v in values if v is not None]
    return None if not values else median(values)


def _score_band(row):
    return _bucket(float(row["overall_score"]), SCORE_EDGES)


def _structure(row):
    return str((row.get("profile_json") or {}).get("structure") or "UNKNOWN")


def _candidate_key(kind, parts):
    return kind + "::" + "|".join(str(p) for p in parts)


class ConditionalEdgeAttributionService:
    """Read-only conditional edge attribution over certified M77 replay artifacts."""

    def __init__(self, session):
        self.session = session
        self.analytics = HistoricalChampionAnalyticsService(session)
        self.regime_service = HistoricalRegimeAuthorityService(session)

    def _rows(self, replay_run_ids: Sequence[str]):
        rows = []
        for replay_run_id in replay_run_ids:
            rows.extend(self.analytics._rows(replay_run_id))
        rows.sort(key=lambda row: (row["as_of"], row["symbol"], row["prediction_id"]))
        return rows

    @staticmethod
    def _enrich(rows, regime_map):
        enriched = []
        for original in rows:
            row = dict(original)
            snapshot = regime_map.get(row["as_of"])
            row["historical_regime"] = snapshot.regime if snapshot else "UNKNOWN"
            row["historical_trend_state"] = snapshot.trend_state if snapshot else "UNKNOWN"
            row["historical_volatility_state"] = snapshot.volatility_state if snapshot else "UNKNOWN"
            row["historical_breadth_state"] = snapshot.breadth_state if snapshot else "UNKNOWN"
            row["score_band"] = _score_band(row)
            row["structure"] = _structure(row)
            enriched.append(row)
        return enriched

    @staticmethod
    def _control_means(rows, horizon):
        field = f"r{horizon}"
        grouped = defaultdict(lambda: [0.0, 0])
        for row in rows:
            raw = _raw_return_from_stored(row["direction"], row[field])
            if raw is None:
                continue
            key = (row["as_of"], row["historical_regime"], row["score_band"])
            grouped[key][0] += raw
            grouped[key][1] += 1
        return grouped

    @staticmethod
    def _matched_excess(candidate_rows, all_rows, horizon):
        field = f"r{horizon}"
        controls = ConditionalEdgeAttributionService._control_means(all_rows, horizon)
        excess = []
        control_aligned = []
        for row in candidate_rows:
            thesis = _thesis_return_from_stored(row["direction"], row[field])
            raw = _raw_return_from_stored(row["direction"], row[field])
            if thesis is None or raw is None or row["direction"] not in DIRECTIONAL:
                continue
            key = (row["as_of"], row["historical_regime"], row["score_band"])
            total, count = controls.get(key, (0.0, 0))
            if count <= 1:
                continue
            peer_raw = (total - raw) / (count - 1)
            sign = -1.0 if row["direction"] in BEARISH else 1.0
            peer_aligned = peer_raw * sign
            control_aligned.append(peer_aligned)
            excess.append(thesis - peer_aligned)
        return {
            "matched_observations": len(excess),
            "matched_control_thesis_return_avg_pct": _avg(control_aligned),
            "matched_excess_thesis_return_avg_pct": _avg(excess),
            "control_contract": (
                "leave-one-out same replay date + historical regime + overall-score band; "
                "control raw underlying return is aligned to the candidate direction. "
                "Liquidity/volatility matching is not claimed."
            ),
        }

    @staticmethod
    def _symbol_breadth(rows, horizon):
        field = f"r{horizon}"
        by_symbol = defaultdict(list)
        for row in rows:
            value = _thesis_return_from_stored(row["direction"], row[field])
            if value is not None:
                by_symbol[row["symbol"]].append(value)
        means = {symbol: mean(values) for symbol, values in by_symbol.items() if values}
        values = list(means.values())
        return {
            "symbols": len(values),
            "positive_symbol_rate_pct": _pct(sum(v > 0 for v in values), len(values)),
            "median_symbol_thesis_return_pct": _median(values),
            "mean_symbol_thesis_return_pct": _avg(values),
        }

    @staticmethod
    def _year_persistence(rows, horizon):
        field = f"r{horizon}"
        by_year = defaultdict(list)
        for row in rows:
            value = _thesis_return_from_stored(row["direction"], row[field])
            if value is not None:
                by_year[row["as_of"].year].append(value)
        yearly = []
        for year, values in sorted(by_year.items()):
            if len(values) < MIN_YEAR_OBS:
                continue
            yearly.append({
                "year": year,
                "observations": len(values),
                "thesis_return_avg_pct": mean(values),
                "hit_rate_pct": _pct(sum(v > 0 for v in values), len(values)),
            })
        positive = sum(item["thesis_return_avg_pct"] > 0 for item in yearly)
        return {
            "qualified_years": len(yearly),
            "positive_years": positive,
            "positive_year_rate_pct": _pct(positive, len(yearly)),
            "median_year_thesis_return_pct": _median(
                item["thesis_return_avg_pct"] for item in yearly
            ),
            "worst_year_thesis_return_pct": None if not yearly else min(
                item["thesis_return_avg_pct"] for item in yearly
            ),
            "median_year_hit_rate_pct": _median(item["hit_rate_pct"] for item in yearly),
            "yearly": yearly,
        }

    def _candidate_record(self, candidate_id, dimensions, rows, all_rows, session_index, horizon):
        nonoverlap = self.analytics._non_overlapping(rows, session_index, horizon)
        summary = _summarize(rows)
        non_summary = _summarize(nonoverlap)
        persistence = self._year_persistence(rows, horizon)
        breadth = self._symbol_breadth(rows, horizon)
        control = self._matched_excess(rows, all_rows, horizon)
        return_field = f"thesis_aligned_return_{horizon}d_avg_pct"
        hit_field = f"directional_hit_rate_{horizon}d_pct"
        non_return = non_summary[return_field]
        non_hit = non_summary[hit_field]
        enough = (
            len(rows) >= MIN_RAW_OBS
            and len(nonoverlap) >= (MIN_NONOVERLAP_20 if horizon == 20 else MIN_NONOVERLAP_60)
            and breadth["symbols"] >= MIN_SYMBOLS
            and persistence["qualified_years"] >= 4
        )
        positive_years = persistence["positive_years"]
        symbol_rate = breadth["positive_symbol_rate_pct"] or 0.0
        excess = control["matched_excess_thesis_return_avg_pct"]
        if not enough:
            grade, status = "D", "INSUFFICIENT_INDEPENDENT_EVIDENCE"
        elif positive_years == persistence["qualified_years"] and (non_return or 0) > 0 and (non_hit or 0) >= 52 and symbol_rate >= 55 and (excess or 0) > 0:
            grade, status = "A", "MULTIYEAR_SUPPORTED"
        elif positive_years >= max(3, persistence["qualified_years"] - 1) and (non_return or 0) > 0 and (non_hit or 0) > 50 and symbol_rate >= 50 and (excess or 0) > 0:
            grade, status = "B", "CONDITIONAL_SUPPORTED"
        elif positive_years <= 1 and (non_return or 0) < 0:
            grade, status = "F", "NOT_SUPPORTED"
        else:
            grade, status = "C", "MIXED_EVIDENCE"
        return {
            "candidate_id": candidate_id,
            "dimensions": dimensions,
            "horizon": horizon,
            "raw_observations": len(rows),
            "non_overlapping_observations": len(nonoverlap),
            "overlap_fraction_pct": _pct(len(rows) - len(nonoverlap), len(rows)),
            "thesis_return_avg_pct": summary[return_field],
            "directional_hit_rate_pct": summary[hit_field],
            "nonoverlap_thesis_return_avg_pct": non_return,
            "nonoverlap_directional_hit_rate_pct": non_hit,
            "year_persistence": persistence,
            "symbol_breadth": breadth,
            "matched_control": control,
            "evidence_grade": grade,
            "certification_status": status,
            "production_effect": False,
        }

    @staticmethod
    def _candidate_groups(rows):
        groups = defaultdict(list)
        for row in rows:
            if row["direction"] not in DIRECTIONAL:
                continue
            dimensions = [
                ("direction", {"direction": row["direction"]}),
                ("direction_score", {"direction": row["direction"], "score_band": row["score_band"]}),
                ("direction_category", {"direction": row["direction"], "primary_category": row.get("primary_category") or "UNKNOWN"}),
                ("direction_structure", {"direction": row["direction"], "structure": row["structure"]}),
                ("direction_regime", {"direction": row["direction"], "historical_regime": row["historical_regime"]}),
                ("direction_score_regime", {"direction": row["direction"], "score_band": row["score_band"], "historical_regime": row["historical_regime"]}),
                ("direction_category_score", {"direction": row["direction"], "primary_category": row.get("primary_category") or "UNKNOWN", "score_band": row["score_band"]}),
                ("direction_category_structure", {"direction": row["direction"], "primary_category": row.get("primary_category") or "UNKNOWN", "structure": row["structure"]}),
            ]
            for kind, dims in dimensions:
                parts = [f"{key}={dims[key]}" for key in sorted(dims)]
                groups[(_candidate_key(kind, parts), tuple(sorted(dims.items())))].append(row)
        return groups

    def _bearish_attribution(self, rows, all_rows, session_index):
        bearish = [row for row in rows if row["direction"] in BEARISH]
        report = {}
        for horizon in (20, 60):
            summary = _summarize(bearish)
            matched = self._matched_excess(bearish, all_rows, horizon)
            nonoverlap = self.analytics._non_overlapping(bearish, session_index, horizon)
            raw_field = f"raw_underlying_return_{horizon}d_avg_pct"
            thesis_field = f"thesis_aligned_return_{horizon}d_avg_pct"
            raw_return = summary[raw_field]
            thesis_return = summary[thesis_field]
            excess = matched["matched_excess_thesis_return_avg_pct"]
            if (thesis_return or 0) < 0 and (excess or 0) > 0:
                diagnosis = "RELATIVE_UNDERPERFORMANCE_ONLY"
            elif (thesis_return or 0) < 0 and (excess or 0) <= 0:
                diagnosis = "NO_ABSOLUTE_OR_RELATIVE_BEARISH_EDGE"
            else:
                diagnosis = "MIXED_OR_CONDITIONAL"
            report[f"{horizon}d"] = {
                "observations": len(bearish),
                "raw_underlying_return_avg_pct": raw_return,
                "thesis_aligned_return_avg_pct": thesis_return,
                "directional_hit_rate_pct": summary[f"directional_hit_rate_{horizon}d_pct"],
                "non_overlapping_observations": len(nonoverlap),
                "nonoverlap_summary": _summarize(nonoverlap),
                "matched_control": matched,
                "diagnosis": diagnosis,
                "automatic_inversion_allowed": False,
            }
        return report

    def build_report(self, replay_run_ids: Sequence[str]):
        rows = self._rows(replay_run_ids)
        if not rows:
            raise RuntimeError("No M77 replay observations available")
        regime_map = self.regime_service.build_authority(row["as_of"] for row in rows)
        rows = self._enrich(rows, regime_map)
        directional = [row for row in rows if row["direction"] in DIRECTIONAL]
        session_index = self.analytics._session_index()
        candidate_registry = []
        for (candidate_id, dims_tuple), candidate_rows in self._candidate_groups(rows).items():
            if len(candidate_rows) < MIN_RAW_OBS:
                continue
            dims = dict(dims_tuple)
            for horizon in (20, 60):
                candidate_registry.append(
                    self._candidate_record(
                        candidate_id, dims, candidate_rows, directional,
                        session_index, horizon,
                    )
                )
        candidate_registry.sort(
            key=lambda item: (
                {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}.get(item["evidence_grade"], 9),
                -(item.get("nonoverlap_thesis_return_avg_pct") or -999),
                item["candidate_id"], item["horizon"],
            )
        )
        regime_counts = defaultdict(int)
        quality_counts = defaultdict(int)
        for snapshot in regime_map.values():
            regime_counts[snapshot.regime] += 1
            quality_counts[snapshot.evidence_quality] += 1
        return {
            "attribution_version": ATTRIBUTION_VERSION,
            "regime_authority_version": REGIME_AUTHORITY_VERSION,
            "governance": {
                "mode": "READ_ONLY_CONDITIONAL_EDGE_ATTRIBUTION",
                "production_authority_effect": False,
                "production_model_mutation": False,
                "automatic_threshold_change": False,
                "automatic_bearish_inversion": False,
                "automatic_champion_promotion": False,
                "current_universe_survivorship_bias_free_claim": False,
                "pit_sector_membership_claim": False,
                "matched_control_limitations": "same date/regime/score-band only; no liquidity or single-name volatility match",
            },
            "coverage": {
                "observations": len(rows),
                "directional_observations": len(directional),
                "symbols": len({row["symbol"] for row in rows}),
                "replay_dates": len({row["as_of"] for row in rows}),
                "first_as_of": min(row["as_of"] for row in rows),
                "last_as_of": max(row["as_of"] for row in rows),
            },
            "historical_regime_authority": {
                "regime_counts": dict(sorted(regime_counts.items())),
                "evidence_quality_counts": dict(sorted(quality_counts.items())),
                "snapshots": [regime_map[key].as_dict() for key in sorted(regime_map)],
            },
            "bearish_failure_attribution": self._bearish_attribution(
                rows, directional, session_index
            ),
            "candidate_registry": candidate_registry,
            "candidate_summary": {
                "total": len(candidate_registry),
                "grade_A": sum(item["evidence_grade"] == "A" for item in candidate_registry),
                "grade_B": sum(item["evidence_grade"] == "B" for item in candidate_registry),
                "grade_C": sum(item["evidence_grade"] == "C" for item in candidate_registry),
                "grade_D": sum(item["evidence_grade"] == "D" for item in candidate_registry),
                "grade_F": sum(item["evidence_grade"] == "F" for item in candidate_registry),
            },
        }
