#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from datetime import date
from pathlib import Path

from trading_ai.historical_underlying_replay.jpl_horizons_ephemeris import (
    fetch_geocentric_ecliptic_state,
    fetch_geocentric_ecliptic_state_vector,
)
from trading_ai.historical_underlying_replay.vedic_astronomy_foundation import (
    adist,karana,ketu_from_rahu,lahiri_ayanamsha_deg,nakshatra,rashi,
    sidereal_longitude,tithi,true_node_from_state,yoga,
)

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/"reports/m77/m77_15_0_jpl_ephemeris_cache"
REF=ROOT/"config/m77/m77_15_1_frozen_parity_reference.json"
CERT=ROOT/"reports/m77/m77_15_1_lahiri_true_node_parity.json"
PANCH=ROOT/"reports/m77/m77_15_1_panchanga_foundation.json"
VERSION="M77.15.1-LAHIRI-TRUE-NODE-PANCHANGA-FOUNDATION-1.0"
CONFIRM="RUN_M77_15_1_LAHIRI_TRUE_NODE_PARITY"
DATES=(date(2023,3,20),date(2024,9,22),date(2025,12,1),date(2026,8,21))
AYAN_TOL_DEG=0.01
NODE_TOL_DEG=1.0

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def load_certification_json(path):
    raw=path.read_text()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # M77.15.1 legacy writer accidentally emitted a literal two-character
        # backslash-n suffix after the JSON document. Repair that exact shape.
        cleaned=raw
        while cleaned.endswith("\\n"):
            cleaned=cleaned[:-2]
        cleaned=cleaned.rstrip()
        obj=json.loads(cleaned)
        write_json_atomic(path,obj)
        return obj


def parity():
    refs=json.loads(REF.read_text())["dates"]; rows=[]
    for d in DATES:
        key=d.isoformat(); ref=refs[key]
        ay=lahiri_ayanamsha_deg(d)
        moon=fetch_geocentric_ecliptic_state_vector("MOON",d,CACHE)
        rahu=true_node_from_state(moon["x_au"],moon["y_au"],moon["z_au"],moon["vx_au_per_day"],moon["vy_au_per_day"],moon["vz_au_per_day"])
        rows.append({"date":key,"lahiri_interpolated_deg":ay,"lahiri_reference_deg":ref["lahiri_ayanamsha_deg"],
          "lahiri_error_deg":abs(ay-ref["lahiri_ayanamsha_deg"]),"jpl_true_node_deg":rahu,
          "swiss_true_node_reference_deg":ref["swiss_true_node_deg"],"true_node_error_deg":adist(rahu,ref["swiss_true_node_deg"])})
    maxa=max(x["lahiri_error_deg"] for x in rows); maxn=max(x["true_node_error_deg"] for x in rows)
    ok_a=maxa<=AYAN_TOL_DEG; ok_n=maxn<=NODE_TOL_DEG
    out={"version":VERSION,"status":"READY","rows":rows,"thresholds":{"lahiri_max_error_deg":AYAN_TOL_DEG,"true_node_max_error_deg":NODE_TOL_DEG},
      "acceptance":{"lahiri_ayanamsha_parity":ok_a,"true_node_authority":ok_n,
        "sidereal_feature_materialization":ok_a and ok_n,"production_authority_effect":False},
      "next_step":"MATERIALIZE_PANCHANGA_FOUNDATION" if ok_a and ok_n else "STOP_REVIEW_PARITY_FAILURE",
      "production_authority_effect":False}
    write_json_atomic(CERT,out); return out

def materialize():
    if not CERT.exists(): raise SystemExit("Run M77.15.1 parity first")
    cert=load_certification_json(CERT)
    if not cert["acceptance"].get("sidereal_feature_materialization"):
        raise SystemExit("Sidereal materialization blocked: parity not certified")
    rows=[]
    for d in DATES:
        sun=fetch_geocentric_ecliptic_state("SUN",d,CACHE)
        moon=fetch_geocentric_ecliptic_state("MOON",d,CACHE)
        moon_state=fetch_geocentric_ecliptic_state_vector("MOON",d,CACHE)
        sun_sid=sidereal_longitude(sun["tropical_ecliptic_longitude_deg"],d)
        moon_sid=sidereal_longitude(moon["tropical_ecliptic_longitude_deg"],d)
        rahu=true_node_from_state(moon_state["x_au"],moon_state["y_au"],moon_state["z_au"],moon_state["vx_au_per_day"],moon_state["vy_au_per_day"],moon_state["vz_au_per_day"])
        rows.append({"date":d.isoformat(),"lahiri_ayanamsha_deg":lahiri_ayanamsha_deg(d),
          "sun_sidereal_deg":sun_sid,"moon_sidereal_deg":moon_sid,
          "sun_rashi":rashi(sun_sid),"moon_rashi":rashi(moon_sid),"moon_nakshatra":nakshatra(moon_sid),
          "tithi":tithi(sun_sid,moon_sid),"yoga":yoga(sun_sid,moon_sid),"karana":karana(sun_sid,moon_sid),
          "rahu_true_node_deg":rahu,"ketu_deg":ketu_from_rahu(rahu)})
    out={"version":VERSION,"status":"READY","mode":"PANCHANGA_FOUNDATION_SAMPLE","rows":rows,
      "governance":{"financial_backtesting":False,"traditional_interpretation":False,"database_writes":False,"production_authority_effect":False},
      "next_step":"BUILD_M77_15_2_SINGLE_FACTOR_PANCHANGA_STUDY","production_authority_effect":False}
    write_json_atomic(PANCH,out); return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=("preflight","parity","materialize")); ap.add_argument("--confirm"); a=ap.parse_args()
    if a.mode=="preflight":
        print(json.dumps({"version":VERSION,"status":"READY","confirmation_required":CONFIRM,
          "frozen_dates":[x.isoformat() for x in DATES],"lahiri_authority":"SWISS_EPHEMERIS_2.10.03_MONTHLY_BENCHMARK_INTERPOLATION_2000_2040",
          "true_node_authority":"NASA_JPL_HORIZONS_MOON_STATE_VECTOR_OSCULATING_ASCENDING_NODE",
          "true_node_independent_reference":"SWISS_EPHEMERIS_TRUE_NODE_2.10.03",
          "panchanga_scope":["RASHI","NAKSHATRA","PADA","TITHI","PAKSHA","YOGA","KARANA","RAHU","KETU"],
          "financial_backtesting":False,"database_writes":False,"production_authority_effect":False},indent=2)); return
    if a.mode=="parity":
        if a.confirm!=CONFIRM: raise SystemExit(f"confirmation required: {CONFIRM}")
        o=parity()
        print(json.dumps({"status":o["status"],"acceptance":o["acceptance"],"next_step":o["next_step"],"production_authority_effect":False},indent=2)); return
    o=materialize()
    print(json.dumps({"status":o["status"],"mode":o["mode"],"rows":len(o["rows"]),"next_step":o["next_step"],"production_authority_effect":False},indent=2))
if __name__=="__main__": main()
