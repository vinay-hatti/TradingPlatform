from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_ai.research.m77.candidate_quality_management_interaction import (
    InteractionConfig,
    _metrics,
    _nonoverlap,
    load_primary_panel,
)

VERSION = "M77.28.0-REGIME-CONDITIONED-EDGE-STABILITY-DISCOVERY-1.0"
DEVELOPMENT_END = pd.Timestamp("2017-12-31")
SELECTOR = "PROBABILITY_UP_TOP20"
MIN_PRIOR_REGIME_DATES = 126
REGIME_LOOKBACK_DATES = 504
LOW_Q = 1.0 / 3.0
HIGH_Q = 2.0 / 3.0

# These regime definitions are frozen before M77.28 outcome inspection.  Each dynamic
# threshold is calculated from PRIOR market dates only, preventing future-date leakage.
REGIME_FAMILIES = (
    "VOLATILITY",
    "TREND_BREADTH",
    "MOMENTUM_BREADTH",
    "PROBABILITY_LEVEL",
    "PROBABILITY_DISPERSION",
    "COMPOSITE",
    "CALENDAR",
)


class RegimeStabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegimeStabilityConfig:
    project_root: str
    executable_panel_path: str = InteractionConfig.executable_panel_path
    timing_panel_path: str = InteractionConfig.timing_panel_path
    output_dir: str = "research_data/m77_28/regime_conditioned_edge_stability_discovery"
    min_prior_regime_dates: int = MIN_PRIOR_REGIME_DATES
    regime_lookback_dates: int = REGIME_LOOKBACK_DATES


def _resolve(root: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    return p if p.is_absolute() else root / p


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


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))
    os.replace(tmp, path)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _md(df: pd.DataFrame, n: int = 40) -> str:
    if df.empty:
        return "_No rows._"
    x = df.head(n)
    cols = [str(c) for c in x.columns]

    def fmt(v: Any) -> str:
        if pd.isna(v):
            return ""
        if isinstance(v, (float, np.floating)):
            return f"{float(v):.6g}"
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, row in x.iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in x.columns) + " |")
    return "\n".join(lines)


def _safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _daily_context(panel: pd.DataFrame) -> pd.DataFrame:
    required = ["as_of", "probability_up", "atr_pct_14", "dist_sma_20", "px_ret_5"]
    missing = [c for c in required if c not in panel.columns]
    if missing:
        raise RegimeStabilityError(f"M77.28 missing required point-in-time context columns: {missing}")

    p = panel.copy()
    for c in ("probability_up", "atr_pct_14", "dist_sma_20", "px_ret_5"):
        p[c] = _safe_numeric(p[c])

    g = p.groupby("as_of", sort=True)
    daily = g.agg(
        candidate_rows=("symbol", "size"),
        candidate_symbols=("symbol", "nunique"),
        median_atr_pct_14=("atr_pct_14", "median"),
        median_probability_up=("probability_up", "median"),
        probability_dispersion=("probability_up", "std"),
    ).reset_index()
    daily["above_sma20_fraction"] = g["dist_sma_20"].apply(lambda x: float((_safe_numeric(x) > 0).mean())).to_numpy()
    daily["mom5_positive_fraction"] = g["px_ret_5"].apply(lambda x: float((_safe_numeric(x) > 0).mean())).to_numpy()
    daily["calendar_year"] = daily["as_of"].dt.year
    daily["month"] = daily["as_of"].dt.month
    return daily


def _prior_quantile_buckets(
    daily: pd.DataFrame,
    column: str,
    low_label: str,
    middle_label: str,
    high_label: str,
    min_prior: int,
    lookback: int,
) -> pd.Series:
    values = _safe_numeric(daily[column]).to_numpy(dtype=float)
    labels: list[str | None] = []
    for i, v in enumerate(values):
        start = max(0, i - lookback)
        hist = values[start:i]
        hist = hist[np.isfinite(hist)]
        if not np.isfinite(v) or len(hist) < min_prior:
            labels.append(None)
            continue
        lo = float(np.quantile(hist, LOW_Q))
        hi = float(np.quantile(hist, HIGH_Q))
        if v <= lo:
            labels.append(low_label)
        elif v >= hi:
            labels.append(high_label)
        else:
            labels.append(middle_label)
    return pd.Series(labels, index=daily.index, dtype="object")


def build_regime_calendar(panel: pd.DataFrame, cfg: RegimeStabilityConfig) -> pd.DataFrame:
    daily = _daily_context(panel)
    if (daily["as_of"] > DEVELOPMENT_END).any():
        raise RegimeStabilityError("M77.28 refuses post-2017 evidence")

    daily["VOLATILITY"] = _prior_quantile_buckets(
        daily, "median_atr_pct_14", "LOW", "MID", "HIGH",
        cfg.min_prior_regime_dates, cfg.regime_lookback_dates,
    )
    daily["TREND_BREADTH"] = _prior_quantile_buckets(
        daily, "above_sma20_fraction", "WEAK", "MIXED", "STRONG",
        cfg.min_prior_regime_dates, cfg.regime_lookback_dates,
    )
    daily["MOMENTUM_BREADTH"] = _prior_quantile_buckets(
        daily, "mom5_positive_fraction", "WEAK", "MIXED", "STRONG",
        cfg.min_prior_regime_dates, cfg.regime_lookback_dates,
    )
    daily["PROBABILITY_LEVEL"] = _prior_quantile_buckets(
        daily, "median_probability_up", "LOW", "MID", "HIGH",
        cfg.min_prior_regime_dates, cfg.regime_lookback_dates,
    )
    daily["PROBABILITY_DISPERSION"] = _prior_quantile_buckets(
        daily, "probability_dispersion", "LOW", "MID", "HIGH",
        cfg.min_prior_regime_dates, cfg.regime_lookback_dates,
    )

    # Composite states use only same-date labels already determined from prior-date thresholds.
    composite = []
    for _, r in daily.iterrows():
        vol = r["VOLATILITY"]
        trend = r["TREND_BREADTH"]
        mom = r["MOMENTUM_BREADTH"]
        if vol == "HIGH" and (trend == "WEAK" or mom == "WEAK"):
            composite.append("STRESS")
        elif vol == "LOW" and trend == "STRONG" and mom == "STRONG":
            composite.append("RISK_ON")
        elif vol is None or trend is None or mom is None or pd.isna(vol) or pd.isna(trend) or pd.isna(mom):
            composite.append(None)
        else:
            composite.append("OTHER")
    daily["COMPOSITE"] = composite

    # Calendar buckets are descriptive/frozen and do not use outcome information.
    daily["CALENDAR"] = np.select(
        [daily["month"].isin([1, 2, 3]), daily["month"].isin([4, 5, 6]), daily["month"].isin([7, 8, 9])],
        ["Q1", "Q2", "Q3"],
        default="Q4",
    )
    return daily


def _selector_mask(panel: pd.DataFrame) -> pd.Series:
    if "rank_probability_up" not in panel.columns:
        panel["rank_probability_up"] = panel.groupby("as_of")["probability_up"].rank(method="average", pct=True)
    return panel["rank_probability_up"] >= 0.80


def _evaluate_slice(g: pd.DataFrame) -> dict[str, Any]:
    selected = g[_selector_mask(g)].copy()
    complement = g[~_selector_mask(g)].copy()
    sm = _metrics(selected)
    cm = _metrics(complement)
    sn = _metrics(_nonoverlap(selected)) if not selected.empty else {"n": 0}
    return {
        "population_n": int(len(g)),
        "population_symbols": int(g["symbol"].nunique()),
        **{f"selected_{k}": v for k, v in sm.items()},
        **{f"complement_{k}": v for k, v in cm.items()},
        "interaction_mean_r_uplift": sm.get("mean_r", np.nan) - cm.get("mean_r", np.nan),
        "interaction_profit_factor_uplift": sm.get("profit_factor", np.nan) - cm.get("profit_factor", np.nan),
        "interaction_win_rate_uplift": sm.get("win_rate", np.nan) - cm.get("win_rate", np.nan),
        "nonoverlap_selected_mean_r": sn.get("mean_r", np.nan),
        "nonoverlap_selected_profit_factor": sn.get("profit_factor", np.nan),
    }


def regime_evidence(panel: pd.DataFrame, calendar: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = ["as_of", *REGIME_FAMILIES]
    p = panel.merge(calendar[cols], on="as_of", how="left", validate="many_to_one")
    evidence: list[dict[str, Any]] = []
    years: list[dict[str, Any]] = []

    for family in REGIME_FAMILIES:
        labels = [x for x in p[family].dropna().astype(str).unique().tolist()]
        for label in sorted(labels):
            g = p[p[family].astype(str) == label].copy()
            row = {"regime_family": family, "regime_state": label, **_evaluate_slice(g)}
            evidence.append(row)
            for year, yg in g.groupby(g["as_of"].dt.year):
                ym = _evaluate_slice(yg)
                years.append({
                    "regime_family": family,
                    "regime_state": label,
                    "year": int(year),
                    "population_n": ym["population_n"],
                    "selected_n": ym.get("selected_n", 0),
                    "interaction_mean_r_uplift": ym.get("interaction_mean_r_uplift", np.nan),
                    "interaction_profit_factor_uplift": ym.get("interaction_profit_factor_uplift", np.nan),
                })
    return pd.DataFrame(evidence), pd.DataFrame(years)


def regime_readiness(evidence: pd.DataFrame, years: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if evidence.empty:
        raise RegimeStabilityError("No M77.28 regime evidence materialized")

    y = years.copy()
    y["positive"] = (y["interaction_mean_r_uplift"] > 0) & (y["interaction_profit_factor_uplift"] > 0)
    ys = y.groupby(["regime_family", "regime_state"])["positive"].agg(["sum", "count"]).reset_index()
    ys["positive_year_fraction"] = ys["sum"] / ys["count"].replace(0, np.nan)

    r = evidence.merge(
        ys[["regime_family", "regime_state", "positive_year_fraction"]],
        on=["regime_family", "regime_state"], how="left",
    )
    r["gate_selected_n"] = r["selected_n"] >= 350
    r["gate_selected_symbols"] = r["selected_symbols"] >= 100
    r["gate_mean_r_positive"] = r["selected_mean_r"] > 0
    r["gate_pf"] = r["selected_profit_factor"] >= 1.15
    r["gate_interaction_uplift_positive"] = r["interaction_mean_r_uplift"] > 0
    r["gate_interaction_pf_uplift_positive"] = r["interaction_profit_factor_uplift"] > 0
    r["gate_nonoverlap"] = r["nonoverlap_selected_mean_r"] > 0
    r["gate_nonoverlap_pf"] = r["nonoverlap_selected_profit_factor"] >= 1.10
    r["gate_year_stability"] = r["positive_year_fraction"] >= 0.60
    r["gate_concentration"] = r["selected_top10_abs_contribution_fraction"] <= 0.35
    r["gate_gap"] = r["selected_gap_stop_fraction"] <= 0.12
    r["gate_tail"] = r["selected_tail_1pct_r"] >= -2.75
    gates = [c for c in r.columns if c.startswith("gate_")]
    r["regime_supports_interaction"] = r[gates].all(axis=1)

    fam_rows: list[dict[str, Any]] = []
    for family, fg in r.groupby("regime_family"):
        usable = fg[fg["gate_selected_n"] & fg["gate_selected_symbols"]].copy()
        support = usable["regime_supports_interaction"].fillna(False)
        fam_rows.append({
            "regime_family": family,
            "states_observed": int(len(fg)),
            "states_with_adequate_sample": int(len(usable)),
            "states_supporting_interaction": int(support.sum()),
            "support_fraction": float(support.mean()) if len(support) else np.nan,
            "minimum_interaction_mean_r_uplift": float(usable["interaction_mean_r_uplift"].min()) if len(usable) else np.nan,
            "minimum_selected_mean_r": float(usable["selected_mean_r"].min()) if len(usable) else np.nan,
            "minimum_nonoverlap_selected_mean_r": float(usable["nonoverlap_selected_mean_r"].min()) if len(usable) else np.nan,
        })
    f = pd.DataFrame(fam_rows)
    f["gate_multiple_states"] = f["states_with_adequate_sample"] >= 2
    f["gate_support_fraction"] = f["support_fraction"] >= 0.50
    f["family_stable"] = f["gate_multiple_states"] & f["gate_support_fraction"]

    return r.sort_values(["regime_family", "regime_state"]).reset_index(drop=True), f.sort_values("regime_family").reset_index(drop=True)


def overall_stability(families: pd.DataFrame) -> dict[str, Any]:
    # Calendar is diagnostic; structural stability is governed on five dynamic families + composite.
    structural = families[families["regime_family"] != "CALENDAR"].copy()
    stable_count = int(structural["family_stable"].fillna(False).sum())
    family_count = int(len(structural))
    dynamic_ready = bool(family_count >= 6 and stable_count >= 5)
    raw_minimum_support = structural["support_fraction"].min() if family_count else np.nan
    minimum_support = float(raw_minimum_support) if pd.notna(raw_minimum_support) else None
    return {
        "structural_family_count": family_count,
        "stable_structural_family_count": stable_count,
        "minimum_structural_support_fraction": minimum_support,
        "gate_at_least_5_of_6_structural_families_stable": bool(stable_count >= 5),
        "gate_no_structural_family_zero_support": bool((structural["states_supporting_interaction"] > 0).all()) if family_count else False,
        "development_regime_stability_verdict": "READY_FOR_REVIEW" if dynamic_ready and bool((structural["states_supporting_interaction"] > 0).all()) else "NOT_STABLE_ENOUGH",
    }


def run_lab(cfg: RegimeStabilityConfig) -> dict[str, Any]:
    root = Path(cfg.project_root).expanduser().resolve()
    outdir = _resolve(root, cfg.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    panel, upstream = load_primary_panel(InteractionConfig(
        project_root=cfg.project_root,
        executable_panel_path=cfg.executable_panel_path,
        timing_panel_path=cfg.timing_panel_path,
    ))
    if (panel["as_of"] > DEVELOPMENT_END).any():
        raise RegimeStabilityError("M77.28 refuses post-2017 primary panel")

    calendar = build_regime_calendar(panel, cfg)
    evidence, years = regime_evidence(panel, calendar)
    readiness, families = regime_readiness(evidence, years)
    stability = overall_stability(families)

    calendar.to_csv(outdir / "point_in_time_regime_calendar.csv", index=False)
    evidence.to_csv(outdir / "regime_conditioned_interaction_evidence.csv", index=False)
    years.to_csv(outdir / "regime_conditioned_interaction_year_evidence.csv", index=False)
    readiness.to_csv(outdir / "regime_conditioned_interaction_readiness.csv", index=False)
    families.to_csv(outdir / "regime_family_stability.csv", index=False)

    report = [
        "# M77.28 Regime-Conditioned Edge Stability Discovery", "",
        "## Frozen interaction under test", "",
        "- PIT Trade-Builder-ready LONG + DRVE PASS.",
        "- PROBABILITY_UP top 20% selected contemporaneously.",
        "- NEXT_OPEN entry; 5 ATR target; 3 ATR stop; 60-session maximum hold.",
        "- No selector, geometry, or regime threshold is outcome-retuned.",
        "- Dynamic regime thresholds use prior market dates only.",
        "- 2018-2026 outcomes are not read.", "",
        "## Overall stability", "", "```json", json.dumps(stability, indent=2, sort_keys=True, default=_json_default), "```", "",
        "## Regime-family stability", "", _md(families), "",
        "## Regime-state evidence", "", _md(readiness, 60), "",
    ]
    (outdir / "REGIME_CONDITIONED_EDGE_STABILITY_REPORT.md").write_text("\n".join(report))

    summary = {
        "version": VERSION,
        "status": "COMPLETE",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_boundary": "2017-12-31",
        "consumed_2018_2026_rows_read": 0,
        "selector": SELECTOR,
        "frozen_management_geometry": {"entry": "NEXT_OPEN", "target_atr": 5.0, "stop_atr": 3.0, "horizon": 60},
        "regime_families": list(REGIME_FAMILIES),
        "min_prior_regime_dates": int(cfg.min_prior_regime_dates),
        "regime_lookback_dates": int(cfg.regime_lookback_dates),
        "point_in_time_regime_thresholds": True,
        "primary_panel_rows": int(len(panel)),
        "primary_symbols": int(panel["symbol"].nunique()),
        "regime_dates": int(len(calendar)),
        "regime_evidence_rows": int(len(evidence)),
        **stability,
        "m77_23_drv_modified": False,
        "m77_24_1_psve_modified": False,
        "m77_26_2_mge_modified": False,
        "m77_27_1_cqmi_modified": False,
        "production_authority_effect": False,
        "polygon_api_called": False,
        "automatic_retraining": False,
        "next_step": "REVIEW DEVELOPMENT-ONLY REGIME STABILITY; DO NOT CREATE OR MODIFY A PROSPECTIVE PROTOCOL FROM M77.28 WITHOUT EXPLICIT GOVERNANCE REVIEW",
        "upstream_sha256": upstream,
    }
    _atomic_json(outdir / "regime_conditioned_edge_stability_summary.json", summary)
    _atomic_json(outdir / "run_manifest.json", {"version": VERSION, "config": asdict(cfg), "summary": summary})
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M77.28 development-only regime-conditioned edge stability discovery")
    p.add_argument("--project-root", required=True)
    p.add_argument("--executable-panel-path", default=RegimeStabilityConfig.executable_panel_path)
    p.add_argument("--timing-panel-path", default=RegimeStabilityConfig.timing_panel_path)
    p.add_argument("--output-dir", default=RegimeStabilityConfig.output_dir)
    p.add_argument("--min-prior-regime-dates", type=int, default=MIN_PRIOR_REGIME_DATES)
    p.add_argument("--regime-lookback-dates", type=int, default=REGIME_LOOKBACK_DATES)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    cfg = RegimeStabilityConfig(
        project_root=a.project_root,
        executable_panel_path=a.executable_panel_path,
        timing_panel_path=a.timing_panel_path,
        output_dir=a.output_dir,
        min_prior_regime_dates=a.min_prior_regime_dates,
        regime_lookback_dates=a.regime_lookback_dates,
    )
    print(json.dumps(run_lab(cfg), indent=2, sort_keys=True, default=_json_default))
    return 0
