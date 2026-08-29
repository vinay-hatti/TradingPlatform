from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_ai.research.m77.edge_discovery_lab import EdgeLabError, _json_default, sanitize_nonfinite_numeric
from trading_ai.research.m77.bearish_deterioration_lab import HORIZONS, TAILS, DEVELOPMENT_END

VERSION = "M77.22.1-INTEGRITY-AWARE-BEARISH-TAIL-RECALIBRATION-1.0"
TREATMENTS = (
    "RAW",
    "INTEGRITY_CLEAN",
    "WINSOR_99_9",
    "WINSOR_99_5",
    "TRIM_0_1",
    "TRIM_0_5",
    "EXCLUDE_ABS_GT_50",
    "EXCLUDE_ABS_GT_100",
)


@dataclass(frozen=True)
class IntegrityAwareBearishConfig:
    project_root: str
    development_predictions: str = "research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"
    integrity_evidence: str = "research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz"
    development_panel: str = "research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
    output_root: str = "research_data/m77_22_1/integrity_aware_bearish_recalibration"
    horizons: tuple[int, ...] = HORIZONS
    tails: tuple[float, ...] = TAILS
    execution_mode: str = "DEVELOPMENT_ONLY_INTEGRITY_AWARE_BEARISH_RECALIBRATION"

    def validate(self) -> None:
        if self.execution_mode != "DEVELOPMENT_ONLY_INTEGRITY_AWARE_BEARISH_RECALIBRATION":
            raise EdgeLabError("M77.22.1 authorizes Development-only integrity-aware bearish recalibration")
        if tuple(self.horizons) != HORIZONS or tuple(self.tails) != TAILS:
            raise EdgeLabError("M77.22.1 frozen horizons/tails changed")
        for raw in (self.development_predictions, self.integrity_evidence, self.development_panel, self.output_root):
            low = raw.lower()
            if "m77_21_3" in low or "validation" in low or "final_holdout" in low:
                raise EdgeLabError("M77.22.1 may not read Validation or Final Holdout artifacts")


def _resolve(root: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (root / p).resolve()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, default=_json_default)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _atomic_csv(path: Path, frame: pd.DataFrame, compression: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False, compression=compression)
    os.replace(tmp, path)


def _load_predictions(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise EdgeLabError(f"Development predictions missing: {path}")
    df = pd.read_csv(path, compression="gzip", low_memory=False)
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.dropna(subset=["symbol", "as_of", "horizon", "probability_up"]).copy()
    df = df[df["horizon"].isin(HORIZONS)].copy()
    if df.empty or df["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError("M77.22.1 predictions are empty or cross Development boundary")
    if "test_year" in df.columns and pd.to_numeric(df["test_year"], errors="coerce").max() > 2017:
        raise EdgeLabError("M77.22.1 predictions contain post-2017 outcomes")
    df, _ = sanitize_nonfinite_numeric(df)
    return df.sort_values(["as_of", "horizon", "symbol"]).reset_index(drop=True)


def _load_integrity(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise EdgeLabError(f"Integrity evidence missing: {path}")
    df = pd.read_csv(path, compression="gzip", low_memory=False)
    required = {
        "symbol", "as_of", "horizon", "raw_authority_present", "interval_integrity_clean",
        "source_return_matches_raw", "raw_recomputed_return", "interval_integrity_event_count",
    }
    missing = required - set(df.columns)
    if missing:
        raise EdgeLabError(f"integrity evidence missing columns: {sorted(missing)}")
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.dropna(subset=["symbol", "as_of", "horizon"]).copy()
    if df["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError("integrity evidence crosses Development boundary")
    if df.duplicated(["symbol", "as_of", "horizon"]).any():
        raise EdgeLabError("integrity evidence is not unique by symbol/as_of/horizon")
    df["integrity_clean_strict"] = (
        df["raw_authority_present"].fillna(False).astype(bool)
        & df["interval_integrity_clean"].fillna(False).astype(bool)
        & df["source_return_matches_raw"].fillna(False).astype(bool)
        & pd.to_numeric(df["interval_integrity_event_count"], errors="coerce").fillna(1).eq(0)
    )
    return df


def _load_panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise EdgeLabError(f"Development panel missing: {path}")
    df = pd.read_pickle(path, compression="gzip")
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.dropna(subset=["symbol", "as_of"]).copy()
    if df["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError("panel crosses Development boundary")
    return df


def _select_tail(df: pd.DataFrame, horizon: int, tail: float) -> pd.DataFrame:
    d = df[df["horizon"] == horizon].copy()
    chunks: list[pd.DataFrame] = []
    for _, g in d.groupby("as_of", sort=False):
        k = max(1, int(math.ceil(len(g) * tail)))
        chunks.append(g.nsmallest(k, "probability_up"))
    return pd.concat(chunks, ignore_index=True) if chunks else d.iloc[0:0].copy()


def _annotate(pred: pd.DataFrame, integ: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "symbol", "as_of", "horizon", "raw_authority_present", "interval_integrity_event_count",
        "interval_integrity_clean", "source_return_matches_raw", "raw_recomputed_return", "integrity_clean_strict",
    ]
    out = pred.merge(integ[cols], on=["symbol", "as_of", "horizon"], how="left", validate="one_to_one")
    out["integrity_evidence_present"] = out["integrity_clean_strict"].notna()
    out["integrity_clean_strict"] = out["integrity_clean_strict"].fillna(False).astype(bool)
    return out


def _treated_returns(sel: pd.DataFrame, h: int, treatment: str) -> pd.DataFrame:
    rcol = f"fwd_ret_{h}"
    d = sel.copy()
    d["raw_return"] = pd.to_numeric(d[rcol], errors="coerce")
    d = d[np.isfinite(d["raw_return"])].copy()
    if treatment == "INTEGRITY_CLEAN":
        d = d[d["integrity_clean_strict"]].copy()
        d["treated_return"] = d["raw_return"]
    elif treatment == "EXCLUDE_ABS_GT_50":
        d = d[d["raw_return"].abs() <= 0.50].copy(); d["treated_return"] = d["raw_return"]
    elif treatment == "EXCLUDE_ABS_GT_100":
        d = d[d["raw_return"].abs() <= 1.00].copy(); d["treated_return"] = d["raw_return"]
    elif treatment in {"WINSOR_99_9", "WINSOR_99_5"}:
        q = 0.001 if treatment == "WINSOR_99_9" else 0.005
        if not d.empty:
            lo, hi = d["raw_return"].quantile([q, 1-q]).tolist()
            d["treated_return"] = d["raw_return"].clip(lo, hi)
        else:
            d["treated_return"] = d["raw_return"]
    elif treatment in {"TRIM_0_1", "TRIM_0_5"}:
        q = 0.001 if treatment == "TRIM_0_1" else 0.005
        if not d.empty:
            lo, hi = d["raw_return"].quantile([q, 1-q]).tolist()
            d = d[d["raw_return"].between(lo, hi)].copy()
        d["treated_return"] = d["raw_return"]
    else:
        d["treated_return"] = d["raw_return"]
    d["signed_return"] = -d["treated_return"]
    return d


def _tail_recalibration(annotated: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        base = annotated[annotated["horizon"] == h].copy()
        rcol = f"fwd_ret_{h}"
        if rcol not in annotated.columns or base.empty:
            continue
        base_ret = pd.to_numeric(base[rcol], errors="coerce")
        baseline_short_win = float((base_ret[np.isfinite(base_ret)] < 0).mean())
        for tail in TAILS:
            sel = _select_tail(annotated, h, tail)
            raw_n = int(pd.to_numeric(sel[rcol], errors="coerce").notna().sum())
            for tr in TREATMENTS:
                d = _treated_returns(sel, h, tr)
                if d.empty:
                    continue
                rows.append({
                    "horizon": h,
                    "tail_fraction": tail,
                    "treatment": tr,
                    "n": int(len(d)),
                    "raw_tail_n": raw_n,
                    "retained_fraction": float(len(d) / raw_n) if raw_n else np.nan,
                    "unique_symbols": int(d["symbol"].nunique()),
                    "selection_dates": int(d["as_of"].nunique()),
                    "short_win_rate": float((d["raw_return"] < 0).mean()),
                    "short_win_rate_edge_vs_full_universe": float((d["raw_return"] < 0).mean() - baseline_short_win),
                    "mean_signed_return": float(d["signed_return"].mean()),
                    "median_signed_return": float(d["signed_return"].median()),
                    "p10_signed_return": float(d["signed_return"].quantile(0.10)),
                    "p90_signed_return": float(d["signed_return"].quantile(0.90)),
                    "positive_years": int(d.groupby(d["as_of"].dt.year)["signed_return"].mean().gt(0).sum()),
                    "years": int(d["as_of"].dt.year.nunique()),
                })
    return pd.DataFrame(rows)


def _year_recalibration(annotated: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        if f"fwd_ret_{h}" not in annotated.columns or annotated[annotated["horizon"] == h].empty:
            continue
        for tail in TAILS:
            sel = _select_tail(annotated, h, tail)
            for tr in TREATMENTS:
                d = _treated_returns(sel, h, tr)
                for yr, g in d.groupby(d["as_of"].dt.year):
                    rows.append({
                        "horizon": h, "tail_fraction": tail, "treatment": tr, "test_year": int(yr),
                        "n": int(len(g)), "unique_symbols": int(g["symbol"].nunique()),
                        "short_win_rate": float((g["raw_return"] < 0).mean()),
                        "mean_signed_return": float(g["signed_return"].mean()),
                        "median_signed_return": float(g["signed_return"].median()),
                    })
    return pd.DataFrame(rows)


def _concentration(annotated: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        if f"fwd_ret_{h}" not in annotated.columns or annotated[annotated["horizon"] == h].empty:
            continue
        for tail in TAILS:
            sel = _select_tail(annotated, h, tail)
            for tr in ("RAW", "INTEGRITY_CLEAN", "EXCLUDE_ABS_GT_100"):
                d = _treated_returns(sel, h, tr)
                if d.empty:
                    continue
                sym = d.groupby(d["symbol"].astype(str))["signed_return"].sum().abs().sort_values(ascending=False)
                yr = d.groupby(d["as_of"].dt.year)["signed_return"].sum().abs().sort_values(ascending=False)
                sden = float(sym.sum()); yden = float(yr.sum())
                rows.append({
                    "horizon": h, "tail_fraction": tail, "treatment": tr,
                    "n": int(len(d)), "unique_symbols": int(d["symbol"].nunique()), "years": int(d["as_of"].dt.year.nunique()),
                    "largest_symbol_abs_contribution_fraction": float(sym.iloc[0] / sden) if sden else np.nan,
                    "top5_symbol_abs_contribution_fraction": float(sym.head(5).sum() / sden) if sden else np.nan,
                    "top10_symbol_abs_contribution_fraction": float(sym.head(10).sum() / sden) if sden else np.nan,
                    "largest_year_abs_contribution_fraction": float(yr.iloc[0] / yden) if yden else np.nan,
                    "top3_year_abs_contribution_fraction": float(yr.head(3).sum() / yden) if yden else np.nan,
                })
    return pd.DataFrame(rows)


def _avoidance(annotated: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        base = annotated[annotated["horizon"] == h].copy()
        rcol = f"fwd_ret_{h}"
        if rcol not in annotated.columns or base.empty:
            continue
        base["ret"] = pd.to_numeric(base[rcol], errors="coerce")
        base = base[np.isfinite(base["ret"]) & base["integrity_clean_strict"]].copy()
        if base.empty:
            continue
        total_losses = int((base["ret"] < 0).sum())
        total_severe = int((base["ret"] <= -0.10).sum())
        for tail in TAILS:
            # Membership is formed before integrity filtering; then intersect with clean authority.
            raw_sel = _select_tail(annotated, h, tail)[["symbol", "as_of"]].drop_duplicates()
            ex = base.merge(raw_sel.assign(_excluded=True), on=["symbol", "as_of"], how="left")
            excluded_mask = ex["_excluded"].eq(True)
            excluded = ex[excluded_mask].copy()
            retained = ex[~excluded_mask].copy()
            if excluded.empty or retained.empty:
                continue
            ex_losses = int((excluded["ret"] < 0).sum())
            ex_severe = int((excluded["ret"] <= -0.10).sum())
            excluded_fraction = float(len(excluded) / len(base))
            loss_capture = float(ex_losses / total_losses) if total_losses else np.nan
            severe_capture = float(ex_severe / total_severe) if total_severe else np.nan
            rows.append({
                "horizon": h, "tail_fraction_excluded": tail,
                "clean_population_n": int(len(base)), "excluded_n": int(len(excluded)), "retained_n": int(len(retained)),
                "excluded_fraction": excluded_fraction,
                "baseline_loss_rate": float((base["ret"] < 0).mean()),
                "retained_loss_rate": float((retained["ret"] < 0).mean()),
                "loss_rate_reduction": float((base["ret"] < 0).mean() - (retained["ret"] < 0).mean()),
                "baseline_severe_loss_rate_le_10pct": float((base["ret"] <= -0.10).mean()),
                "retained_severe_loss_rate_le_10pct": float((retained["ret"] <= -0.10).mean()),
                "severe_loss_rate_reduction": float((base["ret"] <= -0.10).mean() - (retained["ret"] <= -0.10).mean()),
                "losses_captured_fraction": loss_capture,
                "severe_losses_captured_fraction": severe_capture,
                "loss_capture_lift_vs_random": float(loss_capture / excluded_fraction) if excluded_fraction > 0 and np.isfinite(loss_capture) else np.nan,
                "severe_loss_capture_lift_vs_random": float(severe_capture / excluded_fraction) if excluded_fraction > 0 and np.isfinite(severe_capture) else np.nan,
                "excluded_mean_return": float(excluded["ret"].mean()),
                "excluded_median_return": float(excluded["ret"].median()),
            })
    return pd.DataFrame(rows)


def _barrier(panel: pd.DataFrame, annotated: pd.DataFrame) -> pd.DataFrame:
    cols = ["symbol", "as_of"] + [c for c in panel.columns if c.startswith(("short_barrier_", "short_days_"))]
    b = panel[cols].drop_duplicates(["symbol", "as_of"])
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        for tail in TAILS:
            sel = _select_tail(annotated, h, tail)
            sel = sel[sel["integrity_clean_strict"]].merge(b, on=["symbol", "as_of"], how="left")
            tag_end = f"_h{h}"
            for c in [x for x in sel.columns if x.startswith("short_barrier_") and x.endswith(tag_end)]:
                vals = pd.to_numeric(sel[c], errors="coerce").dropna()
                if vals.empty:
                    continue
                wins = int((vals == 1).sum()); losses = int((vals == -1).sum()); unresolved = int((vals == 0).sum())
                resolved = wins + losses
                parts = c.replace("short_barrier_t", "").split("_s")
                target = float(parts[0].replace("p", ".")); stop = float(parts[1].split("_h")[0].replace("p", "."))
                exp = ((wins * target) - (losses * stop)) / resolved if resolved else np.nan
                rows.append({
                    "horizon": h, "tail_fraction": tail, "target_atr": target, "stop_atr": stop,
                    "integrity_clean_n": int(len(sel)), "resolved_n": resolved, "unresolved_n": unresolved,
                    "wins": wins, "losses": losses, "resolved_win_rate": float(wins/resolved) if resolved else np.nan,
                    "expectancy_r": float(exp) if np.isfinite(exp) else np.nan,
                })
    return pd.DataFrame(rows)


def _candidate_assessment(tails: pd.DataFrame, conc: pd.DataFrame, barriers: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    clean = tails[(tails["treatment"] == "INTEGRITY_CLEAN") & (tails["tail_fraction"] == 0.01)].copy()
    for _, r in clean.iterrows():
        h = int(r["horizon"])
        c = conc[(conc.horizon == h) & (conc.tail_fraction == 0.01) & (conc.treatment == "INTEGRITY_CLEAN")]
        b = barriers[(barriers.horizon == h) & (barriers.tail_fraction == 0.01)]
        best = b.sort_values("expectancy_r", ascending=False).iloc[0] if not b.empty else None
        top10 = float(c.iloc[0]["top10_symbol_abs_contribution_fraction"]) if not c.empty else np.nan
        passes = (
            int(r["n"]) >= 2000
            and int(r["unique_symbols"]) >= 200
            and float(r["short_win_rate"]) >= 0.55
            and float(r["median_signed_return"]) > 0
            and int(r["positive_years"]) >= 7
            and np.isfinite(top10) and top10 <= 0.50
            and best is not None and float(best["expectancy_r"]) >= 0.10
        )
        rows.append({
            "horizon": h, "tail_fraction": 0.01, "integrity_clean_n": int(r["n"]),
            "unique_symbols": int(r["unique_symbols"]), "short_win_rate": float(r["short_win_rate"]),
            "median_signed_return": float(r["median_signed_return"]), "mean_signed_return": float(r["mean_signed_return"]),
            "positive_years": int(r["positive_years"]), "years": int(r["years"]),
            "top10_symbol_abs_contribution_fraction": top10,
            "best_barrier_expectancy_r": float(best["expectancy_r"]) if best is not None else np.nan,
            "best_barrier_target_atr": float(best["target_atr"]) if best is not None else np.nan,
            "best_barrier_stop_atr": float(best["stop_atr"]) if best is not None else np.nan,
            "passes_development_integrity_protocol_readiness": bool(passes),
        })
    return pd.DataFrame(rows).sort_values(["passes_development_integrity_protocol_readiness", "best_barrier_expectancy_r", "median_signed_return"], ascending=[False, False, False])


def _write_report(out: Path, summary: dict[str, Any], assess: pd.DataFrame, avoid: pd.DataFrame) -> None:
    lines = [
        "# M77.22.1 Integrity-Aware Bearish Tail & Avoidance Recalibration", "",
        f"Status: **{summary['status']}**", "",
        "Development-only recalibration. Consumed 2018–2022 Validation is not read and 2023+ Final Holdout remains sealed.", "",
        "## Headline", "",
        f"- Development predictions annotated: {summary['prediction_rows_annotated']:,}",
        f"- Strict integrity-clean fraction: {summary['integrity_clean_fraction']:.4%}",
        f"- Bottom-1% horizons passing Development protocol-readiness gates: {summary['protocol_ready_bottom1_horizons']}", "",
    ]
    if not assess.empty:
        lines += ["## Bottom-1% integrity-clean assessment", ""]
        for _, r in assess.iterrows():
            lines.append(f"- {int(r.horizon)}d: win {r.short_win_rate:.2%}; median signed {r.median_signed_return:.2%}; top-10 symbol concentration {r.top10_symbol_abs_contribution_fraction:.2%}; best barrier expectancy {r.best_barrier_expectancy_r:+.3f}R; readiness={bool(r.passes_development_integrity_protocol_readiness)}")
        lines.append("")
    if not avoid.empty:
        a = avoid.sort_values("severe_loss_capture_lift_vs_random", ascending=False).iloc[0]
        lines += ["## Strongest integrity-clean avoidance efficiency", "", f"{int(a.horizon)}d bottom {100*a.tail_fraction_excluded:.1f}% captured severe losses at {a.severe_loss_capture_lift_vs_random:.2f}x the rate expected from random exclusion.", ""]
    lines += ["## Governance", "", "- Validation 2018–2022: NOT READ", "- Final Holdout 2023+: SEALED", "- Polygon API calls: NONE", "- Production authority effect: NONE", "- No Final Holdout protocol is authorized by this phase.", ""]
    (out / "INTEGRITY_AWARE_BEARISH_RECALIBRATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run_lab(cfg: IntegrityAwareBearishConfig) -> dict[str, Any]:
    cfg.validate()
    root = Path(cfg.project_root).expanduser().resolve()
    pred = _load_predictions(_resolve(root, cfg.development_predictions))
    integ = _load_integrity(_resolve(root, cfg.integrity_evidence))
    panel = _load_panel(_resolve(root, cfg.development_panel))
    out = _resolve(root, cfg.output_root); out.mkdir(parents=True, exist_ok=True)
    ann = _annotate(pred, integ)

    tails = _tail_recalibration(ann)
    years = _year_recalibration(ann)
    conc = _concentration(ann)
    avoid = _avoidance(ann)
    barrier = _barrier(panel, ann)
    assess = _candidate_assessment(tails, conc, barrier)

    _atomic_csv(out / "integrity_aware_bearish_tail_recalibration.csv", tails)
    _atomic_csv(out / "integrity_aware_bearish_year_evidence.csv", years)
    _atomic_csv(out / "integrity_aware_bearish_concentration.csv", conc)
    _atomic_csv(out / "integrity_aware_avoidance_evidence.csv", avoid)
    _atomic_csv(out / "integrity_aware_defined_risk_evidence.csv", barrier)
    _atomic_csv(out / "bottom1_protocol_readiness_assessment.csv", assess)

    present = int(ann["integrity_evidence_present"].sum())
    clean = int(ann["integrity_clean_strict"].sum())
    ready = int(assess["passes_development_integrity_protocol_readiness"].sum()) if not assess.empty else 0
    summary = {
        "version": VERSION, "status": "COMPLETE", "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_boundary": "2017-12-31", "prediction_rows_annotated": int(len(ann)),
        "integrity_evidence_rows_matched": present, "integrity_clean_prediction_rows": clean,
        "integrity_clean_fraction": float(clean / len(ann)) if len(ann) else 0.0,
        "tail_recalibration_rows": int(len(tails)), "year_recalibration_rows": int(len(years)),
        "concentration_rows": int(len(conc)), "avoidance_rows": int(len(avoid)), "defined_risk_rows": int(len(barrier)),
        "protocol_ready_bottom1_horizons": ready,
        "validation_partition_opened": False, "validation_rows_read": 0,
        "consumed_validation_reused_for_tuning": False,
        "final_holdout_opened": False, "final_holdout_rows_read": 0,
        "polygon_api_called": False, "production_authority_effect": False,
        "next_step": "REVIEW_INTEGRITY_CLEAN_BEARISH_EVIDENCE_BEFORE_ANY_FINAL_HOLDOUT_PROTOCOL_DECISION",
    }
    _atomic_json(out / "integrity_aware_bearish_recalibration_summary.json", summary)
    _atomic_json(out / "run_manifest.json", {"config": asdict(cfg), "summary": summary, "governance": {"validation_allowed": False, "final_holdout_allowed": False}})
    _write_report(out, summary, assess, avoid)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M77.22.1 Integrity-Aware Bearish Tail & Avoidance Recalibration")
    p.add_argument("--project-root", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_lab(IntegrityAwareBearishConfig(project_root=args.project_root))
    print(json.dumps(summary, indent=2, sort_keys=True, default=_json_default))
    return 0
