from __future__ import annotations

import argparse
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

from trading_ai.research.m77.edge_discovery_lab import EdgeLabError, _json_default
from trading_ai.research.m77.multivariate_tail_lab import _weekly_portfolio_returns

VERSION = "M77.21.2.1-HISTORICAL-PRICE-INTEGRITY-ROBUST-RECALIBRATION-1.0"
DEVELOPMENT_END = pd.Timestamp("2017-12-31")
SEALED_TOKENS = ("validation_target", "final_holdout", "validation_scoring", "final_holdout_scoring")
DEFAULT_HORIZONS = (15, 20, 30, 45, 60)
DEFAULT_TAILS = (0.01, 0.025, 0.05, 0.10, 0.20)
DEFAULT_TOP_K = (1, 3, 5, 10, 20)


@dataclass(frozen=True)
class IntegrityConfig:
    project_root: str
    source_tail_root: str = "research_data/m77_21_2/multivariate_predictive_tail_lab"
    source_panel_root: str = "research_data/m77_21_0/edge_discovery_lab"
    raw_daily_root: str = "research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization/daily_bars"
    output_root: str = "research_data/m77_21_2_1/historical_price_integrity_lab"
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    tail_fractions: tuple[float, ...] = DEFAULT_TAILS
    top_k: tuple[int, ...] = DEFAULT_TOP_K
    severe_daily_move: float = 0.50
    extreme_daily_move: float = 1.00
    robust_z_floor_move: float = 0.20
    robust_z_threshold: float = 15.0
    return_match_tolerance: float = 2e-6
    execution_mode: str = "DEVELOPMENT_INTEGRITY_RECALIBRATION_ONLY"

    def validate(self) -> None:
        if self.execution_mode != "DEVELOPMENT_INTEGRITY_RECALIBRATION_ONLY":
            raise EdgeLabError("M77.21.2.1 authorizes DEVELOPMENT_INTEGRITY_RECALIBRATION_ONLY")
        if any(h < 1 for h in self.horizons):
            raise EdgeLabError("horizons must be positive")
        if not 0 < self.severe_daily_move < self.extreme_daily_move:
            raise EdgeLabError("invalid daily move thresholds")


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


def _assert_paths(cfg: IntegrityConfig) -> tuple[Path, Path, Path, Path, Path]:
    root = Path(cfg.project_root).resolve()
    tail = _resolve(root, cfg.source_tail_root)
    panel = _resolve(root, cfg.source_panel_root)
    raw = _resolve(root, cfg.raw_daily_root)
    out = _resolve(root, cfg.output_root)
    for label, p in (("source_tail_root", tail), ("source_panel_root", panel), ("raw_daily_root", raw), ("output_root", out)):
        if any(tok in str(p).lower() for tok in SEALED_TOKENS):
            raise EdgeLabError(f"{label} points at sealed path: {p}")
    if "research_data" not in out.parts:
        raise EdgeLabError("output_root must be under research_data")
    if not (tail / "walk_forward_predictions.csv.gz").exists():
        raise EdgeLabError(f"M77.21.2 predictions missing under {tail}")
    if not (panel / "checkpoints" / "panel.pkl.gz").exists():
        raise EdgeLabError(f"M77.21 panel missing under {panel}")
    if not raw.exists():
        raise EdgeLabError(f"frozen Polygon daily-bar authority missing: {raw}")
    return root, tail, panel, raw, out


def _read_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, compression="gzip")
    required = {"session_date", "open", "high", "low", "close"}
    if not required.issubset(df.columns):
        raise EdgeLabError(f"daily file missing fields {sorted(required - set(df.columns))}: {path}")
    df["session_date"] = pd.to_datetime(df["session_date"], errors="coerce")
    for c in ("open", "high", "low", "close", "volume", "vwap", "transactions"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["session_date"]).sort_values("session_date").reset_index(drop=True)


def _splitlike_ratio(prev_close: pd.Series, close: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    a = pd.to_numeric(prev_close, errors="coerce").to_numpy(float)
    b = pd.to_numeric(close, errors="coerce").to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.maximum(a / b, b / a)
    factors = np.array([2.0, 3.0, 4.0, 5.0, 10.0, 20.0])
    distance = np.full(len(ratio), np.nan)
    nearest = np.full(len(ratio), np.nan)
    for i, r in enumerate(ratio):
        if not np.isfinite(r):
            continue
        j = int(np.argmin(np.abs(factors - r) / factors))
        nearest[i] = factors[j]
        distance[i] = abs(factors[j] - r) / factors[j]
    return nearest, distance


def classify_daily_integrity(symbol: str, daily: pd.DataFrame, cfg: IntegrityConfig) -> pd.DataFrame:
    d = daily[daily["session_date"] <= DEVELOPMENT_END].copy()
    d["prev_close"] = d["close"].shift(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        d["daily_return"] = d["close"] / d["prev_close"] - 1.0
    r = d["daily_return"].replace([np.inf, -np.inf], np.nan)
    # Historical-only rolling volatility baseline; shifted to avoid using the candidate move itself.
    vol = r.rolling(60, min_periods=20).std(ddof=1).shift(1)
    d["prior_60d_vol"] = vol
    d["robust_move_z"] = r.abs() / vol.replace(0.0, np.nan)
    nearest, dist = _splitlike_ratio(d["prev_close"], d["close"])
    d["nearest_split_factor"] = nearest
    d["split_ratio_relative_error"] = dist
    invalid = (~np.isfinite(d["close"])) | (d["close"] <= 0) | (d["high"] < d["low"]) | (d["high"] < d["close"]) | (d["low"] > d["close"])
    extreme = r.abs() >= cfg.extreme_daily_move
    severe = r.abs() >= cfg.severe_daily_move
    zflag = (r.abs() >= cfg.robust_z_floor_move) & (d["robust_move_z"] >= cfg.robust_z_threshold)
    splitlike = severe & (d["split_ratio_relative_error"] <= 0.03)
    d["integrity_flag"] = invalid | severe | zflag
    d["classification"] = "NORMAL"
    d.loc[zflag, "classification"] = "STATISTICAL_DISCONTINUITY_SUSPECT"
    d.loc[severe, "classification"] = "SEVERE_DISCONTINUITY_SUSPECT"
    d.loc[extreme, "classification"] = "EXTREME_DISCONTINUITY_SUSPECT"
    d.loc[splitlike, "classification"] = "POTENTIAL_ADJUSTMENT_OR_IDENTITY_BREAK"
    d.loc[invalid, "classification"] = "INVALID_OHLC"
    d["symbol"] = symbol
    cols = ["symbol", "session_date", "prev_close", "close", "daily_return", "prior_60d_vol", "robust_move_z", "nearest_split_factor", "split_ratio_relative_error", "classification", "integrity_flag"]
    return d.loc[d["integrity_flag"], cols].reset_index(drop=True)


def scan_daily_authority(raw_root: Path, symbols: set[str], cfg: IntegrityConfig) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    events: list[pd.DataFrame] = []
    daily_by_symbol: dict[str, pd.DataFrame] = {}
    for path in sorted(raw_root.glob("*.daily.csv.gz")):
        symbol = path.name.removesuffix(".daily.csv.gz")
        if symbol not in symbols:
            continue
        d = _read_daily(path)
        d = d[d["session_date"] <= DEVELOPMENT_END].copy()
        daily_by_symbol[symbol] = d
        e = classify_daily_integrity(symbol, d, cfg)
        if not e.empty:
            events.append(e)
    return (pd.concat(events, ignore_index=True) if events else pd.DataFrame()), daily_by_symbol


def annotate_prediction_integrity(predictions: pd.DataFrame, daily_by_symbol: dict[str, pd.DataFrame], cfg: IntegrityConfig) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for symbol, p in predictions.groupby("symbol", sort=False):
        d = daily_by_symbol.get(symbol)
        if d is None or d.empty:
            q = p[["symbol", "as_of", "horizon", "test_year"]].copy()
            q["raw_authority_present"] = False
            q["interval_integrity_event_count"] = np.nan
            q["interval_integrity_clean"] = False
            q["raw_recomputed_return"] = np.nan
            q["source_return_abs_error"] = np.nan
            q["source_return_matches_raw"] = False
            rows.append(q)
            continue
        dates = d["session_date"].to_numpy(dtype="datetime64[ns]")
        close = pd.to_numeric(d["close"], errors="coerce").to_numpy(float)
        flagged = classify_daily_integrity(symbol, d, cfg)
        flag_dates = set(pd.to_datetime(flagged["session_date"]).to_numpy(dtype="datetime64[ns]")) if not flagged.empty else set()
        flag_arr = np.array([x in flag_dates for x in dates], dtype=int)
        csum = np.concatenate([[0], np.cumsum(flag_arr)])
        q = p[["symbol", "as_of", "horizon", "test_year"]].copy()
        q["as_of"] = pd.to_datetime(q["as_of"])
        counts=[]; rawret=[]; err=[]; matches=[]; clean=[]
        for _, r in q.iterrows():
            asof=np.datetime64(r["as_of"].to_datetime64()); h=int(r["horizon"])
            idx=int(np.searchsorted(dates, asof, side="left"))
            if idx >= len(dates) or dates[idx] != asof or idx+h >= len(dates) or not np.isfinite(close[idx]) or close[idx] <= 0:
                counts.append(np.nan); rawret.append(np.nan); err.append(np.nan); matches.append(False); clean.append(False); continue
            cnt=int(csum[idx+h+1]-csum[idx+1])
            rr=float(close[idx+h]/close[idx]-1.0) if np.isfinite(close[idx+h]) else np.nan
            src=float(p.loc[r.name, f"fwd_ret_{h}"]) if f"fwd_ret_{h}" in p.columns and pd.notna(p.loc[r.name, f"fwd_ret_{h}"]) else np.nan
            ee=abs(rr-src) if np.isfinite(rr) and np.isfinite(src) else np.nan
            counts.append(cnt); rawret.append(rr); err.append(ee); matches.append(bool(np.isfinite(ee) and ee <= cfg.return_match_tolerance)); clean.append(cnt==0)
        q["raw_authority_present"] = True
        q["interval_integrity_event_count"] = counts
        q["interval_integrity_clean"] = clean
        q["raw_recomputed_return"] = rawret
        q["source_return_abs_error"] = err
        q["source_return_matches_raw"] = matches
        rows.append(q)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _tail_selection(pred: pd.DataFrame, horizon: int, frac: float, direction: str) -> pd.DataFrame:
    parts=[]
    ph=pred[pred["horizon"]==horizon]
    for _, yf in ph.groupby("test_year", sort=True):
        k=max(1,int(len(yf)*frac)); ordered=yf.sort_values("probability_up")
        parts.append(ordered.tail(k) if direction=="LONG" else ordered.head(k))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _transform(vals: pd.Series, treatment: str) -> pd.Series:
    x=pd.to_numeric(vals,errors="coerce").replace([np.inf,-np.inf],np.nan)
    if treatment=="RAW": return x
    if treatment=="WINSOR_99_9":
        lo,hi=x.quantile([.001,.999]); return x.clip(lo,hi)
    if treatment=="WINSOR_99_5":
        lo,hi=x.quantile([.005,.995]); return x.clip(lo,hi)
    if treatment=="TRIM_0_1":
        lo,hi=x.quantile([.001,.999]); return x.where(x.between(lo,hi))
    if treatment=="TRIM_0_5":
        lo,hi=x.quantile([.005,.995]); return x.where(x.between(lo,hi))
    if treatment=="EXCLUDE_ABS_GT_50": return x.where(x.abs()<=.50)
    if treatment=="EXCLUDE_ABS_GT_100": return x.where(x.abs()<=1.00)
    raise ValueError(treatment)


def robust_tail_recalibration(predictions: pd.DataFrame, integrity: pd.DataFrame, cfg: IntegrityConfig) -> tuple[pd.DataFrame,pd.DataFrame]:
    keys=["symbol","as_of","horizon","test_year"]
    p=predictions.copy();p["as_of"]=pd.to_datetime(p["as_of"])
    integ=integrity.copy();integ["as_of"]=pd.to_datetime(integ["as_of"])
    p=p.merge(integ[keys+["interval_integrity_clean","source_return_matches_raw"]],on=keys,how="left",validate="one_to_one")
    treatments=("RAW","WINSOR_99_9","WINSOR_99_5","TRIM_0_1","TRIM_0_5","EXCLUDE_ABS_GT_50","EXCLUDE_ABS_GT_100","INTEGRITY_CLEAN")
    rows=[]; years=[]
    for h in cfg.horizons:
        col=f"fwd_ret_{h}"
        for frac in cfg.tail_fractions:
            for direction in ("LONG","SHORT"):
                sel=_tail_selection(p,h,frac,direction)
                if sel.empty: continue
                sign=1.0 if direction=="LONG" else -1.0
                original=pd.to_numeric(sel[col],errors="coerce")*sign
                for treatment in treatments:
                    if treatment=="INTEGRITY_CLEAN":
                        use=original.where(sel["interval_integrity_clean"].fillna(False) & sel["source_return_matches_raw"].fillna(False))
                    else: use=_transform(original,treatment)
                    valid=use.dropna()
                    rows.append({"horizon":h,"tail_fraction":frac,"direction":direction,"treatment":treatment,"n":int(valid.size),"retained_fraction":float(valid.size/max(original.notna().sum(),1)),"win_rate":float((valid>0).mean()) if len(valid) else np.nan,"mean_return":float(valid.mean()) if len(valid) else np.nan,"median_return":float(valid.median()) if len(valid) else np.nan,"p10":float(valid.quantile(.10)) if len(valid) else np.nan,"p90":float(valid.quantile(.90)) if len(valid) else np.nan})
                    for year, ys in sel.assign(_signed=original).groupby("test_year",sort=True):
                        y=ys["_signed"]
                        if treatment=="INTEGRITY_CLEAN": y=y.where(ys["interval_integrity_clean"].fillna(False)&ys["source_return_matches_raw"].fillna(False))
                        else: y=_transform(y,treatment)
                        y=y.dropna()
                        years.append({"horizon":h,"tail_fraction":frac,"direction":direction,"treatment":treatment,"test_year":int(year),"n":int(len(y)),"win_rate":float((y>0).mean()) if len(y) else np.nan,"mean_return":float(y.mean()) if len(y) else np.nan,"median_return":float(y.median()) if len(y) else np.nan})
    return pd.DataFrame(rows),pd.DataFrame(years)


def contribution_concentration(predictions: pd.DataFrame, integrity: pd.DataFrame, cfg: IntegrityConfig) -> pd.DataFrame:
    keys=["symbol","as_of","horizon","test_year"]
    p=predictions.copy();p["as_of"]=pd.to_datetime(p["as_of"])
    i=integrity.copy();i["as_of"]=pd.to_datetime(i["as_of"])
    p=p.merge(i[keys+["interval_integrity_clean","source_return_matches_raw"]],on=keys,how="left",validate="one_to_one")
    rows=[]
    for h in cfg.horizons:
      col=f"fwd_ret_{h}"
      for frac in cfg.tail_fractions:
       for direction in ("LONG","SHORT"):
        sel=_tail_selection(p,h,frac,direction)
        if sel.empty: continue
        sign=1 if direction=="LONG" else -1
        sel=sel.assign(signed=pd.to_numeric(sel[col],errors="coerce")*sign)
        clean=sel[sel["interval_integrity_clean"].fillna(False)&sel["source_return_matches_raw"].fillna(False)].dropna(subset=["signed"])
        for label,g in (("RAW",sel.dropna(subset=["signed"])),("INTEGRITY_CLEAN",clean)):
            if g.empty: continue
            sym=g.groupby("symbol")["signed"].sum().sort_values(ascending=False)
            yr=g.groupby("test_year")["signed"].sum().sort_values(ascending=False)
            pos_total=float(sym.clip(lower=0).sum())
            top5=float(sym.head(5).clip(lower=0).sum()/pos_total) if pos_total>0 else np.nan
            top10=float(sym.head(10).clip(lower=0).sum()/pos_total) if pos_total>0 else np.nan
            ypos=float(yr.clip(lower=0).sum())
            rows.append({"horizon":h,"tail_fraction":frac,"direction":direction,"treatment":label,"n":len(g),"unique_symbols":g["symbol"].nunique(),"years":g["test_year"].nunique(),"largest_symbol_contribution":float(sym.iloc[0]/pos_total) if pos_total>0 else np.nan,"top5_symbol_positive_contribution_fraction":top5,"top10_symbol_positive_contribution_fraction":top10,"largest_year_positive_contribution_fraction":float(yr.iloc[0]/ypos) if ypos>0 else np.nan,"top3_year_positive_contribution_fraction":float(yr.head(3).clip(lower=0).sum()/ypos) if ypos>0 else np.nan})
    return pd.DataFrame(rows)


def robust_portfolio_recalibration(panel: pd.DataFrame, predictions: pd.DataFrame, integrity: pd.DataFrame, cfg: IntegrityConfig) -> pd.DataFrame:
    keys=["symbol","as_of","horizon","test_year"]
    p=predictions.copy();p["as_of"]=pd.to_datetime(p["as_of"])
    i=integrity.copy();i["as_of"]=pd.to_datetime(i["as_of"])
    p=p.merge(i[keys+["interval_integrity_clean","source_return_matches_raw"]],on=keys,how="left",validate="one_to_one")
    rows=[]
    for treatment in ("RAW","INTEGRITY_CLEAN"):
      base=p if treatment=="RAW" else p[p["interval_integrity_clean"].fillna(False)&p["source_return_matches_raw"].fillna(False)]
      for h in cfg.horizons:
       ph=base[base["horizon"]==h]
       for direction in ("LONG","SHORT"):
        for k in cfg.top_k:
         for cost in (0.0,10.0,25.0,50.0):
            curve=_weekly_portfolio_returns(panel,ph,h,direction,k,cost)
            if curve.empty: continue
            r=pd.to_numeric(curve["net_return"],errors="coerce").fillna(0.0)
            # Portfolio weekly moves beyond +/-100% are never silently accepted.
            if (r<=-1.0).any():
                cagr=np.nan; integrity_status="INVALID_WEEKLY_RETURN_LE_MINUS_100"
            else:
                eq=(1+r).cumprod(); years=max((curve["as_of"].max()-curve["as_of"].min()).days/365.25,1/52); cagr=float(eq.iloc[-1]**(1/years)-1) if eq.iloc[-1]>0 else -1.0; integrity_status="OK"
            eq=(1+r).cumprod();peak=eq.cummax();dd=eq/peak-1
            sd=float(r.std(ddof=1));down=float(r[r<0].std(ddof=1));pos=float(r[r>0].sum());neg=float(-r[r<0].sum())
            rows.append({"treatment":treatment,"horizon":h,"direction":direction,"top_k":k,"cost_bps_round_trip_leg":cost,"weeks":len(r),"cagr":cagr,"mean_weekly_return":float(r.mean()),"sharpe":float(r.mean()/sd*math.sqrt(52)) if np.isfinite(sd) and sd>1e-12 else np.nan,"sortino":float(r.mean()/down*math.sqrt(52)) if np.isfinite(down) and down>1e-12 else np.nan,"max_drawdown":float(dd.min()),"profit_factor":pos/neg if neg>1e-12 else np.nan,"integrity_status":integrity_status})
    return pd.DataFrame(rows)


def write_report(path: Path, summary: dict[str,Any], events: pd.DataFrame, tail: pd.DataFrame, concentration: pd.DataFrame, portfolio: pd.DataFrame) -> None:
    lines=["# M77.21.2.1 Historical Price Integrity & Robust Edge Recalibration","",f"- Version: `{VERSION}`",f"- Status: **{summary['status']}**","- Development-only through 2017-12-31","- Validation opened: **NO**","- Final holdout opened: **NO**","- Production effect: **NONE**","","## Integrity authority","",f"- Frozen daily symbols scanned: {summary['daily_symbols_scanned']}",f"- Suspicious daily events: {summary['daily_integrity_events']}",f"- Walk-forward prediction rows annotated: {summary['prediction_rows_annotated']}",f"- Prediction intervals clean and source-return matched: {summary['clean_prediction_intervals']}","","Suspicious events are research exclusions, not automatic corporate-action diagnoses. Potential split/identity classifications are heuristic and fail closed for economic recalibration.","","## Robust tail recalibration",""]
    if not tail.empty:
        c=tail[tail["treatment"]=="INTEGRITY_CLEAN"].sort_values(["horizon","direction","tail_fraction"]).copy()
        for _,r in c[c["tail_fraction"]<=.05].iterrows():
            lines.append(f"- {r['direction']} H{int(r['horizon'])} {float(r['tail_fraction']):.1%}: n={int(r['n'])}, retained={float(r['retained_fraction']):.1%}, win={float(r['win_rate']):.2%}, mean={float(r['mean_return']):+.2%}, median={float(r['median_return']):+.2%}")
    lines += ["","## Contribution concentration","","Candidate tails are separately evaluated for concentration in the largest symbols and years. High concentration is evidence against a generalizable edge.","","## Portfolio recalibration","","RAW and INTEGRITY_CLEAN weekly overlapping-cohort simulations are both retained. The clean result excludes any selection interval containing a flagged daily discontinuity or a source-vs-raw return mismatch.","","## Governance","","No candidate is promoted. This phase exists solely to remove false economic evidence before any sealed external validation is opened.",""]
    path.write_text("\n".join(lines),encoding="utf-8")


def run_integrity_lab(cfg: IntegrityConfig) -> dict[str,Any]:
    cfg.validate(); root,tail_root,panel_root,raw_root,out=_assert_paths(cfg);out.mkdir(parents=True,exist_ok=True)
    manifest={"version":VERSION,"status":"RUNNING","started_at":datetime.now(timezone.utc).isoformat(),"config":asdict(cfg),"governance":{"development_only":True,"development_end":"2017-12-31","validation_partition_opened":False,"final_holdout_opened":False,"production_authority_effect":False,"polygon_api_called":False,"database_access":"NONE"},"completed_stages":[]};_atomic_json(out/"run_manifest.json",manifest)
    pred=pd.read_csv(tail_root/"walk_forward_predictions.csv.gz",compression="gzip",parse_dates=["as_of"])
    if pd.to_datetime(pred["as_of"]).max()>DEVELOPMENT_END: raise EdgeLabError("walk-forward predictions exceed Development boundary")
    symbols=set(pred["symbol"].dropna().astype(str)); events,daily=scan_daily_authority(raw_root,symbols,cfg);_atomic_csv(out/"daily_integrity_events.csv",events)
    manifest["completed_stages"].append("FROZEN_DAILY_AUTHORITY_INTEGRITY_SCAN");_atomic_json(out/"run_manifest.json",manifest)
    integ=annotate_prediction_integrity(pred,daily,cfg);_atomic_csv(out/"prediction_integrity_evidence.csv.gz",integ,compression="gzip")
    manifest["completed_stages"].append("WALK_FORWARD_INTERVAL_INTEGRITY_ANNOTATION")
    tail,year=robust_tail_recalibration(pred,integ,cfg);_atomic_csv(out/"robust_tail_recalibration.csv",tail);_atomic_csv(out/"robust_year_recalibration.csv",year)
    conc=contribution_concentration(pred,integ,cfg);_atomic_csv(out/"contribution_concentration_evidence.csv",conc)
    panel=pd.read_pickle(panel_root/"checkpoints"/"panel.pkl.gz",compression="gzip");panel["as_of"]=pd.to_datetime(panel["as_of"]);panel=panel[panel["as_of"]<=DEVELOPMENT_END].copy()
    port=robust_portfolio_recalibration(panel,pred,integ,cfg);_atomic_csv(out/"robust_portfolio_recalibration.csv",port)
    manifest["completed_stages"].append("ROBUST_TAIL_YEAR_PORTFOLIO_RECALIBRATION")
    clean=int((integ["interval_integrity_clean"].fillna(False)&integ["source_return_matches_raw"].fillna(False)).sum())
    summary={"version":VERSION,"status":"COMPLETE","development_boundary":"2017-12-31","daily_symbols_scanned":len(daily),"daily_integrity_events":int(len(events)),"prediction_rows_annotated":int(len(integ)),"clean_prediction_intervals":clean,"clean_prediction_fraction":float(clean/max(len(integ),1)),"tail_recalibration_rows":int(len(tail)),"portfolio_recalibration_rows":int(len(port)),"validation_partition_opened":False,"final_holdout_opened":False,"production_authority_effect":False,"polygon_api_called":False,"completed_at":datetime.now(timezone.utc).isoformat()};_atomic_json(out/"historical_price_integrity_summary.json",summary);write_report(out/"HISTORICAL_PRICE_INTEGRITY_REPORT.md",summary,events,tail,conc,port)
    manifest["status"]="COMPLETE";manifest["completed_at"]=summary["completed_at"];manifest["completed_stages"].append("RESEARCH_ONLY_INTEGRITY_REPORT_PUBLISHED");_atomic_json(out/"run_manifest.json",manifest);return summary


def build_arg_parser()->argparse.ArgumentParser:
    ap=argparse.ArgumentParser(description="M77.21.2.1 Development-only historical price integrity and robust edge recalibration")
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--source-tail-root",default="research_data/m77_21_2/multivariate_predictive_tail_lab")
    ap.add_argument("--source-panel-root",default="research_data/m77_21_0/edge_discovery_lab")
    ap.add_argument("--raw-daily-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization/daily_bars")
    ap.add_argument("--output-root",default="research_data/m77_21_2_1/historical_price_integrity_lab")
    return ap


def main(argv:Sequence[str]|None=None)->int:
    a=build_arg_parser().parse_args(argv);cfg=IntegrityConfig(project_root=a.project_root,source_tail_root=a.source_tail_root,source_panel_root=a.source_panel_root,raw_daily_root=a.raw_daily_root,output_root=a.output_root);summary=run_integrity_lab(cfg);print(json.dumps(summary,indent=2,sort_keys=True));return 0
