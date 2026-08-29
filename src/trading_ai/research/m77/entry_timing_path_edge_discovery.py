from __future__ import annotations

import argparse
import json
import math
import os
from io import StringIO
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import numpy as np
import pandas as pd

from trading_ai.research.m77.edge_discovery_lab import (
    EdgeLabError,
    engineer_ohlcv_features,
    read_daily_file,
)
from trading_ai.research.m77.positive_selection_edge_discovery import (
    PositiveSelectionConfig,
    load_development_authority,
)

VERSION = "M77.25.0-ENTRY-TIMING-PATH-DEPENDENT-EDGE-DISCOVERY-1.0"
DEVELOPMENT_END = pd.Timestamp("2017-12-31")
DRVE_REFERENCE_HORIZON = 20
OUTCOME_HORIZONS = (20, 30, 45, 60)
MAX_WAIT = 5
GEOMETRIES = ((1.5, 1.0), (2.0, 1.0), (3.0, 1.0))
POLICIES = (
    "NEXT_OPEN",
    "DELAY1_CLOSE",
    "CONFIRM_CLOSE_ABOVE_ASOF_HIGH",
    "PULLBACK_0P5_ATR",
    "PULLBACK_1P0_ATR",
    "BREAKOUT_0P5_ATR",
    "BREAKOUT_1P0_ATR",
    "CLOSE_BREAKOUT_20D",
)

PATH_STATES = (
    "MOM5_POSITIVE",
    "MOM5_NEGATIVE_OR_FLAT",
    "ABOVE_SMA20",
    "BELOW_SMA20",
    "RSI_40_60",
    "RSI_GT_60",
    "ATR_PCT_HIGH",
    "ATR_PCT_LOW",
)


class EntryTimingError(RuntimeError):
    pass


@dataclass(frozen=True)
class EntryTimingConfig:
    project_root: str
    daily_root: str = "research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization"
    prediction_path: str = "research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"
    integrity_path: str = "research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz"
    pit_candidate_path: str = "research_data/m77_22_3/point_in_time_long_candidate_veto/checkpoints/pit_long_candidate_authority.csv.gz"
    output_dir: str = "research_data/m77_25/entry_timing_path_dependent_edge_discovery"
    workers: int = 6


def _resolve(root: Path, raw: str) -> Path:
    p=Path(raw).expanduser()
    return p if p.is_absolute() else root/p


def _json_default(v: Any) -> Any:
    if isinstance(v,(np.integer,)): return int(v)
    if isinstance(v,(np.floating,)): return None if not np.isfinite(v) else float(v)
    if isinstance(v,(pd.Timestamp,datetime)): return v.isoformat()
    if isinstance(v,Path): return str(v)
    raise TypeError(type(v).__name__)


def _atomic_json(path: Path,payload: Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True,default=_json_default))
    os.replace(tmp,path)


def _md(df: pd.DataFrame,n: int=30)->str:
    if df.empty:return "_No rows._"
    x=df.head(n)
    cols=[str(c) for c in x.columns]
    def f(v:Any)->str:
        if pd.isna(v):return ""
        if isinstance(v,(float,np.floating)):return f"{float(v):.6g}"
        return str(v).replace("|","\\|").replace("\n"," ")
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join("---" for _ in cols)+" |"]
    for _,r in x.iterrows():lines.append("| "+" | ".join(f(r[c]) for c in x.columns)+" |")
    return "\n".join(lines)


def load_candidate_dates(cfg: EntryTimingConfig) -> tuple[pd.DataFrame,dict[str,Any]]:
    pcfg=PositiveSelectionConfig(
        project_root=cfg.project_root,
        prediction_path=cfg.prediction_path,
        integrity_path=cfg.integrity_path,
        pit_candidate_path=cfg.pit_candidate_path,
    )
    panel,meta=load_development_authority(pcfg)
    # The certified DRVE protocol is 20 sessions. Use only that historical
    # reference surface to define the pass population, then study timing independently.
    c=panel[panel["horizon"]==DRVE_REFERENCE_HORIZON].copy()
    if c.empty:
        raise EntryTimingError("No Development Trade-Builder-ready + DRVE-pass candidate dates")
    cols=["symbol","as_of"]
    for x in ("probability_up","overall_score","score_overall","idi_trade_quality","score_options_suitability"):
        if x in c.columns:cols.append(x)
    c=c[cols].drop_duplicates(["symbol","as_of"],keep="last").sort_values(["symbol","as_of"])
    if (c["as_of"]>DEVELOPMENT_END).any():
        raise EntryTimingError("M77.25 refuses post-2017 candidate data")
    return c,meta


def _first_idx(mask: np.ndarray,start: int,end: int)->int|None:
    idx=np.flatnonzero(mask[start:end+1])
    return None if len(idx)==0 else int(start+idx[0])


def _entry_for_policy(df: pd.DataFrame,i: int,policy: str)->tuple[int,float,str]|None:
    if i+1>=len(df):return None
    row=df.iloc[i]
    close=float(row["close"]);atr=float(row["atr_14"])
    if not (math.isfinite(close) and math.isfinite(atr) and atr>0):return None
    start=i+1;end=min(len(df)-1,i+MAX_WAIT)
    o=df["open"].to_numpy(float);h=df["high"].to_numpy(float);l=df["low"].to_numpy(float);c=df["close"].to_numpy(float)
    if policy=="NEXT_OPEN":
        return start,float(o[start]),"OPEN"
    if policy=="DELAY1_CLOSE":
        return start,float(c[start]),"CLOSE"
    if policy=="CONFIRM_CLOSE_ABOVE_ASOF_HIGH":
        j=_first_idx(c>float(row["high"]),start,end)
        return None if j is None else (j,float(c[j]),"CLOSE")
    if policy=="PULLBACK_0P5_ATR":
        px=close-0.5*atr;j=_first_idx(l<=px,start,end)
        return None if j is None else (j,px,"TOUCH")
    if policy=="PULLBACK_1P0_ATR":
        px=close-1.0*atr;j=_first_idx(l<=px,start,end)
        return None if j is None else (j,px,"TOUCH")
    if policy=="BREAKOUT_0P5_ATR":
        px=close+0.5*atr;j=_first_idx(h>=px,start,end)
        return None if j is None else (j,px,"TOUCH")
    if policy=="BREAKOUT_1P0_ATR":
        px=close+1.0*atr;j=_first_idx(h>=px,start,end)
        return None if j is None else (j,px,"TOUCH")
    if policy=="CLOSE_BREAKOUT_20D":
        prior_high=float(row.get("prev_high_20",np.nan))
        if not math.isfinite(prior_high):return None
        j=_first_idx(c>prior_high,start,end)
        return None if j is None else (j,float(c[j]),"CLOSE")
    raise EntryTimingError(f"Unknown policy: {policy}")


def _outcomes(df:pd.DataFrame,entry_idx:int,entry_px:float,entry_kind:str,horizon:int,atr:float)->dict[str,Any]|None:
    # Touch/close trigger-day bars are not used for target/stop path outcomes.
    # The earliest path-observation session is the next session for every policy,
    # avoiding daily-OHLC ordering leakage and making policies comparable.
    start=entry_idx+1
    terminal=entry_idx+horizon
    if start>=len(df) or terminal>=len(df):return None
    future=df.iloc[start:terminal+1]
    terminal_close=float(df.iloc[terminal]["close"])
    highs=future["high"].to_numpy(float);lows=future["low"].to_numpy(float)
    out={
        "return":terminal_close/entry_px-1.0,
        "mfe":float(np.nanmax(highs)/entry_px-1.0),
        "mae":float(np.nanmin(lows)/entry_px-1.0),
        "mfe_atr":float((np.nanmax(highs)-entry_px)/atr),
        "mae_atr":float((np.nanmin(lows)-entry_px)/atr),
    }
    for target,stop in GEOMETRIES:
        t=entry_px+target*atr;s=entry_px-stop*atr
        th=np.flatnonzero(highs>=t);sl=np.flatnonzero(lows<=s)
        td=np.inf if len(th)==0 else int(th[0])+1
        sd=np.inf if len(sl)==0 else int(sl[0])+1
        # Same future daily bar target+stop is ambiguous and excluded.
        if np.isfinite(td) and np.isfinite(sd) and td==sd:result=np.nan
        elif td<sd:result=1.0
        elif sd<td:result=-1.0
        else:result=0.0
        tag=f"t{str(target).replace('.','p')}_s{str(stop).replace('.','p')}"
        out[f"barrier_{tag}"]=result
    return out


def _states(row:pd.Series,atr_rank:float|None)->dict[str,bool]:
    r5=float(row.get("px_ret_5",np.nan));ds=float(row.get("dist_sma_20",np.nan));rsi=float(row.get("rsi_14",np.nan))
    return {
        "MOM5_POSITIVE":bool(math.isfinite(r5) and r5>0),
        "MOM5_NEGATIVE_OR_FLAT":bool(math.isfinite(r5) and r5<=0),
        "ABOVE_SMA20":bool(math.isfinite(ds) and ds>0),
        "BELOW_SMA20":bool(math.isfinite(ds) and ds<=0),
        "RSI_40_60":bool(math.isfinite(rsi) and 40<=rsi<=60),
        "RSI_GT_60":bool(math.isfinite(rsi) and rsi>60),
        "ATR_PCT_HIGH":bool(atr_rank is not None and atr_rank>=0.75),
        "ATR_PCT_LOW":bool(atr_rank is not None and atr_rank<=0.25),
    }


def _process_symbol(args:tuple[str,str,str,list[str],list[str]])->tuple[str,list[dict[str,Any]],str|None]:
    symbol,raw_path,candidate_json,policies,horizons=args
    try:
        candidates=pd.read_json(StringIO(candidate_json),orient="records")
        candidates["as_of"]=pd.to_datetime(candidates["as_of"])
        df=read_daily_file(Path(raw_path),DEVELOPMENT_END.date().isoformat())
        if len(df)<320:return symbol,[],"INSUFFICIENT_HISTORY"
        df=engineer_ohlcv_features(df)
        prev_hi=df["high"].shift(1).rolling(20,min_periods=20).max()
        df["prev_high_20"]=prev_hi
        by_date={pd.Timestamp(d).normalize():i for i,d in enumerate(df["as_of"])}
        rows=[]
        for _,cand in candidates.iterrows():
            d=pd.Timestamp(cand["as_of"]).normalize();i=by_date.get(d)
            if i is None:continue
            base=df.iloc[i];atr=float(base.get("atr_14",np.nan))
            if not math.isfinite(atr) or atr<=0:continue
            common={
                "symbol":symbol,"as_of":d,"candidate_close":float(base["close"]),"candidate_atr":atr,
                "px_ret_5":base.get("px_ret_5"),"dist_sma_20":base.get("dist_sma_20"),
                "rsi_14":base.get("rsi_14"),"atr_pct_14":base.get("atr_pct_14"),
            }
            for policy in policies:
                ent=_entry_for_policy(df,i,policy)
                if ent is None:
                    for horizon in horizons:
                        rows.append({**common,"policy":policy,"horizon":int(horizon),"triggered":False})
                    continue
                ei,ep,kind=ent;wait=ei-i
                for horizon in horizons:
                    o=_outcomes(df,ei,ep,kind,int(horizon),atr)
                    if o is None:continue
                    rows.append({**common,"policy":policy,"horizon":int(horizon),"triggered":True,
                                 "entry_date":df.iloc[ei]["as_of"],"wait_sessions":wait,
                                 "entry_price":ep,"entry_kind":kind,**o})
        if not rows:
            return symbol,[],"NO_CANDIDATE_DATES_MATCHED_RAW_SESSIONS"
        return symbol,rows,None
    except Exception as exc:
        return symbol,[],f"{type(exc).__name__}: {exc}"



def _safe_symbol_from_daily_filename(path: Path) -> str:
    suffix=".daily.csv.gz"
    stem=path.name[:-len(suffix)] if path.name.endswith(suffix) else path.stem
    # Match the certified M77 replay materializer's filename encoding contract.
    try:
        return unquote(stem.replace("_","%"))
    except Exception:
        return stem


def _discover_daily_symbol_paths(daily_root: Path) -> tuple[dict[str,Path],dict[str,Any]]:
    files=sorted(daily_root.rglob("*.daily.csv.gz"))
    if not files:
        raise EntryTimingError(f"No *.daily.csv.gz files found recursively under {daily_root}")
    paths:dict[str,Path]={}
    duplicates:dict[str,list[str]]={}
    for p in files:
        sym=_safe_symbol_from_daily_filename(p)
        if sym in paths and paths[sym]!=p:
            duplicates.setdefault(sym,[str(paths[sym])]).append(str(p))
            continue
        paths[sym]=p
    meta={
        "daily_files_discovered":len(files),
        "decoded_symbols_discovered":len(paths),
        "duplicate_decoded_symbols":duplicates,
    }
    return paths,meta


def build_timing_panel(cfg:EntryTimingConfig,candidates:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    root=Path(cfg.project_root).resolve();daily=_resolve(root,cfg.daily_root)
    if not daily.exists():raise EntryTimingError(f"Daily authority missing: {daily}")
    paths,discovery_meta=_discover_daily_symbol_paths(daily)
    tasks=[];unmatched=[]
    candidate_symbols=sorted({str(x) for x in candidates["symbol"].dropna().astype(str)})
    for symbol,g in candidates.groupby("symbol",sort=False):
        symbol=str(symbol)
        p=paths.get(symbol)
        if p is None:
            unmatched.append(symbol)
            continue
        tasks.append((symbol,str(p),g.to_json(orient="records",date_format="iso"),list(POLICIES),[str(x) for x in OUTCOME_HORIZONS]))
    if not tasks:
        sample_files=sorted(list(paths))[:20]
        sample_candidates=candidate_symbols[:20]
        raise EntryTimingError(
            "No candidate symbols matched recursive daily authority; "
            f"candidate_symbols={len(candidate_symbols)} decoded_daily_symbols={len(paths)} "
            f"sample_candidates={sample_candidates} sample_daily_symbols={sample_files}"
        )
    rows=[];fails=[]
    if cfg.workers<=1:
        results=map(_process_symbol,tasks)
        for sym,r,e in results:
            rows.extend(r)
            if e:fails.append({"symbol":sym,"error":e})
    else:
        with ProcessPoolExecutor(max_workers=cfg.workers) as ex:
            futs=[ex.submit(_process_symbol,t) for t in tasks]
            for fut in as_completed(futs):
                sym,r,e=fut.result();rows.extend(r)
                if e:fails.append({"symbol":sym,"error":e})
    panel=pd.DataFrame(rows)
    if panel.empty:
        failure_counts={}
        for item in fails:
            err=str(item.get("error") or "UNKNOWN")
            failure_counts[err]=failure_counts.get(err,0)+1
        ranked=sorted(failure_counts.items(),key=lambda kv:(-kv[1],kv[0]))
        samples=fails[:20]
        raise EntryTimingError(
            "No entry timing observations materialized after matched-symbol worker execution; "
            f"matched_candidate_symbols={len(tasks)} worker_failures={len(fails)} "
            f"top_failure_counts={ranked[:10]} failure_samples={samples}"
        )
    panel["as_of"]=pd.to_datetime(panel["as_of"])
    panel["entry_date"]=pd.to_datetime(panel.get("entry_date"),errors="coerce")
    # Cross-sectional ATR rank is computed from candidate-date state only.
    atr_base=panel[["symbol","as_of","atr_pct_14"]].drop_duplicates(["symbol","as_of"])
    atr_base["atr_pct_rank"]=atr_base.groupby("as_of")["atr_pct_14"].rank(pct=True,method="average")
    panel=panel.merge(atr_base[["symbol","as_of","atr_pct_rank"]],on=["symbol","as_of"],how="left")
    fail_frame=pd.DataFrame(fails)
    panel.attrs["daily_authority_diagnostics"]={
        **discovery_meta,
        "candidate_symbols":len(candidate_symbols),
        "matched_candidate_symbols":len(tasks),
        "unmatched_candidate_symbols":len(unmatched),
        "unmatched_candidate_symbol_sample":sorted(unmatched)[:50],
    }
    return panel,fail_frame


def _metric(g:pd.DataFrame)->dict[str,Any]:
    z=g[g["triggered"]==True].copy()
    r=pd.to_numeric(z["return"],errors="coerce").dropna()
    if r.empty:return {"triggered_n":0}
    z=z.loc[r.index]
    sym=z.assign(_r=r).groupby("symbol")["_r"].mean()
    return {
        "triggered_n":int(len(r)),"symbols":int(z["symbol"].nunique()),
        "trigger_rate":float(g["triggered"].mean()),
        "mean_wait_sessions":float(z["wait_sessions"].mean()),
        "win_rate":float((r>0).mean()),"mean_return":float(r.mean()),"median_return":float(r.median()),
        "loss_10_rate":float((r<=-0.10).mean()),
        "mean_mfe_atr":float(pd.to_numeric(z["mfe_atr"],errors="coerce").mean()),
        "mean_mae_atr":float(pd.to_numeric(z["mae_atr"],errors="coerce").mean()),
        "equal_symbol_mean_return":float(sym.mean()) if len(sym) else np.nan,
        "positive_symbol_fraction":float((sym>0).mean()) if len(sym) else np.nan,
    }


def evidence_tables(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    rows=[];years=[];states=[];stress=[]
    for horizon in OUTCOME_HORIZONS:
        h=panel[panel["horizon"]==horizon].copy()
        base=h[h["policy"]=="NEXT_OPEN"].copy()
        bm=_metric(base)
        for policy in POLICIES:
            g=h[h["policy"]==policy].copy();m=_metric(g)
            if m.get("triggered_n",0)==0:continue
            row={"horizon":horizon,"policy":policy,**m,
                 "baseline_win_rate":bm.get("win_rate"),"win_rate_uplift":m.get("win_rate",np.nan)-bm.get("win_rate",np.nan),
                 "baseline_mean_return":bm.get("mean_return"),"baseline_equal_symbol_mean_return":bm.get("equal_symbol_mean_return"),"mean_return_uplift":m.get("mean_return",np.nan)-bm.get("mean_return",np.nan),
                 "baseline_loss_10_rate":bm.get("loss_10_rate"),"loss_10_rate_change":m.get("loss_10_rate",np.nan)-bm.get("loss_10_rate",np.nan),
                 "mae_atr_improvement":m.get("mean_mae_atr",np.nan)-bm.get("mean_mae_atr",np.nan)}
            for target,stop in GEOMETRIES:
                tag=f"t{str(target).replace('.','p')}_s{str(stop).replace('.','p')}"
                vals=pd.to_numeric(g.loc[g["triggered"]==True,f"barrier_{tag}"],errors="coerce").dropna()
                row[f"barrier_expectancy_{tag}"]=float(vals.mean()) if len(vals) else np.nan
            rows.append(row)
            for year,yg in g.groupby(g["as_of"].dt.year):
                ym=_metric(yg);yb=_metric(base[base["as_of"].dt.year==year])
                if ym.get("triggered_n",0):
                    years.append({"horizon":horizon,"policy":policy,"year":int(year),
                                  "triggered_n":ym["triggered_n"],
                                  "win_rate_uplift":ym.get("win_rate",np.nan)-yb.get("win_rate",np.nan),
                                  "mean_return_uplift":ym.get("mean_return",np.nan)-yb.get("mean_return",np.nan),
                                  "loss_10_rate_change":ym.get("loss_10_rate",np.nan)-yb.get("loss_10_rate",np.nan)})
            # Fixed candidate-date path-state interactions, not used to redefine the primary cohort.
            for state in PATH_STATES:
                flags=[]
                for _,r in g.iterrows():flags.append(_states(r,r.get("atr_pct_rank")).get(state,False))
                sg=g[pd.Series(flags,index=g.index)]
                if len(sg)==0:continue
                sm=_metric(sg);sb=_metric(base[base.set_index(["symbol","as_of"]).index.isin(sg.set_index(["symbol","as_of"]).index)])
                if sm.get("triggered_n",0):
                    states.append({"horizon":horizon,"policy":policy,"path_state":state,
                                   "triggered_n":sm["triggered_n"],
                                   "win_rate_uplift_vs_state_baseline":sm.get("win_rate",np.nan)-sb.get("win_rate",np.nan),
                                   "mean_return_uplift_vs_state_baseline":sm.get("mean_return",np.nan)-sb.get("mean_return",np.nan)})
            # Non-overlap: keep first entry per symbol until horizon approx elapsed.
            z=g[g["triggered"]==True].sort_values(["symbol","entry_date"])
            keep=[]
            for _,sg in z.groupby("symbol",sort=False):
                last=None
                for idx,r in sg.iterrows():
                    d=pd.Timestamp(r["entry_date"])
                    if last is None or (d-last).days>=math.ceil(horizon*7/5):
                        keep.append(idx);last=d
            nm=_metric(g.loc[keep] if keep else g.iloc[0:0])
            stress.append({"horizon":horizon,"policy":policy,"stress":"NON_OVERLAP",
                           "n":nm.get("triggered_n",0),"win_rate":nm.get("win_rate"),
                           "mean_return":nm.get("mean_return"),"equal_symbol_mean_return":nm.get("equal_symbol_mean_return")})
    return pd.DataFrame(rows),pd.DataFrame(years),pd.DataFrame(states),pd.DataFrame(stress)


def readiness(evidence:pd.DataFrame,years:pd.DataFrame,stress:pd.DataFrame)->pd.DataFrame:
    if evidence.empty:return pd.DataFrame()
    y=years.assign(pos=lambda x:(x["win_rate_uplift"]>0)&(x["mean_return_uplift"]>0)).groupby(["horizon","policy"])["pos"].agg(["sum","count"]).reset_index()
    y["positive_year_fraction"]=y["sum"]/y["count"].replace(0,np.nan)
    n=stress[stress["stress"]=="NON_OVERLAP"][["horizon","policy","n","win_rate","mean_return","equal_symbol_mean_return"]].rename(
        columns={"n":"nonoverlap_n","win_rate":"nonoverlap_win_rate","mean_return":"nonoverlap_mean_return","equal_symbol_mean_return":"nonoverlap_equal_symbol_mean_return"})
    out=evidence.merge(y[["horizon","policy","positive_year_fraction"]],on=["horizon","policy"],how="left").merge(n,on=["horizon","policy"],how="left")
    out["gate_not_baseline"]=out["policy"]!="NEXT_OPEN"
    out["gate_trigger_rate"]=out["trigger_rate"]>=0.30
    out["gate_min_n"]=out["triggered_n"]>=750
    out["gate_min_symbols"]=out["symbols"]>=150
    out["gate_win_uplift"]=out["win_rate_uplift"]>=0.02
    out["gate_return_uplift"]=out["mean_return_uplift"]>=0.0025
    out["gate_loss10_no_worse"]=out["loss_10_rate_change"]<=0
    out["gate_equal_symbol"]=out["equal_symbol_mean_return"]>out["baseline_equal_symbol_mean_return"]
    out["gate_nonoverlap"]=out["nonoverlap_win_rate"]>=out["baseline_win_rate"]+0.01
    out["gate_year_stability"]=out["positive_year_fraction"]>=0.70
    out["gate_barrier"]=out.get("barrier_expectancy_t2p0_s1p0",pd.Series(False,index=out.index))>0
    gates=[c for c in out.columns if c.startswith("gate_")]
    out["development_ready"]=out[gates].all(axis=1)
    return out.sort_values(["development_ready","win_rate_uplift","mean_return_uplift"],ascending=[False,False,False]).reset_index(drop=True)


def run_lab(cfg:EntryTimingConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    candidates,meta=load_candidate_dates(cfg)
    panel,fails=build_timing_panel(cfg,candidates)
    evidence,years,states,stress=evidence_tables(panel)
    ready=readiness(evidence,years,stress)

    panel.to_csv(outdir/"entry_timing_observation_panel.csv.gz",index=False,compression="gzip")
    evidence.to_csv(outdir/"entry_timing_policy_evidence.csv",index=False)
    years.to_csv(outdir/"entry_timing_year_evidence.csv",index=False)
    states.to_csv(outdir/"entry_timing_path_state_evidence.csv",index=False)
    stress.to_csv(outdir/"entry_timing_nonoverlap_stress.csv",index=False)
    ready.to_csv(outdir/"entry_timing_readiness.csv",index=False)
    fails.to_csv(outdir/"entry_timing_symbol_failures.csv",index=False)

    report=[
        "# M77.25 Entry Timing & Path-Dependent Edge Discovery","",
        "## Governance","",
        "- Development-only candidate and price authority through 2017-12-31.",
        "- Candidate population is PIT Trade-Builder-ready LONG after the certified DRVE reference veto.",
        "- M77.24 prospective PSVE-CANDIDATE-001 is not read or modified.",
        "- Touch/confirmation trigger-day bars are excluded from target/stop path evaluation.",
        "- No result authorizes production; 2018-2026 remain consumed for new historical certification.","",
        "## Development-ready timing candidates","",_md(ready[ready["development_ready"]==True]),"",
        "## Highest-ranked timing configurations","",_md(ready.head(25)),"",
    ]
    (outdir/"ENTRY_TIMING_PATH_DEPENDENT_EDGE_REPORT.md").write_text("\n".join(report))
    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31","consumed_2018_2026_rows_read":0,
        "candidate_dates":int(len(candidates)),"candidate_symbols":int(candidates["symbol"].nunique()),
        "daily_authority_diagnostics":dict(panel.attrs.get("daily_authority_diagnostics") or {}),
        "timing_observation_rows":int(len(panel)),"policies":list(POLICIES),
        "outcome_horizons":list(OUTCOME_HORIZONS),"max_wait_sessions":MAX_WAIT,
        "development_ready_timing_configurations":int(ready["development_ready"].sum()) if not ready.empty else 0,
        "path_state_rows":int(len(states)),"symbol_failures":int(len(fails)),
        "m77_24_prospective_protocol_read":False,"m77_24_prospective_protocol_modified":False,
        "production_authority_effect":False,"polygon_api_called":False,
        "next_step":"REVIEW DEVELOPMENT-ONLY ENTRY-TIMING CANDIDATES; DO NOT USE CONSUMED 2018-2026 TO RETUNE",
        "upstream_sha256":meta,
    }
    _atomic_json(outdir/"entry_timing_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{"version":VERSION,"config":cfg.__dict__,"summary":summary})
    return summary


def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.25 Development-only entry timing/path edge discovery")
    p.add_argument("--project-root",required=True)
    p.add_argument("--daily-root",default=EntryTimingConfig.daily_root)
    p.add_argument("--prediction-path",default=EntryTimingConfig.prediction_path)
    p.add_argument("--integrity-path",default=EntryTimingConfig.integrity_path)
    p.add_argument("--pit-candidate-path",default=EntryTimingConfig.pit_candidate_path)
    p.add_argument("--output-dir",default=EntryTimingConfig.output_dir)
    p.add_argument("--workers",type=int,default=max(1,min(6,(os.cpu_count() or 4)-1)))
    return p


def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=EntryTimingConfig(project_root=a.project_root,daily_root=a.daily_root,prediction_path=a.prediction_path,
                          integrity_path=a.integrity_path,pit_candidate_path=a.pit_candidate_path,
                          output_dir=a.output_dir,workers=a.workers)
    print(json.dumps(run_lab(cfg),indent=2,sort_keys=True,default=_json_default))
    return 0
