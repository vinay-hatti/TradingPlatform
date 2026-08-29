#!/usr/bin/env python3
from __future__ import annotations

import argparse, bisect, json, math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

from sqlalchemy import text
from trading_ai.database.session import SessionLocal

VERSION="M77.12-CADENCE-ROLE-INCREMENTAL-UTILITY-1.0"
CONFIRM="RUN_M77_12_CADENCE_ROLE_UTILITY"

WEEKLY_MANIFEST=Path("reports/m77/m77_2_multiyear_frozen_champion_manifest.json")
DAILY_MANIFEST=Path("reports/m77/m77_9_daily_model_replay_manifest.json")
DAILY_CERT=Path("reports/m77/m77_9_daily_walk_forward_certification.json")
MONTHLY_MANIFEST=Path("reports/m77/m77_10_monthly_model_replay_manifest.json")
MONTHLY_CERT=Path("reports/m77/m77_10_monthly_walk_forward_certification.json")
M77_11=Path("reports/m77/m77_11_multi_cadence_confluence_conflict_study.json")
PIT=Path("reports/m77/m77_8_daily_pit_regime_snapshots.json")
OUT=Path("reports/m77/m77_12_cadence_role_incremental_utility_certification.json")

MIN_N={5:100,10:100,20:100,60:50,120:30}
MIN_INCREMENTAL={5:.10,10:.10,20:.15,60:.25,120:.35}
MIN_HIT=52.0

def family(direction):
    d=str(direction or "").upper()
    if d in ("BULLISH","STRONG_BULLISH"): return "BULLISH"
    if d in ("BEARISH","STRONG_BEARISH"): return "BEARISH"
    return "NEUTRAL"

def score_band(x):
    if x is None:return "S_UNKNOWN"
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

def role(base_family, secondary_family):
    if base_family not in ("BULLISH","BEARISH"):
        return "NOT_APPLICABLE_NEUTRAL_BASELINE"
    if secondary_family==base_family:return "CONFIRMING"
    if secondary_family=="NEUTRAL":return "NEUTRAL"
    return "CONFLICTING"

def align(raw, direction):
    f=family(direction)
    if f=="BEARISH": return -raw
    return raw

def stat(vals):
    vals=[x for x in vals if x is not None]
    if not vals:return {"n":0,"mean_pct":None,"hit_rate_pct":None,"stdev_pct":None,"t_approx":None}
    n=len(vals); m=mean(vals); sd=pstdev(vals) if n>1 else 0
    return {"n":n,"mean_pct":m,"hit_rate_pct":100*sum(x>0 for x in vals)/n,
            "stdev_pct":sd,"t_approx":(m/(sd/math.sqrt(n))) if sd>0 else None}

def build_index(rows):
    g=defaultdict(list)
    for r in rows:g[str(r["symbol"])].append(dict(r))
    out={}
    for sym,rs in g.items():
        rs.sort(key=lambda x:str(x["as_of"])[:10])
        out[sym]=([str(x["as_of"])[:10] for x in rs],rs)
    return out

def latest_le(index,sym,d):
    row=index.get(sym)
    if not row:return None
    dates,rows=row
    i=bisect.bisect_right(dates,d)-1
    return rows[i] if i>=0 else None

def nonoverlap(rows,h,session_index):
    by=defaultdict(list)
    for r in rows:by[r["symbol"]].append(r)
    out=[]
    for sym,rs in by.items():
        rs.sort(key=lambda x:x["as_of"])
        last=-10**9
        for r in rs:
            i=session_index.get(r["as_of"])
            if i is None:continue
            if i-last>=h:
                out.append(r); last=i
    return out

def frozen_certified(path):
    d=json.loads(path.read_text())
    rows=[]
    for x in d.get("cohort_certification",[]):
        if x.get("certified"):
            rows.append({
                "horizon_sessions":int(x["horizon_sessions"]),
                "regime":x.get("regime"),
                "direction":x.get("direction"),
                "score_band":x.get("score_band"),
                "confidence_band":x.get("confidence_band"),
            })
    return d,rows

def matches(row,cert,regime):
    return (
        regime==cert["regime"]
        and row["direction"]==cert["direction"]
        and score_band(row["overall_score"])==cert["score_band"]
        and conf_band(row["confidence"])==cert["confidence_band"]
    )

def experiment_support(evidence):
    groups=defaultdict(list)
    for e in evidence:
        groups[(e["baseline_source"],e["baseline_id"],e["secondary_cadence"],e["role"])].append(e)
    out=[]
    for key,es in sorted(groups.items()):
        full=[e for e in es if e["year_credit"]=="FULL_YEAR"]
        partial=[e for e in es if e["year_credit"]=="PARTIAL_YEAR"]
        full_pass=sum(e["pass"] for e in full)
        supported=len(full)>=2 and full_pass==len(full)
        out.append({
            "baseline_source":key[0],"baseline_id":key[1],
            "secondary_cadence":key[2],"role":key[3],
            "full_years":len(full),"full_years_passed":full_pass,
            "partial_years":len(partial),"partial_years_passed":sum(e["pass"] for e in partial),
            "research_supported":supported
        })
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["preflight","run"])
    ap.add_argument("--confirm")
    args=ap.parse_args()

    required=(WEEKLY_MANIFEST,DAILY_MANIFEST,DAILY_CERT,MONTHLY_MANIFEST,MONTHLY_CERT,M77_11,PIT)
    missing=[str(p) for p in required if not p.exists()]
    if missing:raise SystemExit("Missing required artifacts: "+", ".join(missing))

    dm=json.loads(DAILY_MANIFEST.read_text())
    mm=json.loads(MONTHLY_MANIFEST.read_text())
    wm=json.loads(WEEKLY_MANIFEST.read_text())
    m11=json.loads(M77_11.read_text())
    dc,daily_certs=frozen_certified(DAILY_CERT)
    mc,monthly_certs=frozen_certified(MONTHLY_CERT)

    if dc.get("summary",{}).get("certified_cohorts")!=len(daily_certs):
        raise SystemExit("FAIL_CLOSED: daily frozen cohort count mismatch")
    if mc.get("summary",{}).get("certified_cohorts")!=len(monthly_certs):
        raise SystemExit("FAIL_CLOSED: monthly frozen cohort count mismatch")
    if m11.get("summary",{}).get("research_supported_class_horizons")!=0:
        raise SystemExit("FAIL_CLOSED: M77.11 expected zero supported confluence classes")

    pre={
        "version":VERSION,"status":"READY","mode":"PREFLIGHT","confirmation_required":CONFIRM,
        "frozen_daily_baselines":len(daily_certs),"frozen_monthly_baselines":len(monthly_certs),
        "monthly_directional_baselines":sum(family(x["direction"])!="NEUTRAL" for x in monthly_certs),
        "predeclared_roles":["CONFIRMING","NEUTRAL","CONFLICTING"],
        "daily_baseline_secondary_cadences":["WEEKLY","MONTHLY"],
        "monthly_baseline_secondary_cadences":["DAILY","WEEKLY"],
        "neighboring_cohort_search":False,
        "production_authority_effect":False,
        "production_model_or_weight_change":False,
        "automatic_shadow_or_champion_promotion":False
    }
    if args.mode=="preflight":
        print(json.dumps(pre,indent=2));return
    if args.confirm!=CONFIRM:
        raise SystemExit(f"Confirmation required: --confirm {CONFIRM}")

    pit=json.loads(PIT.read_text())
    regimes={str(x["as_of"])[:10]:x["regime"] for x in pit.get("snapshots",[])}

    with SessionLocal() as s:
        daily=s.execute(text("""
            SELECT as_of,symbol,direction,overall_score,confidence
            FROM historical_underlying_replay_prediction
            WHERE replay_run_id=:rid ORDER BY as_of,symbol
        """),{"rid":dm["replay_run_id"]}).mappings().all()
        monthly=s.execute(text("""
            SELECT as_of,symbol,direction,overall_score,confidence
            FROM historical_underlying_replay_prediction
            WHERE replay_run_id=:rid ORDER BY as_of,symbol
        """),{"rid":mm["replay_run_id"]}).mappings().all()
        weekly=s.execute(text("""
            SELECT as_of,symbol,direction,overall_score,confidence
            FROM historical_underlying_replay_prediction
            WHERE replay_run_id = ANY(:rids) ORDER BY as_of,symbol
        """),{"rids":wm["replay_run_ids"]}).mappings().all()
        spy=[str(x)[:10] for x in s.execute(text(
            "SELECT DISTINCT date FROM price_history WHERE symbol='SPY' ORDER BY date"
        )).scalars().all()]
        si={d:i for i,d in enumerate(spy)}
        syms=sorted({str(x["symbol"]) for x in daily}|{str(x["symbol"]) for x in monthly})
        prices=defaultdict(dict)
        for sym,dt,close in s.execute(text("""
            SELECT symbol,date,close FROM price_history
            WHERE symbol = ANY(:symbols) ORDER BY symbol,date
        """),{"symbols":syms}).all():
            if close is not None:prices[str(sym)][str(dt)[:10]]=float(close)

    di=build_index(daily);wi=build_index(weekly);mi=build_index(monthly)
    raw_experiments=[]
    missing_bindings=defaultdict(int)

    for c in daily_certs:
        h=c["horizon_sessions"]
        bid=f'DAILY::{h}::{c["regime"]}::{c["direction"]}::{c["score_band"]}::{c["confidence_band"]}'
        for r in daily:
            d=str(r["as_of"])[:10];sym=str(r["symbol"]);reg=regimes.get(d)
            if not matches(r,c,reg):continue
            if d not in si or prices[sym].get(d) is None:continue
            j=si[d]+h
            if j>=len(spy):continue
            px=prices[sym].get(spy[j]);base=prices[sym][d]
            if px is None:continue
            ret=align(100*(px/base-1),r["direction"])
            for sec_name,index in (("WEEKLY",wi),("MONTHLY",mi)):
                sec=latest_le(index,sym,d)
                if sec is None:
                    missing_bindings[f"DAILY_BASELINE_{sec_name}"]+=1;continue
                raw_experiments.append({
                    "baseline_source":"DAILY","baseline_id":bid,"secondary_cadence":sec_name,
                    "role":role(family(r["direction"]),family(sec["direction"])),
                    "h":h,"as_of":d,"year":int(d[:4]),"symbol":sym,"ret":ret
                })

    neutral_excluded=[]
    for c in monthly_certs:
        if family(c["direction"])=="NEUTRAL":
            neutral_excluded.append(c);continue
        h=c["horizon_sessions"]
        bid=f'MONTHLY::{h}::{c["regime"]}::{c["direction"]}::{c["score_band"]}::{c["confidence_band"]}'
        for r in monthly:
            d=str(r["as_of"])[:10];sym=str(r["symbol"]);reg=regimes.get(d)
            if not matches(r,c,reg):continue
            if d not in si or prices[sym].get(d) is None:continue
            j=si[d]+h
            if j>=len(spy):continue
            px=prices[sym].get(spy[j]);base=prices[sym][d]
            if px is None:continue
            ret=align(100*(px/base-1),r["direction"])
            for sec_name,index in (("DAILY",di),("WEEKLY",wi)):
                sec=latest_le(index,sym,d)
                if sec is None:
                    missing_bindings[f"MONTHLY_BASELINE_{sec_name}"]+=1;continue
                raw_experiments.append({
                    "baseline_source":"MONTHLY","baseline_id":bid,"secondary_cadence":sec_name,
                    "role":role(family(r["direction"]),family(sec["direction"])),
                    "h":h,"as_of":d,"year":int(d[:4]),"symbol":sym,"ret":ret
                })

    evidence=[]
    baselines=sorted({(x["baseline_source"],x["baseline_id"],x["secondary_cadence"],x["h"]) for x in raw_experiments})
    for bs,bid,sec,h in baselines:
        rows=[x for x in raw_experiments if x["baseline_source"]==bs and x["baseline_id"]==bid and x["secondary_cadence"]==sec and x["h"]==h]
        sampled=nonoverlap(rows,h,si)
        years=sorted(set(x["year"] for x in sampled))
        for y in years:
            yr=[x for x in sampled if x["year"]==y]
            base_stat=stat([x["ret"] for x in yr])
            for rl in ("CONFIRMING","NEUTRAL","CONFLICTING"):
                subset=[x for x in yr if x["role"]==rl]
                ss=stat([x["ret"] for x in subset])
                inc=(ss["mean_pct"]-base_stat["mean_pct"]) if ss["mean_pct"] is not None and base_stat["mean_pct"] is not None else None
                passed=(
                    ss["n"]>=MIN_N[h]
                    and ss["mean_pct"] is not None and ss["mean_pct"]>0
                    and ss["hit_rate_pct"] is not None and ss["hit_rate_pct"]>=MIN_HIT
                    and inc is not None and inc>=MIN_INCREMENTAL[h]
                )
                evidence.append({
                    "baseline_source":bs,"baseline_id":bid,"secondary_cadence":sec,"role":rl,
                    "horizon_sessions":h,"year":y,
                    "year_credit":"PARTIAL_YEAR" if y==max(years) else "FULL_YEAR",
                    "frozen_baseline":base_stat,"role_subset":ss,
                    "incremental_vs_same_frozen_baseline_pct":inc,"pass":passed
                })

    support=experiment_support(evidence)
    supported=[x for x in support if x["research_supported"]]

    result={
        "version":VERSION,"status":"READY",
        "governance":{"research_only":True,"database_read_only":True,"database_writes":False,
                      "neighboring_cohort_search":False,"frozen_baseline_cohorts_only":True,
                      "production_authority_effect":False,"production_model_or_weight_change":False,
                      "production_decision_change":False,"automatic_shadow_activation":False,
                      "automatic_champion_promotion":False},
        "lineage":{"daily_certification":str(DAILY_CERT),"monthly_certification":str(MONTHLY_CERT),
                   "m77_11":str(M77_11),"weekly_manifest":str(WEEKLY_MANIFEST)},
        "frozen_baselines":{"daily":daily_certs,"monthly":monthly_certs,
                            "monthly_neutral_excluded_from_directional_overlay":neutral_excluded},
        "methodology":{"question":"Does a secondary cadence role improve an already-certified frozen baseline?",
                       "roles":["CONFIRMING","NEUTRAL","CONFLICTING"],
                       "daily_baseline_overlays":["WEEKLY","MONTHLY"],
                       "monthly_baseline_overlays":["DAILY","WEEKLY"],
                       "binding":"latest secondary cadence as_of <= frozen baseline observation date",
                       "future_leakage_prohibited":True,
                       "non_overlap":"deterministic per-symbol spacing >= baseline outcome horizon on SPY session index",
                       "comparison":"role subset versus same frozen certified baseline, same year/horizon",
                       "full_year_support":"at least 2 full years and every evaluated full year must pass; partial year supporting only",
                       "minimum_n":MIN_N,"minimum_hit_rate_pct":MIN_HIT,"minimum_incremental_pct":MIN_INCREMENTAL,
                       "neutral_monthly_baselines":"excluded from directional CONFIRMING/CONFLICTING role certification"},
        "coverage":{"raw_role_observations":len(raw_experiments),
                    "symbols":len(set(x["symbol"] for x in raw_experiments)),
                    "first_as_of":min((x["as_of"] for x in raw_experiments),default=None),
                    "last_as_of":max((x["as_of"] for x in raw_experiments),default=None),
                    "missing_secondary_bindings":dict(sorted(missing_bindings.items()))},
        "evidence":evidence,"support":support,"research_supported":supported,
        "summary":{"frozen_daily_baselines":len(daily_certs),"frozen_monthly_baselines":len(monthly_certs),
                   "directional_monthly_baselines":len(monthly_certs)-len(neutral_excluded),
                   "tested_baseline_overlay_role_combinations":len(support),
                   "research_supported_role_utilities":len(supported),
                   "supported_by_baseline_source":{
                       "DAILY":sum(x["research_supported"] and x["baseline_source"]=="DAILY" for x in support),
                       "MONTHLY":sum(x["research_supported"] and x["baseline_source"]=="MONTHLY" for x in support)}},
        "next_step":"REVIEW_CADENCE_ROLE_UTILITY_BEFORE_ANY_SHADOW_POLICY",
        "production_authority_effect":False
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":"READY","version":VERSION,"output":str(OUT),
                      "coverage":result["coverage"],"summary":result["summary"],
                      "next_step":result["next_step"],"production_authority_effect":False},indent=2))

if __name__=="__main__":
    main()
