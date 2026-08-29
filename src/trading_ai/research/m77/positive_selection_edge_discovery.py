from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

VERSION = "M77.24.0-POSITIVE-SELECTION-EDGE-DISCOVERY-1.0"
DEVELOPMENT_END = pd.Timestamp("2017-12-31")
CONSUMED_HISTORY_START = pd.Timestamp("2018-01-01")
PROSPECTIVE_NOT_BEFORE = pd.Timestamp("2026-08-27")
HORIZONS = (15, 20, 30, 45, 60)
TAIL_FRACTIONS = (0.05, 0.10, 0.20)
PRIMARY_POPULATION = "pop_certified_trade_builder_ready"

NUMERIC_FEATURES = (
    "probability_up",
    "overall_score",
    "score_overall",
    "score_bullish",
    "score_bearish",
    "score_confidence",
    "score_options_suitability",
    "idi_readiness",
    "idi_trade_quality",
    "idi_capital_priority",
    "profile_confidence",
    "score_overall_rank_pct",
)

SELECTORS = (
    "PROBABILITY_UP",
    "OVERALL_SCORE",
    "IDI_TRADE_QUALITY",
    "OPTIONS_SUITABILITY",
    "RANK_ENSEMBLE",
    "META_HGB",
)


class PositiveSelectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class PositiveSelectionConfig:
    project_root: str
    prediction_path: str = "research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"
    integrity_path: str = "research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz"
    pit_candidate_path: str = "research_data/m77_22_3/point_in_time_long_candidate_veto/checkpoints/pit_long_candidate_authority.csv.gz"
    output_dir: str = "research_data/m77_24/positive_selection_edge_discovery"
    primary_population: str = PRIMARY_POPULATION
    random_state: int = 7724


def _resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_default(v: Any) -> Any:
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if isinstance(v, Path):
        return str(v)
    raise TypeError(type(v).__name__)


def _safe_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _markdown_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    x = df.head(max_rows).copy()
    cols = [str(c) for c in x.columns]
    def fmt(v: Any) -> str:
        if pd.isna(v):
            return ""
        if isinstance(v, (float, np.floating)):
            return f"{float(v):.6g}"
        return str(v).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    for _, r in x.iterrows():
        lines.append("| " + " | ".join(fmt(r[c]) for c in x.columns) + " |")
    return "\n".join(lines)


def load_development_authority(cfg: PositiveSelectionConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = Path(cfg.project_root)
    pp = _resolve(root, cfg.prediction_path)
    ip = _resolve(root, cfg.integrity_path)
    cp = _resolve(root, cfg.pit_candidate_path)
    for p in (pp, ip, cp):
        if not p.exists():
            raise PositiveSelectionError(f"Required authority missing: {p}")

    pred = pd.read_csv(pp)
    integrity = pd.read_csv(ip)
    pit = pd.read_csv(cp)

    pred["as_of"] = pd.to_datetime(pred["as_of"], errors="coerce")
    integrity["as_of"] = pd.to_datetime(integrity["as_of"], errors="coerce")
    pit["as_of"] = pd.to_datetime(pit["as_of"], errors="coerce")

    # Historical governance: positive-selection model selection is Development-only.
    if (pred["as_of"] > DEVELOPMENT_END).any():
        raise PositiveSelectionError("Prediction authority contains post-2017 rows; M77.24 refuses consumed history")
    if (integrity["as_of"] > DEVELOPMENT_END).any():
        raise PositiveSelectionError("Integrity authority contains post-2017 rows; M77.24 refuses consumed history")
    pit = pit[pit["as_of"] <= DEVELOPMENT_END].copy()

    required_pred = {"symbol", "as_of", "horizon", "probability_up"}
    if not required_pred.issubset(pred.columns):
        raise PositiveSelectionError(f"Prediction authority missing: {sorted(required_pred-set(pred.columns))}")
    if cfg.primary_population not in pit.columns:
        raise PositiveSelectionError(f"PIT authority missing population: {cfg.primary_population}")

    integ_cols = ["symbol", "as_of", "horizon", "raw_authority_present",
                  "interval_integrity_clean", "source_return_matches_raw"]
    missing_i = set(integ_cols) - set(integrity.columns)
    if missing_i:
        raise PositiveSelectionError(f"Integrity authority missing: {sorted(missing_i)}")

    pred = pred.merge(integrity[integ_cols], on=["symbol", "as_of", "horizon"], how="left", validate="one_to_one")
    for c in ("raw_authority_present", "interval_integrity_clean", "source_return_matches_raw"):
        pred[c] = pred[c].fillna(False).astype(bool)
    pred["integrity_clean_strict"] = (
        pred["raw_authority_present"] & pred["interval_integrity_clean"] & pred["source_return_matches_raw"]
    )

    pit_cols = ["symbol", "as_of", cfg.primary_population] + [c for c in NUMERIC_FEATURES if c != "probability_up" and c in pit.columns]
    pit_small = pit[pit_cols].drop_duplicates(["symbol", "as_of"], keep="last")
    panel = pred.merge(pit_small, on=["symbol", "as_of"], how="inner", validate="many_to_one")
    panel = panel[(panel[cfg.primary_population].fillna(False).astype(bool)) & panel["integrity_clean_strict"]].copy()

    # Frozen DRVE semantics: rank on the complete contemporaneous prediction cross-section,
    # then remove the bottom 1% from the long-candidate population.
    all_ranks = pred.copy()
    all_ranks["bearish_rank_pct"] = all_ranks.groupby(["as_of", "horizon"])["probability_up"].rank(method="first", pct=True, ascending=True)
    panel = panel.merge(all_ranks[["symbol", "as_of", "horizon", "bearish_rank_pct"]],
                        on=["symbol", "as_of", "horizon"], how="left", validate="one_to_one")
    panel["drv_veto"] = panel["bearish_rank_pct"] <= 0.01
    panel = panel[~panel["drv_veto"]].copy()

    panel["calendar_year"] = panel["as_of"].dt.year
    panel["era"] = np.select(
        [panel["calendar_year"] <= 2010, panel["calendar_year"] <= 2013],
        ["DISCOVERY_SEED", "CONFIRMATION"],
        default="INTERNAL_HOLDOUT",
    )

    for c in NUMERIC_FEATURES:
        if c in panel.columns:
            panel[c] = _safe_num(panel[c])

    meta = {
        "prediction_sha256": _sha256(pp),
        "integrity_sha256": _sha256(ip),
        "pit_candidate_sha256": _sha256(cp),
        "rows": int(len(panel)),
        "symbols": int(panel["symbol"].nunique()),
        "first_as_of": None if panel.empty else panel["as_of"].min().date().isoformat(),
        "last_as_of": None if panel.empty else panel["as_of"].max().date().isoformat(),
        "consumed_2018_2026_rows_read": 0,
    }
    return panel, meta


def _rank_ensemble(frame: pd.DataFrame) -> pd.Series:
    candidates = [c for c in ("probability_up", "score_overall", "overall_score", "idi_trade_quality", "score_options_suitability")
                  if c in frame.columns]
    ranks = []
    for c in candidates:
        ranks.append(frame.groupby("as_of")[c].rank(method="average", pct=True, ascending=True))
    if not ranks:
        return pd.Series(np.nan, index=frame.index)
    return pd.concat(ranks, axis=1).mean(axis=1)


def _selector_score(frame: pd.DataFrame, selector: str) -> pd.Series:
    if selector == "PROBABILITY_UP":
        return _safe_num(frame["probability_up"])
    if selector == "OVERALL_SCORE":
        c = "score_overall" if "score_overall" in frame.columns else "overall_score"
        return _safe_num(frame[c])
    if selector == "IDI_TRADE_QUALITY":
        return _safe_num(frame["idi_trade_quality"])
    if selector == "OPTIONS_SUITABILITY":
        return _safe_num(frame["score_options_suitability"])
    if selector == "RANK_ENSEMBLE":
        return _rank_ensemble(frame)
    raise PositiveSelectionError(f"Unsupported direct selector: {selector}")


def _meta_features(frame: pd.DataFrame) -> list[str]:
    return [c for c in NUMERIC_FEATURES if c in frame.columns]


def walk_forward_meta_scores(panel_h: pd.DataFrame, horizon: int, random_state: int) -> pd.Series:
    ret_col = f"fwd_ret_{horizon}"
    if ret_col not in panel_h.columns:
        return pd.Series(np.nan, index=panel_h.index, dtype=float)
    feats = _meta_features(panel_h)
    if not feats:
        return pd.Series(np.nan, index=panel_h.index, dtype=float)

    scores = pd.Series(np.nan, index=panel_h.index, dtype=float)
    years = sorted(int(y) for y in panel_h["calendar_year"].dropna().unique())
    for year in years:
        # Reserve 2008-2010 as seed; every scored year is strictly forward of training.
        if year < 2011:
            continue
        tr = panel_h[panel_h["calendar_year"] < year].copy()
        te = panel_h[panel_h["calendar_year"] == year].copy()
        y = (_safe_num(tr[ret_col]) > 0).astype(int)
        valid = _safe_num(tr[ret_col]).notna()
        tr = tr.loc[valid]
        y = y.loc[valid]
        if len(tr) < 300 or y.nunique() < 2 or len(te) == 0:
            continue
        model = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingClassifier(
                learning_rate=0.04,
                max_iter=140,
                max_leaf_nodes=15,
                min_samples_leaf=35,
                l2_regularization=1.0,
                random_state=random_state + year + horizon,
            )),
        ])
        model.fit(tr[feats], y)
        scores.loc[te.index] = model.predict_proba(te[feats])[:, 1]
    return scores


def _stats(frame: pd.DataFrame, horizon: int) -> dict[str, Any]:
    r = _safe_num(frame[f"fwd_ret_{horizon}"]).dropna()
    if r.empty:
        return {"n": 0}
    symbol_means = frame.assign(_r=_safe_num(frame[f"fwd_ret_{horizon}"])).groupby("symbol")["_r"].mean().dropna()
    return {
        "n": int(len(r)),
        "symbols": int(frame.loc[r.index, "symbol"].nunique()),
        "win_rate": float((r > 0).mean()),
        "mean_return": float(r.mean()),
        "median_return": float(r.median()),
        "loss_10_rate": float((r <= -0.10).mean()),
        "loss_20_rate": float((r <= -0.20).mean()),
        "equal_symbol_mean_return": float(symbol_means.mean()) if len(symbol_means) else np.nan,
        "positive_symbol_fraction": float((symbol_means > 0).mean()) if len(symbol_means) else np.nan,
    }


def _nonoverlap(frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    keep = []
    for _, g in frame.sort_values(["symbol", "as_of"]).groupby("symbol", sort=False):
        last = None
        for idx, r in g.iterrows():
            d = pd.Timestamp(r["as_of"])
            if last is None or (d - last).days >= int(math.ceil(horizon * 7 / 5)):
                keep.append(idx)
                last = d
    return frame.loc[keep].copy()


def _concentration(frame: pd.DataFrame, horizon: int) -> dict[str, float]:
    if frame.empty:
        return {"largest_symbol_abs_contribution_fraction": np.nan, "top10_symbol_abs_contribution_fraction": np.nan}
    x = frame.assign(_r=_safe_num(frame[f"fwd_ret_{horizon}"])).dropna(subset=["_r"])
    contrib = x.groupby("symbol")["_r"].sum()
    denom = float(contrib.abs().sum())
    if denom <= 0:
        return {"largest_symbol_abs_contribution_fraction": np.nan, "top10_symbol_abs_contribution_fraction": np.nan}
    a = contrib.abs().sort_values(ascending=False)
    return {
        "largest_symbol_abs_contribution_fraction": float(a.iloc[0] / denom),
        "top10_symbol_abs_contribution_fraction": float(a.head(10).sum() / denom),
    }


def selection_evidence(panel: pd.DataFrame, cfg: PositiveSelectionConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []

    for h in HORIZONS:
        ph = panel[panel["horizon"] == h].copy()
        ret_col = f"fwd_ret_{h}"
        if ph.empty or ret_col not in ph.columns:
            continue
        ph = ph[_safe_num(ph[ret_col]).notna()].copy()
        if ph.empty:
            continue
        ph["META_HGB"] = walk_forward_meta_scores(ph, h, cfg.random_state)
        for selector in SELECTORS:
            if selector == "META_HGB":
                score = ph["META_HGB"]
            else:
                try:
                    score = _selector_score(ph, selector)
                except (KeyError, PositiveSelectionError):
                    continue
            sx = ph.copy()
            sx["_selector_score"] = score
            sx = sx[sx["_selector_score"].notna()].copy()
            # Strictly forward-scored comparable sample for all selectors.
            sx = sx[sx["calendar_year"] >= 2011].copy()
            if sx.empty:
                continue
            sx["_selector_rank"] = sx.groupby("as_of")["_selector_score"].rank(method="first", pct=True, ascending=False)

            baseline = _stats(sx, h)
            for frac in TAIL_FRACTIONS:
                sel = sx[sx["_selector_rank"] <= frac].copy()
                st = _stats(sel, h)
                non = _nonoverlap(sel, h)
                nonst = _stats(non, h)
                conc = _concentration(sel, h)
                row = {
                    "horizon": h,
                    "selector": selector,
                    "top_fraction": frac,
                    "baseline_n": baseline.get("n", 0),
                    "selected_n": st.get("n", 0),
                    "selected_symbols": st.get("symbols", 0),
                    "baseline_win_rate": baseline.get("win_rate"),
                    "selected_win_rate": st.get("win_rate"),
                    "win_rate_uplift": st.get("win_rate", np.nan) - baseline.get("win_rate", np.nan),
                    "baseline_mean_return": baseline.get("mean_return"),
                    "selected_mean_return": st.get("mean_return"),
                    "mean_return_uplift": st.get("mean_return", np.nan) - baseline.get("mean_return", np.nan),
                    "baseline_median_return": baseline.get("median_return"),
                    "selected_median_return": st.get("median_return"),
                    "median_return_uplift": st.get("median_return", np.nan) - baseline.get("median_return", np.nan),
                    "baseline_loss_10_rate": baseline.get("loss_10_rate"),
                    "selected_loss_10_rate": st.get("loss_10_rate"),
                    "loss_10_rate_change": st.get("loss_10_rate", np.nan) - baseline.get("loss_10_rate", np.nan),
                    "selected_equal_symbol_mean_return": st.get("equal_symbol_mean_return"),
                    "selected_positive_symbol_fraction": st.get("positive_symbol_fraction"),
                    "nonoverlap_n": nonst.get("n", 0),
                    "nonoverlap_win_rate": nonst.get("win_rate"),
                    "nonoverlap_mean_return": nonst.get("mean_return"),
                    **conc,
                }
                rows.append(row)

                for year, gy in sx.groupby("calendar_year"):
                    sy = gy[gy["_selector_rank"] <= frac]
                    b = _stats(gy, h)
                    q = _stats(sy, h)
                    year_rows.append({
                        "horizon": h, "selector": selector, "top_fraction": frac, "year": int(year),
                        "baseline_n": b.get("n", 0), "selected_n": q.get("n", 0),
                        "win_rate_uplift": q.get("win_rate", np.nan) - b.get("win_rate", np.nan),
                        "mean_return_uplift": q.get("mean_return", np.nan) - b.get("mean_return", np.nan),
                        "loss_10_rate_change": q.get("loss_10_rate", np.nan) - b.get("loss_10_rate", np.nan),
                    })

                # Top contributor exclusion stress is evaluated after selection is frozen.
                by_symbol = sel.assign(_r=_safe_num(sel[ret_col])).groupby("symbol")["_r"].sum().abs().sort_values(ascending=False)
                for remove_n in (1, 5, 10):
                    drop = set(by_symbol.head(remove_n).index)
                    z = sel[~sel["symbol"].isin(drop)]
                    zz = _stats(z, h)
                    stress_rows.append({
                        "horizon": h, "selector": selector, "top_fraction": frac,
                        "remove_top_contributors": remove_n, "n": zz.get("n", 0),
                        "win_rate": zz.get("win_rate"), "mean_return": zz.get("mean_return"),
                        "equal_symbol_mean_return": zz.get("equal_symbol_mean_return"),
                    })

    return pd.DataFrame(rows), pd.DataFrame(year_rows), pd.DataFrame(stress_rows)


def readiness(evidence: pd.DataFrame, year_evidence: pd.DataFrame) -> pd.DataFrame:
    if evidence.empty:
        return pd.DataFrame()
    out = evidence.copy()
    pos_years = (
        year_evidence.assign(
            positive=lambda x: (x["win_rate_uplift"] > 0) & (x["mean_return_uplift"] > 0)
        ).groupby(["horizon", "selector", "top_fraction"])["positive"].agg(["sum", "count"]).reset_index()
    )
    pos_years["positive_year_fraction"] = pos_years["sum"] / pos_years["count"].replace(0, np.nan)
    out = out.merge(
        pos_years[["horizon", "selector", "top_fraction", "positive_year_fraction"]],
        on=["horizon", "selector", "top_fraction"], how="left"
    )
    out["gate_min_selected_n"] = out["selected_n"] >= 500
    out["gate_min_symbols"] = out["selected_symbols"] >= 100
    out["gate_win_rate_uplift"] = out["win_rate_uplift"] >= 0.02
    out["gate_mean_return_uplift"] = out["mean_return_uplift"] >= 0.0025
    out["gate_no_loss10_deterioration"] = out["loss_10_rate_change"] <= 0
    out["gate_equal_symbol_positive"] = out["selected_equal_symbol_mean_return"] > 0
    out["gate_positive_symbols"] = out["selected_positive_symbol_fraction"] >= 0.55
    out["gate_nonoverlap_win_rate"] = out["nonoverlap_win_rate"] >= (out["baseline_win_rate"] + 0.01)
    out["gate_concentration"] = out["top10_symbol_abs_contribution_fraction"] <= 0.40
    out["gate_year_stability"] = out["positive_year_fraction"] >= (5 / 7)
    gates = [c for c in out.columns if c.startswith("gate_")]
    out["development_ready"] = out[gates].all(axis=1)
    return out.sort_values(
        ["development_ready", "win_rate_uplift", "mean_return_uplift"],
        ascending=[False, False, False]
    ).reset_index(drop=True)


def run_lab(cfg: PositiveSelectionConfig) -> dict[str, Any]:
    root = Path(cfg.project_root)
    outdir = _resolve(root, cfg.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    panel, meta = load_development_authority(cfg)
    evidence, years, stress = selection_evidence(panel, cfg)
    ready = readiness(evidence, years)

    evidence.to_csv(outdir / "positive_selection_evidence.csv", index=False)
    years.to_csv(outdir / "positive_selection_year_evidence.csv", index=False)
    stress.to_csv(outdir / "positive_selection_concentration_stress.csv", index=False)
    ready.to_csv(outdir / "positive_selection_readiness.csv", index=False)

    top = ready.head(20) if not ready.empty else ready
    report = [
        "# M77.24 Positive Selection Edge Discovery",
        "",
        "## Governance",
        "",
        "- Model/selector discovery uses only historical Development data through 2017-12-31.",
        "- 2018-2022 Validation and 2023-2026 Final Holdout are treated as consumed and are not read.",
        "- DRVE bottom-1% exclusions are applied before positive-selection testing.",
        "- No historical period remains untouched for a new positive-selection certification.",
        "- Any candidate discovered here requires prospective certification using observations strictly after 2026-08-26.",
        "",
        "## Highest-ranked Development-only configurations",
        "",
        _markdown_table(top),
        "",
    ]
    (outdir / "POSITIVE_SELECTION_EDGE_DISCOVERY_REPORT.md").write_text("\n".join(report))

    protocol_boundary = {
        "version": "M77.24-PROSPECTIVE-BOUNDARY-1.0",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "historical_model_selection_end": DEVELOPMENT_END.date().isoformat(),
        "consumed_history": "2018-01-01 through 2026-08-26",
        "prospective_certification_not_before": PROSPECTIVE_NOT_BEFORE.date().isoformat(),
        "automatic_production_promotion": False,
        "production_authority_effect": False,
    }
    (outdir / "PROSPECTIVE_CERTIFICATION_BOUNDARY.json").write_text(
        json.dumps(protocol_boundary, indent=2, sort_keys=True)
    )

    ready_count = int(ready["development_ready"].sum()) if not ready.empty else 0
    summary = {
        "version": VERSION,
        "status": "COMPLETE",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_boundary": DEVELOPMENT_END.date().isoformat(),
        "consumed_history_opened_for_tuning": False,
        "consumed_2018_2026_rows_read": int(meta["consumed_2018_2026_rows_read"]),
        "prospective_certification_not_before": PROSPECTIVE_NOT_BEFORE.date().isoformat(),
        "primary_population": cfg.primary_population,
        "development_candidate_rows_after_drv_veto": int(len(panel)),
        "development_symbols": int(panel["symbol"].nunique()) if not panel.empty else 0,
        "selectors_tested": list(SELECTORS),
        "horizons": list(HORIZONS),
        "top_fractions": list(TAIL_FRACTIONS),
        "selection_evidence_rows": int(len(evidence)),
        "development_ready_configurations": ready_count,
        "production_authority_effect": False,
        "polygon_api_called": False,
        "automatic_retraining": False,
        "next_step": (
            "REVIEW_DEVELOPMENT_ONLY_POSITIVE_SELECTION_CANDIDATES; "
            "IF ANY SURVIVE, FREEZE ONE PROSPECTIVE PROTOCOL WITHOUT USING CONSUMED 2018-2026 OUTCOMES"
        ),
        "upstream_sha256": {
            "walk_forward_predictions.csv.gz": meta["prediction_sha256"],
            "prediction_integrity_evidence.csv.gz": meta["integrity_sha256"],
            "pit_long_candidate_authority.csv.gz": meta["pit_candidate_sha256"],
        },
    }
    (outdir / "positive_selection_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=_json_default))
    (outdir / "run_manifest.json").write_text(json.dumps({
        "version": VERSION,
        "config": cfg.__dict__,
        "outputs": sorted(p.name for p in outdir.iterdir() if p.is_file()),
        "governance": protocol_boundary,
    }, indent=2, sort_keys=True, default=_json_default))
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M77.24 Development-only positive-selection edge discovery")
    p.add_argument("--project-root", required=True)
    p.add_argument("--prediction-path", default=PositiveSelectionConfig.prediction_path)
    p.add_argument("--integrity-path", default=PositiveSelectionConfig.integrity_path)
    p.add_argument("--pit-candidate-path", default=PositiveSelectionConfig.pit_candidate_path)
    p.add_argument("--output-dir", default=PositiveSelectionConfig.output_dir)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    cfg = PositiveSelectionConfig(
        project_root=a.project_root,
        prediction_path=a.prediction_path,
        integrity_path=a.integrity_path,
        pit_candidate_path=a.pit_candidate_path,
        output_dir=a.output_dir,
    )
    print(json.dumps(run_lab(cfg), indent=2, sort_keys=True, default=_json_default))
    return 0
