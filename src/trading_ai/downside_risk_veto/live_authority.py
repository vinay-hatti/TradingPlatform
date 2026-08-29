from __future__ import annotations

import bisect
import hashlib
import importlib.util
import json
import math
import os
import statistics
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text

from trading_ai.research.m77.edge_discovery_lab import add_cross_sectional_ranks, engineer_ohlcv_features
from .service import CHAMPION_ID, CERTIFIED_PROTOCOL, DEFAULT_AUTHORITY, DEFAULT_CHAMPION_META, verify_champion_files

TRAINING_GATE = "reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json"
DEV_HELPER = "scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py"
DEV_EVAL = "reports/m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.json"


def _R(root: Path, raw: str | Path) -> Path:
    p = Path(raw).expanduser(); return p.resolve() if p.is_absolute() else (root / p).resolve()

def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh: return json.load(fh)

def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh: json.dump(payload,fh,indent=2,sort_keys=True,default=str);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def _imp(name: str, path: Path):
    spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def _fl(v):
    if v is None or isinstance(v,bool): return None
    try:
        x=float(v);return x if math.isfinite(x) else None
    except Exception:return None

def _atr1d(p):
    one=(p.get("timeframe_states") or {}).get("1d")
    if not isinstance(one,dict):return None
    hits=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if "atr" in str(k).lower():
                    q=_fl(v)
                    if q is not None:hits.append(q)
                if isinstance(v,dict):walk(v)
    walk(one);u=sorted(set(round(x,14) for x in hits));return float(u[0]) if len(u)==1 else None

def _level_price(x):
    if isinstance(x,(int,float)):return _fl(x)
    if not isinstance(x,dict):return None
    for k in ("price","level","value"):
        q=_fl(x.get(k))
        if q is not None:return q
    return None

def _nearest(levels,ref):
    vals=[q for q in (_level_price(x) for x in (levels or [])) if q is not None]
    if not vals or not ref:return None
    q=min(vals,key=lambda x:abs(x-ref));return (q-ref)/ref

def _history(rows):
    out={}
    for r in rows:out.setdefault(str(r["symbol"]).upper(),[]).append((str(r["date"])[:10],float(r["open"]),float(r["high"]),float(r["low"]),float(r["close"]),float(r["volume"] or 0)))
    for s in out:out[s].sort()
    return out

def _idx(h,d):
    ds=[x[0] for x in h];i=bisect.bisect_right(ds,d)-1;return i if i>=0 else None

def _tr(h,d,n):
    i=_idx(h,d)
    if i is None or i-n<0:return None
    b=h[i-n][4];return None if not b else h[i][4]/b-1

def _loc52(h,d):
    i=_idx(h,d)
    if i is None:return (None,None)
    w=h[max(0,i-251):i+1]
    if len(w)<2:return (None,None)
    c=h[i][4];hi=max(x[4] for x in w);lo=min(x[4] for x in w)
    return (None if not hi else c/hi-1,None if not lo else c/lo-1)

def _weekly_closes(h,d):
    b={}
    for row in h:
        if row[0]>d:continue
        z=date.fromisoformat(row[0]);iso=z.isocalendar();b[(iso.year,iso.week)]=(row[0],row[4])
    return [b[k][1] for k in sorted(b)]

def _wret(c,n):return None if len(c)<=n or not c[-1-n] else c[-1]/c[-1-n]-1

def _wvol(c,n):
    if len(c)<=n:return None
    rs=[c[i]/c[i-1]-1 for i in range(len(c)-n,len(c)) if c[i-1]]
    return None if len(rs)<2 else statistics.stdev(rs)*(52.0**0.5)

def _wdd(c,n):
    if not c:return None
    w=c[-n:] if len(c)>=n else c;p=max(w);return None if not p else c[-1]/p-1

def _publication_asof(pub):
    p=dict(pub.get("payload_json") or {});lin=dict(p.get("lineage") or {})
    return str(lin.get("market_as_of_date") or lin.get("source_as_of_date") or pub["snapshot_timestamp"])[:10]

def _prior_state(authority_path: Path) -> dict[str, dict[str, Any]]:
    if not authority_path.exists():return {}
    try:
        a=_load_json(authority_path);return dict(a.get("prospective_state") or {})
    except Exception:return {}



def _polygon_daily_microstructure(asof: str, wanted_symbols: list[str] | set[str]) -> tuple[dict[str, dict[str, float | None]], dict[str, Any]]:
    """Fetch certified raw Polygon daily aggregate fields used by DRVE champion.

    The production price_history authority intentionally stores OHLCV only, while
    the certified M77 research authority also preserved Polygon aggregate `vw`
    (VWAP) and `n` (transaction count).  DRVE-CHAMPION-001 requires those two raw
    fields.  This performs one grouped-daily Polygon request for the scanner's
    already-frozen as-of date; it does not fetch historical bars and does not
    alter price_history.
    """
    wanted={str(x).strip().upper() for x in wanted_symbols if str(x).strip()}
    if not wanted:
        return {},{"called":False,"as_of":asof,"wanted_symbols":0,"matched_symbols":0,"missing_symbols":[]}

    api_key=os.getenv("POLYGON_API_KEY")
    if not api_key:
        try:
            from trading_ai.config import settings
            api_key=getattr(settings,"polygon_api_key",None)
        except Exception:
            api_key=None
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY is required for certified DRVE vwap/transactions parity")

    from polygon import RESTClient
    client=RESTClient(api_key=str(api_key), connect_timeout=5.0, read_timeout=30.0, num_pools=1, retries=0)
    try:
        try:
            aggregates=client.get_grouped_daily_aggs(date=str(asof), adjusted=True, include_otc=False)
        except TypeError:
            aggregates=client.get_grouped_daily_aggs(date=str(asof), adjusted=True)

        out: dict[str, dict[str, float | None]]={}
        for a in aggregates:
            raw_ticker=str(getattr(a,"ticker",None) or getattr(a,"symbol",None) or "").strip().upper()
            if not raw_ticker:
                continue
            aliases={raw_ticker,raw_ticker.replace(".","-"),raw_ticker.replace("-",".")}
            canonical=next((x for x in aliases if x in wanted),None)
            if canonical is None:
                continue
            vw=_fl(getattr(a,"vwap",None))
            n=_fl(getattr(a,"transactions",None))
            if n is None:
                n=_fl(getattr(a,"transaction_count",None))
            out[canonical]={"vwap":vw,"transactions":n,"provider_ticker":raw_ticker}
        missing=sorted(wanted-set(out))
        return out,{
            "called":True,
            "source":"POLYGON_GROUPED_DAILY_AGGREGATES",
            "as_of":str(asof),
            "adjusted":True,
            "wanted_symbols":len(wanted),
            "matched_symbols":len(out),
            "missing_symbols":missing,
            "vwap_present":sum(1 for x in out.values() if x.get("vwap") is not None),
            "transactions_present":sum(1 for x in out.values() if x.get("transactions") is not None),
        }
    finally:
        close=getattr(client,"close",None)
        if callable(close):
            close()



def _build_live_baseline(root: Path, authority_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    gate=_load_json(_R(root,TRAINING_GATE));dev_eval=_load_json(_R(root,DEV_EVAL));helper=_imp("m77_23_frozen_structured_helper",_R(root,DEV_HELPER))
    certified_cols=list(dev_eval.get("training_feature_columns") or [])
    if len(certified_cols)!=99:raise RuntimeError(f"Certified prospective feature registry invalid: {len(certified_cols)}")
    prior=_prior_state(authority_path)
    from trading_ai.database.session import SessionLocal
    with SessionLocal() as s:
        pub=s.execute(text("""SELECT scanner_run_id,status,snapshot_timestamp,payload_json FROM stock_scanner_publications
            WHERE publication_name='current_stock_intelligence' AND status IN ('READY','DEGRADED') ORDER BY snapshot_timestamp DESC LIMIT 1""")).mappings().first()
        if not pub:raise RuntimeError("No READY/DEGRADED current_stock_intelligence publication")
        pub=dict(pub);asof=_publication_asof(pub)
        candidates=[dict(x) for x in s.execute(text("""SELECT symbol,score,payload_json,snapshot_timestamp FROM stock_scanner_candidates
            WHERE scanner_run_id=:r ORDER BY symbol"""),{"r":pub["scanner_run_id"]}).mappings()]
        symbols=sorted({str(x["symbol"]).upper() for x in candidates});needed=sorted(set(symbols+["SPY"]))
        start=(date.fromisoformat(asof)-timedelta(days=900)).isoformat()
        prices=list(s.execute(text("""SELECT symbol,date,open,high,low,close,volume FROM price_history
            WHERE UPPER(symbol)=ANY(:symbols) AND date>=:start AND date<=:d AND close>0 ORDER BY symbol,date"""),{"symbols":needed,"start":start,"d":asof}).mappings())
        ready_rows=[dict(x) for x in s.execute(text("""SELECT o.symbol,o.direction,e.ready_for_trade_builder,e.payload_json
            FROM institutional_option_opportunities o
            JOIN institutional_option_execution_recommendations e ON e.opportunity_id=o.opportunity_id
            WHERE o.stock_scanner_run_id=:r AND o.state='READY_FOR_EXECUTION'"""),{"r":pub["scanner_run_id"]}).mappings()]
    microstructure,micro_meta=_polygon_daily_microstructure(asof,symbols)
    from trading_ai.institutional_options.trade_builder_authority import classify_trade_builder_authority
    trade_builder_ready_long_symbols={str(x["symbol"]).upper() for x in ready_rows if str(x.get("direction") or "").upper() in {"BULLISH","LONG","CALL"} and classify_trade_builder_authority(x.get("payload_json"),x.get("ready_for_trade_builder")).get("authorized")}
    ph=_history(prices);spy=ph.get("SPY") or [];wc=_weekly_closes(spy,asof);cmap={str(x["symbol"]).upper():x for x in candidates}
    dirs=[str((dict(x.get("payload_json") or {}).get("direction") or "")).upper() for x in candidates];n=len(dirs);bull=sum(x=="BULLISH" for x in dirs);bear=sum(x=="BEARISH" for x in dirs)
    ctx={"F060":None if not n else bull/n,"F061":None if not n else bear/n,"F062":_wret(wc,13),"F063":_wret(wc,26),"F064":_wvol(wc,26),"F065":_wdd(wc,52)}
    rows=[];state={};feature_cols=set()
    for sym in symbols:
        # Certified M77 rows existed only when a Polygon daily aggregate existed
        # for that session.  Do not synthesize/impute an entirely absent current
        # aggregate into the cross-section; missing symbols fail closed later.
        if sym not in microstructure:
            continue
        c=cmap[sym];p=dict(c.get("payload_json") or {});h=ph.get(sym) or [];i=_idx(h,asof);ref=None if i is None else h[i][4]
        atr=_atr1d(p);rs13=_tr(h,asof,65);sp13=_tr(spy,asof,65);rs26=_tr(h,asof,130);sp26=_tr(spy,asof,130);dd,dl=_loc52(h,asof)
        vals={"F001":_fl(c.get("score")),"F002":_fl(p.get("confidence")),"F003":p.get("direction"),"F010":_fl(p.get("alignment_score")),"F011":p.get("primary_timeframe"),
              "F020":atr,"F021":None if atr is None or not ref else atr/ref,"F030":None if not ref else _nearest(p.get("support_levels"),ref),"F031":None if not ref else _nearest(p.get("resistance_levels"),ref),
              "F032":len(p.get("support_levels") or []),"F033":len(p.get("resistance_levels") or []),"F040":(p.get("breakout") or {}).get("state"),"F050":(p.get("participation") or {}).get("state"),"F012":None,"F051":None,
              **ctx,"F070":{"rs_13w":None if rs13 is None or sp13 is None else rs13-sp13,"rs_26w":None if rs26 is None or sp26 is None else rs26-sp26},"F080":dd,"F081":dl}
        prev=prior.get(sym);cur=vals.get("F003")
        if prev is None: vals["F090"]=None;vals["F091"]=None;age=None
        else:
            changed=(prev.get("direction") is not None and cur!=prev.get("direction"));pa=prev.get("direction_age");age=1 if changed else (2 if pa is None else int(pa)+1);vals["F090"]=age;vals["F091"]=bool(changed)
        state[sym]={"direction":cur,"direction_age":age}
        flat=helper.flatten_base_features(vals);flat.update(helper.build_structured(p,gate));feature_cols.update(flat)
        pit={f"pit_{k}":v for k,v in flat.items()}
        # OHLCV technical features use only historical/current bars.
        if len(h)>=260:
            d=pd.DataFrame(h,columns=["as_of","open","high","low","close","volume"]);d["as_of"]=pd.to_datetime(d["as_of"]);d=engineer_ohlcv_features(d);last=d[d.as_of<=pd.Timestamp(asof)].tail(1)
            tech={} if last.empty else {k:last.iloc[0][k] for k in last.columns if k not in {"as_of","open","high","low","close","volume"}}
        else:tech={}
        micro=microstructure.get(sym,{})
        tech["vwap"]=micro.get("vwap")
        tech["transactions"]=micro.get("transactions")
        rows.append({"symbol":sym,"as_of":pd.Timestamp(asof),**tech,**pit})
    if sorted(feature_cols) != sorted(certified_cols):
        missing = sorted(set(certified_cols) - set(feature_cols))
        extra = sorted(set(feature_cols) - set(certified_cols))
        raise RuntimeError(f"Frozen live PIT feature registry mismatch: missing={missing} extra={extra}")
    live=pd.DataFrame(rows);live=add_cross_sectional_ranks(live)
    return live,{"stock_scanner_run_id":str(pub["scanner_run_id"]),"as_of":asof,"snapshot_timestamp":str(pub["snapshot_timestamp"]),"prospective_state":state,"source_feature_columns":sorted(feature_cols),"certified_feature_columns":certified_cols,"trade_builder_ready_long_symbols":sorted(trade_builder_ready_long_symbols),"polygon_daily_microstructure":micro_meta}


def select_bottom_tail(scored: pd.DataFrame, fraction: float = 0.01) -> pd.DataFrame:
    if scored.empty:return scored.copy()
    d=scored.sort_values(["probability_up","symbol"],ascending=[True,True]).reset_index(drop=True)
    n=len(d);k=max(1,int(math.ceil(n*fraction)));d["cross_section_rank"]=np.arange(1,n+1);d["cross_section_percentile"]=d["cross_section_rank"]/n;d["veto"]=False;d.loc[:k-1,"veto"]=True
    return d


def refresh_live_authority(project_root: str | Path) -> dict[str, Any]:
    root=Path(project_root).expanduser().resolve();meta_path=_R(root,DEFAULT_CHAMPION_META);authority_path=_R(root,DEFAULT_AUTHORITY)
    if not meta_path.exists():raise RuntimeError("Certified DRVE champion metadata missing; materialize champion first")
    meta=_load_json(meta_path);verify_champion_files(root,meta)
    if meta.get("champion_id")!=CHAMPION_ID or meta.get("final_holdout_certified") is not True:raise RuntimeError("DRVE champion certification invalid")
    live,ctx=_build_live_baseline(root,authority_path);features=list(meta.get("feature_columns") or [])
    missing=sorted(set(features)-set(live.columns));parity_valid=not missing
    if missing:raise RuntimeError(f"Live feature parity failed; missing champion columns: {missing}")
    model=joblib.load(root/str(meta["model_path"]));X=live.reindex(columns=features).apply(pd.to_numeric,errors="coerce").replace([np.inf,-np.inf],np.nan);proba=model.predict_proba(X)[:,1]
    scored=select_bottom_tail(pd.DataFrame({"symbol":live.symbol.astype(str).str.upper(),"probability_up":proba}),0.01)
    ready_long=set(ctx.get("trade_builder_ready_long_symbols") or [])
    records={r.symbol:{"probability_up":float(r.probability_up),"cross_section_percentile":float(r.cross_section_percentile),"cross_section_rank":int(r.cross_section_rank),"veto":bool(r.veto),"trade_builder_ready_long":r.symbol in ready_long} for r in scored.itertuples()}
    ev=dict(meta.get("final_holdout_evidence") or {})
    payload={"version":"M77.23-CURRENT-DOWNSIDE-RISK-VETO-AUTHORITY-1.0","champion_id":CHAMPION_ID,"protocol":CERTIFIED_PROTOCOL,"generated_at":datetime.now(timezone.utc).isoformat(),
             "stock_scanner_run_id":ctx["stock_scanner_run_id"],"market_as_of_date":ctx["as_of"],"stock_publication_snapshot_timestamp":ctx["snapshot_timestamp"],"model_fingerprint":meta.get("model_fingerprint"),
             "feature_parity_valid":parity_valid,"champion_feature_count":len(features),"scored_symbol_count":len(scored),"veto_count":int(scored.veto.sum()),"veto_fraction":0.01,
             "records":records,"prospective_state":ctx["prospective_state"],"polygon_daily_microstructure":ctx.get("polygon_daily_microstructure"),
             "certification_evidence":{"final_holdout_verdict":"PASS","severe_loss_capture_lift_vs_random":ev.get("severe_loss_capture_lift_vs_random"),"vetoed_loss_10_rate":ev.get("vetoed_loss_10_rate"),"baseline_loss_10_rate":ev.get("baseline_loss_10_rate")},
             "no_automatic_retraining":True,"production_scope":"TRADE_BUILDER_READY_LONG_ONLY"}
    history = authority_path.parent / "history" / f"{ctx['as_of']}_{ctx['stock_scanner_run_id']}.json"
    if not history.exists():
        _atomic_json(history, payload)
    _atomic_json(authority_path,payload);return payload
