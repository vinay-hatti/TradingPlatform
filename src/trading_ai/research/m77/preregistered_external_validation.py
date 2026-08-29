from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from trading_ai.research.m77.edge_discovery_lab import (
    EdgeLabError,
    _json_default,
    _numeric_feature_columns,
    add_cross_sectional_ranks,
    add_forward_outcomes,
    engineer_ohlcv_features,
    load_certified_pit_feature_matrix,
    read_daily_file,
    sanitize_nonfinite_numeric,
)
from trading_ai.research.m77.multivariate_tail_lab import _model, _select_fold_features

VERSION = "M77.21.3-PREREGISTERED-EXTERNAL-VALIDATION-1.0"
VALIDATION_START = pd.Timestamp("2018-01-01")
VALIDATION_END = pd.Timestamp("2022-12-31")
FINAL_HOLDOUT_START = pd.Timestamp("2023-01-01")
PRIMARY_HORIZON = 20
PRIMARY_TAIL = 0.01
SECONDARY_HORIZONS = (15, 20, 30, 45, 60)
SECONDARY_TAILS = (0.01, 0.025, 0.05)
PRIMARY_BARRIER_TARGET_ATR = 2.0
PRIMARY_BARRIER_STOP_ATR = 1.5

# These hashes bind M77.21.3 to the exact Development-era evidence reviewed before Validation was opened.
EXPECTED_UPSTREAM_HASHES = {
    "multivariate_tail_summary.json": "2a88dac1563542c6a6cd2c36f206b6f086cf5d9e89225d4f3c8f35754fef770d",
    "walk_forward_fold_metrics.csv": "0464d35f58829dd3f94426840337ddaae84b9d57fcb6ace5d2d3341ae0c0502f",
    "historical_price_integrity_summary.json": "30280e4de6946efd9f770a5c65de22e692ddc4e485a589969b21611fc301c7b6",
}

PRIMARY_GATES: dict[str, float | int] = {
    "minimum_observations": 800,
    "minimum_unique_symbols": 150,
    "minimum_win_rate": 0.58,
    "minimum_win_rate_edge_vs_validation_baseline": 0.02,
    "minimum_median_return": 0.005,
    "minimum_mean_return": 0.0,
    "minimum_positive_years": 4,
    "minimum_barrier_expectancy_r": 0.10,
    "maximum_largest_symbol_abs_contribution_fraction": 0.10,
    "maximum_top10_symbol_abs_contribution_fraction": 0.35,
    "maximum_top1_vs_top5_win_rate_inversion": 0.015,
}


@dataclass(frozen=True)
class ValidationConfig:
    project_root: str
    development_panel: str = "research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
    multivariate_root: str = "research_data/m77_21_2/multivariate_predictive_tail_lab"
    integrity_root: str = "research_data/m77_21_2_1/historical_price_integrity_lab"
    validation_feature_root: str = "research_data/m77_19_8_7_10_5_2_4/validation_feature_matrix_certified_backfill"
    raw_daily_root: str = "research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization/daily_bars"
    output_root: str = "research_data/m77_21_3/preregistered_external_validation"
    horizons: tuple[int, ...] = SECONDARY_HORIZONS
    tail_fractions: tuple[float, ...] = SECONDARY_TAILS
    workers: int = 6
    max_features: int = 80
    random_seed: int = 77212
    model_max_iter: int = 150
    model_leaf_nodes: int = 15
    model_min_samples_leaf: int = 100
    execution_mode: str = "VALIDATION_ONLY_ONE_TIME_PREREGISTERED"

    def validate(self) -> None:
        if self.execution_mode != "VALIDATION_ONLY_ONE_TIME_PREREGISTERED":
            raise EdgeLabError("M77.21.3 only authorizes preregistered Validation-only execution")
        if tuple(self.horizons) != SECONDARY_HORIZONS:
            raise EdgeLabError("M77.21.3 frozen horizons cannot be changed")
        if tuple(self.tail_fractions) != SECONDARY_TAILS:
            raise EdgeLabError("M77.21.3 frozen tail fractions cannot be changed")
        if self.max_features != 80 or self.random_seed != 77212:
            raise EdgeLabError("M77.21.3 frozen model configuration changed")
        if self.model_max_iter != 150 or self.model_leaf_nodes != 15 or self.model_min_samples_leaf != 100:
            raise EdgeLabError("M77.21.3 frozen model hyperparameters changed")
        if self.workers < 1:
            raise EdgeLabError("workers must be >=1")


def _resolve(root: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (root / p).resolve()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default).encode()
    return hashlib.sha256(raw).hexdigest()


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


def preregistration_payload() -> dict[str, Any]:
    payload = {
        "version": VERSION,
        "registered_before_validation_open": True,
        "primary_hypothesis": {
            "direction": "LONG",
            "horizon_sessions": PRIMARY_HORIZON,
            "selection": "CONTEMPORANEOUS_WEEKLY_CROSS_SECTION_TOP_1_PERCENT_PROBABILITY_UP",
            "tail_fraction": PRIMARY_TAIL,
            "barrier_target_atr": PRIMARY_BARRIER_TARGET_ATR,
            "barrier_stop_atr": PRIMARY_BARRIER_STOP_ATR,
        },
        "secondary_horizons": list(SECONDARY_HORIZONS),
        "secondary_tail_fractions": list(SECONDARY_TAILS),
        "model": {
            "family": "HistGradientBoostingClassifier",
            "feature_selection": "DEVELOPMENT_ONLY_TOP80_BY_NONMISSING_COUNT_THEN_VARIANCE",
            "imputer": "DEVELOPMENT_ONLY_MEDIAN",
            "max_iter": 150,
            "max_leaf_nodes": 15,
            "learning_rate": 0.05,
            "l2_regularization": 1.0,
            "min_samples_leaf": 100,
            "random_seed": 77212,
        },
        "validation_window": {"start": "2018-01-01", "end": "2022-12-31"},
        "final_holdout_start": "2023-01-01",
        "primary_acceptance_gates": PRIMARY_GATES,
        "governance": {
            "validation_model_refit": False,
            "validation_feature_selection": False,
            "validation_threshold_search": False,
            "validation_hyperparameter_tuning": False,
            "validation_outcome_dependent_protocol_change": False,
            "secondary_evidence_can_override_primary_failure": False,
            "final_holdout_open_authorized": False,
            "production_authority_effect": False,
        },
        "upstream_evidence_sha256": EXPECTED_UPSTREAM_HASHES,
    }
    payload["preregistration_sha256"] = _canonical_sha(payload)
    return payload


def _verify_upstream(root: Path, cfg: ValidationConfig) -> dict[str, str]:
    multi = _resolve(root, cfg.multivariate_root)
    integ = _resolve(root, cfg.integrity_root)
    targets = {
        "multivariate_tail_summary.json": multi / "multivariate_tail_summary.json",
        "walk_forward_fold_metrics.csv": multi / "walk_forward_fold_metrics.csv",
        "historical_price_integrity_summary.json": integ / "historical_price_integrity_summary.json",
    }
    actual: dict[str, str] = {}
    for name, path in targets.items():
        if not path.exists():
            raise EdgeLabError(f"required preregistration dependency missing: {path}")
        actual[name] = _sha256(path)
        if actual[name] != EXPECTED_UPSTREAM_HASHES[name]:
            raise EdgeLabError(f"upstream Development evidence changed for {name}; Validation remains sealed")
    summary = json.loads(targets["multivariate_tail_summary.json"].read_text())
    if summary.get("validation_partition_opened") is not False or summary.get("final_holdout_opened") is not False:
        raise EdgeLabError("upstream M77.21.2 governance state invalid")
    isum = json.loads(targets["historical_price_integrity_summary.json"].read_text())
    if isum.get("validation_partition_opened") is not False or isum.get("final_holdout_opened") is not False:
        raise EdgeLabError("upstream M77.21.2.1 governance state invalid")
    return actual


def _load_development_panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise EdgeLabError(f"Development panel missing: {path}")
    panel = pd.read_pickle(path, compression="gzip")
    panel["as_of"] = pd.to_datetime(panel["as_of"], errors="coerce")
    panel = panel.dropna(subset=["as_of", "symbol"]).copy()
    if panel["as_of"].max() > pd.Timestamp("2017-12-31"):
        raise EdgeLabError("Development panel crosses Validation boundary")
    panel, _ = sanitize_nonfinite_numeric(panel)
    return panel.sort_values(["as_of", "symbol"]).reset_index(drop=True)


def _validation_symbol_worker(args: tuple[str, tuple[int, ...]]) -> tuple[str, pd.DataFrame | None, str | None]:
    raw_path, horizons = args
    path = Path(raw_path)
    symbol = path.name.removesuffix(".daily.csv.gz")
    try:
        d = read_daily_file(path, "2022-12-31")
        if len(d) < 300 + max(horizons):
            return symbol, None, "INSUFFICIENT_HISTORY"
        d = engineer_ohlcv_features(d)
        d = add_forward_outcomes(d, horizons, ((PRIMARY_BARRIER_TARGET_ATR, PRIMARY_BARRIER_STOP_ATR),))
        d["symbol"] = symbol
        d["calendar_year"] = d["as_of"].dt.year
        d["month"] = d["as_of"].dt.month
        d["weekday"] = d["as_of"].dt.weekday
        iso = d["as_of"].dt.isocalendar()
        key = iso["year"].astype(str) + "-" + iso["week"].astype(str)
        d = d.loc[d.groupby(key, sort=False)["as_of"].idxmax()].copy()
        d = d[d["as_of"].between(VALIDATION_START, VALIDATION_END, inclusive="both")].copy()
        return symbol, d, None
    except Exception as exc:
        return symbol, None, f"{type(exc).__name__}: {exc}"


def _build_validation_panel(root: Path, cfg: ValidationConfig, out: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    cache = out / "checkpoints" / "validation_panel.pkl.gz"
    meta_path = out / "checkpoints" / "validation_panel_meta.json"
    if cache.exists() and meta_path.exists():
        panel = pd.read_pickle(cache, compression="gzip")
        panel["as_of"] = pd.to_datetime(panel["as_of"])
        if panel["as_of"].min() < VALIDATION_START or panel["as_of"].max() > VALIDATION_END:
            raise EdgeLabError("cached Validation panel escaped authorized window")
        return panel, json.loads(meta_path.read_text())

    raw_root = _resolve(root, cfg.raw_daily_root)
    feature_root = _resolve(root, cfg.validation_feature_root)
    if not raw_root.exists() or not feature_root.exists():
        raise EdgeLabError("Validation daily or certified feature authority missing")
    pit = load_certified_pit_feature_matrix(feature_root, "2022-12-31")
    pit = pit[pit["as_of"].between(VALIDATION_START, VALIDATION_END, inclusive="both")].copy()
    symbols = set(pit["symbol"].dropna().astype(str))
    tasks = []
    for p in sorted(raw_root.glob("*.daily.csv.gz")):
        sym = p.name.removesuffix(".daily.csv.gz")
        if sym in symbols:
            tasks.append((str(p), cfg.horizons))
    if not tasks:
        raise EdgeLabError("no Validation daily files intersect certified feature authority")
    frames: list[pd.DataFrame] = []
    failures: dict[str, str] = {}
    with ProcessPoolExecutor(max_workers=cfg.workers) as ex:
        futs = [ex.submit(_validation_symbol_worker, x) for x in tasks]
        for fut in as_completed(futs):
            sym, frame, err = fut.result()
            if frame is not None and not frame.empty:
                frames.append(frame)
            elif err:
                failures[sym] = err
    if not frames:
        raise EdgeLabError("Validation OHLCV panel construction produced zero rows")
    panel = pd.concat(frames, ignore_index=True)
    panel = panel.merge(pit, on=["symbol", "as_of"], how="left", validate="many_to_one")
    panel = add_cross_sectional_ranks(panel)
    panel, nonfinite = sanitize_nonfinite_numeric(panel)
    panel = panel.sort_values(["as_of", "symbol"]).reset_index(drop=True)
    if panel["as_of"].min() < VALIDATION_START or panel["as_of"].max() > VALIDATION_END:
        raise EdgeLabError("constructed Validation panel escaped authorized dates")
    cache.parent.mkdir(parents=True, exist_ok=True)
    panel.to_pickle(cache, compression="gzip")
    meta = {
        "rows": int(len(panel)),
        "symbols": int(panel["symbol"].nunique()),
        "first_as_of": str(panel["as_of"].min().date()),
        "last_as_of": str(panel["as_of"].max().date()),
        "worker_failures": failures,
        "nonfinite_replacements": nonfinite,
        "validation_feature_rows": int(len(pit)),
        "final_holdout_rows_opened": 0,
    }
    _atomic_json(meta_path, meta)
    return panel, meta


def _fit_frozen_models(dev: pd.DataFrame, val: pd.DataFrame, cfg: ValidationConfig, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    preds: list[pd.DataFrame] = []
    model_rows: list[dict[str, Any]] = []
    numeric = _numeric_feature_columns(dev)
    for h in cfg.horizons:
        outcome = f"fwd_ret_{h}"
        train = dev.dropna(subset=[outcome]).copy()
        test = val.dropna(subset=[outcome]).copy()
        cols = _select_fold_features(train, numeric, cfg.max_features)
        if not cols:
            raise EdgeLabError(f"no frozen Development features available for h{h}")
        Xtr = train.reindex(columns=cols).apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        Xte = test.reindex(columns=cols).apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        ytr = (train[outcome] > 0).astype(int)
        yte = (test[outcome] > 0).astype(int)
        model = _model(cfg)  # config fields intentionally match TailLabConfig names used by _model
        model.fit(Xtr, ytr)
        proba = model.predict_proba(Xte)[:, 1]
        labels = (proba >= 0.5).astype(int)
        auc = roc_auc_score(yte, proba) if yte.nunique() > 1 else np.nan
        bal = balanced_accuracy_score(yte, labels)
        keep = ["symbol", "as_of", "close", outcome, f"fwd_ret_{h}_delay1", f"mfe_{h}", f"mae_{h}", f"mfe_atr_{h}", f"mae_atr_{h}"]
        barrier = f"long_barrier_t2p0_s1p5_h{h}"
        days = f"long_days_t2p0_s1p5_h{h}"
        keep.extend([barrier, days])
        keep = [c for c in keep if c in test]
        p = test[keep].copy()
        p["horizon"] = h
        p["probability_up"] = proba
        p["actual_up"] = yte.to_numpy()
        p["validation_year"] = p["as_of"].dt.year
        p["validation_auc"] = auc
        p["validation_balanced_accuracy"] = bal
        preds.append(p)
        model_rows.append({
            "horizon": h,
            "development_rows": int(len(train)),
            "development_symbols": int(train["symbol"].nunique()),
            "validation_rows": int(len(test)),
            "validation_symbols": int(test["symbol"].nunique()),
            "feature_count": len(cols),
            "feature_columns_sha256": _canonical_sha(cols),
            "feature_columns": "|".join(cols),
            "validation_auc": float(auc) if np.isfinite(auc) else np.nan,
            "validation_balanced_accuracy": float(bal),
        })
    return pd.concat(preds, ignore_index=True), pd.DataFrame(model_rows)


def _validation_integrity(pred: pd.DataFrame, raw_root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    needed = set(pred["symbol"].astype(str))
    for path in sorted(raw_root.glob("*.daily.csv.gz")):
        symbol = path.name.removesuffix(".daily.csv.gz")
        if symbol not in needed:
            continue
        d = pd.read_csv(path, compression="gzip")
        d["session_date"] = pd.to_datetime(d["session_date"], errors="coerce")
        d["close"] = pd.to_numeric(d["close"], errors="coerce")
        d = d[d["session_date"] <= VALIDATION_END].dropna(subset=["session_date", "close"]).sort_values("session_date")
        prev = d["close"].shift(1)
        ret = d["close"] / prev - 1.0
        vol = ret.rolling(60, min_periods=20).std(ddof=1).shift(1)
        z = ret.abs() / vol.replace(0.0, np.nan)
        flag = (ret.abs() >= 0.50) | ((ret.abs() >= 0.20) & (z >= 15.0)) | (~np.isfinite(d["close"])) | (d["close"] <= 0)
        dates = d["session_date"].to_numpy(dtype="datetime64[ns]")
        close = d["close"].to_numpy(float)
        f = flag.fillna(False).to_numpy(int)
        csum = np.concatenate([[0], np.cumsum(f)])
        for idx, r in pred[pred["symbol"] == symbol].iterrows():
            asof = np.datetime64(pd.Timestamp(r["as_of"]).to_datetime64())
            h = int(r["horizon"])
            i = int(np.searchsorted(dates, asof, side="left"))
            clean = False; count = np.nan; recomputed = np.nan; matches = False
            if i < len(dates) and dates[i] == asof and i + h < len(dates) and dates[i+h] < np.datetime64(FINAL_HOLDOUT_START):
                count = int(csum[i+h+1] - csum[i+1])
                recomputed = float(close[i+h] / close[i] - 1.0)
                src = float(r[f"fwd_ret_{h}"])
                matches = bool(np.isfinite(recomputed) and np.isfinite(src) and abs(recomputed-src) <= 2e-6)
                clean = bool(count == 0 and matches)
            rows.append({"prediction_index": idx, "interval_integrity_event_count": count, "raw_recomputed_return": recomputed, "source_return_matches_raw": matches, "integrity_clean": clean})
    return pd.DataFrame(rows)


def _select_cross_section(pred: pd.DataFrame, horizon: int, frac: float, direction: str) -> pd.DataFrame:
    d = pred[pred["horizon"] == horizon].copy()
    if d.empty:
        return d
    ascending = direction == "SHORT"
    rank = d.groupby("as_of", observed=True)["probability_up"].rank(method="first", ascending=ascending)
    count = d.groupby("as_of", observed=True)["probability_up"].transform("count")
    d["cross_section_rank_pct"] = rank / count
    return d[d["cross_section_rank_pct"] <= frac].copy()


def _tail_metrics(pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows=[]; years=[]
    for h in SECONDARY_HORIZONS:
        base = pred[(pred["horizon"] == h) & (pred["integrity_clean"])].copy()
        base_ret = pd.to_numeric(base[f"fwd_ret_{h}"], errors="coerce")
        base_win = float((base_ret > 0).mean()) if len(base) else np.nan
        for frac in SECONDARY_TAILS:
            for direction in ("LONG", "SHORT"):
                s = _select_cross_section(base, h, frac, direction)
                raw = pd.to_numeric(s[f"fwd_ret_{h}"], errors="coerce")
                signed = raw if direction == "LONG" else -raw
                win = float((signed > 0).mean()) if len(s) else np.nan
                rows.append({
                    "horizon":h,"tail_fraction":frac,"direction":direction,"n":int(len(s)),"unique_symbols":int(s["symbol"].nunique()),"selection_dates":int(s["as_of"].nunique()),
                    "win_rate":win,"baseline_long_win_rate":base_win,"win_rate_edge_vs_direction_baseline": (win-base_win if direction=="LONG" else win-(1-base_win)) if np.isfinite(win) and np.isfinite(base_win) else np.nan,
                    "mean_signed_return":float(signed.mean()) if len(s) else np.nan,"median_signed_return":float(signed.median()) if len(s) else np.nan,
                    "mean_mfe_atr":float(pd.to_numeric(s.get(f"mfe_atr_{h}"),errors="coerce").mean()) if direction=="LONG" and f"mfe_atr_{h}" in s else np.nan,
                    "mean_mae_atr":float(pd.to_numeric(s.get(f"mae_atr_{h}"),errors="coerce").mean()) if direction=="LONG" and f"mae_atr_{h}" in s else np.nan,
                })
                for y,g in s.groupby(s["as_of"].dt.year):
                    rr=pd.to_numeric(g[f"fwd_ret_{h}"],errors="coerce"); sr=rr if direction=="LONG" else -rr
                    years.append({"horizon":h,"tail_fraction":frac,"direction":direction,"year":int(y),"n":int(len(g)),"unique_symbols":int(g["symbol"].nunique()),"win_rate":float((sr>0).mean()),"mean_signed_return":float(sr.mean()),"median_signed_return":float(sr.median())})
    return pd.DataFrame(rows), pd.DataFrame(years)


def _primary_details(pred: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    base = pred[(pred["horizon"]==PRIMARY_HORIZON)&(pred["integrity_clean"])].copy()
    s = _select_cross_section(base, PRIMARY_HORIZON, PRIMARY_TAIL, "LONG")
    r = pd.to_numeric(s[f"fwd_ret_{PRIMARY_HORIZON}"],errors="coerce")
    baseline = pd.to_numeric(base[f"fwd_ret_{PRIMARY_HORIZON}"],errors="coerce")
    yearly = s.assign(year=s["as_of"].dt.year).groupby("year",observed=True).agg(n=("symbol","size"),unique_symbols=("symbol","nunique"),mean_return=(f"fwd_ret_{PRIMARY_HORIZON}","mean"),median_return=(f"fwd_ret_{PRIMARY_HORIZON}","median"))
    yearly["positive_mean"] = yearly["mean_return"] > 0
    barrier_col=f"long_barrier_t2p0_s1p5_h{PRIMARY_HORIZON}"
    b=pd.to_numeric(s[barrier_col],errors="coerce") if barrier_col in s else pd.Series(dtype=float)
    resolved=b[b.isin([-1.0,1.0])]
    bwr=float((resolved==1).mean()) if len(resolved) else np.nan
    expectancy=(bwr*PRIMARY_BARRIER_TARGET_ATR - (1-bwr)*PRIMARY_BARRIER_STOP_ATR)/PRIMARY_BARRIER_STOP_ATR if np.isfinite(bwr) else np.nan
    sym=s.assign(_r=r).groupby("symbol",observed=True)["_r"].sum().abs().sort_values(ascending=False)
    denom=float(sym.sum())
    largest=float(sym.iloc[0]/denom) if len(sym) and denom>0 else np.nan
    top10=float(sym.head(10).sum()/denom) if len(sym) and denom>0 else np.nan
    metrics={
        "n":int(len(s)),"unique_symbols":int(s["symbol"].nunique()),"selection_dates":int(s["as_of"].nunique()),
        "win_rate":float((r>0).mean()),"validation_baseline_win_rate":float((baseline>0).mean()),"win_rate_edge_vs_validation_baseline":float((r>0).mean()-(baseline>0).mean()),
        "mean_return":float(r.mean()),"median_return":float(r.median()),"positive_years":int(yearly["positive_mean"].sum()),"years_observed":int(len(yearly)),
        "barrier_resolved_n":int(len(resolved)),"barrier_win_rate":bwr,"barrier_expectancy_r":expectancy,
        "largest_symbol_abs_contribution_fraction":largest,"top10_symbol_abs_contribution_fraction":top10,
    }
    return metrics, yearly.reset_index()


def _evaluate_primary_gates(metrics: dict[str, Any], tails: pd.DataFrame) -> tuple[dict[str, bool], str]:
    g={
        "minimum_observations": metrics["n"] >= int(PRIMARY_GATES["minimum_observations"]),
        "minimum_unique_symbols": metrics["unique_symbols"] >= int(PRIMARY_GATES["minimum_unique_symbols"]),
        "minimum_win_rate": metrics["win_rate"] >= float(PRIMARY_GATES["minimum_win_rate"]),
        "minimum_win_rate_edge_vs_validation_baseline": metrics["win_rate_edge_vs_validation_baseline"] >= float(PRIMARY_GATES["minimum_win_rate_edge_vs_validation_baseline"]),
        "minimum_median_return": metrics["median_return"] >= float(PRIMARY_GATES["minimum_median_return"]),
        "minimum_mean_return": metrics["mean_return"] > float(PRIMARY_GATES["minimum_mean_return"]),
        "minimum_positive_years": metrics["positive_years"] >= int(PRIMARY_GATES["minimum_positive_years"]),
        "minimum_barrier_expectancy_r": np.isfinite(metrics["barrier_expectancy_r"]) and metrics["barrier_expectancy_r"] >= float(PRIMARY_GATES["minimum_barrier_expectancy_r"]),
        "maximum_largest_symbol_abs_contribution_fraction": np.isfinite(metrics["largest_symbol_abs_contribution_fraction"]) and metrics["largest_symbol_abs_contribution_fraction"] <= float(PRIMARY_GATES["maximum_largest_symbol_abs_contribution_fraction"]),
        "maximum_top10_symbol_abs_contribution_fraction": np.isfinite(metrics["top10_symbol_abs_contribution_fraction"]) and metrics["top10_symbol_abs_contribution_fraction"] <= float(PRIMARY_GATES["maximum_top10_symbol_abs_contribution_fraction"]),
    }
    q=tails[(tails["horizon"]==20)&(tails["direction"]=="LONG")].set_index("tail_fraction")
    if 0.01 in q.index and 0.05 in q.index:
        inversion=float(q.loc[0.05,"win_rate"]-q.loc[0.01,"win_rate"])
        g["top1_not_materially_worse_than_top5"] = inversion <= float(PRIMARY_GATES["maximum_top1_vs_top5_win_rate_inversion"])
    else:
        g["top1_not_materially_worse_than_top5"] = False
    return g, "PASS" if all(g.values()) else "FAIL"


def _write_report(path: Path, summary: dict[str, Any], metrics: dict[str, Any], gates: dict[str,bool]) -> None:
    lines=[
        "# M77.21.3 Preregistered External Validation",
        "",
        f"**Primary verdict: {summary['primary_validation_verdict']}**",
        "",
        "Primary hypothesis: 20-session LONG, contemporaneous weekly cross-section top 1% probability-up rank.",
        "",
        f"Validation observations selected: {metrics['n']}",
        f"Unique symbols: {metrics['unique_symbols']}",
        f"Win rate: {metrics['win_rate']:.4%}",
        f"Validation baseline win rate: {metrics['validation_baseline_win_rate']:.4%}",
        f"Win-rate edge: {metrics['win_rate_edge_vs_validation_baseline']:.4%}",
        f"Mean return: {metrics['mean_return']:.4%}",
        f"Median return: {metrics['median_return']:.4%}",
        f"Positive validation years: {metrics['positive_years']} / {metrics['years_observed']}",
        f"2 ATR / 1.5 ATR barrier expectancy: {metrics['barrier_expectancy_r']:.4f} R",
        "",
        "## Preregistered acceptance gates",
    ]
    for k,v in gates.items(): lines.append(f"- {'PASS' if v else 'FAIL'} — {k}")
    lines += ["", "## Governance", "- Validation opened: YES", "- Final Holdout opened: NO", "- Validation model retuning: NO", "- Validation feature selection: NO", "- Production authority effect: NONE", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_validation(cfg: ValidationConfig) -> dict[str, Any]:
    cfg.validate()
    root=Path(cfg.project_root).resolve(); out=_resolve(root,cfg.output_root); out.mkdir(parents=True,exist_ok=True)
    prereg=preregistration_payload(); prereg_path=out/"PREREGISTRATION_FROZEN.json"
    complete_path=out/"preregistered_external_validation_summary.json"
    if complete_path.exists():
        prior=json.loads(complete_path.read_text())
        if prior.get("status")=="COMPLETE" and prior.get("preregistration_sha256")==prereg["preregistration_sha256"]:
            return prior
        raise EdgeLabError("existing Validation output has incompatible preregistration identity")
    upstream=_verify_upstream(root,cfg)
    if prereg_path.exists():
        prior=json.loads(prereg_path.read_text())
        if prior.get("preregistration_sha256") != prereg["preregistration_sha256"]:
            raise EdgeLabError("frozen preregistration file changed; Validation remains closed")
    else:
        _atomic_json(prereg_path,prereg)
    marker=out/"VALIDATION_OPENED_ONCE.json"
    if marker.exists():
        m=json.loads(marker.read_text())
        if m.get("preregistration_sha256") != prereg["preregistration_sha256"]:
            raise EdgeLabError("Validation marker preregistration mismatch")
    else:
        _atomic_json(marker,{"opened_at":datetime.now(timezone.utc).isoformat(),"preregistration_sha256":prereg["preregistration_sha256"],"validation_window":["2018-01-01","2022-12-31"],"final_holdout_opened":False})

    dev=_load_development_panel(_resolve(root,cfg.development_panel))
    val,val_meta=_build_validation_panel(root,cfg,out)
    predictions,model_evidence=_fit_frozen_models(dev,val,cfg,out)
    integrity=_validation_integrity(predictions,_resolve(root,cfg.raw_daily_root))
    predictions=predictions.reset_index(drop=True); predictions["prediction_index"]=predictions.index
    predictions=predictions.merge(integrity,on="prediction_index",how="left",validate="one_to_one")
    if predictions["as_of"].max()>=FINAL_HOLDOUT_START:
        raise EdgeLabError("Final Holdout prediction row opened")
    _atomic_csv(out/"validation_predictions.csv.gz",predictions,compression="gzip")
    _atomic_csv(out/"validation_model_evidence.csv",model_evidence)
    tails,years=_tail_metrics(predictions)
    _atomic_csv(out/"validation_tail_evidence.csv",tails); _atomic_csv(out/"validation_year_evidence.csv",years)
    primary,primary_years=_primary_details(predictions); _atomic_csv(out/"primary_year_evidence.csv",primary_years)
    gates,verdict=_evaluate_primary_gates(primary,tails)
    gate_rows=pd.DataFrame([{"gate":k,"passed":v} for k,v in gates.items()]); _atomic_csv(out/"primary_acceptance_gate_evidence.csv",gate_rows)
    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),"preregistration_sha256":prereg["preregistration_sha256"],
        "primary_validation_verdict":verdict,"primary_metrics":primary,"primary_gate_results":gates,"validation_panel":val_meta,
        "validation_prediction_rows":int(len(predictions)),"validation_symbols":int(predictions["symbol"].nunique()),"validation_start":"2018-01-01","validation_end":"2022-12-31",
        "upstream_evidence_sha256":upstream,"validation_partition_opened":True,"validation_outcomes_opened":True,"validation_model_refit_performed":False,"validation_model_retuning_performed":False,"validation_feature_selection_performed":False,"validation_threshold_search_performed":False,
        "final_holdout_opened":False,"final_holdout_authorized":False,"polygon_api_called":False,"production_authority_effect":False,
        "next_step":"REVIEW_PRIMARY_VALIDATION_VERDICT_AND_FREEZE_END_TO_END_TRADE_CONSTRUCTION_BEFORE_ANY_FINAL_HOLDOUT_DECISION" if verdict=="PASS" else "REJECT_OR_RESEARCH_NEW_DEVELOPMENT_BRANCH_WITHOUT_REUSING_THIS_VALIDATION_OUTCOME_FOR_TUNING",
    }
    _atomic_json(complete_path,summary); _write_report(out/"PREREGISTERED_EXTERNAL_VALIDATION_REPORT.md",summary,primary,gates)
    run_manifest={"version":VERSION,"config":asdict(cfg),"preregistration":prereg,"summary_sha256":_sha256(complete_path),"final_holdout_opened":False,"production_authority_effect":False}
    _atomic_json(out/"run_manifest.json",run_manifest)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    ap=argparse.ArgumentParser(description="M77.21.3 preregistered Validation-only external certification")
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--workers",type=int,default=6)
    return ap


def main(argv: Sequence[str] | None=None) -> int:
    a=build_arg_parser().parse_args(argv)
    cfg=ValidationConfig(project_root=a.project_root,workers=a.workers)
    summary=run_validation(cfg)
    print(json.dumps(summary,indent=2,sort_keys=True,default=_json_default))
    return 0
