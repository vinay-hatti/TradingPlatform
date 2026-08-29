from __future__ import annotations

import argparse
import gzip
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
from sklearn.metrics import roc_auc_score

from trading_ai.research.m77.edge_discovery_lab import (
    EdgeLabError, _json_default, _numeric_feature_columns, add_cross_sectional_ranks,
    add_forward_outcomes, engineer_ohlcv_features, load_certified_pit_feature_matrix,
    read_daily_file, sanitize_nonfinite_numeric,
)
from trading_ai.research.m77.multivariate_tail_lab import _model, _select_fold_features, TailLabConfig
from trading_ai.research.m77.point_in_time_long_candidate_veto import _str, _num, _is_bullish
from trading_ai.research.m77.bearish_concentration_risk_governance import _markdown_table

VERSION = "M77.22.4-PREREGISTERED-FINAL-HOLDOUT-DOWNSIDE-RISK-VETO-1.0"
FINAL_START = pd.Timestamp("2023-01-01")
FINAL_END = pd.Timestamp("2026-08-21")
PRIMARY_HORIZON = 20
PRIMARY_TAIL = 0.01
PRIMARY_POPULATION = "pop_certified_trade_builder_ready"
EXPECTED_UPSTREAM_HASHES = {
    "point_in_time_long_candidate_veto_summary.json": "0e3c71988e1bcef51dd3b0f5c11c1afedcf5b78dd432575ea5989261af498759",
    "candidate_long_bearish_veto_evidence.csv": "8aa15d076800c4f6b7f13454df157b97adb25f1ed9df6d2b7080d30eb6d55e9e",
    "candidate_long_veto_readiness.csv": "95f6c75996a99b550c080c5c3b06227348bbf6409c1b405c21c2cf42ac055c6e",
    "run_manifest.json": "8a91dd106229f56bce4d6f3364a4584081c0e990a7664a6a3edf36ca792f1167",
}
PRIMARY_GATES = {
    "minimum_candidate_rows": 1000,
    "minimum_veto_rows": 50,
    "minimum_veto_symbols": 30,
    "minimum_severe_loss_capture_lift_vs_random": 2.0,
    "minimum_loss_10_rate_reduction": 0.0,
    "minimum_mean_return_improvement": -0.001,
    "minimum_win_rate_improvement": -0.0025,
    "minimum_vetoed_loss_10_rate_edge": 0.0,
    "minimum_positive_risk_improvement_year_fraction": 0.75,
}

@dataclass(frozen=True)
class FinalHoldoutVetoConfig:
    project_root: str
    development_panel: str = "research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
    final_feature_root: str = "research_data/m77_19_8_7_10_7_6_1/final_holdout_feature_matrix_certified_backfill"
    raw_daily_root: str = "research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization/daily_bars"
    pit_profiles_root: str = "research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay/weekly/profiles"
    upstream_root: str = "research_data/m77_22_3/point_in_time_long_candidate_veto"
    output_root: str = "research_data/m77_22_4/preregistered_final_holdout_downside_risk_veto"
    workers: int = 6
    max_features: int = 80
    execution_mode: str = "FINAL_HOLDOUT_ONE_TIME_PREREGISTERED_RISK_VETO"

    def validate(self) -> None:
        if self.execution_mode != "FINAL_HOLDOUT_ONE_TIME_PREREGISTERED_RISK_VETO":
            raise EdgeLabError("M77.22.4 authorizes only the frozen one-time Final Holdout veto protocol")
        if self.workers < 1 or self.max_features != 80:
            raise EdgeLabError("M77.22.4 frozen execution configuration changed")


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
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default).encode()).hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent); os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, default=_json_default); fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def _atomic_csv(path: Path, frame: pd.DataFrame, compression: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False, compression=compression)
    os.replace(tmp, path)


def build_preregistration() -> dict[str, Any]:
    payload = {
        "version": VERSION,
        "protocol_kind": "ONE_TIME_FINAL_HOLDOUT_DOWNSIDE_RISK_VETO_CERTIFICATION",
        "primary_population": PRIMARY_POPULATION,
        "primary_horizon_sessions": PRIMARY_HORIZON,
        "primary_veto": "BOTTOM_1_PERCENT_CONTEMPORANEOUS_CROSS_SECTION_PROBABILITY_UP",
        "tail_fraction": PRIMARY_TAIL,
        "final_holdout_window": {"start": str(FINAL_START.date()), "end": str(FINAL_END.date())},
        "primary_acceptance_gates": PRIMARY_GATES,
        "model": {
            "family": "HistGradientBoostingClassifier",
            "training_partition": "DEVELOPMENT_ONLY_THROUGH_2017_12_31",
            "feature_selection": "DEVELOPMENT_ONLY_TOP80_BY_NONMISSING_COUNT_THEN_VARIANCE",
            "imputer": "DEVELOPMENT_ONLY_MEDIAN",
            "max_iter": 150, "max_leaf_nodes": 15, "learning_rate": 0.05,
            "l2_regularization": 1.0, "min_samples_leaf": 100, "random_seed": 77212,
        },
        "governance": {
            "consumed_validation_read": False,
            "final_holdout_model_retuning": False,
            "final_holdout_feature_selection": False,
            "final_holdout_threshold_search": False,
            "secondary_configuration_can_rescue_primary_failure": False,
            "production_authority_effect": False,
        },
        "upstream_evidence_sha256": EXPECTED_UPSTREAM_HASHES,
    }
    payload["preregistration_sha256"] = _canonical_sha(payload)
    return payload


def _verify_upstream(root: Path, cfg: FinalHoldoutVetoConfig) -> dict[str, str]:
    upstream = _resolve(root, cfg.upstream_root)
    actual = {}
    for name, expected in EXPECTED_UPSTREAM_HASHES.items():
        p = upstream / name
        if not p.exists(): raise EdgeLabError(f"required M77.22.3 evidence missing: {p}")
        actual[name] = _sha256(p)
        if actual[name] != expected: raise EdgeLabError(f"M77.22.3 evidence changed for {name}; Final Holdout remains sealed")
    summary = json.loads((upstream / "point_in_time_long_candidate_veto_summary.json").read_text())
    if summary.get("validation_rows_read") != 0 or summary.get("final_holdout_opened") is not False:
        raise EdgeLabError("M77.22.3 governance state invalid for Final Holdout advancement")
    ready = pd.read_csv(upstream / "candidate_long_veto_readiness.csv")
    row = ready[(ready.population == PRIMARY_POPULATION) & (ready.horizon == PRIMARY_HORIZON)]
    if row.empty or not bool(row.iloc[0].passes_development_risk_governance_readiness):
        raise EdgeLabError("frozen primary M77.22.3 protocol was not Development-ready")
    return actual


def _extract_final_candidate(obj: dict[str, Any]) -> dict[str, Any] | None:
    as_of = pd.to_datetime(obj.get("as_of"), errors="coerce")
    if pd.isna(as_of) or as_of < FINAL_START or as_of > FINAL_END: return None
    p = obj.get("profile") or {}; scores = p.get("scores") or {}; idi = p.get("decision_intelligence") or {}
    trade_plan = p.get("trade_plan") or {}; cert = trade_plan.get("certification") or {}; entry_exec = cert.get("entry_execution") or {}
    direction = p.get("direction") or obj.get("direction"); bullish = _is_bullish(direction)
    trade_builder_ready = bool(cert.get("trade_builder_ready") or entry_exec.get("trade_builder_ready"))
    return {
        "symbol": str(obj.get("symbol") or p.get("symbol") or "").upper(), "as_of": as_of,
        "profile_direction": _str(direction), "score_overall": _num(scores.get("overall")),
        "cert_status": _str(cert.get("status")), "trade_builder_ready": trade_builder_ready,
        PRIMARY_POPULATION: bullish and _str(cert.get("status")) == "PASS" and trade_builder_ready,
    }


def reconstruct_final_candidate_authority(profiles_root: Path, out: Path) -> pd.DataFrame:
    checkpoint = out / "checkpoints" / "final_holdout_candidate_authority.csv.gz"
    meta_path = out / "checkpoints" / "final_holdout_candidate_authority_meta.json"
    files = sorted(profiles_root.glob("*.jsonl.gz"))
    if not files: raise EdgeLabError(f"no PIT profile files under {profiles_root}")
    signature = hashlib.sha256("\n".join(f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}" for p in files).encode()).hexdigest()
    if checkpoint.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("source_signature") == signature:
            d = pd.read_csv(checkpoint, compression="gzip"); d["as_of"] = pd.to_datetime(d["as_of"]); return d
    rows=[]; failures=[]
    for path in files:
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for n, line in enumerate(fh,1):
                    if not line.strip(): continue
                    try: rec = _extract_final_candidate(json.loads(line))
                    except Exception as exc: failures.append({"file":path.name,"line":n,"error":repr(exc)}); continue
                    if rec and rec["symbol"]: rows.append(rec)
        except Exception as exc: failures.append({"file":path.name,"line":"","error":repr(exc)})
    if not rows: raise EdgeLabError("no Final Holdout PIT candidate rows reconstructed")
    d = pd.DataFrame(rows).drop_duplicates(["symbol","as_of"],keep="last").sort_values(["as_of","symbol"]).reset_index(drop=True)
    if d.as_of.min() < FINAL_START or d.as_of.max() > FINAL_END: raise EdgeLabError("Final candidate authority escaped frozen window")
    _atomic_csv(checkpoint,d,compression="gzip"); _atomic_csv(out/"final_holdout_profile_parse_failures.csv",pd.DataFrame(failures))
    _atomic_json(meta_path,{"source_signature":signature,"rows":len(d),"symbols":d.symbol.nunique(),"failures":len(failures)})
    return d


def _final_symbol_worker(args: tuple[str, int]) -> tuple[str, pd.DataFrame | None, str | None]:
    raw_path, horizon = args; path=Path(raw_path); symbol=path.name.removesuffix(".daily.csv.gz")
    try:
        d=read_daily_file(path,str(FINAL_END.date()))
        if len(d)<300+horizon: return symbol,None,"INSUFFICIENT_HISTORY"
        d=engineer_ohlcv_features(d); d=add_forward_outcomes(d,(horizon,),())
        d["symbol"]=symbol; iso=d["as_of"].dt.isocalendar(); key=iso["year"].astype(str)+"-"+iso["week"].astype(str)
        d=d.loc[d.groupby(key,sort=False)["as_of"].idxmax()].copy()
        d=d[d["as_of"].between(FINAL_START,FINAL_END,inclusive="both")].copy()
        return symbol,d,None
    except Exception as exc: return symbol,None,f"{type(exc).__name__}: {exc}"


def build_final_panel(root: Path, cfg: FinalHoldoutVetoConfig, out: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    cache=out/"checkpoints"/"final_holdout_panel.pkl.gz"; meta_path=out/"checkpoints"/"final_holdout_panel_meta.json"
    if cache.exists() and meta_path.exists():
        d=pd.read_pickle(cache,compression="gzip"); d["as_of"]=pd.to_datetime(d["as_of"]); return d,json.loads(meta_path.read_text())
    feature_root=_resolve(root,cfg.final_feature_root); raw_root=_resolve(root,cfg.raw_daily_root)
    if not feature_root.exists() or not raw_root.exists(): raise EdgeLabError("Final Holdout feature or daily authority missing")
    pit=load_certified_pit_feature_matrix(feature_root,str(FINAL_END.date()))
    pit=pit[pit.as_of.between(FINAL_START,FINAL_END,inclusive="both")].copy()
    symbols=set(pit.symbol.dropna().astype(str)); tasks=[(str(p),PRIMARY_HORIZON) for p in sorted(raw_root.glob("*.daily.csv.gz")) if p.name.removesuffix(".daily.csv.gz") in symbols]
    frames=[]; failures={}
    with ProcessPoolExecutor(max_workers=cfg.workers) as ex:
        futs=[ex.submit(_final_symbol_worker,t) for t in tasks]
        for fut in as_completed(futs):
            s,d,e=fut.result(); frames.append(d) if d is not None and not d.empty else failures.__setitem__(s,e or "EMPTY")
    if not frames: raise EdgeLabError("Final Holdout panel construction produced zero rows")
    panel=pd.concat(frames,ignore_index=True).merge(pit,on=["symbol","as_of"],how="left",validate="many_to_one")
    panel=add_cross_sectional_ranks(panel); panel,nonfinite=sanitize_nonfinite_numeric(panel); panel=panel.sort_values(["as_of","symbol"]).reset_index(drop=True)
    if panel.as_of.min()<FINAL_START or panel.as_of.max()>FINAL_END: raise EdgeLabError("Final Holdout panel escaped frozen dates")
    cache.parent.mkdir(parents=True,exist_ok=True); panel.to_pickle(cache,compression="gzip")
    meta={"rows":len(panel),"symbols":panel.symbol.nunique(),"first_as_of":str(panel.as_of.min().date()),"last_as_of":str(panel.as_of.max().date()),"feature_rows":len(pit),"worker_failures":failures,"nonfinite_replacements":nonfinite}
    _atomic_json(meta_path,meta); return panel,meta


def score_final_holdout(dev: pd.DataFrame, final: pd.DataFrame, cfg: FinalHoldoutVetoConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    h=PRIMARY_HORIZON; outcome=f"fwd_ret_{h}"
    train=dev.dropna(subset=[outcome]).copy(); test=final.dropna(subset=[outcome]).copy()
    numeric=_numeric_feature_columns(dev); cols=_select_fold_features(train,numeric,cfg.max_features)
    Xtr=train.reindex(columns=cols).apply(pd.to_numeric,errors="coerce").replace([np.inf,-np.inf],np.nan)
    Xte=test.reindex(columns=cols).apply(pd.to_numeric,errors="coerce").replace([np.inf,-np.inf],np.nan)
    ytr=(train[outcome]>0).astype(int); yte=(test[outcome]>0).astype(int)
    model_cfg=TailLabConfig(project_root=cfg.project_root)
    model=_model(model_cfg); model.fit(Xtr,ytr); proba=model.predict_proba(Xte)[:,1]
    p=test[["symbol","as_of",outcome,f"mfe_atr_{h}",f"mae_atr_{h}"]].copy(); p["probability_up"]=proba; p["final_year"]=p.as_of.dt.year; p["horizon"]=h
    auc=roc_auc_score(yte,proba) if yte.nunique()>1 else np.nan
    return p,{"development_rows":len(train),"development_symbols":train.symbol.nunique(),"final_rows":len(test),"final_symbols":test.symbol.nunique(),"feature_count":len(cols),"auc":auc,"feature_columns":cols}



def _final_holdout_integrity(pred: pd.DataFrame, raw_root: Path) -> pd.DataFrame:
    """Evaluate raw-price integrity for the frozen 2023+ Final Holdout only.

    This intentionally does not reuse the Validation-era integrity helper because
    that helper truncates daily authority at 2022-12-31 and rejects intervals
    crossing into the Final Holdout.
    """
    required = {"symbol", "as_of", "horizon", f"fwd_ret_{PRIMARY_HORIZON}", "prediction_index"}
    missing = sorted(required.difference(pred.columns))
    if missing:
        raise EdgeLabError(f"Final Holdout integrity input missing columns: {missing}")

    horizon_values = pd.to_numeric(pred["horizon"], errors="coerce")
    if horizon_values.isna().any() or not horizon_values.eq(PRIMARY_HORIZON).all():
        raise EdgeLabError(f"Final Holdout integrity requires frozen horizon={PRIMARY_HORIZON}")

    rows: list[dict[str, Any]] = []
    needed = set(pred["symbol"].astype(str))
    paths = sorted(raw_root.rglob("*.daily.csv.gz"))
    by_symbol = {p.name.removesuffix(".daily.csv.gz"): p for p in paths if p.name.removesuffix(".daily.csv.gz") in needed}

    for symbol, group in pred.groupby("symbol", sort=False):
        symbol = str(symbol)
        path = by_symbol.get(symbol)
        if path is None:
            for idx in group.index:
                rows.append({
                    "prediction_index": int(group.loc[idx, "prediction_index"]),
                    "raw_authority_present": False,
                    "interval_integrity_event_count": np.nan,
                    "raw_recomputed_return": np.nan,
                    "source_return_matches_raw": False,
                    "interval_integrity_clean": False,
                })
            continue

        d = pd.read_csv(path, compression="gzip")
        date_col = "session_date" if "session_date" in d.columns else ("date" if "date" in d.columns else None)
        if date_col is None or "close" not in d.columns:
            for idx in group.index:
                rows.append({
                    "prediction_index": int(group.loc[idx, "prediction_index"]),
                    "raw_authority_present": True,
                    "interval_integrity_event_count": np.nan,
                    "raw_recomputed_return": np.nan,
                    "source_return_matches_raw": False,
                    "interval_integrity_clean": False,
                })
            continue

        d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
        d["close"] = pd.to_numeric(d["close"], errors="coerce")
        d = d[
            (d[date_col] >= FINAL_START - pd.Timedelta(days=370))
            & (d[date_col] <= FINAL_END)
        ].dropna(subset=[date_col, "close"]).sort_values(date_col).drop_duplicates(date_col, keep="last")

        prev = d["close"].shift(1)
        ret = d["close"] / prev - 1.0
        vol = ret.rolling(60, min_periods=20).std(ddof=1).shift(1)
        z = ret.abs() / vol.replace(0.0, np.nan)
        invalid_close = (~np.isfinite(d["close"])) | (d["close"] <= 0)
        event_flag = (ret.abs() >= 0.50) | ((ret.abs() >= 0.20) & (z >= 15.0)) | invalid_close

        dates = d[date_col].to_numpy(dtype="datetime64[ns]")
        closes = d["close"].to_numpy(float)
        flags = event_flag.fillna(False).to_numpy(int)
        csum = np.concatenate([[0], np.cumsum(flags)])

        for _, r in group.iterrows():
            prediction_index = int(r["prediction_index"])
            asof_ts = pd.Timestamp(r["as_of"])
            asof = np.datetime64(asof_ts.to_datetime64())
            h = int(r["horizon"])
            i = int(np.searchsorted(dates, asof, side="left"))

            raw_present = bool(i < len(dates) and dates[i] == asof)
            count = np.nan
            recomputed = np.nan
            matches = False
            clean = False

            # Final-Holdout outcomes are usable only if the full horizon exists
            # inside the frozen authority ending 2026-08-21.
            if raw_present and i + h < len(dates) and dates[i + h] <= np.datetime64(FINAL_END):
                count = int(csum[i + h + 1] - csum[i + 1])
                if np.isfinite(closes[i]) and closes[i] > 0 and np.isfinite(closes[i + h]):
                    recomputed = float(closes[i + h] / closes[i] - 1.0)
                src = pd.to_numeric(pd.Series([r[f"fwd_ret_{h}"]]), errors="coerce").iloc[0]
                matches = bool(
                    np.isfinite(recomputed)
                    and np.isfinite(src)
                    and abs(float(recomputed) - float(src)) <= 2e-6
                )
                clean = bool(count == 0 and matches)

            rows.append({
                "prediction_index": prediction_index,
                "raw_authority_present": raw_present,
                "interval_integrity_event_count": count,
                "raw_recomputed_return": recomputed,
                "source_return_matches_raw": matches,
                "interval_integrity_clean": clean,
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=[
            "prediction_index", "raw_authority_present", "interval_integrity_event_count",
            "raw_recomputed_return", "source_return_matches_raw", "interval_integrity_clean",
        ])
    if out["prediction_index"].duplicated().any():
        raise EdgeLabError("Final Holdout integrity produced duplicate prediction_index rows")
    return out.sort_values("prediction_index").reset_index(drop=True)


def _select_tail(pred: pd.DataFrame) -> pd.DataFrame:
    parts=[]
    for _,g in pred.groupby("as_of",sort=False):
        k=max(1,int(math.ceil(len(g)*PRIMARY_TAIL))); parts.append(g.nsmallest(k,"probability_up"))
    return pd.concat(parts,ignore_index=True) if parts else pred.iloc[0:0].copy()


def evaluate_primary(pred: pd.DataFrame, authority: pd.DataFrame, raw_root: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    pred=pred.copy()
    if "horizon" not in pred.columns:
        pred["horizon"]=PRIMARY_HORIZON
    else:
        horizon_values=pd.to_numeric(pred["horizon"],errors="coerce")
        if horizon_values.isna().any() or not horizon_values.eq(PRIMARY_HORIZON).all():
            raise EdgeLabError(f"Final Holdout prediction horizon must be frozen at {PRIMARY_HORIZON}")
    integrity=_final_holdout_integrity(pred.reset_index(drop=True).assign(prediction_index=lambda x:x.index),raw_root)
    p=pred.reset_index(drop=True); p["prediction_index"]=p.index; p=p.merge(integrity,on="prediction_index",how="left",validate="one_to_one")
    for col in ("raw_authority_present", "interval_integrity_clean", "source_return_matches_raw"):
        if col not in p.columns:
            p[col] = False
        p[col] = p[col].fillna(False).astype(bool)
    clean_flag=(p["raw_authority_present"] & p["interval_integrity_clean"] & p["source_return_matches_raw"])
    p["integrity_clean_strict"]=clean_flag
    tail=_select_tail(p)[["symbol","as_of"]].drop_duplicates().assign(veto=True)
    keys=authority.loc[authority[PRIMARY_POPULATION].fillna(False).astype(bool),["symbol","as_of"]].drop_duplicates()
    d=p[p.integrity_clean_strict].merge(keys,on=["symbol","as_of"],how="inner"); d=d.merge(tail,on=["symbol","as_of"],how="left"); d["veto"]=d.veto.eq(True)
    r=pd.to_numeric(d[f"fwd_ret_{PRIMARY_HORIZON}"],errors="coerce"); d=d[np.isfinite(r)].copy(); r=pd.to_numeric(d[f"fwd_ret_{PRIMARY_HORIZON}"],errors="coerce")
    vetoed=d[d.veto].copy(); kept=d[~d.veto].copy()
    def m(x):
        rr=pd.to_numeric(x[f"fwd_ret_{PRIMARY_HORIZON}"],errors="coerce"); return {"n":len(x),"symbols":x.symbol.nunique(),"win_rate":float((rr>0).mean()) if len(x) else np.nan,"mean_return":float(rr.mean()) if len(x) else np.nan,"loss10":float((rr<=-0.10).mean()) if len(x) else np.nan,"loss20":float((rr<=-0.20).mean()) if len(x) else np.nan}
    b,k,v=m(d),m(kept),m(vetoed); severe_total=int((r<=-0.10).sum()); vr=pd.to_numeric(vetoed[f"fwd_ret_{PRIMARY_HORIZON}"],errors="coerce"); severe_veto=int((vr<=-0.10).sum()); veto_frac=len(vetoed)/len(d) if len(d) else np.nan; capture=severe_veto/severe_total if severe_total else np.nan; lift=capture/veto_frac if severe_total and veto_frac else np.nan
    years=[]
    for y,g in d.groupby(d.as_of.dt.year):
        gg=g[~g.veto]; br=pd.to_numeric(g[f"fwd_ret_{PRIMARY_HORIZON}"],errors="coerce"); kr=pd.to_numeric(gg[f"fwd_ret_{PRIMARY_HORIZON}"],errors="coerce")
        years.append({"year":int(y),"candidate_n":len(g),"veto_n":int(g.veto.sum()),"baseline_loss_10_rate":float((br<=-0.10).mean()),"post_veto_loss_10_rate":float((kr<=-0.10).mean()) if len(gg) else np.nan,"loss_10_rate_reduction":float((br<=-0.10).mean()-(kr<=-0.10).mean()) if len(gg) else np.nan,"baseline_mean_return":float(br.mean()),"post_veto_mean_return":float(kr.mean()) if len(gg) else np.nan})
    year_df=pd.DataFrame(years); positive_years=int((year_df.loss_10_rate_reduction>0).sum()) if not year_df.empty else 0; year_fraction=positive_years/len(year_df) if len(year_df) else 0.0
    metrics={"candidate_n":b["n"],"candidate_symbols":b["symbols"],"veto_n":v["n"],"veto_symbols":v["symbols"],"veto_fraction":veto_frac,"baseline_win_rate":b["win_rate"],"post_veto_win_rate":k["win_rate"],"win_rate_improvement":k["win_rate"]-b["win_rate"],"baseline_mean_return":b["mean_return"],"post_veto_mean_return":k["mean_return"],"mean_return_improvement":k["mean_return"]-b["mean_return"],"baseline_loss_10_rate":b["loss10"],"post_veto_loss_10_rate":k["loss10"],"loss_10_rate_reduction":b["loss10"]-k["loss10"],"baseline_loss_20_rate":b["loss20"],"post_veto_loss_20_rate":k["loss20"],"vetoed_loss_10_rate":v["loss10"],"vetoed_loss_20_rate":v["loss20"],"severe_losses":severe_total,"severe_losses_vetoed":severe_veto,"severe_loss_capture_fraction":capture,"severe_loss_capture_lift_vs_random":lift,"years_observed":len(year_df),"positive_risk_improvement_years":positive_years,"positive_risk_improvement_year_fraction":year_fraction,"integrity_clean_fraction":float(p.integrity_clean_strict.mean())}
    return metrics,year_df,p


def evaluate_gates(m: dict[str, Any]) -> tuple[dict[str,bool],str]:
    gates={
        "minimum_candidate_rows":m["candidate_n"]>=PRIMARY_GATES["minimum_candidate_rows"],
        "minimum_veto_rows":m["veto_n"]>=PRIMARY_GATES["minimum_veto_rows"],
        "minimum_veto_symbols":m["veto_symbols"]>=PRIMARY_GATES["minimum_veto_symbols"],
        "minimum_severe_loss_capture_lift_vs_random":pd.notna(m["severe_loss_capture_lift_vs_random"]) and m["severe_loss_capture_lift_vs_random"]>=PRIMARY_GATES["minimum_severe_loss_capture_lift_vs_random"],
        "minimum_loss_10_rate_reduction":pd.notna(m["loss_10_rate_reduction"]) and m["loss_10_rate_reduction"]>PRIMARY_GATES["minimum_loss_10_rate_reduction"],
        "minimum_mean_return_improvement":pd.notna(m["mean_return_improvement"]) and m["mean_return_improvement"]>=PRIMARY_GATES["minimum_mean_return_improvement"],
        "minimum_win_rate_improvement":pd.notna(m["win_rate_improvement"]) and m["win_rate_improvement"]>=PRIMARY_GATES["minimum_win_rate_improvement"],
        "minimum_vetoed_loss_10_rate_edge":pd.notna(m["vetoed_loss_10_rate"]) and m["vetoed_loss_10_rate"]>m["baseline_loss_10_rate"]+PRIMARY_GATES["minimum_vetoed_loss_10_rate_edge"],
        "minimum_positive_risk_improvement_year_fraction":m["positive_risk_improvement_year_fraction"]>=PRIMARY_GATES["minimum_positive_risk_improvement_year_fraction"],
    }
    return gates,"PASS" if all(gates.values()) else "FAIL"


def _write_report(out: Path, summary: dict[str,Any], years: pd.DataFrame) -> None:
    lines=["# M77.22.4 Preregistered Final Holdout Downside-Risk Veto Certification","",f"Primary verdict: **{summary['primary_final_holdout_verdict']}**","",f"Protocol: {PRIMARY_POPULATION}, {PRIMARY_HORIZON} sessions, contemporaneous bottom 1% bearish-risk veto.","", "## Primary metrics","",_markdown_table(pd.DataFrame([summary['primary_metrics']])),"","## Gate results","",_markdown_table(pd.DataFrame([{"gate":k,"passed":v} for k,v in summary['primary_gate_results'].items()])),""]
    if not years.empty: lines += ["## Year evidence","",_markdown_table(years),""]
    lines += ["## Governance","","- This branch-specific Final Holdout protocol is one-time and preregistered.","- 2018-2022 consumed Validation is not read for tuning or scoring.","- Development-only model fitting is frozen; no Final Holdout feature selection, threshold search, or retuning occurs.","- Secondary configurations cannot rescue a failed primary.","- No production authority changes are performed.",""]
    (out/"PREREGISTERED_FINAL_HOLDOUT_DOWNSIDE_RISK_VETO_REPORT.md").write_text("\n".join(lines),encoding="utf-8")


def run_final_holdout(cfg: FinalHoldoutVetoConfig) -> dict[str,Any]:
    cfg.validate(); root=Path(cfg.project_root).expanduser().resolve(); out=_resolve(root,cfg.output_root); out.mkdir(parents=True,exist_ok=True)
    prereg=build_preregistration(); prereg_path=out/"PREREGISTRATION_FROZEN.json"; marker=out/"FINAL_HOLDOUT_OPENED_ONCE.json"; complete=out/"preregistered_final_holdout_summary.json"
    if complete.exists(): return json.loads(complete.read_text())
    upstream=_verify_upstream(root,cfg)
    if prereg_path.exists() and json.loads(prereg_path.read_text()).get("preregistration_sha256")!=prereg["preregistration_sha256"]: raise EdgeLabError("Final Holdout preregistration changed after freeze")
    _atomic_json(prereg_path,prereg)
    if marker.exists():
        old=json.loads(marker.read_text())
        if old.get("preregistration_sha256")!=prereg["preregistration_sha256"]: raise EdgeLabError("Final Holdout marker belongs to a different protocol")
    else:
        _atomic_json(marker,{"opened_at":datetime.now(timezone.utc).isoformat(),"preregistration_sha256":prereg["preregistration_sha256"],"authorized_window":{"start":str(FINAL_START.date()),"end":str(FINAL_END.date())},"branch_specific_one_time_open":True})
    authority=reconstruct_final_candidate_authority(_resolve(root,cfg.pit_profiles_root),out)
    dev=pd.read_pickle(_resolve(root,cfg.development_panel),compression="gzip"); dev["as_of"]=pd.to_datetime(dev["as_of"],errors="coerce"); dev=dev[dev.as_of<=pd.Timestamp("2017-12-31")].copy(); dev,_=sanitize_nonfinite_numeric(dev)
    final,meta=build_final_panel(root,cfg,out); pred,model_evidence=score_final_holdout(dev,final,cfg)
    metrics,years,annotated=evaluate_primary(pred,authority,_resolve(root,cfg.raw_daily_root)); gates,verdict=evaluate_gates(metrics)
    _atomic_csv(out/"final_holdout_predictions.csv.gz",annotated,compression="gzip"); _atomic_csv(out/"primary_year_evidence.csv",years); _atomic_csv(out/"primary_acceptance_gate_evidence.csv",pd.DataFrame([{"gate":k,"passed":v} for k,v in gates.items()])); _atomic_json(out/"final_holdout_model_evidence.json",model_evidence)
    summary={"version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),"preregistration_sha256":prereg["preregistration_sha256"],"primary_final_holdout_verdict":verdict,"primary_metrics":metrics,"primary_gate_results":gates,"final_holdout_panel":meta,"final_holdout_prediction_rows":len(pred),"final_holdout_candidate_rows":len(authority),"final_holdout_start":str(FINAL_START.date()),"final_holdout_end":str(FINAL_END.date()),"final_holdout_partition_opened":True,"final_holdout_outcomes_opened":True,"consumed_validation_rows_read":0,"consumed_validation_reused_for_tuning":False,"final_holdout_model_retuning_performed":False,"final_holdout_feature_selection_performed":False,"final_holdout_threshold_search_performed":False,"polygon_api_called":False,"production_authority_effect":False,"upstream_evidence_sha256":upstream,"next_step":"REVIEW_FINAL_HOLDOUT_VERDICT; NO AUTOMATIC PRODUCTION PROMOTION"}
    _atomic_json(complete,summary); _write_report(out,summary,years); _atomic_json(out/"run_manifest.json",{"version":VERSION,"config":asdict(cfg),"preregistration":prereg,"summary_sha256":_sha256(complete)})
    return summary


def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.22.4 one-time preregistered Final Holdout downside-risk veto certification"); p.add_argument("--project-root",required=True); p.add_argument("--workers",type=int,default=6); return p

def main(argv: Sequence[str] | None=None) -> int:
    a=build_parser().parse_args(argv); s=run_final_holdout(FinalHoldoutVetoConfig(project_root=a.project_root,workers=a.workers)); print(json.dumps(s,indent=2,sort_keys=True,default=_json_default)); return 0
