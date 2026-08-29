from __future__ import annotations

from collections import defaultdict
from statistics import mean, median

from sqlalchemy import text

ANALYTICS_VERSION = "M77.1.1.1-CHAMPION-ANALYTICS-1.0"
DIRECTIONAL = {"BULLISH", "STRONG_BULLISH", "BEARISH", "STRONG_BEARISH"}
BULLISH = {"BULLISH", "STRONG_BULLISH"}
BEARISH = {"BEARISH", "STRONG_BEARISH"}
HORIZONS = (5, 10, 20, 40, 60)


def _f(value):
    return None if value is None else float(value)


def _avg(values):
    values = [float(value) for value in values if value is not None]
    return None if not values else mean(values)


def _median(values):
    values = [float(value) for value in values if value is not None]
    return None if not values else median(values)


def _pct(numerator, denominator):
    return None if not denominator else numerator / denominator * 100.0


def _bucket(value, edges):
    for low, high in zip(edges, edges[1:]):
        if low <= value < high:
            return f"[{low:g},{high:g})"
    return f"[{edges[-1]:g},+]"


def _stored_return_is_thesis_aligned(direction: str) -> bool:
    return str(direction or "").upper() in DIRECTIONAL


def _raw_return_from_stored(direction: str, stored_return):
    """Reconstruct raw underlying return from M77.1 stored return semantics.

    M77.1 persists raw*sign for directional predictions. Therefore bearish
    stored returns are already thesis-aligned and must be inverted exactly
    once to recover raw underlying return. Neutral rows are stored raw.
    """
    if stored_return is None:
        return None
    value = float(stored_return)
    direction = str(direction or "").upper()
    if direction in BEARISH:
        return -value
    return value


def _thesis_return_from_stored(direction: str, stored_return):
    """Return the governed thesis-aligned return represented by M77.1 storage."""
    if stored_return is None:
        return None
    direction = str(direction or "").upper()
    if direction in DIRECTIONAL:
        return float(stored_return)
    return None


def _raw_excursions_from_stored(direction: str, stored_mfe, stored_mae):
    """Reconstruct raw-price excursions while preserving M77.1 thesis metrics.

    For bearish predictions M77.1 stores favorable downside as positive MFE and
    adverse upside as negative MAE. Raw-price MFE is therefore -stored MAE and
    raw-price MAE is -stored MFE. Bullish values are already raw-price aligned.
    """
    mfe = _f(stored_mfe)
    mae = _f(stored_mae)
    direction = str(direction or "").upper()
    if mfe is None or mae is None:
        return None, None
    if direction in BEARISH:
        return -mae, -mfe
    return mfe, mae


def _summarize(rows):
    directional = [row for row in rows if row["direction"] in DIRECTIONAL]
    neutral = [row for row in rows if row["direction"] == "NEUTRAL"]
    entry_count = sum(bool(row["entry_triggered"]) for row in rows)
    ambiguous_count = sum(bool(row["ambiguous_same_bar"]) for row in rows)
    out = {
        "observations": len(rows),
        "directional_observations": len(directional),
        "neutral_observations": len(neutral),
        "entry_triggered": entry_count,
        "entry_trigger_rate_pct": _pct(entry_count, len(rows)),
        "ambiguous_same_bar": ambiguous_count,
        "ambiguous_rate_pct": _pct(ambiguous_count, len(rows)),
    }

    for horizon in HORIZONS:
        field = f"r{horizon}"
        thesis_values = [
            _thesis_return_from_stored(row["direction"], row[field])
            for row in directional
        ]
        raw_values = [
            _raw_return_from_stored(row["direction"], row[field])
            for row in directional
        ]
        thesis_realized = [value for value in thesis_values if value is not None]
        out[f"raw_underlying_return_{horizon}d_avg_pct"] = _avg(raw_values)
        out[f"raw_underlying_return_{horizon}d_median_pct"] = _median(raw_values)
        out[f"thesis_aligned_return_{horizon}d_avg_pct"] = _avg(thesis_values)
        out[f"thesis_aligned_return_{horizon}d_median_pct"] = _median(thesis_values)
        out[f"directional_hit_rate_{horizon}d_pct"] = _pct(
            sum(value > 0 for value in thesis_realized), len(thesis_realized)
        )

    thesis_mfe = []
    thesis_mae = []
    raw_mfe = []
    raw_mae = []
    for row in directional:
        thesis_mfe.append(_f(row["mfe_pct"]))
        thesis_mae.append(_f(row["mae_pct"]))
        rmfe, rmae = _raw_excursions_from_stored(
            row["direction"], row["mfe_pct"], row["mae_pct"]
        )
        raw_mfe.append(rmfe)
        raw_mae.append(rmae)
    out["raw_price_mfe_avg_pct"] = _avg(raw_mfe)
    out["raw_price_mae_avg_pct"] = _avg(raw_mae)
    out["thesis_mfe_avg_pct"] = _avg(thesis_mfe)
    out["thesis_mae_avg_pct"] = _avg(thesis_mae)

    for horizon in (20, 60):
        values = [
            abs(float(row[f"r{horizon}"]))
            for row in neutral
            if row[f"r{horizon}"] is not None
        ]
        for band in (3.0, 5.0, 8.0):
            out[f"neutral_{horizon}d_within_{band:g}pct_rate"] = _pct(
                sum(value <= band for value in values), len(values)
            )
    return out


class HistoricalChampionAnalyticsService:
    """Read-only analytics over M77.1 replay artifacts.

    This service never writes production authority, replay predictions, or replay
    outcomes. M77.1.1.1 explicitly reports both raw-underlying and thesis-aligned
    semantics so stored directional returns can never be accidentally inverted
    twice in research interpretation.
    """

    def __init__(self, session):
        self.session = session

    def _run(self, replay_run_id):
        if replay_run_id:
            row = self.session.execute(
                text(
                    "SELECT * FROM historical_underlying_replay_run "
                    "WHERE replay_run_id=:r"
                ),
                {"r": replay_run_id},
            ).mappings().one_or_none()
        else:
            row = self.session.execute(
                text(
                    "SELECT * FROM historical_underlying_replay_run "
                    "ORDER BY started_at DESC LIMIT 1"
                )
            ).mappings().one_or_none()
        if not row:
            raise RuntimeError("No M77.1 historical underlying replay run found")
        if str(row["status"]) not in {"READY", "DEGRADED"}:
            raise RuntimeError(f"Replay run is not reportable: {row['status']}")
        return dict(row)

    def _rows(self, replay_run_id):
        sql = text(
            """
            SELECT
                p.prediction_id,
                p.symbol,
                p.as_of,
                p.direction,
                p.primary_category,
                p.overall_score,
                p.confidence,
                p.profile_json,
                o.status,
                o.entry_triggered,
                o.ambiguous_same_bar,
                o.mfe_pct,
                o.mae_pct,
                o.return_5d_pct AS r5,
                o.return_10d_pct AS r10,
                o.return_20d_pct AS r20,
                o.return_40d_pct AS r40,
                o.return_60d_pct AS r60,
                o.outcome_json
            FROM historical_underlying_replay_prediction p
            JOIN historical_underlying_replay_outcome o USING(prediction_id)
            WHERE p.replay_run_id=:r
            ORDER BY p.as_of, p.symbol
            """
        )
        return [
            dict(row)
            for row in self.session.execute(sql, {"r": replay_run_id}).mappings()
        ]

    def _session_index(self):
        return {
            session_date: index
            for index, session_date in enumerate(
                self.session.scalars(
                    text("SELECT date FROM price_history WHERE symbol='SPY' ORDER BY date")
                )
            )
        }

    @staticmethod
    def _target_stats(rows):
        stats = {}
        for target in (1, 2, 3):
            values = []
            for row in rows:
                value = (
                    ((row.get("outcome_json") or {}).get("target_before_stop") or {})
                    .get(str(target))
                )
                if value is not None:
                    values.append(value)
            unambiguous = [value for value in values if value != "AMBIGUOUS_SAME_BAR"]
            stats[f"target_{target}_observed"] = len(values)
            stats[f"target_{target}_ambiguous"] = sum(
                value == "AMBIGUOUS_SAME_BAR" for value in values
            )
            stats[f"target_{target}_before_stop_rate_pct"] = _pct(
                sum(value is True for value in unambiguous), len(unambiguous)
            )
        return stats

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
    def _non_overlapping(rows, session_index, horizon):
        by_symbol = defaultdict(list)
        for row in rows:
            if row["as_of"] in session_index:
                by_symbol[row["symbol"]].append(row)
        chosen = []
        for symbol in sorted(by_symbol):
            last = -(10**9)
            for row in sorted(by_symbol[symbol], key=lambda item: item["as_of"]):
                index = session_index[row["as_of"]]
                if index - last >= horizon:
                    chosen.append(row)
                    last = index
        return chosen

    @staticmethod
    def _cluster_summary(rows, cluster_key, horizon):
        groups = defaultdict(list)
        field = f"r{horizon}"
        for row in rows:
            value = _thesis_return_from_stored(row["direction"], row[field])
            if row["direction"] in DIRECTIONAL and value is not None:
                groups[row[cluster_key]].append(value)
        means = [mean(values) for values in groups.values() if values]
        return {
            "clusters": len(means),
            "mean_of_cluster_means_pct": None if not means else mean(means),
            "median_cluster_mean_pct": None if not means else median(means),
            "positive_cluster_rate_pct": None
            if not means
            else _pct(sum(value > 0 for value in means), len(means)),
        }

    def build_report(self, replay_run_id=None):
        run = self._run(replay_run_id)
        rows = self._rows(run["replay_run_id"])
        if not rows:
            raise RuntimeError("Replay run has no prediction/outcome rows")

        session_index = self._session_index()
        directional = [row for row in rows if row["direction"] in DIRECTIONAL]
        edges = (0, 40, 50, 60, 70, 80, 90, 101)
        structure = defaultdict(list)
        alignment = defaultdict(list)
        timeframe = defaultdict(list)
        regimes = defaultdict(int)

        for row in rows:
            profile = row.get("profile_json") or {}
            structure[str(profile.get("structure") or "UNKNOWN")].append(row)
            alignment[
                _bucket(
                    float(profile.get("alignment_score") or 0),
                    (0, 25, 50, 65, 80, 101),
                )
            ].append(row)
            states = profile.get("timeframe_states") or {}
            signature = "/".join(
                str((states.get(timeframe_name) or {}).get("direction") or "NA")
                for timeframe_name in ("1d", "1w", "1mo")
            )
            timeframe[signature].append(row)
            regimes[
                str((profile.get("context") or {}).get("market_regime") or "UNKNOWN")
            ] += 1

        overlap = {}
        for horizon in (20, 60):
            cohort = self._non_overlapping(directional, session_index, horizon)
            overlap[f"{horizon}d"] = {
                "all_directional_observations": len(directional),
                "non_overlapping_observations": len(cohort),
                "overlap_fraction_pct": None
                if not directional
                else (1 - len(cohort) / len(directional)) * 100,
                "non_overlapping_summary": _summarize(cohort),
            }

        return {
            "analytics_version": ANALYTICS_VERSION,
            "governance": {
                "mode": "READ_ONLY_POST_REPLAY_ANALYTICS",
                "production_authority_effect": False,
                "prediction_mutation": False,
                "outcome_mutation": False,
                "important_semantics": {
                    "stored_return_columns": (
                        "M77.1 persists thesis-aligned returns for directional "
                        "BULLISH/BEARISH rows (raw underlying return multiplied by "
                        "direction sign); NEUTRAL retains raw underlying return."
                    ),
                    "raw_return_columns": (
                        "M77.1.1.1 reconstructs raw underlying returns for reporting "
                        "only. Bearish stored values are inverted exactly once; the "
                        "stored replay artifact is not mutated."
                    ),
                    "mfe_mae": (
                        "M77.1 persists thesis-aligned favorable/adverse excursion. "
                        "M77.1.1.1 additionally reconstructs raw-price excursions for "
                        "transparent interpretation."
                    ),
                    "confidence": (
                        "Stock Intelligence confidence is analyzed as a score, NOT "
                        "treated as a calibrated probability; no Brier/ECE claim is made."
                    ),
                    "sector": (
                        "Historical PIT sector membership unavailable; no sector-"
                        "certification claim."
                    ),
                    "universe": (
                        "CURRENT_UNIVERSE_HISTORICAL_REPLAY; survivorship-bias-free "
                        "claim prohibited."
                    ),
                },
            },
            "run": run,
            "overall": {**_summarize(rows), **self._target_stats(rows)},
            "by_direction": self._group(rows, lambda row: row["direction"]),
            "by_primary_category": self._group(
                rows, lambda row: row.get("primary_category") or "UNKNOWN"
            ),
            "by_confidence_bucket": self._group(
                rows, lambda row: _bucket(float(row["confidence"]), edges)
            ),
            "by_overall_score_bucket": self._group(
                rows, lambda row: _bucket(float(row["overall_score"]), edges)
            ),
            "by_structure": [
                {"group": key, **_summarize(values)}
                for key, values in sorted(structure.items())
            ],
            "by_alignment_bucket": [
                {"group": key, **_summarize(values)}
                for key, values in sorted(alignment.items())
            ],
            "by_timeframe_direction_signature": [
                {"group": key, **_summarize(values)}
                for key, values in sorted(timeframe.items())
            ],
            "context_availability": {
                "market_regime_counts": dict(sorted(regimes.items()))
            },
            "overlap_governance": overlap,
            "cluster_robustness": {
                "symbol_clustered_20d": self._cluster_summary(
                    directional, "symbol", 20
                ),
                "date_clustered_20d": self._cluster_summary(
                    directional, "as_of", 20
                ),
                "symbol_clustered_60d": self._cluster_summary(
                    directional, "symbol", 60
                ),
                "date_clustered_60d": self._cluster_summary(
                    directional, "as_of", 60
                ),
            },
        }
