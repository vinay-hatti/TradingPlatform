#!/usr/bin/env python3
from __future__ import annotations

import csv,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
M=ROOT/"research_data/m77_15_6_4/polygon_coverage_lineage/manifests/latest.json"
OUT=ROOT/"reports/m77/m77_15_6_5_1_qqq_lineage_ohlc_forensic_audit.json"

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def load_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))

def violation(row):
    try:
        o=float(row["open"]); h=float(row["high"]); l=float(row["low"]); c=float(row["close"])
    except Exception:
        return "MISSING_OR_INVALID_OHLC"
    if min(o,h,l,c)<=0:
        return "NONPOSITIVE_OHLC"
    if h < max(o,c,l) or l > min(o,c,h):
        return "OHLC_INVARIANT"
    return None

if not M.exists():
    raise SystemExit("M77.15.6.4 manifest missing")

m=json.loads(M.read_text())
qline=Path(m["qqq_lineage"]["stitched_path"])
if not qline.exists():
    raise SystemExit(f"QQQ lineage file missing: {qline}")

rows=load_csv(qline)
bad=[]
for i,r in enumerate(rows):
    why=violation(r)
    if why:
        lo=max(0,i-3); hi=min(len(rows),i+4)
        neighbors=[]
        for j in range(lo,hi):
            x=dict(rows[j])
            x["is_violation_row"]=j==i
            neighbors.append(x)
        bad.append({
            "row_index":i,
            "date":r.get("date"),
            "source_ticker":r.get("polygon_ticker"),
            "reason":why,
            "row":r,
            "neighbors":neighbors,
        })

source_detail={}
for sym in ("QQQ","QQQQ"):
    entry=m["source_series"][sym]
    p=Path(entry["normalized_path"]) if entry.get("normalized_path") else None
    if p and p.exists():
        src=load_csv(p)
        bydate={r["date"]:r for r in src}
        source_detail[sym]={
            "row_count":len(src),
            "matching_violation_dates":{
                b["date"]:bydate.get(b["date"]) for b in bad if b["date"] in bydate
            },
            "raw_pages":entry.get("raw_pages") or [],
        }

out={
    "version":"M77.15.6.5.1-QQQ-LINEAGE-OHLC-FORENSIC-AUDIT-1.0",
    "status":"READY",
    "qqq_lineage_path":str(qline),
    "lineage_row_count":len(rows),
    "violation_count":len(bad),
    "violations":bad,
    "source_series_evidence":source_detail,
    "governance":{
        "diagnostic_only":True,
        "automatic_repair":False,
        "source_value_mutation":False,
        "lineage_mutation":False,
        "database_writes":False,
        "production_price_history_writes":False,
        "production_authority_effect":False,
    },
    "next_step":"CLASSIFY_SINGLE_QQQ_LINEAGE_OHLC_ANOMALY_AS_SOURCE_DATA_OR_STITCH_DEFECT_BEFORE_ANY_REPAIR"
}
write_json_atomic(OUT,out)

print("=== M77.15.6.5.1 QQQ LINEAGE OHLC FORENSIC AUDIT ===")
print("lineage_rows:",len(rows))
print("violation_count:",len(bad))
for b in bad:
    print()
    print("VIOLATION")
    print(" date:",b["date"])
    print(" source_ticker:",b["source_ticker"])
    print(" reason:",b["reason"])
    print(" row:",b["row"])
    print(" neighbors:")
    for n in b["neighbors"]:
        mark=" <-- VIOLATION" if n["is_violation_row"] else ""
        print("  ",n["date"],n["polygon_ticker"],
              "O=",n["open"],"H=",n["high"],"L=",n["low"],"C=",n["close"],mark)
    for sym,e in source_detail.items():
        match=e["matching_violation_dates"].get(b["date"])
        if match:
            print(f" source_{sym}_same_date:",match)
print()
print("automatic_repair: False")
print("production_authority_effect: False")
print("next_step:",out["next_step"])
