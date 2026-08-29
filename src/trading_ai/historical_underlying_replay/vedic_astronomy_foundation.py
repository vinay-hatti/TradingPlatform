from __future__ import annotations

import json
import math
from bisect import bisect_right
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BENCH=ROOT/"config/m77/m77_15_1_lahiri_monthly_benchmarks_2000_2040.json"

RASHI=("MESHA","VRISHABHA","MITHUNA","KARKA","SIMHA","KANYA","TULA","VRISCHIKA","DHANU","MAKARA","KUMBHA","MEENA")
NAKSHATRA=("ASHWINI","BHARANI","KRITTIKA","ROHINI","MRIGASHIRSHA","ARDRA","PUNARVASU","PUSHYA","ASHLESHA","MAGHA","PURVA_PHALGUNI","UTTARA_PHALGUNI","HASTA","CHITRA","SWATI","VISHAKHA","ANURADHA","JYESHTHA","MULA","PURVA_ASHADHA","UTTARA_ASHADHA","SHRAVANA","DHANISHTHA","SHATABHISHA","PURVA_BHADRAPADA","UTTARA_BHADRAPADA","REVATI")
YOGA=("VISHKAMBHA","PRITI","AYUSHMAN","SAUBHAGYA","SHOBHANA","ATIGANDA","SUKARMA","DHRITI","SHULA","GANDA","VRIDDHI","DHRUVA","VYAGHATA","HARSHANA","VAJRA","SIDDHI","VYATIPATA","VARIYANA","PARIGHA","SHIVA","SIDDHA","SADHYA","SHUBHA","SHUKLA","BRAHMA","INDRA","VAIDHRITI")
MOVABLE_KARANA=("BAVA","BALAVA","KAULAVA","TAITILA","GARA","VANIJA","VISHTI")

def norm(x): return x%360.0
def adist(a,b):
    d=abs(norm(a)-norm(b))%360
    return min(d,360-d)

def _ordinal_fraction(d):
    if isinstance(d,date) and not isinstance(d,datetime):
        dt=datetime(d.year,d.month,d.day,12,tzinfo=timezone.utc)
    else:
        dt=d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return dt.timestamp()/86400.0

def lahiri_ayanamsha_deg(d):
    x=json.loads(BENCH.read_text())["values_deg"]
    items=sorted((date.fromisoformat(k),float(v)) for k,v in x.items())
    xs=[_ordinal_fraction(k) for k,_ in items]; ys=[v for _,v in items]
    q=_ordinal_fraction(d)
    if q<xs[0] or q>xs[-1]:
        raise RuntimeError("Lahiri interpolation authority supports 2000-01-01 through 2040-12-01 only")
    i=bisect_right(xs,q)
    if i==0:return ys[0]
    if i>=len(xs):return ys[-1]
    x0,x1=xs[i-1],xs[i]; y0,y1=ys[i-1],ys[i]
    return y0+(y1-y0)*(q-x0)/(x1-x0)

def sidereal_longitude(tropical_deg,d):
    return norm(tropical_deg-lahiri_ayanamsha_deg(d))

def rashi(sid_deg):
    x=norm(sid_deg); i=int(x//30)
    return {"index":i,"name":RASHI[i],"degree_in_rashi":x-i*30}

def nakshatra(sid_deg):
    x=norm(sid_deg); span=360/27; i=min(26,int(x//span)); within=x-i*span
    return {"index":i,"name":NAKSHATRA[i],"pada":min(4,int(within/(span/4))+1),"degree_in_nakshatra":within}

def tithi(sun_sid,moon_sid):
    elong=norm(moon_sid-sun_sid); i=min(29,int(elong//12))
    return {"index":i,"number":i+1,"paksha":"SHUKLA" if i<15 else "KRISHNA","degree_in_tithi":elong-i*12}

def yoga(sun_sid,moon_sid):
    x=norm(sun_sid+moon_sid); span=360/27; i=min(26,int(x//span))
    return {"index":i,"name":YOGA[i],"degree_in_yoga":x-i*span}

def karana(sun_sid,moon_sid):
    elong=norm(moon_sid-sun_sid)
    half_index=min(59,int(elong//6))
    if half_index==0:name="KIMSTUGHNA"
    elif 1<=half_index<=56:name=MOVABLE_KARANA[(half_index-1)%7]
    elif half_index==57:name="SHAKUNI"
    elif half_index==58:name="CHATUSHPADA"
    else:name="NAGA"
    return {"half_tithi_index":half_index,"name":name,"degree_in_karana":elong-half_index*6}

def true_node_from_state(x,y,z,vx,vy,vz):
    # Instantaneous osculating ascending node from geocentric ecliptic state.
    hx=y*vz-z*vy
    hy=z*vx-x*vz
    nx=-hy
    ny=hx
    if abs(nx)<1e-18 and abs(ny)<1e-18:
        raise RuntimeError("Degenerate lunar orbital node vector")
    return norm(math.degrees(math.atan2(ny,nx)))

def ketu_from_rahu(rahu_deg): return norm(rahu_deg+180.0)
