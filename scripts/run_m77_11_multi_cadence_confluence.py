#!/usr/bin/env python3
from __future__ import annotations

import argparse, bisect, json, math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

from sqlalchemy import text
from trading_ai.database.session import SessionLocal

VERSION = "M77.11-MULTI-CADENCE-CONFLUENCE-CONFLICT-1.0"
CONFIRM = "RUN_M77_11_MULTI_CADENCE_CONFLUENCE"

WEEKLY_MANIFEST = Path("reports/m77/m77_2_multiyear_frozen_champion_manifest.json")
DAILY_MANIFEST = Path("reports/m77/m77_9_daily_model_replay_manifest.json")
DAILY_CERT = Path("reports/m77/m77_9_daily_walk_forward_certification.json")
MONTHLY_MANIFEST = Path("reports/m77/m77_10_monthly_model_replay_manifest.json")
MONTHLY_CERT = Path("reports/m77/m77_10_monthly_walk_forward_certification.json")
PIT = Path("reports/m77/m77_8_daily_pit_regime_snapshots.json")

OUT = Path("reports/m77/m77_11_multi_cadence_confluence_conflict_study.json")
HORIZONS = (5, 10, 20, 60, 120)
MIN_N = {5: 100, 10: 100, 20: 100, 60: 75, 120: 50}
MIN_INCREMENTAL = {5: .10, 10: .10, 20: .15, 60: .25, 120: .35}
MIN_HIT = 52.0

def family(direction):
    d = str(direction or "").upper()
    if d in ("BULLISH", "STRONG_BULLISH"): return "BULLISH"
    if d in ("BEARISH", "STRONG_BEARISH"): return "BEARISH"
    return "NEUTRAL"

def score_band(x):
    if x is None: return "S_UNKNOWN"
    x=float(x)
    if x<60:return "S_LT60"
    if x<70:return "S60_69"
    if x<80:return "S70_79"
    if x<90:return "S80_89"
    return "S90_100"

def conf_band(x):
    if x is None:return "C_UNKNOWN"
    x=float(x)
    if x<70:return "C_LT70"
    if x<80:return "C70_79"
    return "C80_100"

def classify(d,w,m):
    if d==w==m=="BULLISH": return "FULL_BULLISH_CONFLUENCE"
    if d==w==m=="BEARISH": return "FULL_BEARISH_CONFLUENCE"
    if w=="BULLISH" and m=="BULLISH" and d=="BEARISH": return "DAILY_BEARISH_COUNTERTREND"
    if w=="BEARISH" and m=="BEARISH" and d=="BULLISH": return "DAILY_BULLISH_COUNTERTREND"
    if d=="BULLISH" and w=="BULLISH" and m!="BULLISH": return "SHORT_MEDIUM_BULLISH_CONFLUENCE"
    if d=="BEARISH" and w=="BEARISH" and m!="BEARISH": return "SHORT_MEDIUM_BEARISH_CONFLUENCE"
    if w=="BULLISH" and m=="BULLISH" and d!="BULLISH": return "MEDIUM_LONG_BULLISH_CONFLUENCE"
    if w=="BEARISH" and m=="BEARISH" and d!="BEARISH": return "MEDIUM_LONG_BEARISH_CONFLUENCE"
    if d=="BULLISH" and m=="BULLISH" and w!="BULLISH": return "WEEKLY_BEARISH_OR_NEUTRAL_CONFLICT"
    if d=="BEARISH" and m=="BEARISH" and w!="BEARISH": return "WEEKLY_BULLISH_OR_NEUTRAL_CONFLICT"
    return "MIXED_OR_NEUTRAL"

def thesis_family(d,w,m):
    xs=(d,w,m)
    b=sum(x=="BULLISH" for x in xs)
    s=sum(x=="BEARISH" for x in xs)
    if b>=2:return "BULLISH"
    if s>=2:return "BEARISH"
    return "NEUTRAL"

def align(raw, thesis):
    if thesis=="BEARISH": return -raw
    if thesis=="BULLISH": return raw
    return None

def stat(vals):
    vals=[x for x in vals if x is not None]
    if not vals:return {"n":0,"mean_pct":None,"hit_rate_pct":None,"stdev_pct":None,"t_approx":None}
    n=len(vals); m=mean(vals); sd=pstdev(vals) if n>1 else 0
    return {"n":n,"mean_pct":m,"hit_rate_pct":100*sum(x>0 for x in vals)/n,
            "stdev_pct":sd,"t_approx":(m/(sd/math.sqrt(n))) if sd>0 else None}

def latest_le(index, symbol, d):
    row=index.get(symbol)
    if not row:return None
    dates,vals=row
    i=bisect.bisect_right(dates,d)-1
    return vals[i] if i>=0 else None

def build_index(rows):
    g=defaultdict(list)
    for r in rows:g[str(r["symbol"])].append(dict(r))
    out={}
    for sym,rs in g.items():
        rs.sort(key=lambda x:str(x["as_of"])[:10])
        out[sym]=([str(x["as_of"])[:10] for x in rs],rs)
    return out

def nonoverlap(rows,h,session_index):
    # deterministic per-symbol non-overlap using the actual SPY session index
    by=defaultdict(list)
    for r in rows: by[r["symbol"]].append(r)
    out=[]
    for sym,rs in by.items():
        rs.sort(key=lambda x:x["as_of"])
        last=-10**9
        for r in rs:
            i=session_index.get(r["as_of"])
            if i is None: continue
            if i-last>=h:
                out.append(r); last=i
    return out

def certified_sets(path):
    d=json.loads(path.read_text())
    out=set()
    for x in d.get("cohort_certification",[]):
        if not x.get("certified"): continue
        out.add((
            int(x["horizon_sessions"]),
            x.get("regime"),
            x.get("direction"),
            x.get("score_band"),
            x.get("confidence_band"),
        ))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["preflight","run"])
    ap.add_argument("--confirm")
    a=ap.parse_args()

    required=(WEEKLY_MANIFEST,DAILY_MANIFEST,DAILY_CERT,MONTHLY_MANIFEST,MONTHLY_CERT,PIT)
    missing=[str(p) for p in required if not p.exists()]
    if missing: raise SystemExit("Missing required M77 artifacts: "+", ".join(missing))

    wm=json.loads(WEEKLY_MANIFEST.read_text())
    dm=json.loads(DAILY_MANIFEST.read_text())
    mm=json.loads(MONTHLY_MANIFEST.read_text())
    dc=json.loads(DAILY_CERT.read_text())
    mc=json.loads(MONTHLY_CERT.read_text())

    weekly_ids=list(wm.get("replay_run_ids") or [])
    daily_id=dm["replay_run_id"]
    monthly_id=mm["replay_run_id"]

    pre={
      "version":VERSION,"status":"READY","mode":"PREFLIGHT","confirmation_required":CONFIRM,
      "weekly_replay_runs":len(weekly_ids),"daily_replay_run_id":daily_id,"monthly_replay_run_id":monthly_id,
      "daily_certified_cohorts":dc.get("summary",{}).get("certified_cohorts"),
      "monthly_certified_cohorts":mc.get("summary",{}).get("certified_cohorts"),
      "horizons":list(HORIZONS),
      "production_authority_effect":False,
      "production_model_or_weight_change":False,
      "existing_daily_weekly_monthly_mutation":False
    }
    if a.mode=="preflight":
        print(json.dumps(pre,indent=2)); return
    if a.confirm!=CONFIRM:
        raise SystemExit(f"Confirmation required: --confirm {CONFIRM}")

    pit=json.loads(PIT.read_text())
    regimes={str(x["as_of"])[:10]:x["regime"] for x in pit.get("snapshots",[])}

    with SessionLocal() as s:
        daily=s.execute(text("""
          SELECT as_of,symbol,direction,overall_score,confidence
          FROM historical_underlying_replay_prediction
          WHERE replay_run_id=:rid ORDER BY as_of,symbol
        """),{"rid":daily_id}).mappings().all()
        monthly=s.execute(text("""
          SELECT as_of,symbol,direction,overall_score,confidence
          FROM historical_underlying_replay_prediction
          WHERE replay_run_id=:rid ORDER BY as_of,symbol
        """),{"rid":monthly_id}).mappings().all()
        weekly=s.execute(text("""
          SELECT as_of,symbol,direction,overall_score,confidence
          FROM historical_underlying_replay_prediction
          WHERE replay_run_id = ANY(:rids) ORDER BY as_of,symbol
        """),{"rids":weekly_ids}).mappings().all()

        spy=[str(x)[:10] for x in s.execute(text(
          "SELECT DISTINCT date FROM price_history WHERE symbol='SPY' ORDER BY date"
        )).scalars().all()]
        si={d:i for i,d in enumerate(spy)}

        syms=sorted({str(r["symbol"]) for r in daily})
        prices=defaultdict(dict)
        for sym,dt,close in s.execute(text("""
          SELECT symbol,date,close FROM price_history
          WHERE symbol = ANY(:symbols) ORDER BY symbol,date
        """),{"symbols":syms}).all():
            if close is not None: prices[str(sym)][str(dt)[:10]]=float(close)

    wi=build_index(weekly); mi=build_index(monthly)
    daily_cert=certified_sets(DAILY_CERT); monthly_cert=certified_sets(MONTHLY_CERT)

    aligned=[]
    miss={"weekly":0,"monthly":0,"pit":0,"price":0}
    for d0 in daily:
        d=str(d0["as_of"])[:10]; sym=str(d0["symbol"])
        w=latest_le(wi,sym,d); m=latest_le(mi,sym,d)
        if w is None: miss["weekly"]+=1; continue
        if m is None: miss["monthly"]+=1; continue
        reg=regimes.get(d)
        if reg is None: miss["pit"]+=1; continue
        base=prices[sym].get(d)
        if base is None or d not in si: miss["price"]+=1; continue

        df=family(d0["direction"]); wf=family(w["direction"]); mf=family(m["direction"])
        cls=classify(df,wf,mf); thesis=thesis_family(df,wf,mf)
        for h in HORIZONS:
            j=si[d]+h
            if j>=len(spy): continue
            td=spy[j]; px=prices[sym].get(td)
            if px is None: continue
            raw=100*(px/base-1)
            ar=align(raw,thesis)
            dkey=(h,reg,d0["direction"],score_band(d0["overall_score"]),conf_band(d0["confidence"]))
            mreg=regimes.get(str(m["as_of"])[:10])
            mkey=(h,mreg,m["direction"],score_band(m["overall_score"]),conf_band(m["confidence"]))
            aligned.append({
              "as_of":d,"year":int(d[:4]),"symbol":sym,"h":h,"target_date":td,
              "class":cls,"thesis":thesis,"aligned_return":ar,"raw_return":raw,
              "daily_family":df,"weekly_family":wf,"monthly_family":mf,
              "daily_direction":d0["direction"],"weekly_direction":w["direction"],"monthly_direction":m["direction"],
              "daily_certified_component":dkey in daily_cert,
              "monthly_certified_component":mkey in monthly_cert,
              "daily_regime":reg,
            })

    # Evaluate predefined confluence classes on deterministic non-overlapping samples.
    classes=sorted({r["class"] for r in aligned})
    evidence=[]
    for h in HORIZONS:
        hrows=[r for r in aligned if r["h"]==h and r["thesis"]!="NEUTRAL"]
        sampled=nonoverlap(hrows,h,si)
        years=sorted(set(r["year"] for r in sampled))
        for cls in classes:
            cr=[r for r in sampled if r["class"]==cls]
            if not cr: continue
            # component baselines: same majority thesis, conditioned separately on each cadence direction family.
            thesis=cr[0]["thesis"]
            for y in years:
                yr=[r for r in cr if r["year"]==y]
                if not yr: continue
                pool=[r for r in sampled if r["year"]==y and r["thesis"]==thesis]
                ds=stat([r["aligned_return"] for r in pool if r["daily_family"]==cr[0]["daily_family"]])
                ws=stat([r["aligned_return"] for r in pool if r["weekly_family"]==cr[0]["weekly_family"]])
                ms=stat([r["aligned_return"] for r in pool if r["monthly_family"]==cr[0]["monthly_family"]])
                gs=stat([r["aligned_return"] for r in yr])
                means=[x["mean_pct"] for x in (ds,ws,ms) if x["mean_pct"] is not None]
                best=max(means) if means else None
                inc=(gs["mean_pct"]-best) if gs["mean_pct"] is not None and best is not None else None
                evidence.append({
                  "horizon_sessions":h,"class":cls,"year":y,
                  "year_credit":"PARTIAL_YEAR" if y==max(years) else "FULL_YEAR",
                  "group":gs,"daily_component_baseline":ds,"weekly_component_baseline":ws,"monthly_component_baseline":ms,
                  "best_component_mean_pct":best,"incremental_vs_best_component_pct":inc,
                  "pass":(
                    gs["n"]>=MIN_N[h] and gs["mean_pct"] is not None and gs["mean_pct"]>0
                    and gs["hit_rate_pct"]>=MIN_HIT and inc is not None and inc>=MIN_INCREMENTAL[h]
                  )
                })

    support=[]
    for h in HORIZONS:
        for cls in classes:
            es=[e for e in evidence if e["horizon_sessions"]==h and e["class"]==cls]
            full=[e for e in es if e["year_credit"]=="FULL_YEAR"]
            partial=[e for e in es if e["year_credit"]=="PARTIAL_YEAR"]
            full_pass=sum(e["pass"] for e in full)
            # Research support requires at least two full years and every evaluated full year to pass;
            # partial year is supporting only and never required for full-year credit.
            supported=len(full)>=2 and full_pass==len(full)
            support.append({
              "horizon_sessions":h,"class":cls,"full_years":len(full),"full_years_passed":full_pass,
              "partial_years":len(partial),"partial_years_passed":sum(e["pass"] for e in partial),
              "research_supported":supported
            })

    supported=[x for x in support if x["research_supported"]]
    result={
      "version":VERSION,"status":"READY",
      "governance":{"research_only":True,"database_read_only":True,"database_writes":False,
                    "production_authority_effect":False,"production_model_or_weight_change":False,
                    "automatic_champion_promotion":False,"existing_daily_weekly_monthly_mutation":False},
      "lineage":{"weekly_replay_run_ids":weekly_ids,"daily_replay_run_id":daily_id,"monthly_replay_run_id":monthly_id,
                 "daily_certification":str(DAILY_CERT),"monthly_certification":str(MONTHLY_CERT)},
      "methodology":{"entry_clock":"DAILY replay observation date",
                     "weekly_binding":"latest weekly replay state with as_of <= daily date",
                     "monthly_binding":"latest monthly replay state with as_of <= daily date",
                     "future_leakage_prohibited":True,
                     "outcomes_sessions":list(HORIZONS),
                     "non_overlap":"deterministic per-symbol spacing >= outcome horizon on SPY trading-session index",
                     "incremental_edge":"confluence thesis-aligned mean minus strongest same-year component direction-family baseline",
                     "full_year_support":"at least 2 full years and every evaluated full year passes; partial year supporting only",
                     "minimum_n":MIN_N,"minimum_hit_rate_pct":MIN_HIT,"minimum_incremental_edge_pct":MIN_INCREMENTAL},
      "coverage":{"aligned_horizon_observations":len(aligned),"symbols":len(set(r["symbol"] for r in aligned)),
                  "first_as_of":min((r["as_of"] for r in aligned),default=None),"last_as_of":max((r["as_of"] for r in aligned),default=None),
                  "missing_bindings":miss},
      "component_certification":{"daily_certified_cohorts":dc.get("summary",{}).get("certified_cohorts"),
                                 "monthly_certified_cohorts":mc.get("summary",{}).get("certified_cohorts")},
      "evidence":evidence,"support":support,
      "summary":{"predefined_classes":len(classes),"research_supported_class_horizons":len(supported),
                 "supported_by_horizon":{str(h):sum(x["research_supported"] and x["horizon_sessions"]==h for x in support) for h in HORIZONS}},
      "research_supported":supported,
      "next_step":"REVIEW_INCREMENTAL_EDGE_BEFORE_ANY_SHADOW_POLICY",
      "production_authority_effect":False
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":"READY","version":VERSION,"output":str(OUT),
                      "coverage":result["coverage"],"summary":result["summary"],
                      "next_step":result["next_step"],"production_authority_effect":False},indent=2))

if __name__=="__main__":
    main()
