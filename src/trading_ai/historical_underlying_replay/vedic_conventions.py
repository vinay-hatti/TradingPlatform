from __future__ import annotations

VEDIC_CONVENTIONS={
"zodiac":"SIDEREAL","ayanamsha":"LAHIRI_CHITRAPAKSHA","observer":"GEOCENTRIC",
"time_basis":"UTC","daily_reference_time_utc":"12:00:00",
"graha_scope_phase_0":["SUN","MOON","MERCURY","VENUS","MARS","JUPITER","SATURN"],
"node_convention":"TRUE_NODE","node_status":"DEFERRED_PENDING_AUTHORITATIVE_LUNAR_ORBIT_PLANE_DERIVATION",
"rashi_count":12,"nakshatra_count":27,"pada_count_per_nakshatra":4,"tithi_count":30,
"boundary_policy":"LEFT_CLOSED_RIGHT_OPEN","traditional_financial_interpretations":"NOT_ASSUMED",
"production_authority_effect":False}

RASHI=("MESHA","VRISHABHA","MITHUNA","KARKA","SIMHA","KANYA","TULA","VRISCHIKA","DHANU","MAKARA","KUMBHA","MEENA")
NAKSHATRA=("ASHWINI","BHARANI","KRITTIKA","ROHINI","MRIGASHIRSHA","ARDRA","PUNARVASU","PUSHYA","ASHLESHA",
"MAGHA","PURVA_PHALGUNI","UTTARA_PHALGUNI","HASTA","CHITRA","SWATI","VISHAKHA","ANURADHA","JYESHTHA",
"MULA","PURVA_ASHADHA","UTTARA_ASHADHA","SHRAVANA","DHANISHTHA","SHATABHISHA","PURVA_BHADRAPADA","UTTARA_BHADRAPADA","REVATI")

def norm(x): return x%360.0
def require_ayanamsha(ayanamsha_deg):
    if ayanamsha_deg is None:
        raise RuntimeError("Sidereal feature materialization is fail-closed until independently validated Lahiri/Chitrapaksha ayanamsha is supplied.")
    return float(ayanamsha_deg)
def sidereal_longitude(tropical_longitude_deg,ayanamsha_deg): return norm(tropical_longitude_deg-require_ayanamsha(ayanamsha_deg))
def rashi_from_sidereal(deg):
    x=norm(deg); i=int(x//30); return {"index":i,"name":RASHI[i],"degree_in_rashi":x-i*30}
def nakshatra_from_sidereal(deg):
    x=norm(deg); span=360/27; i=min(26,int(x//span)); within=x-i*span; pada=min(4,int(within/(span/4))+1)
    return {"index":i,"name":NAKSHATRA[i],"pada":pada,"degree_in_nakshatra":within}
def tithi_from_sidereal_sun_moon(sun_deg,moon_deg):
    elong=norm(moon_deg-sun_deg); i=min(29,int(elong//12))
    return {"index":i,"number":i+1,"paksha":"SHUKLA" if i<15 else "KRISHNA","degree_in_tithi":elong-i*12}
