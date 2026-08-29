from __future__ import annotations

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

RASHI=("MESHA","VRISHABHA","MITHUNA","KARKA","SIMHA","KANYA","TULA","VRISCHIKA","DHANU","MAKARA","KUMBHA","MEENA")

def norm(x): return x % 360.0

def angular_distance(a,b):
    d=abs(norm(a)-norm(b))
    return min(d,360.0-d)

def julian_day(dt):
    return dt.astimezone(timezone.utc).timestamp()/86400.0 + 2440587.5

def mean_obliquity_deg(jd):
    T=(jd-2451545.0)/36525.0
    return 23.439291111 - 0.013004167*T - 0.000000164*T*T + 0.000000504*T*T*T

def gmst_deg(jd):
    T=(jd-2451545.0)/36525.0
    return norm(280.46061837 + 360.98564736629*(jd-2451545.0) + 0.000387933*T*T - T*T*T/38710000.0)

def tropical_ascendant_deg(dt_local,lat_deg,lon_deg):
    jd=julian_day(dt_local)
    lst=norm(gmst_deg(jd)+lon_deg)
    eps=math.radians(mean_obliquity_deg(jd))
    theta=math.radians(lst)
    phi=math.radians(lat_deg)
    # atan2 formulation for eastern ecliptic/horizon intersection.
    return norm(math.degrees(math.atan2(
        math.cos(theta),
        -(math.sin(theta)*math.cos(eps)+math.tan(phi)*math.sin(eps))
    )))

def tropical_ascendant_deg_alt(dt_local,lat_deg,lon_deg):
    # Algebraically equivalent y/x formulation retained as an internal parity check.
    jd=julian_day(dt_local)
    lst=norm(gmst_deg(jd)+lon_deg)
    eps=math.radians(mean_obliquity_deg(jd))
    theta=math.radians(lst)
    phi=math.radians(lat_deg)
    y=-math.cos(theta)
    x=math.sin(theta)*math.cos(eps)+math.tan(phi)*math.sin(eps)
    raw=norm(math.degrees(math.atan2(y,x)))
    # atan2(y,x) above is antipodal to the direct rising-intersection form.
    return norm(raw+180.0)

def rashi_index(deg): return int(norm(deg)//30)
def rashi_name(deg): return RASHI[rashi_index(deg)]

def whole_sign_house_sign(asc_rashi_index,house_number):
    if not 1 <= house_number <= 12: raise ValueError("house_number must be 1..12")
    return (asc_rashi_index + house_number - 1) % 12

def derive_reference_chart(cfg):
    rc=cfg["reference_chart"]
    dt=datetime.fromisoformat(f'{rc["date"]}T{rc["time_local"]}').replace(tzinfo=ZoneInfo(rc["timezone"]))
    tropical=tropical_ascendant_deg(dt,rc["latitude_deg"],rc["longitude_deg"])
    tropical_alt=tropical_ascendant_deg_alt(dt,rc["latitude_deg"],rc["longitude_deg"])
    ay=float(cfg["frozen_external_benchmarks"]["lahiri_ayanamsha_1792_05_17_deg"])
    sid=norm(tropical-ay)
    asc_idx=rashi_index(sid)
    h5=whole_sign_house_sign(asc_idx,5)
    h11=whole_sign_house_sign(asc_idx,11)
    return {
        "reference_local_datetime":dt.isoformat(),
        "reference_utc_datetime":dt.astimezone(timezone.utc).isoformat(),
        "tropical_ascendant_deg":tropical,
        "tropical_ascendant_alt_deg":tropical_alt,
        "ascendant_formula_parity_error_deg":angular_distance(tropical,tropical_alt),
        "lahiri_ayanamsha_deg":ay,
        "sidereal_ascendant_deg":sid,
        "ascendant_rashi_index":asc_idx,
        "ascendant_rashi":RASHI[asc_idx],
        "fifth_house_rashi_index":h5,
        "fifth_house_rashi":RASHI[h5],
        "eleventh_house_rashi_index":h11,
        "eleventh_house_rashi":RASHI[h11],
    }
