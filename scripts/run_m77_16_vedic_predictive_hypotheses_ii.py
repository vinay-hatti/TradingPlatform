#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math,random
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean,pstdev

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_16_vedic_predictive_hypotheses_ii.json"
OUT=ROOT/"reports/m77/m77_16_vedic_predictive_hypotheses_ii.json"
CERT=ROOT/"reports/m77/m77_15_6_5_2_material_long_history_proxy_authority_certification.json"
EVENTS=ROOT/"data/m77/m77_15_4_astronomical_event_registry_2000_2040.csv"
PANCH=ROOT/"data/m77/m77_15_2_panchanga_daily_2000_2040.csv"
GRAHA=ROOT/"data/m77/m77_15_3_graha_state_daily_2000_2040.csv"
CONFIRM="RUN_M77_16_VEDIC_PREDICTIVE_HYPOTHESES_II"
RNG_SEED=771600
CIRCULAR_SHIFTS=2048

def load_csv(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def write_json_atomic(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(x,indent=2,default=str)+"\n"); json.loads(t.read_text()); t.replace(p)
def bh(items):
    s=sorted(items,key=lambda x:x[1]); m=len(s); q={}; prev=1.0
    for i,(k,p) in reversed(list(enumerate(s,1))):
        prev=min(prev,p*m/i); q[k]=prev
    return q
def daily_returns(c):
    return [None]+[c[i]/c[i-1]-1 for i in range(1,len(c))]
def vec(c,r,i,h):
    if i+h>=len(c): return None
    f=c[i+h]/c[i]-1; path=[c[j]/c[i]-1 for j in range(i+1,i+h+1)]
    rr=[x for x in r[i+1:i+h+1] if x is not None]
    return {"FORWARD_RETURN":f,"ABSOLUTE_RETURN":abs(f),"REALIZED_VOLATILITY":pstdev(rr)*math.sqrt(252) if len(rr)>=2 else 0.0,
            "MAX_ADVERSE_EXCURSION":min(path) if path else 0.0,"MAX_FAVORABLE_EXCURSION":max(path) if path else 0.0}
def matched(event,eligible,vals,dates):
    ev=set(event); out=[]
    for i in event:
        c=[j for j in eligible if j not in ev and dates[j].weekday()==dates[i].weekday() and dates[j].month==dates[i].month]
        if c: out.append(vals[i]-mean(vals[j] for j in c))
    return mean(out) if out else None
def circ_event(event,eligible,vals,rng):
    n=len(eligible); pos={idx:k for k,idx in enumerate(eligible)}; base=[pos[i] for i in event if i in pos]
    shifts=list(range(1,n))
    if len(shifts)>CIRCULAR_SHIFTS: shifts=rng.sample(shifts,CIRCULAR_SHIFTS)
    return [mean(vals[eligible[(k+s)%n]] for k in base) for s in shifts] if base else []
def circ_label(labels,eligible,vals,level,rng):
    n=len(eligible); labs=[labels[i] for i in eligible]; shifts=list(range(1,n))
    if len(shifts)>CIRCULAR_SHIFTS: shifts=rng.sample(shifts,CIRCULAR_SHIFTS)
    out=[]
    for s in shifts:
        v=[vals[eligible[k]] for k in range(n) if labs[(k+s)%n]==level]
        if v: out.append(mean(v))
    return out
def emp(obs,null):
    if not null:return 1.0
    c=mean(null); d=abs(obs-c)
    return (1+sum(abs(x-c)>=d for x in null))/(len(null)+1)
def direction(x): return 0 if x is None or x==0 else (1 if x>0 else -1)
def eras(event,eligible,vals,dates,blocks):
    ev=set(event); out=[]
    for a,b in blocks:
        ei=[i for i in event if a<=dates[i].isoformat()<=b]
        ci=[i for i in eligible if i not in ev and a<=dates[i].isoformat()<=b]
        inc=None if not ei or not ci else mean(vals[i] for i in ei)-mean(vals[i] for i in ci)
        out.append({"era":[a,b],"event_n":len(ei),"incremental_vs_complement":inc})
    return out
def sun_rashi(lon):
    n=("MESHA","VRISHABHA","MITHUNA","KARKA","SIMHA","KANYA","TULA","VRISCHIKA","DHANU","MAKARA","KUMBHA","MEENA")
    return n[int(float(lon)//30)%12]
def ingress_rows(graha):
    s=sorted(graha,key=lambda r:r["date"]); out=[]; prev=None
    for r in s:
        lon=r.get("sun_sidereal_deg")
        if lon is None: continue
        cur=sun_rashi(lon)
        if prev is not None and cur!=prev: out.append({"date":r["date"],"rashi":cur})
        prev=cur
    return out
def atichari(graha):
    usable=[]; speeds=[]
    for r in sorted(graha,key=lambda x:x["date"]):
        v=r.get("jupiter_sidereal_speed_deg_per_day") or r.get("jupiter_speed_deg_per_day")
        if v is None: continue
        v=float(v); usable.append((r["date"],v))
        if v>0:speeds.append(v)
    if not speeds:return {},None
    s=sorted(speeds); q=s[max(0,min(len(s)-1,math.ceil(.90*len(s))-1))]
    return {d:("ATICHARI" if v>0 and v>=q else "NORMAL") for d,v in usable},q

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=("preflight","run")); ap.add_argument("--confirm")
    a=ap.parse_args(); cfg=json.loads(CFG.read_text())
    if not CERT.exists(): raise SystemExit("M77.16 blocked: M77.15.6.5.2 certification missing")
    cert=json.loads(CERT.read_text())
    if not cert.get("certified_for_m77_15_7_long_history_replication"): raise SystemExit("M77.16 blocked: long-history authority not certified")
    if cert["common_authority"]["session_count"]<cfg["authority"]["minimum_common_sessions"]: raise SystemExit("M77.16 blocked: insufficient long-history sessions")

    if a.mode=="preflight":
        print(json.dumps({"version":cfg["version"],"status":"READY","confirmation_required":CONFIRM,
          "authority_common_sessions":cert["common_authority"]["session_count"],
          "authority_range":[cert["common_authority"]["first_date"],cert["common_authority"]["last_date"]],
          "long_history_instruments":cfg["authority"]["long_history_instruments"],
          "canonical_recent_confirmation":cfg["authority"]["canonical_recent_confirmation"],
          "scope_note":cfg["authority"]["scope_note"],"hypotheses":cfg["hypotheses"],
          "production_authority_effect":False},indent=2)); return

    if a.confirm!=CONFIRM: raise SystemExit(f"confirmation required: {CONFIRM}")

    events=load_csv(EVENTS); panch={r["date"]:r for r in load_csv(PANCH)}
    graha_rows=load_csv(GRAHA); ingress=ingress_rows(graha_rows); ati,ati_q=atichari(graha_rows)
    results=[]; pvals=defaultdict(list); rng=random.Random(RNG_SEED)

    for target,meta in cfg["authority"]["long_history_instruments"].items():
        rows=load_csv(ROOT/meta["file"])
        if len(rows)<cfg["authority"]["minimum_common_sessions"]: raise SystemExit(f"{target} has insufficient long-history rows")
        dates=[date.fromisoformat(r["date"]) for r in rows]; close=[float(r["close"]) for r in rows]
        dret=daily_returns(close); bydate={r["date"]:i for i,r in enumerate(rows)}

        # H1
        idx=[bydate[e["event_date"]] for e in events if e["event_family"] in cfg["hypotheses"]["H1_JUPITER_RAHU_EXPANSION"]["states"] and e["event_date"] in bydate]
        for h in cfg["hypotheses"]["H1_JUPITER_RAHU_EXPANSION"]["horizons"]:
            vv={i:vec(close,dret,i,h) for i in range(len(rows)-h)}
            for outcome,pred in cfg["hypotheses"]["H1_JUPITER_RAHU_EXPANSION"]["prediction"].items():
                vals={i:vv[i][outcome] for i in vv}; eligible=sorted(vals); ev=[i for i in idx if i in vals]
                if not ev:continue
                em=mean(vals[i] for i in ev); comp=[vals[i] for i in eligible if i not in set(ev)]
                inc=em-mean(comp); incm=matched(ev,eligible,vals,dates); p=emp(em,circ_event(ev,eligible,vals,rng))
                k=f"H1|{target}|{h}|{outcome}"; pvals["H1"].append((k,p))
                results.append({"hypothesis":"H1_JUPITER_RAHU_EXPANSION","key":k,"target":target,"research_instrument":meta["instrument"],
                  "horizon_sessions":h,"outcome":outcome,"prediction":pred,"event_n":len(ev),"event_mean":em,
                  "incremental_vs_complement":inc,"incremental_vs_weekday_month":incm,"circular_empirical_p":p,
                  "era_stats":eras(ev,eligible,vals,dates,cfg["frozen_eras"])})

        # H2
        imeta={}
        for e in ingress:
            d=e["date"]
            if d in bydate and d in panch:
                i=bydate[d]
                imeta[i]={"SUN_INGRESS_RASHI":e["rashi"],"MOON_NAKSHATRA_AT_INGRESS":panch[d].get("moon_nakshatra"),
                          "TITHI_AT_INGRESS":panch[d].get("tithi"),"WEEKDAY_AT_INGRESS":str(date.fromisoformat(d).weekday())}
        h=cfg["hypotheses"]["H2_SOLAR_INGRESS_SANKRANTI"]["horizon_sessions"]; vv={i:vec(close,dret,i,h) for i in range(len(rows)-h)}
        for feat in cfg["hypotheses"]["H2_SOLAR_INGRESS_SANKRANTI"]["features"]:
            labels={i:x[feat] for i,x in imeta.items() if i in vv and x.get(feat) is not None}
            for outcome in cfg["hypotheses"]["H2_SOLAR_INGRESS_SANKRANTI"]["outcomes"]:
                vals={i:vv[i][outcome] for i in labels}; eligible=sorted(vals)
                for level in sorted(set(labels.values())):
                    ev=[i for i in eligible if labels[i]==level]
                    if len(ev)<4:continue
                    em=mean(vals[i] for i in ev); comp=[vals[i] for i in eligible if i not in set(ev)]
                    inc=em-mean(comp); incm=matched(ev,eligible,vals,dates); p=emp(em,circ_label(labels,eligible,vals,level,rng))
                    k=f"H2|{target}|{feat}|{level}|{outcome}"; pvals["H2"].append((k,p))
                    results.append({"hypothesis":"H2_SOLAR_INGRESS_SANKRANTI","key":k,"target":target,"research_instrument":meta["instrument"],
                      "horizon_sessions":h,"feature":feat,"level":level,"outcome":outcome,"event_n":len(ev),"event_mean":em,
                      "incremental_vs_complement":inc,"incremental_vs_weekday_month":incm,"circular_empirical_p":p,
                      "era_stats":eras(ev,eligible,vals,dates,cfg["frozen_eras"])})

        # H4
        if ati_q is not None:
            for h in cfg["hypotheses"]["H4_JUPITER_ATICHARI_VELOCITY"]["horizons"]:
                vv={i:vec(close,dret,i,h) for i in range(len(rows)-h)}
                labels={i:ati[rows[i]["date"]] for i in vv if rows[i]["date"] in ati}
                for outcome,pred in cfg["hypotheses"]["H4_JUPITER_ATICHARI_VELOCITY"]["prediction"].items():
                    vals={i:vv[i][outcome] for i in labels}; eligible=sorted(vals); ev=[i for i in eligible if labels[i]=="ATICHARI"]
                    if not ev:continue
                    em=mean(vals[i] for i in ev); comp=[vals[i] for i in eligible if i not in set(ev)]
                    inc=em-mean(comp); incm=matched(ev,eligible,vals,dates); p=emp(em,circ_label(labels,eligible,vals,"ATICHARI",rng))
                    k=f"H4|{target}|{h}|{outcome}"; pvals["H4"].append((k,p))
                    results.append({"hypothesis":"H4_JUPITER_ATICHARI_VELOCITY","key":k,"target":target,"research_instrument":meta["instrument"],
                      "horizon_sessions":h,"outcome":outcome,"prediction":pred,"event_n":len(ev),"event_mean":em,
                      "atichari_velocity_threshold_deg_per_day":ati_q,"incremental_vs_complement":inc,
                      "incremental_vs_weekday_month":incm,"circular_empirical_p":p,
                      "era_stats":eras(ev,eligible,vals,dates,cfg["frozen_eras"])})

    qmaps={fam:bh(items) for fam,items in pvals.items()}
    supported=0
    for r in results:
        fam=r["hypothesis"].split("_",1)[0]; r["bh_q"]=qmaps[fam].get(r["key"],1.0)
        inc=r["incremental_vs_complement"]; incm=r["incremental_vs_weekday_month"]
        era_incs=[e["incremental_vs_complement"] for e in r["era_stats"] if e["incremental_vs_complement"] is not None]
        same=sum(1 for x in era_incs if direction(x)==direction(inc) and direction(inc)!=0)
        pred=r.get("prediction"); dg=True
        if pred=="POSITIVE": dg=inc>0
        elif pred=="NONNEGATIVE": dg=inc>=0
        gate={"sample_size":r["event_n"]>=8,"bh_q_le_0_05":r["bh_q"]<=.05,"directional_prediction_satisfied":dg,
              "matched_control_direction_consistency":direction(inc)==direction(incm) and direction(inc)!=0,
              "at_least_3_eligible_eras":len(era_incs)>=3,"at_least_3_same_direction_eras":same>=3}
        r["research_gate"]=gate; r["status"]="LONG_HISTORY_RESEARCH_SUPPORTED_CANDIDATE" if all(gate.values()) else "UNSUPPORTED"
        supported+=r["status"]=="LONG_HISTORY_RESEARCH_SUPPORTED_CANDIDATE"

    out={"version":cfg["version"],"status":"READY","authority":{"common_sessions":cert["common_authority"]["session_count"],
      "range":[cert["common_authority"]["first_date"],cert["common_authority"]["last_date"]],
      "long_history_instruments":cfg["authority"]["long_history_instruments"],"scope_note":cfg["authority"]["scope_note"]},
      "hypothesis_result_count":len(results),"long_history_research_supported_candidate_count":supported,
      "blocked_hypotheses":[{"hypothesis":"H3_RAHU_KETU_FINANCIAL_HOUSE_AXIS","status":"BLOCKED_PENDING_MARKET_CHART_AUTHORITY",
      "required":cfg["hypotheses"]["H3_RAHU_KETU_FINANCIAL_HOUSE_AXIS"]["required"]}],
      "atichari_velocity_threshold_deg_per_day":ati_q,"results":results,
      "governance":{"pre_registered":True,"proxy_results_are_not_index_results":True,"canonical_recent_confirmation_required_before_promotion":True,
      "database_writes":False,"production_authority_effect":False},
      "next_step":"REVIEW_LONG_HISTORY_SURVIVORS_THEN_BUILD_CANONICAL_RECENT_CONFIRMATION_ONLY_FOR_SURVIVORS" if supported else "NO_LONG_HISTORY_SURVIVORS_CLOSE_H1_H2_H4_AND_LEAVE_H3_BLOCKED",
      "production_authority_effect":False}
    write_json_atomic(OUT,out)
    print(json.dumps({"version":cfg["version"],"status":"READY","authority_common_sessions":out["authority"]["common_sessions"],
      "authority_range":out["authority"]["range"],"long_history_instruments":{k:v["instrument"] for k,v in cfg["authority"]["long_history_instruments"].items()},
      "hypothesis_result_count":len(results),"long_history_research_supported_candidate_count":supported,
      "blocked_hypotheses":["H3_RAHU_KETU_FINANCIAL_HOUSE_AXIS"],"atichari_velocity_threshold_deg_per_day":ati_q,
      "next_step":out["next_step"],"production_authority_effect":False},indent=2))
if __name__=="__main__": main()
