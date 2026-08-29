#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from datetime import date
from pathlib import Path
from trading_ai.historical_underlying_replay.astronomical_cycles import glon as candidate_glon
from trading_ai.historical_underlying_replay.jpl_horizons_ephemeris import fetch_geocentric_ecliptic_state
from trading_ai.historical_underlying_replay.vedic_conventions import VEDIC_CONVENTIONS

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/"reports/m77/m77_15_0_jpl_ephemeris_cache"
OUT=ROOT/"reports/m77/m77_15_0_ephemeris_foundation_parity.json"
VERSION="M77.15.0-VEDIC-EPHEMERIS-FOUNDATION-1.0"
CONFIRM="RUN_M77_15_0_JPL_EPHEMERIS_PARITY"
DATES=(date(2023,3,20),date(2024,9,22),date(2025,12,1),date(2026,8,21))
PARITY=("MERCURY","MARS","JUPITER","SATURN")
SCOPE=("SUN","MOON","MERCURY","VENUS","MARS","JUPITER","SATURN")
def adist(a,b):
    d=abs((a%360)-(b%360))%360; return min(d,360-d)
def preflight():
    return {"version":VERSION,"status":"READY","mode":"PREFLIGHT","confirmation_required":CONFIRM,
      "authoritative_provider":"NASA_JPL_HORIZONS","provider_endpoint":"https://ssd.jpl.nasa.gov/api/horizons.api",
       "provider_api_version_documented":"1.3",
      "provider_api_versions_accepted":["1.2","1.3"],"provider_request_mode":"SEQUENTIAL_ONE_REQUEST_AT_A_TIME",
      "authoritative_scope":SCOPE,"frozen_parity_dates":[d.isoformat() for d in DATES],"frozen_conventions":VEDIC_CONVENTIONS,
      "sidereal_materialization_gate":"BLOCKED_PENDING_INDEPENDENT_LAHIRI_AYANAMSHA_PARITY",
      "node_materialization_gate":"BLOCKED_PENDING_TRUE_NODE_AUTHORITATIVE_DERIVATION",
      "production_authority_effect":False,"database_writes":False}
def run():
    authority=[]; parity=[]
    for d in DATES:
        daily={}
        for body in SCOPE:
            st=fetch_geocentric_ecliptic_state(body,d,CACHE); daily[body]=st; authority.append(st)
        for body in PARITY:
            j=daily[body]["tropical_ecliptic_longitude_deg"]; c=candidate_glon(body.lower(),d)
            parity.append({"date":d.isoformat(),"body":body,"jpl_tropical_longitude_deg":j,
              "existing_m77_14_low_precision_deg":c,"angular_error_deg":adist(j,c)})
    errs=[x["angular_error_deg"] for x in parity]
    out={"version":VERSION,"status":"READY","mode":"AUTHORITATIVE_EPHEMERIS_FOUNDATION_AND_DIAGNOSTIC_PARITY",
      "authoritative_provider":"NASA_JPL_HORIZONS","authoritative_state_count":len(authority),
      "diagnostic_candidate_parity":{"comparisons":len(parity),"mean_angular_error_deg":sum(errs)/len(errs),
        "max_angular_error_deg":max(errs),"rows":parity,
        "disposition":"DIAGNOSTIC_ONLY_EXISTING_LOW_PRECISION_ENGINE_NOT_VEDIC_AUTHORITY"},
      "vedic_conventions":VEDIC_CONVENTIONS,
      "acceptance":{"jpl_authoritative_states_materialized":len(authority)==len(DATES)*len(SCOPE),
        "sidereal_feature_materialization":False,"lahiri_ayanamsha_parity":False,"true_node_authority":False,
        "production_authority_effect":False},
      "next_step":"BUILD_M77_15_1_LAHIRI_AYANAMSHA_AND_TRUE_NODE_PARITY_THEN_PANCHANGA",
      "production_authority_effect":False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,indent=2,default=str)+"\n"); return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=("preflight","parity")); ap.add_argument("--confirm"); a=ap.parse_args()
    if a.mode=="preflight": print(json.dumps(preflight(),indent=2,default=str)); return
    if a.confirm!=CONFIRM: raise SystemExit(f"confirmation required: {CONFIRM}")
    o=run(); p=o["diagnostic_candidate_parity"]
    print(json.dumps({"version":o["version"],"status":o["status"],"authoritative_provider":o["authoritative_provider"],
      "authoritative_state_count":o["authoritative_state_count"],"diagnostic_candidate_parity":{"comparisons":p["comparisons"],
      "mean_angular_error_deg":p["mean_angular_error_deg"],"max_angular_error_deg":p["max_angular_error_deg"],
      "disposition":p["disposition"]},"acceptance":o["acceptance"],"next_step":o["next_step"],"production_authority_effect":False},indent=2))
if __name__=="__main__": main()
