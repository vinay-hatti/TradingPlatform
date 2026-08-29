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

VERSION = "M77.22.0-BEARISH-DETERIORATION-AVOIDANCE-EDGE-RESEARCH-1.0"
DEVELOPMENT_END = pd.Timestamp("2017-12-31")
PREDICTION_START = pd.Timestamp("2008-01-01")
HORIZONS = (15, 20, 30, 45, 60)
TAILS = (0.01, 0.025, 0.05, 0.10)
RESEARCH_PARTITIONS = {
    "DISCOVERY": (2008, 2010),
    "CONFIRMATION": (2011, 2013),
    "INTERNAL_HOLDOUT": (2014, 2017),
}


@dataclass(frozen=True)
class BearishResearchConfig:
    project_root: str
    development_predictions: str = "research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"
    development_panel: str = "research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
    output_root: str = "research_data/m77_22/bearish_deterioration_avoidance_lab"
    horizons: tuple[int, ...] = HORIZONS
    tails: tuple[float, ...] = TAILS
    max_attribution_features: int = 20
    max_rule_features: int = 12
    minimum_candidate_rows: int = 250
    minimum_candidate_symbols: int = 50
    minimum_partition_rows: int = 75
    maximum_top10_symbol_fraction: float = 0.55
    execution_mode: str = "DEVELOPMENT_ONLY_BEARISH_RESEARCH"

    def validate(self) -> None:
        if self.execution_mode != "DEVELOPMENT_ONLY_BEARISH_RESEARCH":
            raise EdgeLabError("M77.22 authorizes Development-only bearish research")
        if tuple(self.horizons) != HORIZONS or tuple(self.tails) != TAILS:
            raise EdgeLabError("M77.22 frozen research horizons/tails changed")
        if self.minimum_candidate_rows < 100 or self.minimum_candidate_symbols < 20:
            raise EdgeLabError("candidate breadth gates cannot be weakened below research floor")
        for raw in (self.development_predictions, self.development_panel, self.output_root):
            if "m77_21_3" in raw.lower() or "validation" in raw.lower() or "final_holdout" in raw.lower():
                raise EdgeLabError("M77.22 may not read Validation or Final Holdout artifacts")


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
        raise EdgeLabError(f"Development walk-forward predictions missing: {path}")
    df = pd.read_csv(path, compression="gzip", low_memory=False)
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.dropna(subset=["as_of", "symbol", "horizon", "probability_up"]).copy()
    df = df[df["horizon"].isin(HORIZONS)].copy()
    if df.empty:
        raise EdgeLabError("no Development walk-forward prediction rows found")
    if df["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError("M77.22 Development predictions cross 2017-12-31 boundary")
    if df["as_of"].min() < PREDICTION_START:
        df = df[df["as_of"] >= PREDICTION_START].copy()
    if "test_year" in df.columns and pd.to_numeric(df["test_year"], errors="coerce").max() > 2017:
        raise EdgeLabError("M77.22 Development predictions include post-2017 test years")
    df, _ = sanitize_nonfinite_numeric(df)
    return df.sort_values(["as_of", "horizon", "symbol"]).reset_index(drop=True)


def _load_panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise EdgeLabError(f"Development panel missing: {path}")
    df = pd.read_pickle(path, compression="gzip")
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.dropna(subset=["as_of", "symbol"]).copy()
    if df["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError("M77.22 Development panel crosses 2017-12-31 boundary")
    df, _ = sanitize_nonfinite_numeric(df)
    return df.sort_values(["as_of", "symbol"]).reset_index(drop=True)


def _partition(year: pd.Series) -> pd.Series:
    y = pd.to_numeric(year, errors="coerce")
    out = pd.Series("OUTSIDE", index=year.index, dtype="object")
    for name, (lo, hi) in RESEARCH_PARTITIONS.items():
        out[(y >= lo) & (y <= hi)] = name
    return out


def _select_tail(df: pd.DataFrame, horizon: int, tail: float) -> pd.DataFrame:
    d = df[df["horizon"] == horizon].copy()
    if d.empty:
        return d
    chunks: list[pd.DataFrame] = []
    for _, g in d.groupby("as_of", sort=False):
        n = len(g)
        k = max(1, int(math.ceil(n * tail)))
        chunks.append(g.nsmallest(k, "probability_up"))
    return pd.concat(chunks, ignore_index=True) if chunks else d.iloc[0:0].copy()


def _tail_evidence(pred: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        base = pred[pred["horizon"] == h].copy()
        rcol = f"fwd_ret_{h}"
        if rcol not in base.columns:
            continue
        base_ret = pd.to_numeric(base[rcol], errors="coerce")
        baseline_short_win = float((base_ret < 0).mean())
        baseline_signed_mean = float((-base_ret).mean())
        for tail in TAILS:
            sel = _select_tail(pred, h, tail)
            r = pd.to_numeric(sel[rcol], errors="coerce")
            r = r[np.isfinite(r)]
            if r.empty:
                continue
            signed = -r
            rows.append({
                "horizon": h,
                "tail_fraction": tail,
                "n": int(len(r)),
                "unique_symbols": int(sel.loc[r.index if r.index.isin(sel.index).all() else sel.index, "symbol"].nunique()),
                "selection_dates": int(sel["as_of"].nunique()),
                "short_win_rate": float((r < 0).mean()),
                "short_win_rate_edge": float((r < 0).mean() - baseline_short_win),
                "mean_signed_return": float(signed.mean()),
                "median_signed_return": float(signed.median()),
                "baseline_mean_signed_return": baseline_signed_mean,
                "mean_signed_return_edge": float(signed.mean() - baseline_signed_mean),
                "p10_signed_return": float(signed.quantile(0.10)),
                "p90_signed_return": float(signed.quantile(0.90)),
                "positive_years": int(pd.DataFrame({"year": sel["as_of"].dt.year.values, "signed": -pd.to_numeric(sel[rcol], errors="coerce").values}).groupby("year")["signed"].mean().gt(0).sum()),
                "years": int(sel["as_of"].dt.year.nunique()),
            })
    return pd.DataFrame(rows)


def _avoidance_evidence(pred: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        base = pred[pred["horizon"] == h].copy()
        rcol = f"fwd_ret_{h}"
        if rcol not in base.columns:
            continue
        ret = pd.to_numeric(base[rcol], errors="coerce")
        base = base[np.isfinite(ret)].copy()
        base["ret"] = pd.to_numeric(base[rcol], errors="coerce")
        baseline_loss = float((base["ret"] < 0).mean())
        baseline_severe = float((base["ret"] <= -0.10).mean())
        baseline_p10 = float(base["ret"].quantile(0.10))
        for tail in TAILS:
            selected_idx: set[int] = set()
            for _, g in base.groupby("as_of", sort=False):
                k = max(1, int(math.ceil(len(g) * tail)))
                selected_idx.update(g.nsmallest(k, "probability_up").index.tolist())
            kept = base.loc[~base.index.isin(selected_idx)]
            excluded = base.loc[base.index.isin(selected_idx)]
            if kept.empty or excluded.empty:
                continue
            rows.append({
                "horizon": h,
                "tail_fraction_excluded": tail,
                "excluded_n": int(len(excluded)),
                "retained_n": int(len(kept)),
                "baseline_long_loss_rate": baseline_loss,
                "retained_long_loss_rate": float((kept["ret"] < 0).mean()),
                "loss_rate_reduction": float(baseline_loss - (kept["ret"] < 0).mean()),
                "baseline_severe_loss_rate_le_10pct": baseline_severe,
                "retained_severe_loss_rate_le_10pct": float((kept["ret"] <= -0.10).mean()),
                "severe_loss_rate_reduction": float(baseline_severe - (kept["ret"] <= -0.10).mean()),
                "baseline_p10_return": baseline_p10,
                "retained_p10_return": float(kept["ret"].quantile(0.10)),
                "p10_return_improvement": float(kept["ret"].quantile(0.10) - baseline_p10),
                "excluded_mean_return": float(excluded["ret"].mean()),
                "excluded_median_return": float(excluded["ret"].median()),
            })
    return pd.DataFrame(rows)


def _merge_features(pred: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    blocked = {"close", "open", "high", "low", "volume"}
    key = ["symbol", "as_of"]
    panel_cols = []
    for c in panel.columns:
        if c in key or c in blocked:
            continue
        if c.startswith(("fwd_", "mfe_", "mae_", "long_barrier_", "short_barrier_", "long_days_", "short_days_")):
            continue
        if pd.api.types.is_numeric_dtype(panel[c]):
            panel_cols.append(c)
    panel_cols = panel_cols[:250]
    merged = pred.merge(panel[key + panel_cols], on=key, how="left", suffixes=("", "__panel"))
    merged, _ = sanitize_nonfinite_numeric(merged)
    return merged


def _feature_attribution(merged: pd.DataFrame, max_features: int) -> pd.DataFrame:
    blocked_prefix = ("fwd_", "mfe_", "mae_", "long_barrier_", "short_barrier_", "long_days_", "short_days_")
    meta = {"horizon", "test_year", "probability_up", "actual_up", "fold_auc", "fold_balanced_accuracy"}
    numeric = [c for c in merged.columns if pd.api.types.is_numeric_dtype(merged[c]) and c not in meta and not c.startswith(blocked_prefix)]
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        d = merged[merged["horizon"] == h].copy()
        if d.empty:
            continue
        sel = _select_tail(d, h, 0.05)
        sel_keys = set(zip(sel["symbol"].astype(str), sel["as_of"].astype(str)))
        key_series = list(zip(d["symbol"].astype(str), d["as_of"].astype(str)))
        is_tail = pd.Series([k in sel_keys for k in key_series], index=d.index)
        rest = d.loc[~is_tail]
        tail = d.loc[is_tail]
        for c in numeric:
            a = pd.to_numeric(tail[c], errors="coerce")
            b = pd.to_numeric(rest[c], errors="coerce")
            a = a[np.isfinite(a)]; b = b[np.isfinite(b)]
            if len(a) < 100 or len(b) < 500:
                continue
            sd = float(b.std(ddof=0))
            if not np.isfinite(sd) or sd <= 1e-12:
                continue
            shift = float((a.mean() - b.mean()) / sd)
            rows.append({
                "horizon": h,
                "feature": c,
                "tail_n": int(len(a)),
                "rest_n": int(len(b)),
                "mean_standardized_shift": shift,
                "abs_standardized_shift": abs(shift),
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["horizon", "abs_standardized_shift"], ascending=[True, False]).groupby("horizon", as_index=False).head(max_features).reset_index(drop=True)


def _rank_features(merged: pd.DataFrame, attribution: pd.DataFrame, max_features: int) -> tuple[pd.DataFrame, list[str]]:
    if attribution.empty:
        return merged.copy(), []
    feats = attribution.groupby("feature")["abs_standardized_shift"].mean().sort_values(ascending=False).head(max_features).index.tolist()
    out = merged.copy()
    for f in feats:
        out[f"rank__{f}"] = out.groupby("as_of")[f].rank(pct=True, method="average")
    return out, feats


def _candidate_mask(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for cond in spec["conditions"]:
        s = pd.to_numeric(df[cond["column"]], errors="coerce")
        if cond["op"] == "LE":
            mask &= s <= cond["value"]
        else:
            mask &= s >= cond["value"]
    return mask.fillna(False)


def _candidate_stats(df: pd.DataFrame, h: int, spec: dict[str, Any]) -> dict[str, Any] | None:
    rcol = f"fwd_ret_{h}"
    d = df[df["horizon"] == h].copy()
    if d.empty or rcol not in d.columns:
        return None
    mask = _candidate_mask(d, spec)
    s = d.loc[mask].copy()
    r = pd.to_numeric(s[rcol], errors="coerce")
    s = s[np.isfinite(r)].copy(); r = pd.to_numeric(s[rcol], errors="coerce")
    if s.empty:
        return None
    signed = -r
    sym = signed.groupby(s["symbol"].astype(str)).sum().abs().sort_values(ascending=False)
    denom = float(sym.sum())
    top10 = float(sym.head(10).sum() / denom) if denom > 0 else 1.0
    years = signed.groupby(s["as_of"].dt.year).mean()
    return {
        "n": int(len(s)),
        "unique_symbols": int(s["symbol"].nunique()),
        "short_win_rate": float((r < 0).mean()),
        "mean_signed_return": float(signed.mean()),
        "median_signed_return": float(signed.median()),
        "positive_years": int((years > 0).sum()),
        "years": int(len(years)),
        "top10_symbol_abs_contribution_fraction": top10,
    }


def _rule_discovery(ranked: pd.DataFrame, attribution: pd.DataFrame, feats: list[str], cfg: BearishResearchConfig) -> pd.DataFrame:
    if not feats:
        return pd.DataFrame()
    direction: dict[tuple[int, str], str] = {}
    for _, r in attribution.iterrows():
        direction[(int(r["horizon"]), str(r["feature"]))] = "LE" if float(r["mean_standardized_shift"]) < 0 else "GE"
    specs: list[dict[str, Any]] = []
    for h in HORIZONS:
        hf = [f for f in feats if (h, f) in direction][: cfg.max_rule_features]
        for f in hf:
            op = direction[(h, f)]
            value = 0.20 if op == "LE" else 0.80
            specs.append({"horizon": h, "conditions": [{"column": f"rank__{f}", "op": op, "value": value}], "label": f"{f}:{op}{value}"})
        for i in range(min(6, len(hf))):
            for j in range(i + 1, min(6, len(hf))):
                f1, f2 = hf[i], hf[j]
                c1 = {"column": f"rank__{f1}", "op": direction[(h, f1)], "value": 0.25 if direction[(h, f1)] == "LE" else 0.75}
                c2 = {"column": f"rank__{f2}", "op": direction[(h, f2)], "value": 0.25 if direction[(h, f2)] == "LE" else 0.75}
                specs.append({"horizon": h, "conditions": [c1, c2], "label": f"{f1}&{f2}"})
    rows: list[dict[str, Any]] = []
    for idx, spec in enumerate(specs, 1):
        h = spec["horizon"]
        part_stats: dict[str, dict[str, Any] | None] = {}
        for name, (lo, hi) in RESEARCH_PARTITIONS.items():
            part = ranked[(ranked["as_of"].dt.year >= lo) & (ranked["as_of"].dt.year <= hi)]
            part_stats[name] = _candidate_stats(part, h, spec)
        full = _candidate_stats(ranked, h, spec)
        if not full:
            continue
        robust = (
            full["n"] >= cfg.minimum_candidate_rows
            and full["unique_symbols"] >= cfg.minimum_candidate_symbols
            and full["top10_symbol_abs_contribution_fraction"] <= cfg.maximum_top10_symbol_fraction
            and all(
                s is not None
                and s["n"] >= cfg.minimum_partition_rows
                and s["short_win_rate"] > 0.50
                and s["mean_signed_return"] > 0
                for s in part_stats.values()
            )
        )
        row: dict[str, Any] = {
            "candidate_id": f"M77B-{idx:05d}",
            "horizon": h,
            "label": spec["label"],
            "conditions_json": json.dumps(spec["conditions"], sort_keys=True),
            **full,
            "passes_research_robustness": bool(robust),
        }
        for name, stats in part_stats.items():
            prefix = name.lower()
            if stats:
                for k in ("n", "unique_symbols", "short_win_rate", "mean_signed_return", "median_signed_return"):
                    row[f"{prefix}_{k}"] = stats[k]
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["passes_research_robustness", "mean_signed_return", "short_win_rate"], ascending=[False, False, False]).reset_index(drop=True)


def _barrier_evidence(panel: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    merge_cols = ["symbol", "as_of"] + [c for c in panel.columns if c.startswith(("short_barrier_", "short_days_"))]
    b = panel[merge_cols].drop_duplicates(["symbol", "as_of"])
    for h in HORIZONS:
        for tail in TAILS:
            sel = _select_tail(pred, h, tail).merge(b, on=["symbol", "as_of"], how="left")
            tag_end = f"_h{h}"
            for c in [x for x in sel.columns if x.startswith("short_barrier_") and x.endswith(tag_end)]:
                vals = pd.to_numeric(sel[c], errors="coerce").dropna()
                if vals.empty:
                    continue
                wins = int((vals == 1).sum()); losses = int((vals == -1).sum())
                resolved = wins + losses
                parts = c.replace("short_barrier_t", "").split("_s")
                target = float(parts[0].replace("p", "."))
                stop = float(parts[1].split("_h")[0].replace("p", "."))
                expectancy = ((wins * target) - (losses * stop)) / resolved if resolved else np.nan
                rows.append({
                    "horizon": h,
                    "tail_fraction": tail,
                    "target_atr": target,
                    "stop_atr": stop,
                    "n": int(len(sel)),
                    "resolved_n": int(resolved),
                    "wins": wins,
                    "losses": losses,
                    "resolved_win_rate": float(wins / resolved) if resolved else np.nan,
                    "expectancy_r": float(expectancy) if np.isfinite(expectancy) else np.nan,
                })
    return pd.DataFrame(rows)


def _write_report(out: Path, summary: dict[str, Any], tails: pd.DataFrame, rules: pd.DataFrame, avoidance: pd.DataFrame) -> None:
    lines = [
        "# M77.22 Bearish Deterioration & Avoidance Edge Research",
        "",
        f"Status: **{summary['status']}**",
        "",
        "This branch uses Development-era evidence only. 2018–2022 Validation is treated as consumed and is not read. 2023+ Final Holdout remains sealed.",
        "",
        "## Headline",
        "",
        f"- Development prediction rows: {summary['development_prediction_rows']:,}",
        f"- Development panel rows: {summary['development_panel_rows']:,}",
        f"- Robust bearish rule candidates: {summary['robust_bearish_rule_candidates']}",
        f"- Validation rows read: 0",
        f"- Final Holdout rows read: 0",
        "",
    ]
    if not tails.empty:
        best = tails.sort_values(["short_win_rate_edge", "mean_signed_return"], ascending=False).iloc[0]
        lines += ["## Strongest Development bearish tail", "", f"Horizon {int(best.horizon)} sessions, bottom {100*best.tail_fraction:.1f}%: short win rate {best.short_win_rate:.2%}, edge {best.short_win_rate_edge:.2%}, median signed return {best.median_signed_return:.2%}.", ""]
    if not rules.empty:
        r = rules[rules["passes_research_robustness"]]
        if not r.empty:
            top = r.iloc[0]
            lines += ["## Strongest explainable research rule", "", f"{top.candidate_id}: {top.label}; horizon {int(top.horizon)}; short win rate {top.short_win_rate:.2%}; median signed return {top.median_signed_return:.2%}; {int(top.unique_symbols)} symbols.", ""]
    if not avoidance.empty:
        a = avoidance.sort_values("severe_loss_rate_reduction", ascending=False).iloc[0]
        lines += ["## Avoidance value", "", f"Excluding the bottom {100*a.tail_fraction_excluded:.1f}% at {int(a.horizon)} sessions reduced the <=-10% long-loss rate by {a.severe_loss_rate_reduction:.2%} in Development research.", ""]
    lines += ["## Governance", "", "- Production authority effect: NONE", "- Polygon API calls: NONE", "- 2018–2022 Validation: NOT READ", "- 2023+ Final Holdout: SEALED", "- Any candidate produced here remains RESEARCH_ONLY until separately preregistered and tested on untouched evidence.", ""]
    (out / "BEARISH_DETERIORATION_AVOIDANCE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run_lab(cfg: BearishResearchConfig) -> dict[str, Any]:
    cfg.validate()
    root = Path(cfg.project_root).expanduser().resolve()
    pred_path = _resolve(root, cfg.development_predictions)
    panel_path = _resolve(root, cfg.development_panel)
    out = _resolve(root, cfg.output_root)
    out.mkdir(parents=True, exist_ok=True)

    pred = _load_predictions(pred_path)
    panel = _load_panel(panel_path)
    pred["research_partition"] = _partition(pred["as_of"].dt.year)
    pred = pred[pred["research_partition"] != "OUTSIDE"].copy()

    tails = _tail_evidence(pred)
    avoidance = _avoidance_evidence(pred)
    merged = _merge_features(pred, panel)
    attribution = _feature_attribution(merged, cfg.max_attribution_features)
    ranked, feats = _rank_features(merged, attribution, cfg.max_rule_features)
    rules = _rule_discovery(ranked, attribution, feats, cfg)
    barriers = _barrier_evidence(panel, pred)

    _atomic_csv(out / "bearish_tail_evidence.csv", tails)
    _atomic_csv(out / "avoidance_filter_evidence.csv", avoidance)
    _atomic_csv(out / "feature_deterioration_attribution.csv", attribution)
    _atomic_csv(out / "bearish_hypothesis_registry.csv", rules)
    _atomic_csv(out / "defined_risk_bearish_evidence.csv", barriers)

    robust_n = int(rules["passes_research_robustness"].sum()) if not rules.empty else 0
    summary = {
        "version": VERSION,
        "status": "COMPLETE",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_boundary": "2017-12-31",
        "development_prediction_rows": int(len(pred)),
        "development_panel_rows": int(len(panel)),
        "symbols": int(pred["symbol"].nunique()),
        "horizons": list(HORIZONS),
        "tail_evidence_rows": int(len(tails)),
        "avoidance_evidence_rows": int(len(avoidance)),
        "attribution_rows": int(len(attribution)),
        "rule_candidates": int(len(rules)),
        "robust_bearish_rule_candidates": robust_n,
        "defined_risk_rows": int(len(barriers)),
        "validation_partition_opened": False,
        "validation_rows_read": 0,
        "consumed_validation_reused_for_tuning": False,
        "final_holdout_opened": False,
        "final_holdout_rows_read": 0,
        "polygon_api_called": False,
        "production_authority_effect": False,
        "next_step": "REVIEW_DEVELOPMENT_ONLY_BEARISH_CANDIDATES_AND_FREEZE_NEW_PROTOCOL_BEFORE_ANY_FINAL_HOLDOUT_USE",
    }
    _atomic_json(out / "bearish_deterioration_summary.json", summary)
    _atomic_json(out / "run_manifest.json", {"config": asdict(cfg), "summary": summary, "governance": {"validation_source_allowed": False, "final_holdout_allowed": False}})
    _write_report(out, summary, tails, rules, avoidance)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M77.22 Development-only Bearish Deterioration & Avoidance Edge Research")
    p.add_argument("--project-root", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_lab(BearishResearchConfig(project_root=args.project_root))
    print(json.dumps(summary, indent=2, sort_keys=True, default=_json_default))
    return 0
