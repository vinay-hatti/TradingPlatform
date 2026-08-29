#!/usr/bin/env python3
from __future__ import annotations
import csv,json,hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_15_6_5_2_source_anomaly_quarantine.json"
OUT=ROOT/"reports/m77/m77_15_6_5_2_material_long_history_proxy_authority_certification.json"

FIELDS=("research_target","research_instrument","authority_type","proxy_for",
        "source_ticker","date","open","high","low","close","volume","vwap",
        "transactions","source_timestamp_ms")

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def write_csv_atomic(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)
    tmp.replace(path)

def load_csv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def bad_ohlc(r):
    try:
        o=float(r["open"]); h=float(r["high"]); l=float(r["low"]); c=float(r["close"])
    except Exception:
        return True
    return min(o,h,l,c)<=0 or h<max(o,c,l) or l>min(o,c,h)

cfg=json.loads(CFG.read_text())
manifest=ROOT/cfg["source_manifest"]
forensic=ROOT/cfg["forensic_artifact"]
if not manifest.exists(): raise SystemExit("M77.15.6.4 manifest missing")
if not forensic.exists(): raise SystemExit("M77.15.6.5.1 forensic artifact missing")

m=json.loads(manifest.read_text())
f=json.loads(forensic.read_text())

# Fail closed unless the forensic evidence is exactly the pre-frozen anomaly.
q=cfg["frozen_quarantine"][0]
viol=f.get("violations") or []
match=[
    x for x in viol
    if x.get("date")==q["date"]
    and x.get("source_ticker")==q["source_ticker"]
    and x.get("reason")=="NONPOSITIVE_OHLC"
    and float((x.get("row") or {}).get("low"))==0.0
]
if len(match)!=1:
    raise SystemExit("Frozen source-anomaly evidence contract not satisfied")

source_same=(f.get("source_series_evidence") or {}).get("QQQ",{}).get("matching_violation_dates",{}).get(q["date"])
if not source_same or float(source_same.get("low"))!=0.0:
    raise SystemExit("Forensic source QQQ same-date evidence does not match low=0 anomaly")

paths={
    "SPX":Path(m["source_series"]["SPY"]["normalized_path"]),
    "NDX":Path(m["qqq_lineage"]["stitched_path"]),
    "RUT":Path(m["source_series"]["IWM"]["normalized_path"]),
}
raw={k:load_csv(p) for k,p in paths.items()}
bydate={k:{r["date"]:r for r in rows} for k,rows in raw.items()}
common=sorted(set.intersection(*(set(x) for x in bydate.values())))
quarantine_dates={x["date"] for x in cfg["frozen_quarantine"]}
cert_dates=[d for d in common if d not in quarantine_dates]

root=ROOT/cfg["output_root"]
target_results={}
for target in ("SPX","NDX","RUT"):
    instrument={"SPX":"SPY","NDX":"QQQ_LINEAGE","RUT":"IWM"}[target]
    rows=[]
    for d in cert_dates:
        s=bydate[target][d]
        rows.append({
            "research_target":target,
            "research_instrument":instrument,
            "authority_type":"MATERIAL_LONG_HISTORY_TRADABLE_PROXY",
            "proxy_for":target,
            "source_ticker":s.get("polygon_ticker"),
            "date":d,
            "open":s.get("open"),"high":s.get("high"),"low":s.get("low"),"close":s.get("close"),
            "volume":s.get("volume"),"vwap":s.get("vwap"),
            "transactions":s.get("transactions"),"source_timestamp_ms":s.get("source_timestamp_ms"),
        })
    outp=root/f"{target}_{instrument}_COMMON.csv"
    write_csv_atomic(outp,rows)
    dates=[r["date"] for r in rows]
    dupes=len(dates)-len(set(dates))
    bad=sum(1 for r in rows if bad_ohlc(r))
    target_results[target]={
        "research_instrument":instrument,
        "path":str(outp),
        "sha256":sha(outp),
        "row_count":len(rows),
        "first_date":dates[0] if dates else None,
        "last_date":dates[-1] if dates else None,
        "duplicate_date_count":dupes,
        "ohlc_violation_count":bad,
    }

gates={
    "forensic_source_anomaly_confirmed":True,
    "quarantine_count_exactly_one":len(quarantine_dates)==1,
    "quarantine_date_is_2004_07_28":quarantine_dates=={"2004-07-28"},
    "common_start_preserved":cert_dates[0]==cfg["common_start"],
    "common_sessions_ge_minimum":len(cert_dates)>=cfg["minimum_common_sessions"],
    "all_targets_same_session_count":len({x["row_count"] for x in target_results.values()})==1,
    "all_targets_zero_duplicates":all(x["duplicate_date_count"]==0 for x in target_results.values()),
    "all_targets_zero_ohlc_violations":all(x["ohlc_violation_count"]==0 for x in target_results.values()),
    "source_values_not_mutated":cfg["quarantine_policy"]["source_values_mutated"] is False,
    "price_imputation_prohibited":cfg["quarantine_policy"]["price_imputation"] is False,
}
certified=all(gates.values())

out={
  "version":"M77.15.6.5.2-SOURCE-ANOMALY-QUARANTINE-RECERTIFICATION-1.0",
  "status":"READY",
  "classification":"CONFIRMED_POLYGON_SOURCE_OHLC_ANOMALY_NOT_LINEAGE_STITCH_DEFECT",
  "source_anomaly":{
      "date":"2004-07-28","ticker":"QQQ","field":"low","value":0.0,
      "evidence":"same invalid low exists in normalized QQQ source row before lineage stitch"
  },
  "quarantine_policy":cfg["quarantine_policy"],
  "quarantined_dates":sorted(quarantine_dates),
  "common_authority":{
      "first_date":cert_dates[0] if cert_dates else None,
      "last_date":cert_dates[-1] if cert_dates else None,
      "session_count":len(cert_dates),
      "minimum_sessions":cfg["minimum_common_sessions"],
      "sessions_removed_for_source_quality":len(common)-len(cert_dates),
  },
  "targets":target_results,
  "gates":gates,
  "certified_for_m77_15_7_long_history_replication":certified,
  "promotion_governance":{
      "proxy_results_are_not_index_results":True,
      "proxy_only_survivor_may_not_advance":True,
      "canonical_recent_index_confirmation_required":True,
      "same_effect_direction_required_across_authorities":True,
      "dependence_robust_confirmation_required":True,
  },
  "replication_era_policy":{
      "frozen_eras":[
          ["2003-09-10","2008-12-31"],
          ["2009-01-01","2014-12-31"],
          ["2015-01-01","2020-12-31"],
          ["2021-01-01",cert_dates[-1] if cert_dates else None],
      ],
      "posthoc_era_changes_prohibited":True,
  },
  "database_writes":False,
  "production_price_history_writes":False,
  "production_authority_effect":False,
  "next_step":"BUILD_M77_15_7_LONG_HISTORY_REPLICATION" if certified else "REVIEW_M77_15_6_5_2_FAILURES",
}
write_json_atomic(OUT,out)
print(json.dumps(out,indent=2))
