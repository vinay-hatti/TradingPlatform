from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import mean, median
from typing import Iterable, Sequence

from trading_ai.historical_underlying_replay.analytics import (
    BEARISH,
    BULLISH,
    DIRECTIONAL,
    HistoricalChampionAnalyticsService,
    _summarize,
    _thesis_return_from_stored,
)
from trading_ai.historical_underlying_replay.attribution import (
    ConditionalEdgeAttributionService,
)
from trading_ai.historical_underlying_replay.regime import (
    HistoricalRegimeAuthorityService,
    REGIME_AUTHORITY_VERSION,
)

CHALLENGER_VERSION = "M77.4-GOVERNED-CHALLENGER-WALK-FORWARD-1.0"
MODE = "READ_ONLY_EXPANDING_WINDOW_PURGED_WALK_FORWARD"
HORIZONS = (20, 60)
MIN_TRAIN_NONOVERLAP = {20: 60, 60: 30}
MIN_VALIDATION_NONOVERLAP = {20: 30, 60: 20}
MIN_TRAIN_SYMBOLS = 30
MIN_TRAIN_POSITIVE_SYMBOL_RATE = 52.0
MIN_TRAIN_HIT_RATE = 52.0
MIN_VALIDATION_HIT_RATE = 50.0
MIN_TRAIN_YEARS_STRICT = 2


def _avg(values):
    values = [float(v) for v in values if v is not None]
    return None if not values else mean(values)


def _median(values):
    values = [float(v) for v in values if v is not None]
    return None if not values else median(values)


def _pct(n, d):
    return None if not d else n / d * 100.0


def _candidate_horizon_id(candidate_id: str, horizon: int) -> str:
    return f"{candidate_id}@@{horizon}d"


def _year_status(year: int, last_as_of: date) -> str:
    if year < last_as_of.year:
        return "FULL_YEAR"
    if year == last_as_of.year:
        return "PARTIAL_YEAR"
    return "FUTURE"


class GovernedChallengerWalkForwardService:
    """
    Research-only expanding-window walk-forward validation.

    Governance:
      * reads existing M77 replay artifacts and price_history only
      * writes no database rows
      * does not mutate Stock Intelligence
      * does not change production thresholds
      * does not invert bearish signals
      * does not promote a challenger to champion
      * purges training observations whose outcome horizon reaches the holdout
    """

    def __init__(self, session):
        self.session = session
        self.analytics = HistoricalChampionAnalyticsService(session)
        self.regime_service = HistoricalRegimeAuthorityService(session)

    def _rows(self, replay_run_ids: Sequence[str]):
        rows = []
        for rid in replay_run_ids:
            rows.extend(self.analytics._rows(rid))
        if not rows:
            raise RuntimeError("No M77 replay observations available")
        rows.sort(key=lambda r: (r["as_of"], r["symbol"], r["prediction_id"]))
        regime_map = self.regime_service.build_authority(r["as_of"] for r in rows)
        return ConditionalEdgeAttributionService._enrich(rows, regime_map), regime_map

    @staticmethod
    def _group_map(rows):
        grouped = {}
        for (candidate_id, dims_tuple), cohort in ConditionalEdgeAttributionService._candidate_groups(rows).items():
            grouped[candidate_id] = {
                "dimensions": dict(dims_tuple),
                "rows": cohort,
            }
        return grouped

    @staticmethod
    def _purged_training(rows, validation_rows, session_index, horizon):
        if not validation_rows:
            return []
        first_validation_index = min(session_index[r["as_of"]] for r in validation_rows if r["as_of"] in session_index)
        out = []
        for row in rows:
            idx = session_index.get(row["as_of"])
            if idx is None:
                continue
            # Critical anti-leakage embargo: a training label is not allowed to consume
            # any session in the validation period.
            if idx + horizon < first_validation_index:
                out.append(row)
        return out

    @staticmethod
    def _yearly(rows, horizon):
        field = f"r{horizon}"
        by_year = defaultdict(list)
        for row in rows:
            value = _thesis_return_from_stored(row["direction"], row[field])
            if value is not None:
                by_year[row["as_of"].year].append(value)
        result = []
        for year, values in sorted(by_year.items()):
            result.append({
                "year": year,
                "observations": len(values),
                "thesis_return_avg_pct": mean(values),
                "hit_rate_pct": _pct(sum(v > 0 for v in values), len(values)),
            })
        return result

    @staticmethod
    def _symbol_breadth(rows, horizon):
        field = f"r{horizon}"
        grouped = defaultdict(list)
        for row in rows:
            value = _thesis_return_from_stored(row["direction"], row[field])
            if value is not None:
                grouped[row["symbol"]].append(value)
        means = [mean(values) for values in grouped.values() if values]
        return {
            "symbols": len(means),
            "positive_symbol_rate_pct": _pct(sum(v > 0 for v in means), len(means)),
            "median_symbol_return_pct": _median(means),
        }

    @staticmethod
    def _matched_excess(candidate_rows, all_rows, horizon):
        return ConditionalEdgeAttributionService._matched_excess(
            candidate_rows, all_rows, horizon
        )

    def _training_metrics(self, cohort, all_train, session_index, horizon):
        non = self.analytics._non_overlapping(cohort, session_index, horizon)
        summary = _summarize(non)
        years = self._yearly(non, horizon)
        breadth = self._symbol_breadth(non, horizon)
        control = self._matched_excess(cohort, all_train, horizon)
        ret = summary[f"thesis_aligned_return_{horizon}d_avg_pct"]
        hit = summary[f"directional_hit_rate_{horizon}d_pct"]
        positive_years = sum(y["thesis_return_avg_pct"] > 0 for y in years)
        worst_year = None if not years else min(y["thesis_return_avg_pct"] for y in years)
        return {
            "raw_observations": len(cohort),
            "non_overlapping_observations": len(non),
            "thesis_return_avg_pct": ret,
            "directional_hit_rate_pct": hit,
            "years": years,
            "positive_years": positive_years,
            "qualified_years": len(years),
            "positive_year_rate_pct": _pct(positive_years, len(years)),
            "worst_year_thesis_return_pct": worst_year,
            "symbol_breadth": breadth,
            "matched_control": control,
        }

    def _training_eligible(self, metrics, validation_year):
        # 2024 is retained as an EARLY diagnostic fold because only 2022(partial)+2023
        # precede it. Strict challenger eligibility starts when >=2 prior calendar
        # years survive purge and are represented.
        strict_years = [y for y in metrics["years"] if y["observations"] >= 20]
        strict = len(strict_years) >= MIN_TRAIN_YEARS_STRICT
        ret = metrics["thesis_return_avg_pct"] or 0.0
        hit = metrics["directional_hit_rate_pct"] or 0.0
        breadth = metrics["symbol_breadth"]
        excess = metrics["matched_control"]["matched_excess_thesis_return_avg_pct"] or 0.0
        all_positive = bool(strict_years) and all(y["thesis_return_avg_pct"] > 0 for y in strict_years)
        enough = (
            metrics["non_overlapping_observations"] >= MIN_TRAIN_NONOVERLAP[
                20 if metrics.get("horizon") == 20 else 60
            ]
            if "horizon" in metrics else True
        )
        eligible = (
            strict
            and enough
            and ret > 0
            and hit >= MIN_TRAIN_HIT_RATE
            and breadth["symbols"] >= MIN_TRAIN_SYMBOLS
            and (breadth["positive_symbol_rate_pct"] or 0) >= MIN_TRAIN_POSITIVE_SYMBOL_RATE
            and excess > 0
            and all_positive
        )
        return eligible, ("STRICT" if strict else "EARLY_DIAGNOSTIC_ONLY")

    def _validation_metrics(self, cohort, all_validation, session_index, horizon):
        non = self.analytics._non_overlapping(cohort, session_index, horizon)
        summary = _summarize(non)
        control = self._matched_excess(cohort, all_validation, horizon)
        ret = summary[f"thesis_aligned_return_{horizon}d_avg_pct"]
        hit = summary[f"directional_hit_rate_{horizon}d_pct"]
        excess = control["matched_excess_thesis_return_avg_pct"]
        enough = len(non) >= MIN_VALIDATION_NONOVERLAP[horizon]
        passed = bool(
            enough
            and (ret or 0) > 0
            and (hit or 0) >= MIN_VALIDATION_HIT_RATE
            and (excess or 0) > 0
        )
        return {
            "raw_observations": len(cohort),
            "non_overlapping_observations": len(non),
            "thesis_return_avg_pct": ret,
            "directional_hit_rate_pct": hit,
            "matched_control": control,
            "passed": passed,
            "failure_reasons": [
                reason for reason, condition in (
                    ("INSUFFICIENT_NON_OVERLAPPING_OBSERVATIONS", not enough),
                    ("NON_POSITIVE_RETURN", (ret or 0) <= 0),
                    ("HIT_RATE_BELOW_50", (hit or 0) < MIN_VALIDATION_HIT_RATE),
                    ("NON_POSITIVE_MATCHED_EXCESS", (excess or 0) <= 0),
                ) if condition
            ],
        }

    def build_report(self, replay_run_ids: Sequence[str]):
        rows, regime_map = self._rows(replay_run_ids)
        directional = [r for r in rows if r["direction"] in DIRECTIONAL]
        session_index = self.analytics._session_index()
        years = sorted({r["as_of"].year for r in directional})
        last_as_of = max(r["as_of"] for r in directional)
        folds = []

        for validation_year in years:
            historical = [r for r in directional if r["as_of"].year < validation_year]
            validation = [r for r in directional if r["as_of"].year == validation_year]
            if not historical or not validation:
                continue
            # Require at least one entire prior year before emitting even a diagnostic fold.
            if validation_year <= min(years):
                continue

            train_groups_all = self._group_map(historical)
            validation_groups = self._group_map(validation)
            fold_candidates = []

            for candidate_id, candidate in sorted(train_groups_all.items()):
                dims = candidate["dimensions"]
                if dims.get("direction") not in BULLISH:
                    # Bearish is not inverted. M77.3 diagnosed no absolute or relative edge.
                    continue
                for horizon in HORIZONS:
                    purged_all_train = self._purged_training(
                        historical, validation, session_index, horizon
                    )
                    purged_groups = self._group_map(purged_all_train)
                    purged_candidate = purged_groups.get(candidate_id)
                    if not purged_candidate:
                        continue
                    train_rows = purged_candidate["rows"]
                    train_metrics = self._training_metrics(
                        train_rows, purged_all_train, session_index, horizon
                    )
                    train_metrics["horizon"] = horizon
                    selected, selection_mode = self._training_eligible(
                        train_metrics, validation_year
                    )

                    val_rows = (validation_groups.get(candidate_id) or {}).get("rows", [])
                    validation_metrics = self._validation_metrics(
                        val_rows, validation, session_index, horizon
                    ) if val_rows else {
                        "raw_observations": 0,
                        "non_overlapping_observations": 0,
                        "thesis_return_avg_pct": None,
                        "directional_hit_rate_pct": None,
                        "matched_control": {
                            "matched_observations": 0,
                            "matched_control_thesis_return_avg_pct": None,
                            "matched_excess_thesis_return_avg_pct": None,
                        },
                        "passed": False,
                        "failure_reasons": ["NO_VALIDATION_OBSERVATIONS"],
                    }

                    fold_candidates.append({
                        "candidate_horizon_id": _candidate_horizon_id(candidate_id, horizon),
                        "candidate_id": candidate_id,
                        "dimensions": dims,
                        "horizon": horizon,
                        "selection_mode": selection_mode,
                        "selected_pre_holdout": selected,
                        "training": train_metrics,
                        "validation": validation_metrics,
                    })

            selected = [x for x in fold_candidates if x["selected_pre_holdout"]]
            folds.append({
                "validation_year": validation_year,
                "validation_period_status": _year_status(validation_year, last_as_of),
                "training_years": sorted({r["as_of"].year for r in historical}),
                "anti_leakage_contract": (
                    "Expanding window with horizon purge: training observations are excluded "
                    "when as_of session index + outcome horizon reaches the first validation session."
                ),
                "candidate_count": len(fold_candidates),
                "selected_pre_holdout_count": len(selected),
                "selected_pass_count": sum(x["validation"]["passed"] for x in selected),
                "selected_fail_count": sum(not x["validation"]["passed"] for x in selected),
                "candidates": fold_candidates,
            })

        # Strict certification: candidate must have been selected BEFORE the holdout,
        # pass at least one FULL_YEAR holdout, and pass every later fold in which it
        # was selected. Partial-year evidence can support but cannot independently certify.
        history = defaultdict(list)
        for fold in folds:
            for item in fold["candidates"]:
                if item["selected_pre_holdout"]:
                    history[item["candidate_horizon_id"]].append({
                        "validation_year": fold["validation_year"],
                        "period_status": fold["validation_period_status"],
                        "passed": item["validation"]["passed"],
                        "validation": item["validation"],
                        "dimensions": item["dimensions"],
                        "horizon": item["horizon"],
                        "candidate_id": item["candidate_id"],
                    })

        certification = []
        for key, records in sorted(history.items()):
            full = [r for r in records if r["period_status"] == "FULL_YEAR"]
            later = records
            certified = bool(full and all(r["passed"] for r in later))
            status = "WALK_FORWARD_SUPPORTED" if certified else "NOT_CERTIFIED"
            if not full and all(r["passed"] for r in later):
                status = "PROVISIONAL_ONLY_NO_FULL_YEAR_HOLDOUT"
            certification.append({
                "candidate_horizon_id": key,
                "candidate_id": records[0]["candidate_id"],
                "dimensions": records[0]["dimensions"],
                "horizon": records[0]["horizon"],
                "selected_holdout_folds": len(records),
                "full_year_holdout_folds": len(full),
                "passed_holdout_folds": sum(r["passed"] for r in records),
                "all_selected_holdouts_passed": all(r["passed"] for r in records),
                "certification_status": status,
                "research_challenger_eligible": certified,
                "folds": records,
            })

        certification.sort(key=lambda x: (
            0 if x["research_challenger_eligible"] else 1,
            -x["passed_holdout_folds"],
            x["candidate_horizon_id"],
        ))
        eligible = [x for x in certification if x["research_challenger_eligible"]]

        return {
            "challenger_version": CHALLENGER_VERSION,
            "regime_authority_version": REGIME_AUTHORITY_VERSION,
            "governance": {
                "mode": MODE,
                "read_only": True,
                "production_authority_effect": False,
                "production_model_mutation": False,
                "production_threshold_change": False,
                "production_weight_change": False,
                "automatic_bearish_inversion": False,
                "automatic_champion_promotion": False,
                "database_writes": False,
                "survivorship_bias_free_claim": False,
                "pit_sector_membership_claim": False,
                "research_only": True,
            },
            "methodology": {
                "candidate_dimensions": (
                    "Same deterministic candidate family used by M77.3; M77.3 full-sample "
                    "evidence grades are NOT used to select candidates for a holdout."
                ),
                "walk_forward": "EXPANDING_WINDOW",
                "label_purge": "HORIZON_PURGED_BEFORE_HOLDOUT",
                "horizons": list(HORIZONS),
                "strict_training_year_requirement": MIN_TRAIN_YEARS_STRICT,
                "production_promotion_allowed": False,
            },
            "coverage": {
                "observations": len(rows),
                "directional_observations": len(directional),
                "symbols": len({r["symbol"] for r in rows}),
                "years": years,
                "first_as_of": min(r["as_of"] for r in rows),
                "last_as_of": last_as_of,
                "regime_dates": len(regime_map),
            },
            "folds": folds,
            "certification": certification,
            "summary": {
                "folds": len(folds),
                "candidate_horizon_histories": len(certification),
                "research_challenger_eligible": len(eligible),
                "eligible_20d": sum(x["horizon"] == 20 for x in eligible),
                "eligible_60d": sum(x["horizon"] == 60 for x in eligible),
                "production_champion_change": False,
            },
            "challenger_policy": {
                "version": CHALLENGER_VERSION,
                "mode": "RESEARCH_SHADOW_ONLY",
                "bearish_policy": "ABSTAIN_FROM_BEARISH_CHALLENGER_SUPPORT_DO_NOT_INVERT",
                "bullish_policy": (
                    "A bullish baseline prediction may receive RESEARCH_WALK_FORWARD_SUPPORTED "
                    "only when it matches at least one research_challenger_eligible cohort."
                ),
                "score_mutation": "NONE",
                "threshold_mutation": "NONE",
                "decision_mutation": "NONE",
                "eligible_candidate_horizon_ids": [
                    x["candidate_horizon_id"] for x in eligible
                ],
            },
        }
