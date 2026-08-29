#!/usr/bin/env python3
from __future__ import annotations
import csv,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"data/m77/m77_15_2_panchanga_daily_2000_2040.csv"
OUT=ROOT/"data/m77/m77_17_1_lunar_phase_daily_2000_2040.csv"
META=ROOT/"data/m77/m77_17_1_lunar_phase_daily_2000_2040.metadata.json"
FIELDS=("date","sun_sidereal_deg","moon_sidereal_deg","lunar_phase_angle_deg","first_quarter_window")

def norm(x): return x%360.0
def adist(a,b):
    d=abs(norm(a)-norm(b)); return min(d,360-d)

if not SRC.exists():
    raise SystemExit("M77.17.1 blocked: certified Panchanga daily registry missing")

with SRC.open() as f:
    rows=list(csv.DictReader(f))

required=("date","sun_sidereal_deg","moon_sidereal_deg")
missing=[k for k in required if k not in (rows[0] if rows else {})]
if missing:
    raise SystemExit(f"M77.17.1 blocked: Panchanga registry missing columns {missing}")

out=[]
for r in rows:
    sun=float(r["sun_sidereal_deg"]); moon=float(r["moon_sidereal_deg"])
    phase=norm(moon-sun)
    active=adist(phase,90.0)<=22.5
    out.append({
        "date":r["date"],"sun_sidereal_deg":sun,"moon_sidereal_deg":moon,
        "lunar_phase_angle_deg":phase,"first_quarter_window":active
    })

OUT.parent.mkdir(parents=True,exist_ok=True)
tmp=OUT.with_suffix(".csv.tmp")
with tmp.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(out)
tmp.replace(OUT)

meta={
 "version":"M77.17.1-LUNAR-FEATURE-AUTHORITY-RECONSTRUCTION-1.0",
 "status":"READY","source":str(SRC),"rows":len(out),
 "first_date":out[0]["date"] if out else None,"last_date":out[-1]["date"] if out else None,
 "definition":{"phase_angle":"MOON_SIDEREAL_LONGITUDE_MINUS_SUN_SIDEREAL_LONGITUDE_MOD_360",
               "first_quarter_center_deg":90.0,"half_width_deg":22.5},
 "first_quarter_window_rows":sum(1 for r in out if r["first_quarter_window"]),
 "financial_outcomes_present":False,"production_authority_effect":False
}
t=META.with_suffix(".json.tmp"); t.write_text(json.dumps(meta,indent=2)+"\n"); json.loads(t.read_text()); t.replace(META)
print(json.dumps(meta,indent=2))
