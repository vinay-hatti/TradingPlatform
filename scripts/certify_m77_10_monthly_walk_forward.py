#!/usr/bin/env python3
from __future__ import annotations
import json, math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

VERSION="M77.10.2-MONTHLY-WALK-FORWARD-CERTIFICATION-1.0"
MANIFEST=Path("reports/m77/m77_10_monthly_model_replay_manifest.json")
PIT=Path("reports/m77/m77_8_daily_pit_regime_snapshots.json")
OUT=Path("reports/m77/m77_10_monthly_walk_forward_certification.json")
HORIZONS=(60,120,180,252)
MIN_TRAIN=100; MIN_HOLD=30; HIT_MIN=52.0
MEAN_FLOOR={60:.35,120:.50,180:.75,252:1.00}

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
def align(direction,raw):
    d=str(direction or "").upper()
    if d in ("BEARISH","STRONG_BEARISH"): return -raw
    return raw
def stats(v):
    n=len(v)
    if not n:return {"n":0,"mean_pct":None,"hit_rate_pct":None,"stdev_pct":None,"t_approx":None}
    m=mean(v); sd=pstdev(v) if n>1 else 0
    return {"n":n,"mean_pct":m,"hit_rate_pct":100*sum(x>0 for x in v)/n,"stdev_pct":sd,
            "t_approx":(m/(sd/math.sqrt(n))) if sd>0 else None}

def main():
    if not MANIFEST.exists(): raise SystemExit("Missing monthly replay manifest")
    if not PIT.exists(): raise SystemExit("Missing M77.8 daily PIT snapshots")
    man=json.loads(MANIFEST.read_text())
    if man.get("status")!="READY": raise SystemExit("Monthly replay not READY")
    rid=man["replay_run_id"]

    pit=json.loads(PIT.read_text())
    regime={str(x["as_of"])[:10]:x["regime"] for x in pit.get("snapshots",[])}

    with SessionLocal() as s:
        preds=s.execute(text("""
          SELECT as_of,symbol,direction,overall_score,confidence
          FROM historical_underlying_replay_prediction
          WHERE replay_run_id=:rid
          ORDER BY as_of,symbol
        """),{"rid":rid}).mappings().all()

        spy_dates=[str(x)[:10] for x in s.execute(text("""
          SELECT DISTINCT date FROM price_history WHERE symbol='SPY' ORDER BY date
        """)).scalars().all()]
        idx={d:i for i,d in enumerate(spy_dates)}

        # Load only symbols participating in this monthly replay.
        syms=sorted({str(r["symbol"]) for r in preds})
        prices=defaultdict(dict)
        rows=s.execute(text("""
          SELECT symbol,date,close FROM price_history
          WHERE symbol = ANY(:symbols)
          ORDER BY symbol,date
        """),{"symbols":syms}).all()
        for sym,dt,close in rows:
            if close is not None: prices[str(sym)][str(dt)[:10]]=float(close)

    obs=[]
    missing_regime=0
    for p in preds:
        d=str(p["as_of"])[:10]
        if d not in idx: continue
        reg=regime.get(d)
        if reg is None:
            missing_regime+=1
            continue
        base=prices[str(p["symbol"])].get(d)
        if not base or base<=0: continue
        i=idx[d]
        for h in HORIZONS:
            if i+h>=len(spy_dates): continue
            td=spy_dates[i+h]
            px=prices[str(p["symbol"])].get(td)
            if px is None or px<=0: continue
            raw=100.0*(px/base-1.0)
            obs.append({"as_of":d,"year":int(d[:4]),"symbol":str(p["symbol"]),"regime":reg,
                        "direction":str(p["direction"]),"score_band":score_band(p["overall_score"]),
                        "confidence_band":conf_band(p["confidence"]),"h":h,"ret":align(p["direction"],raw)})

    years=sorted(set(x["year"] for x in obs)); folds=[]; hist=defaultdict(lambda:{"selected_full":0,"passed_full":0,"selected_total":0,"passed_total":0})
    for y in years:
        tr0=[x for x in obs if x["year"]<y]; ho0=[x for x in obs if x["year"]==y]
        if not tr0 or not ho0: continue
        credit="PARTIAL_YEAR" if y==max(years) else "FULL_YEAR"
        fold={"holdout_year":y,"holdout_credit":credit,"horizons":[]}
        for h in HORIZONS:
            tr=[x for x in tr0 if x["h"]==h]; ho=[x for x in ho0 if x["h"]==h]
            gt=defaultdict(list); gh=defaultdict(list)
            for x in tr: gt[(x["regime"],x["direction"],x["score_band"],x["confidence_band"])].append(x["ret"])
            for x in ho: gh[(x["regime"],x["direction"],x["score_band"],x["confidence_band"])].append(x["ret"])
            selected=[]
            for k,v in gt.items():
                st=stats(v)
                if st["n"]>=MIN_TRAIN and st["mean_pct"]>=MEAN_FLOOR[h] and st["hit_rate_pct"]>=HIT_MIN: selected.append((k,st))
            cohorts=[]
            for k,st in sorted(selected):
                sh=stats(gh.get(k,[])); reasons=[]
                if sh["n"]<MIN_HOLD: reasons.append("HOLDOUT_N_BELOW_MINIMUM")
                if sh["mean_pct"] is None or sh["mean_pct"]<MEAN_FLOOR[h]: reasons.append("HOLDOUT_MEAN_BELOW_FLOOR")
                if sh["hit_rate_pct"] is None or sh["hit_rate_pct"]<HIT_MIN: reasons.append("HOLDOUT_HIT_RATE_BELOW_52")
                passed=not reasons
                cohorts.append({"cohort":{"regime":k[0],"direction":k[1],"score_band":k[2],"confidence_band":k[3]},
                                "training":st,"holdout":sh,"passed":passed,"reasons":reasons})
                ck=(h,)+k; hist[ck]["selected_total"]+=1; hist[ck]["passed_total"]+=int(passed)
                if credit=="FULL_YEAR": hist[ck]["selected_full"]+=1; hist[ck]["passed_full"]+=int(passed)
            fold["horizons"].append({"horizon_sessions":h,"training_observations":len(tr),"holdout_observations":len(ho),
                                     "training_selected_cohorts":len(selected),"passed_cohorts":sum(x["passed"] for x in cohorts),"cohorts":cohorts})
        folds.append(fold)

    certs=[]
    for k,hx in sorted(hist.items()):
        h,reg,dr,sb,cb=k
        ok=hx["selected_full"]>=2 and hx["selected_full"]==hx["passed_full"] and hx["selected_total"]==hx["passed_total"]
        certs.append({"horizon_sessions":h,"regime":reg,"direction":dr,"score_band":sb,"confidence_band":cb,**hx,"certified":ok})
    certified=[x for x in certs if x["certified"]]
    result={"version":VERSION,"status":"READY" if certified else "DEGRADED",
      "governance":{"research_only":True,"database_read_only":True,"database_writes":False,"automatic_champion_promotion":False,
                    "production_authority_effect":False,"existing_weekly_m77_mutation":False,"existing_daily_m77_mutation":False},
      "lineage":{"monthly_replay_run_id":rid,"pit_regime_authority":str(PIT),
                 "long_horizon_outcomes":"computed read-only from Polygon-adjusted price_history on exact SPY-session offsets"},
      "coverage":{"observations":len(obs),"symbols":len(set(x["symbol"] for x in obs)),
                  "first_as_of":min((x["as_of"] for x in obs),default=None),"last_as_of":max((x["as_of"] for x in obs),default=None),
                  "years":years,"missing_pit_regime_predictions":missing_regime},
      "methodology":{"horizons_sessions":list(HORIZONS),"expanding_year_holdout":True,"selection_uses_only_pre_holdout_data":True,
                     "monthly_regime_binding":"exact M77.8 PIT regime on replay observation date",
                     "future_outcomes":"exact 60/120/180/252 SPY trading-session offsets; symbol target close required",
                     "minimum_training_n":MIN_TRAIN,"minimum_holdout_n":MIN_HOLD,"minimum_holdout_hit_rate_pct":HIT_MIN,
                     "minimum_holdout_mean_pct":MEAN_FLOOR,
                     "certification_contract":"at least 2 selected FULL_YEAR holdouts; every selected full and partial holdout must pass"},
      "folds":folds,"cohort_certification":certs,
      "summary":{"folds":len(folds),"certified_cohorts":len(certified),"candidate_cohorts":len(certs),
                 "by_horizon":{str(h):sum(x["certified"] and x["horizon_sessions"]==h for x in certs) for h in HORIZONS}},
      "acceptance":{"monthly_replay_run_present":True,"exact_m77_8_pit_binding":missing_regime==0,
                    "walk_forward_training_precedes_holdout":True,
                    "full_year_holdouts_present":sum(f["holdout_credit"]=="FULL_YEAR" for f in folds)>=2,
                    "production_authority_effect":False},
      "next_step":"BUILD_DAILY_WEEKLY_MONTHLY_CONFLUENCE_CONFLICT_STUDY" if certified else "RETAIN_MONTHLY_RESEARCH_ONLY_NO_CONFLUENCE_PROMOTION",
      "production_authority_effect":False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"version":VERSION,"output":str(OUT),"coverage":result["coverage"],
                      "summary":result["summary"],"acceptance":result["acceptance"],
                      "next_step":result["next_step"],"production_authority_effect":False},indent=2))
if __name__=="__main__": main()
