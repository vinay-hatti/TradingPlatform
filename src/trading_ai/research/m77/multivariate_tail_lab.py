from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import Pipeline

from trading_ai.research.m77.edge_discovery_lab import (
    EdgeLabError,
    _candidate_mask,
    _json_default,
    _numeric_feature_columns,
    sanitize_nonfinite_numeric,
)

VERSION = "M77.21.2-MULTIVARIATE-PREDICTIVE-TAIL-1.0"
DEVELOPMENT_END = pd.Timestamp("2017-12-31")
DEFAULT_HORIZONS = (15, 20, 30, 45, 60)
DEFAULT_TAIL_FRACTIONS = (0.01, 0.025, 0.05, 0.10, 0.20)
DEFAULT_TOP_K = (1, 3, 5, 10, 20)
SEALED_TOKENS = ("validation_target", "final_holdout", "validation_scoring", "final_holdout_scoring")


@dataclass(frozen=True)
class TailLabConfig:
    project_root: str
    source_lab_root: str = "research_data/m77_21_0/edge_discovery_lab"
    output_root: str = "research_data/m77_21_2/multivariate_predictive_tail_lab"
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    tail_fractions: tuple[float, ...] = DEFAULT_TAIL_FRACTIONS
    top_k: tuple[int, ...] = DEFAULT_TOP_K
    first_test_year: int = 2008
    last_test_year: int = 2017
    max_features: int = 80
    min_train_rows: int = 3000
    min_test_rows: int = 500
    min_train_years: int = 5
    random_seed: int = 77212
    model_max_iter: int = 150
    model_leaf_nodes: int = 15
    model_min_samples_leaf: int = 100
    resume: bool = True
    execution_mode: str = "DEVELOPMENT_WALK_FORWARD_ONLY"

    def validate(self) -> None:
        if self.execution_mode != "DEVELOPMENT_WALK_FORWARD_ONLY":
            raise EdgeLabError("M77.21.2 authorizes DEVELOPMENT_WALK_FORWARD_ONLY")
        if self.last_test_year > 2017:
            raise EdgeLabError("M77.21.2 cannot open post-2017 validation/final-holdout data")
        if self.first_test_year < 2004 or self.first_test_year > self.last_test_year:
            raise EdgeLabError("invalid walk-forward year range")
        if self.max_features < 5:
            raise EdgeLabError("max_features must be >= 5")
        if any(h < 1 for h in self.horizons):
            raise EdgeLabError("horizons must be positive")
        if any(not 0 < f <= 0.5 for f in self.tail_fractions):
            raise EdgeLabError("tail fractions must be in (0, 0.5]")


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


def _assert_paths(cfg: TailLabConfig) -> tuple[Path, Path, Path]:
    root = Path(cfg.project_root).resolve()
    src = _resolve(root, cfg.source_lab_root)
    out = _resolve(root, cfg.output_root)
    for label, p in (("source_lab_root", src), ("output_root", out)):
        text = str(p).lower()
        if any(tok in text for tok in SEALED_TOKENS):
            raise EdgeLabError(f"{label} points at sealed path: {p}")
    if "research_data" not in out.parts:
        raise EdgeLabError("output_root must be under research_data")
    panel_path = src / "checkpoints" / "panel.pkl.gz"
    if not panel_path.exists():
        raise EdgeLabError(f"required M77.21 panel missing: {panel_path}")
    return root, src, out


def _load_panel(panel_path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    panel = pd.read_pickle(panel_path, compression="gzip")
    if "as_of" not in panel or "symbol" not in panel:
        raise EdgeLabError("cached panel missing as_of/symbol")
    panel["as_of"] = pd.to_datetime(panel["as_of"], errors="coerce")
    panel = panel.dropna(subset=["as_of", "symbol"]).copy()
    if panel["as_of"].max() > DEVELOPMENT_END:
        raise EdgeLabError(
            f"cached panel exceeds Development boundary: {panel['as_of'].max()} > {DEVELOPMENT_END.date()}"
        )
    panel, counts = sanitize_nonfinite_numeric(panel)
    panel = panel.sort_values(["as_of", "symbol"]).reset_index(drop=True)
    return panel, counts


def _select_fold_features(train: pd.DataFrame, numeric: Sequence[str], max_features: int) -> list[str]:
    scored: list[tuple[str, int, float]] = []
    for col in numeric:
        x = pd.to_numeric(train[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        n = int(x.notna().sum())
        if n == 0:
            continue
        var = float(x.var(skipna=True))
        if not np.isfinite(var):
            var = 0.0
        scored.append((col, n, var))
    return [x[0] for x in sorted(scored, key=lambda z: (z[1], z[2]), reverse=True)[:max_features]]


def _model(cfg: TailLabConfig) -> Pipeline:
    return Pipeline(
        [
            ("imp", SimpleImputer(strategy="median")),
            (
                "m",
                HistGradientBoostingClassifier(
                    max_iter=cfg.model_max_iter,
                    max_leaf_nodes=cfg.model_leaf_nodes,
                    learning_rate=0.05,
                    l2_regularization=1.0,
                    min_samples_leaf=cfg.model_min_samples_leaf,
                    random_state=cfg.random_seed,
                ),
            ),
        ]
    )


def _embargo_days(horizon: int) -> int:
    # Conservative conversion from trading sessions to calendar days plus a buffer.
    # This prevents train outcomes from extending into the test year.
    return int(math.ceil(horizon * 1.7) + 10)


def _fold_cache_path(checkpoint_root: Path, horizon: int, year: int) -> Path:
    return checkpoint_root / f"walk_forward_h{horizon}_{year}.csv.gz"


def walk_forward_predictions(panel: pd.DataFrame, cfg: TailLabConfig, checkpoint_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    numeric = _numeric_feature_columns(panel)
    all_predictions: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []
    checkpoint_root.mkdir(parents=True, exist_ok=True)

    min_year = int(panel["as_of"].dt.year.min())
    for horizon in cfg.horizons:
        outcome = f"fwd_ret_{horizon}"
        if outcome not in panel:
            continue
        for test_year in range(cfg.first_test_year, cfg.last_test_year + 1):
            test_start = pd.Timestamp(f"{test_year}-01-01")
            test_end = pd.Timestamp(f"{test_year}-12-31")
            embargo_cutoff = test_start - pd.Timedelta(days=_embargo_days(horizon))
            train_years = test_year - min_year
            if train_years < cfg.min_train_years:
                continue
            cache = _fold_cache_path(checkpoint_root, horizon, test_year)
            meta_cache = checkpoint_root / f"walk_forward_h{horizon}_{test_year}.meta.json"
            attr_cache = checkpoint_root / f"walk_forward_h{horizon}_{test_year}.attr.csv.gz"
            if cfg.resume and cache.exists():
                pred = pd.read_csv(cache, compression="gzip", parse_dates=["as_of"])
                all_predictions.append(pred)
                if meta_cache.exists():
                    meta = json.loads(meta_cache.read_text(encoding="utf-8"))
                    meta["status"] = "RESUMED"
                    fold_rows.append(meta)
                elif not pred.empty:
                    fold_rows.append({
                        "horizon": horizon, "test_year": test_year, "train_end": str(embargo_cutoff.date()),
                        "test_n": int(len(pred)), "test_symbols": int(pred["symbol"].nunique()), "status": "RESUMED",
                    })
                if attr_cache.exists():
                    cached_attr = pd.read_csv(attr_cache, compression="gzip")
                    attribution_rows.extend(cached_attr.to_dict("records"))
                continue

            train = panel[(panel["as_of"] < embargo_cutoff)].dropna(subset=[outcome]).copy()
            test = panel[panel["as_of"].between(test_start, test_end, inclusive="both")].dropna(subset=[outcome]).copy()
            if len(train) < cfg.min_train_rows or len(test) < cfg.min_test_rows:
                fold_rows.append({
                    "horizon": horizon,
                    "test_year": test_year,
                    "train_n": len(train),
                    "test_n": len(test),
                    "status": "SKIPPED_INSUFFICIENT_ROWS",
                })
                continue
            cols = _select_fold_features(train, numeric, cfg.max_features)
            if not cols:
                continue
            Xtr = train[cols].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
            Xte = test[cols].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
            ytr = (train[outcome] > 0).astype(int)
            yte = (test[outcome] > 0).astype(int)
            model = _model(cfg)
            model.fit(Xtr, ytr)
            probability = model.predict_proba(Xte)[:, 1]
            pred_label = (probability >= 0.5).astype(int)
            auc = roc_auc_score(yte, probability) if yte.nunique() > 1 else np.nan
            bal = balanced_accuracy_score(yte, pred_label)

            keep_cols = [
                "symbol", "as_of", "close", outcome,
                f"fwd_ret_{horizon}_delay1", f"mfe_{horizon}", f"mae_{horizon}",
                f"mfe_atr_{horizon}", f"mae_atr_{horizon}",
            ]
            keep_cols = [c for c in keep_cols if c in test.columns]
            pred = test[keep_cols].copy()
            pred["horizon"] = horizon
            pred["test_year"] = test_year
            pred["probability_up"] = probability
            pred["actual_up"] = yte.to_numpy()
            pred["fold_auc"] = auc
            pred["fold_balanced_accuracy"] = bal
            pred["train_end"] = embargo_cutoff.date().isoformat()
            _atomic_csv(cache, pred, compression="gzip")
            all_predictions.append(pred)

            fold_meta = {
                "horizon": horizon, "test_year": test_year,
                "train_start": str(train["as_of"].min().date()), "train_end": str(embargo_cutoff.date()),
                "train_n": int(len(train)), "train_symbols": int(train["symbol"].nunique()),
                "test_n": int(len(test)), "test_symbols": int(test["symbol"].nunique()),
                "feature_count": len(cols), "test_auc": float(auc) if np.isfinite(auc) else np.nan,
                "test_balanced_accuracy": float(bal), "status": "COMPLETE",
            }
            fold_rows.append(fold_meta)
            _atomic_json(meta_cache, fold_meta)

            fold_attr_start = len(attribution_rows)
            # Explainability fingerprint: how high/low predicted tails differ from the full test population.
            for frac in (0.01, 0.05, 0.10):
                k = max(1, int(len(test) * frac))
                order = np.argsort(probability)
                for direction, idxs in (("LONG", order[-k:]), ("SHORT", order[:k])):
                    base = Xte
                    tail = Xte.iloc[idxs]
                    for col in cols:
                        b = base[col]
                        t = tail[col]
                        sd = float(b.std(skipna=True))
                        shift = float((t.mean(skipna=True) - b.mean(skipna=True)) / sd) if np.isfinite(sd) and sd > 1e-12 else np.nan
                        if np.isfinite(shift):
                            attribution_rows.append({
                                "horizon": horizon, "test_year": test_year, "tail_fraction": frac,
                                "direction": direction, "feature": col,
                                "standardized_mean_shift": shift, "abs_standardized_mean_shift": abs(shift),
                            })
            fold_attrs = pd.DataFrame(attribution_rows[fold_attr_start:])
            _atomic_csv(attr_cache, fold_attrs, compression="gzip")

    predictions = pd.concat(all_predictions, ignore_index=True, sort=False) if all_predictions else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    attrs = pd.DataFrame(attribution_rows)
    return predictions, folds, attrs


def _signed_path(frame: pd.DataFrame, horizon: int, direction: str) -> pd.DataFrame:
    sign = 1.0 if direction == "LONG" else -1.0
    out = pd.DataFrame(index=frame.index)
    raw = pd.to_numeric(frame[f"fwd_ret_{horizon}"], errors="coerce")
    out["signed_return"] = raw * sign
    if f"fwd_ret_{horizon}_delay1" in frame:
        out["signed_delay1_return"] = pd.to_numeric(frame[f"fwd_ret_{horizon}_delay1"], errors="coerce") * sign
    if direction == "LONG":
        if f"mfe_{horizon}" in frame: out["favorable_excursion"] = pd.to_numeric(frame[f"mfe_{horizon}"], errors="coerce")
        if f"mae_{horizon}" in frame: out["adverse_excursion"] = pd.to_numeric(frame[f"mae_{horizon}"], errors="coerce")
        if f"mfe_atr_{horizon}" in frame: out["favorable_excursion_atr"] = pd.to_numeric(frame[f"mfe_atr_{horizon}"], errors="coerce")
        if f"mae_atr_{horizon}" in frame: out["adverse_excursion_atr"] = pd.to_numeric(frame[f"mae_atr_{horizon}"], errors="coerce")
    else:
        if f"mae_{horizon}" in frame: out["favorable_excursion"] = -pd.to_numeric(frame[f"mae_{horizon}"], errors="coerce")
        if f"mfe_{horizon}" in frame: out["adverse_excursion"] = -pd.to_numeric(frame[f"mfe_{horizon}"], errors="coerce")
        if f"mae_atr_{horizon}" in frame: out["favorable_excursion_atr"] = -pd.to_numeric(frame[f"mae_atr_{horizon}"], errors="coerce")
        if f"mfe_atr_{horizon}" in frame: out["adverse_excursion_atr"] = -pd.to_numeric(frame[f"mfe_atr_{horizon}"], errors="coerce")
    return out


def walk_forward_tail_evidence(predictions: pd.DataFrame, cfg: TailLabConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    if predictions.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    for horizon in cfg.horizons:
        ph = predictions[predictions["horizon"] == horizon].copy()
        if ph.empty:
            continue
        raw_all = pd.to_numeric(ph[f"fwd_ret_{horizon}"], errors="coerce")
        for frac in cfg.tail_fractions:
            # Tail is selected independently within each prediction year, preventing later years from dominating ranks.
            selected_parts: dict[str, list[pd.DataFrame]] = {"LONG": [], "SHORT": []}
            for year, yf in ph.groupby("test_year", sort=True):
                k = max(1, int(len(yf) * frac))
                ordered = yf.sort_values("probability_up")
                selected_parts["LONG"].append(ordered.tail(k))
                selected_parts["SHORT"].append(ordered.head(k))
            for direction in ("LONG", "SHORT"):
                sel = pd.concat(selected_parts[direction], ignore_index=True) if selected_parts[direction] else pd.DataFrame()
                if sel.empty:
                    continue
                sign = 1.0 if direction == "LONG" else -1.0
                vals = pd.to_numeric(sel[f"fwd_ret_{horizon}"], errors="coerce") * sign
                base = raw_all * sign
                rows.append({
                    "horizon": horizon,
                    "tail_fraction": frac,
                    "direction": direction,
                    "n": int(vals.notna().sum()),
                    "unique_symbols": int(sel["symbol"].nunique()),
                    "years": int(sel["test_year"].nunique()),
                    "win_rate": float((vals > 0).mean()),
                    "mean_return": float(vals.mean()),
                    "median_return": float(vals.median()),
                    "baseline_win_rate": float((base > 0).mean()),
                    "baseline_mean_return": float(base.mean()),
                    "win_rate_edge": float((vals > 0).mean() - (base > 0).mean()),
                    "mean_return_edge": float(vals.mean() - base.mean()),
                    "net_mean_return_10bps": float(vals.mean() - 0.001),
                    "net_mean_return_25bps": float(vals.mean() - 0.0025),
                    "net_mean_return_50bps": float(vals.mean() - 0.005),
                })
                path = _signed_path(sel, horizon, direction)
                p = {
                    "horizon": horizon,
                    "tail_fraction": frac,
                    "direction": direction,
                    "n": int(len(path)),
                }
                for c in path.columns:
                    s = pd.to_numeric(path[c], errors="coerce")
                    p[f"mean_{c}"] = float(s.mean())
                    p[f"median_{c}"] = float(s.median())
                    p[f"p10_{c}"] = float(s.quantile(0.10))
                    p[f"p90_{c}"] = float(s.quantile(0.90))
                path_rows.append(p)

                for year, ys in sel.groupby("test_year", sort=True):
                    yvals = pd.to_numeric(ys[f"fwd_ret_{horizon}"], errors="coerce") * sign
                    year_rows.append({
                        "horizon": horizon,
                        "tail_fraction": frac,
                        "direction": direction,
                        "test_year": int(year),
                        "n": int(yvals.notna().sum()),
                        "unique_symbols": int(ys["symbol"].nunique()),
                        "win_rate": float((yvals > 0).mean()),
                        "mean_return": float(yvals.mean()),
                        "median_return": float(yvals.median()),
                    })
    return pd.DataFrame(rows), pd.DataFrame(path_rows), pd.DataFrame(year_rows)


def barrier_tail_evidence(panel: pd.DataFrame, predictions: pd.DataFrame, cfg: TailLabConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if predictions.empty:
        return pd.DataFrame()
    key_cols = ["symbol", "as_of"]
    barrier_cols = [c for c in panel.columns if c.startswith(("long_barrier_", "short_barrier_", "long_days_", "short_days_"))]
    if not barrier_cols:
        return pd.DataFrame()
    source = panel[key_cols + barrier_cols].copy()
    for horizon in cfg.horizons:
        ph = predictions[predictions["horizon"] == horizon].merge(source, on=key_cols, how="left", validate="many_to_one")
        if ph.empty:
            continue
        for frac in cfg.tail_fractions:
            parts = {"LONG": [], "SHORT": []}
            for _, yf in ph.groupby("test_year", sort=True):
                k = max(1, int(len(yf) * frac)); ordered = yf.sort_values("probability_up")
                parts["LONG"].append(ordered.tail(k)); parts["SHORT"].append(ordered.head(k))
            for direction in ("LONG", "SHORT"):
                sel = pd.concat(parts[direction], ignore_index=True) if parts[direction] else pd.DataFrame()
                prefix = direction.lower()
                for target, stop in ((1.0,1.0),(1.5,1.0),(2.0,1.0),(3.0,1.0),(2.0,1.5)):
                    tag = f"t{str(target).replace('.', 'p')}_s{str(stop).replace('.', 'p')}_h{horizon}"
                    col = f"{prefix}_barrier_{tag}"
                    dcol = f"{prefix}_days_{tag}"
                    if col not in sel:
                        continue
                    vals = pd.to_numeric(sel[col], errors="coerce").dropna()
                    resolved = vals[vals != 0]
                    wins = int((resolved == 1).sum()); losses = int((resolved == -1).sum()); unresolved = int((vals == 0).sum())
                    days = pd.to_numeric(sel.loc[sel[col].notna(), dcol], errors="coerce") if dcol in sel else pd.Series(dtype=float)
                    rows.append({
                        "horizon": horizon, "tail_fraction": frac, "direction": direction,
                        "target_atr": target, "stop_atr": stop, "n": int(len(vals)),
                        "resolved_n": int(len(resolved)), "wins": wins, "losses": losses,
                        "unresolved": unresolved,
                        "resolved_win_rate": wins / max(wins + losses, 1),
                        "expectancy_r": (wins * target - losses * stop) / max(wins + losses, 1),
                        "mean_days_to_resolution": float(days.mean()) if len(days) else np.nan,
                    })
    return pd.DataFrame(rows)


def corrected_candidate_stationarity(panel: pd.DataFrame, source_lab_root: Path) -> pd.DataFrame:
    registry_path = source_lab_root / "edge_registry.csv"
    if not registry_path.exists():
        return pd.DataFrame()
    reg = pd.read_csv(registry_path)
    if "destruction_pass" not in reg:
        return pd.DataFrame()
    survivors = reg[reg["destruction_pass"] == True].copy()
    rows: list[dict[str, Any]] = []
    eras = (("2003_2007", 2003, 2007), ("2008_2012", 2008, 2012), ("2013_2017", 2013, 2017))
    for _, rec in survivors.iterrows():
        h = int(rec["horizon"]); direction = str(rec["direction"]); sign = 1.0 if direction == "LONG" else -1.0
        mask = _candidate_mask(panel, rec)
        selected = panel.loc[mask, ["symbol", "as_of", "close", f"fwd_ret_{h}"]].dropna(subset=[f"fwd_ret_{h}"]).copy()
        for label, lo, hi in eras:
            sub = selected[selected["as_of"].dt.year.between(lo, hi)].copy()
            vals = pd.to_numeric(sub[f"fwd_ret_{h}"], errors="coerce") * sign
            symbol_means = sub.assign(signed=vals).groupby("symbol")["signed"].mean() if len(sub) else pd.Series(dtype=float)
            rows.append({
                "candidate_key": rec.get("candidate_key"), "edge_id": rec.get("edge_id"),
                "feature": rec.get("feature"), "operator": rec.get("operator"),
                "lower": rec.get("lower"), "upper": rec.get("upper"), "value": rec.get("value"),
                "direction": direction, "horizon": h, "era": label,
                "n": int(vals.notna().sum()), "unique_symbols": int(sub["symbol"].nunique()),
                "win_rate": float((vals > 0).mean()) if len(vals) else np.nan,
                "mean_return": float(vals.mean()) if len(vals) else np.nan,
                "median_return": float(vals.median()) if len(vals) else np.nan,
                "positive_symbol_fraction": float((symbol_means > 0).mean()) if len(symbol_means) else np.nan,
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        gate = out.groupby("candidate_key").agg(
            eras_with_samples=("n", lambda x: int((x >= 50).sum())),
            positive_mean_eras=("mean_return", lambda x: int((x > 0).sum())),
            positive_win_eras=("win_rate", lambda x: int((x > 0.5).sum())),
        ).reset_index()
        gate["corrected_era_stationarity_pass"] = (
            (gate["eras_with_samples"] >= 3) & (gate["positive_mean_eras"] >= 2) & (gate["positive_win_eras"] >= 2)
        )
        out = out.merge(gate, on="candidate_key", how="left")
    return out


def _weekly_portfolio_returns(panel: pd.DataFrame, selections: pd.DataFrame, horizon: int, direction: str, top_k: int, cost_bps: float) -> pd.DataFrame:
    if selections.empty:
        return pd.DataFrame()
    px = panel[["symbol", "as_of", "close"]].dropna().copy()
    px = px.sort_values(["symbol", "as_of"])
    px["prev_close"] = px.groupby("symbol")["close"].shift(1)
    px["weekly_return"] = px["close"] / px["prev_close"] - 1.0
    lookup = px.set_index(["symbol", "as_of"])["weekly_return"]
    all_dates = sorted(panel["as_of"].drop_duplicates())
    date_pos = {d: i for i, d in enumerate(all_dates)}
    hold_weeks = max(1, int(round(horizon / 5.0)))
    sign = 1.0 if direction == "LONG" else -1.0
    positions: list[dict[str, Any]] = []
    for as_of, grp in selections.groupby("as_of", sort=True):
        ordered = grp.sort_values("probability_up", ascending=(direction == "SHORT")).head(top_k)
        start_idx = date_pos.get(as_of)
        if start_idx is None:
            continue
        end_idx = min(len(all_dates) - 1, start_idx + hold_weeks)
        for _, r in ordered.iterrows():
            positions.append({"symbol": r["symbol"], "start_idx": start_idx, "end_idx": end_idx})
    if not positions:
        return pd.DataFrame()
    rows=[]
    for i, dt in enumerate(all_dates):
        active=[p for p in positions if p["start_idx"] < i <= p["end_idx"]]
        if not active:
            continue
        vals=[]
        for p in active:
            try: rv=float(lookup.loc[(p["symbol"], dt)])
            except Exception: continue
            if np.isfinite(rv): vals.append(rv*sign)
        if not vals: continue
        entering=sum(1 for p in positions if p["start_idx"]==i)
        exiting=sum(1 for p in positions if p["end_idx"]==i)
        # Approximate round-trip cost allocated to the current active book.
        cost=(entering+exiting)*cost_bps/10000.0/max(len(active),1)
        rows.append({"as_of":dt,"gross_return":float(np.mean(vals)),"net_return":float(np.mean(vals)-cost),"active_slots":len(active),"entering":entering,"exiting":exiting})
    return pd.DataFrame(rows)


def portfolio_evidence(panel: pd.DataFrame, predictions: pd.DataFrame, cfg: TailLabConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics=[]; curves=[]
    if predictions.empty: return pd.DataFrame(), pd.DataFrame()
    for horizon in cfg.horizons:
        ph=predictions[predictions["horizon"]==horizon].copy()
        if ph.empty: continue
        # At each weekly date choose from truly walk-forward probabilities available on that date.
        for direction in ("LONG","SHORT"):
            for k in cfg.top_k:
                for cost in (0.0,10.0,25.0,50.0):
                    curve=_weekly_portfolio_returns(panel,ph,horizon,direction,k,cost)
                    if curve.empty: continue
                    r=curve["net_return"].fillna(0.0)
                    equity=(1.0+r).cumprod(); peak=equity.cummax(); dd=equity/peak-1.0
                    years=max((curve["as_of"].max()-curve["as_of"].min()).days/365.25,1/52)
                    cagr=float(equity.iloc[-1]**(1/years)-1.0) if equity.iloc[-1]>0 else -1.0
                    sd=float(r.std(ddof=1)); downside=float(r[r<0].std(ddof=1))
                    pos=float(r[r>0].sum()); neg=float(-r[r<0].sum())
                    metrics.append({
                        "horizon":horizon,"direction":direction,"top_k":k,"cost_bps_round_trip_leg":cost,
                        "weeks":int(len(r)),"cagr":cagr,"mean_weekly_return":float(r.mean()),
                        "annualized_return_arithmetic":float(r.mean()*52),
                        "sharpe":float(r.mean()/sd*math.sqrt(52)) if np.isfinite(sd) and sd>1e-12 else np.nan,
                        "sortino":float(r.mean()/downside*math.sqrt(52)) if np.isfinite(downside) and downside>1e-12 else np.nan,
                        "max_drawdown":float(dd.min()),"positive_week_fraction":float((r>0).mean()),
                        "profit_factor":pos/neg if neg>1e-12 else np.nan,
                        "mean_active_slots":float(curve["active_slots"].mean()),"max_active_slots":int(curve["active_slots"].max()),
                    })
                    c=curve.copy(); c["horizon"]=horizon;c["direction"]=direction;c["top_k"]=k;c["cost_bps_round_trip_leg"]=cost;c["equity"]=equity;c["drawdown"]=dd
                    curves.append(c)
    return pd.DataFrame(metrics), pd.concat(curves,ignore_index=True) if curves else pd.DataFrame()


def summarize_attribution(attrs: pd.DataFrame) -> pd.DataFrame:
    if attrs.empty: return attrs
    g=attrs.groupby(["horizon","tail_fraction","direction","feature"],as_index=False).agg(
        folds=("test_year","nunique"),
        mean_standardized_shift=("standardized_mean_shift","mean"),
        median_standardized_shift=("standardized_mean_shift","median"),
        mean_abs_standardized_shift=("abs_standardized_mean_shift","mean"),
    )
    return g.sort_values(["horizon","tail_fraction","direction","mean_abs_standardized_shift"],ascending=[True,True,True,False])


def _monotonicity(tail: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    if tail.empty:return pd.DataFrame()
    for (h,d),g in tail.groupby(["horizon","direction"]):
        g=g.sort_values("tail_fraction",ascending=False) # 20% -> 1%
        y=g["win_rate"].to_numpy(float); x=np.arange(len(y),dtype=float)
        # Desired: win rate should generally improve as tail becomes more selective.
        diffs=np.diff(y)
        rows.append({"horizon":h,"direction":d,"levels":len(g),"strict_improvement_steps":int((diffs>=0).sum()),"total_steps":max(len(diffs),0),"monotonic_fraction":float((diffs>=0).mean()) if len(diffs) else np.nan,"win_rate_20pct":float(g.iloc[0]["win_rate"]),"win_rate_1pct":float(g.iloc[-1]["win_rate"])})
    return pd.DataFrame(rows)


def write_report(path: Path, summary: dict[str,Any], tail: pd.DataFrame, portfolio: pd.DataFrame, stationarity: pd.DataFrame) -> None:
    lines=[
        "# M77.21.2 Multivariate Predictive Tail Laboratory", "",
        f"- Version: `{VERSION}`", f"- Status: **{summary['status']}**",
        "- Research authority: **Development-only through 2017-12-31**",
        "- Validation opened: **NO**", "- Final holdout opened: **NO**", "- Production effect: **NONE**", "",
        "## Walk-forward design", "",
        "Each test year is predicted only from earlier Development-era observations. A horizon-specific embargo removes training rows whose forward outcome could overlap the test year. Tail ranks are formed within each test year before evidence is aggregated.", "",
        "## Strongest walk-forward probability tails", "",
    ]
    if tail.empty: lines.append("No tail evidence was generated.")
    else:
        t=tail.sort_values(["mean_return_edge","win_rate_edge"],ascending=False).head(20)
        for _,r in t.iterrows():
            lines.append(f"- {r['direction']} H{int(r['horizon'])} top/bottom {float(r['tail_fraction']):.1%}: n={int(r['n'])}, symbols={int(r['unique_symbols'])}, win={float(r['win_rate']):.2%}, win-edge={float(r['win_rate_edge']):+.2%}, mean={float(r['mean_return']):+.2%}, mean-edge={float(r['mean_return_edge']):+.2%}")
    lines += ["", "## Portfolio simulation", "", "Portfolio results are weekly mark-to-market research simulations of overlapping cohorts using the cached Development panel. They are not live execution results and do not include options pricing."]
    if not portfolio.empty:
        p=portfolio[portfolio["cost_bps_round_trip_leg"]==25.0].sort_values("sharpe",ascending=False).head(15)
        for _,r in p.iterrows():
            lines.append(f"- {r['direction']} H{int(r['horizon'])} top-{int(r['top_k'])}, 25bps: CAGR={float(r['cagr']):+.2%}, Sharpe={float(r['sharpe']):.2f}, maxDD={float(r['max_drawdown']):.2%}, PF={float(r['profit_factor']):.2f}")
    lines += ["", "## Corrected candidate-era stationarity", ""]
    if stationarity.empty: lines.append("No prior destruction survivor was available for corrected era analysis.")
    else:
        gates=stationarity[["candidate_key","edge_id","feature","direction","horizon","corrected_era_stationarity_pass"]].drop_duplicates()
        lines.append(f"- Candidates evaluated: {len(gates)}")
        lines.append(f"- Candidates passing corrected era gate: {int(gates['corrected_era_stationarity_pass'].fillna(False).sum())}")
    lines += ["", "## Governance conclusion", "", "Nothing produced by M77.21.2 is eligible for production promotion. External validation remains sealed until a small set of hypotheses is preregistered.", ""]
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text("\n".join(lines),encoding="utf-8")


def run_tail_lab(cfg: TailLabConfig) -> dict[str,Any]:
    cfg.validate(); root,src,out=_assert_paths(cfg); out.mkdir(parents=True,exist_ok=True); ck=out/"checkpoints";ck.mkdir(exist_ok=True)
    manifest={"version":VERSION,"status":"RUNNING","started_at":datetime.now(timezone.utc).isoformat(),"config":asdict(cfg),"governance":{"development_only":True,"development_end":"2017-12-31","validation_partition_opened":False,"final_holdout_opened":False,"production_authority_effect":False,"polygon_api_called":False,"database_access":"NONE"},"completed_stages":[]}
    _atomic_json(out/"run_manifest.json",manifest)
    panel,nonfinite=_load_panel(src/"checkpoints"/"panel.pkl.gz")
    _atomic_json(out/"nonfinite_sanitization.json",{"columns":nonfinite,"total_replaced":int(sum(nonfinite.values()))})
    manifest["completed_stages"].append("SOURCE_PANEL_LOADED_DEVELOPMENT_ONLY");_atomic_json(out/"run_manifest.json",manifest)

    stationarity=corrected_candidate_stationarity(panel,src);_atomic_csv(out/"corrected_candidate_stationarity.csv",stationarity)
    manifest["completed_stages"].append("CORRECTED_CANDIDATE_ERA_STATIONARITY")

    preds,folds,attrs=walk_forward_predictions(panel,cfg,ck);_atomic_csv(out/"walk_forward_fold_metrics.csv",folds)
    _atomic_csv(out/"walk_forward_predictions.csv.gz",preds,compression="gzip")
    attr_summary=summarize_attribution(attrs);_atomic_csv(out/"tail_feature_attribution.csv",attr_summary)
    manifest["completed_stages"].append("EMBARGOED_EXPANDING_WALK_FORWARD_PREDICTIONS");_atomic_json(out/"run_manifest.json",manifest)

    tail,path,year=walk_forward_tail_evidence(preds,cfg);_atomic_csv(out/"walk_forward_tail_evidence.csv",tail);_atomic_csv(out/"walk_forward_path_evidence.csv",path);_atomic_csv(out/"walk_forward_year_evidence.csv",year)
    mono=_monotonicity(tail);_atomic_csv(out/"tail_monotonicity_evidence.csv",mono)
    barrier=barrier_tail_evidence(panel,preds,cfg);_atomic_csv(out/"walk_forward_barrier_evidence.csv",barrier)
    manifest["completed_stages"].append("TAIL_PATH_BARRIER_AND_YEAR_STABILITY")

    port,curves=portfolio_evidence(panel,preds,cfg);_atomic_csv(out/"walk_forward_portfolio_evidence.csv",port);_atomic_csv(out/"walk_forward_portfolio_curves.csv.gz",curves,compression="gzip")
    manifest["completed_stages"].append("OVERLAPPING_WEEKLY_MARK_TO_MARKET_PORTFOLIOS")

    stationarity_gates=stationarity[["candidate_key","corrected_era_stationarity_pass"]].drop_duplicates() if not stationarity.empty else pd.DataFrame()
    summary={
        "version":VERSION,"status":"COMPLETE","development_boundary":"2017-12-31","panel_rows":int(len(panel)),"symbols":int(panel["symbol"].nunique()),
        "walk_forward_prediction_rows":int(len(preds)),"walk_forward_folds":int(len(folds[folds.get('status','')!='SKIPPED_INSUFFICIENT_ROWS'])) if not folds.empty else 0,
        "horizons":list(cfg.horizons),"tail_evidence_rows":int(len(tail)),"portfolio_configurations":int(len(port)),
        "corrected_stationarity_candidates":int(len(stationarity_gates)),"corrected_stationarity_survivors":int(stationarity_gates["corrected_era_stationarity_pass"].fillna(False).sum()) if not stationarity_gates.empty else 0,
        "validation_partition_opened":False,"final_holdout_opened":False,"production_authority_effect":False,"polygon_api_called":False,"completed_at":datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(out/"multivariate_tail_summary.json",summary);write_report(out/"MULTIVARIATE_TAIL_REPORT.md",summary,tail,port,stationarity)
    manifest["status"]="COMPLETE";manifest["completed_at"]=summary["completed_at"];manifest["completed_stages"].append("RESEARCH_ONLY_REPORT_PUBLISHED");_atomic_json(out/"run_manifest.json",manifest)
    return summary


def build_arg_parser()->argparse.ArgumentParser:
    ap=argparse.ArgumentParser(description="M77.21.2 Development-only multivariate predictive tail laboratory")
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--source-lab-root",default="research_data/m77_21_0/edge_discovery_lab")
    ap.add_argument("--output-root",default="research_data/m77_21_2/multivariate_predictive_tail_lab")
    ap.add_argument("--first-test-year",type=int,default=2008);ap.add_argument("--last-test-year",type=int,default=2017)
    ap.add_argument("--max-features",type=int,default=80);ap.add_argument("--no-resume",action="store_true")
    return ap


def main(argv:Sequence[str]|None=None)->int:
    a=build_arg_parser().parse_args(argv)
    cfg=TailLabConfig(project_root=a.project_root,source_lab_root=a.source_lab_root,output_root=a.output_root,first_test_year=a.first_test_year,last_test_year=a.last_test_year,max_features=a.max_features,resume=not a.no_resume)
    summary=run_tail_lab(cfg);print(json.dumps(summary,indent=2,sort_keys=True));return 0
