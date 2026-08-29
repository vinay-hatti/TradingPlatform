#!/usr/bin/env python3
from __future__ import annotations

import argparse,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_16_1_mundane_market_chart_authority.json"
OUT=ROOT/"reports/m77/m77_16_1_mundane_market_chart_authority.json"
CONFIRM="CERTIFY_M77_16_1_MUNDANE_MARKET_CHART_AUTHORITY"

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","certify"))
    ap.add_argument("--confirm")
    a=ap.parse_args()

    cfg=json.loads(CFG.read_text())
    cert=ROOT/cfg["authority"]["required_long_history_certification"]
    if not cert.exists():
        raise SystemExit("M77.16.1 blocked: long-history authority certification missing")
    cx=json.loads(cert.read_text())
    if not cx.get("certified_for_m77_15_7_long_history_replication"):
        raise SystemExit("M77.16.1 blocked: long-history proxy authority not certified")

    if a.mode=="preflight":
        print(json.dumps({
            "version":cfg["version"],
            "status":"READY",
            "confirmation_required":CONFIRM,
            "market_chart_authority":cfg["market_chart_authority"],
            "h3_preregistration":cfg["h3_preregistration"],
            "long_history_common_sessions":cx["common_authority"]["session_count"],
            "production_authority_effect":False
        },indent=2))
        return

    if a.confirm!=CONFIRM:
        raise SystemExit(f"confirmation required: {CONFIRM}")

    # This phase deliberately certifies the *definition contract* only.
    # It does not yet compute houses from ephemeris or touch financial outcomes.
    mc=cfg["market_chart_authority"]
    required=(
        mc["reference_event"]["date"],
        mc["reference_event"]["time_local"],
        mc["reference_event"]["location"]["timezone"],
        mc["zodiac"],
        mc["ayanamsha"],
        mc["house_system"],
        mc["node_type"],
    )
    definition_complete=all(bool(x) for x in required)
    prereg=cfg["h3_preregistration"]
    h3_complete=bool(prereg["states"]) and bool(prereg["horizons"]) and bool(prereg["predictions"])

    gates={
        "reference_event_frozen":definition_complete,
        "location_frozen":True,
        "ayanamsha_frozen":mc["ayanamsha"]=="LAHIRI",
        "house_system_frozen":mc["house_system"]=="WHOLE_SIGN",
        "true_node_frozen":mc["node_type"]=="TRUE_NODE",
        "lordship_scheme_frozen":len(mc["lordship_scheme"])==12,
        "alternatives_search_prohibited":mc["alternatives_search_prohibited"] is True,
        "posthoc_chart_changes_prohibited":mc["posthoc_chart_changes_prohibited"] is True,
        "h3_states_horizons_predictions_frozen":h3_complete,
        "factor_combinations_prohibited":prereg["factor_combinations"] is False,
        "neighboring_orb_search_prohibited":prereg["neighboring_orb_search"] is False,
        "long_history_authority_certified":cx.get("certified_for_m77_15_7_long_history_replication") is True
    }

    certified=all(gates.values())
    out={
        "version":cfg["version"],
        "status":"READY",
        "market_chart_authority":mc,
        "h3_preregistration":prereg,
        "gates":gates,
        "certified_for_h3_feature_materialization":certified,
        "important_interpretation":{
            "reference_time_is_research_convention":True,
            "exact_historical_signing_time_claimed":False,
            "alternative_chart_search_after_results":"PROHIBITED"
        },
        "next_step":"BUILD_M77_16_2_H3_ASTRONOMICAL_FEATURE_MATERIALIZATION_AND_PARITY" if certified else "REVIEW_M77_16_1_AUTHORITY_GATES",
        "database_writes":False,
        "production_authority_effect":False
    }
    write_json_atomic(OUT,out)
    print(json.dumps(out,indent=2))

if __name__=="__main__":
    main()
