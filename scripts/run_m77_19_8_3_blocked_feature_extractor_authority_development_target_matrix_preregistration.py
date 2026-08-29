#!/usr/bin/env python3
"""
M77.19.8.3 — Blocked Feature Extractor Authority &
Development Target Matrix Preregistration

Freezes exact semantics for the 10 M77.19.8.2 authority-blocked feature IDs,
and preregisters the future Development-only target join.

No feature backfill is performed here.
No outcome/target file is opened here.
No model fitting/scoring is performed here.
Validation and Final Holdout remain closed.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any

VERSION="M77.19.8.3-BLOCKED-FEATURE-EXTRACTOR-AUTHORITY-DEVELOPMENT-TARGET-MATRIX-PREREGISTRATION-1.0"
EXPECTED_MATRIX_VERSION="M77.19.8.2-DEVELOPMENT-ONLY-FEATURE-MATRIX-MATERIALIZATION-SCHEMA-VALIDATION-1.0"
EXPECTED_FEATURE_VERSION="M77.19.8.1-POINT-IN-TIME-PROSPECTIVE-EDGE-FEATURE-AUTHORITY-1.0"
DEV_END="2017-12-31"
VALIDATION_START="2018-01-01"
FINAL_HOLDOUT_START="2023-01-01"
HORIZONS=[5,10,20]

EXTRACTORS=[
    {
        "feature_id":"F012",
        "name":"timeframe_states_payload",
        "status":"FIELD_LEVEL_FLATTENING_PREREGISTERED",
        "source_authority":"profile.timeframe_states",
        "semantics":"Expose only explicitly enumerated scalar numeric/enum leaf fields after schema census; no whole-payload embedding.",
        "future_access":False,
    },
    {
        "feature_id":"F020",
        "name":"atr_1d",
        "status":"EXTRACTOR_PREREGISTERED",
        "source_authority":"profile.timeframe_states['1d'] native ATR scalar if present",
        "semantics":"Read the native 1d ATR field only; no ATR recomputation from future or external data.",
        "future_access":False,
    },
    {
        "feature_id":"F021",
        "name":"atr_normalized",
        "status":"EXTRACTOR_PREREGISTERED",
        "source_authority":"same-as-of F020 divided by same-as-of reference close",
        "semantics":"ATR/reference_price using values available at the replay as_of only.",
        "future_access":False,
    },
    {
        "feature_id":"F030",
        "name":"nearest_support_distance_pct",
        "status":"EXTRACTOR_PREREGISTERED",
        "source_authority":"profile.support_levels + same-as-of reference close",
        "semantics":"Nearest support by absolute price distance; signed as (support-reference)/reference.",
        "future_access":False,
    },
    {
        "feature_id":"F031",
        "name":"nearest_resistance_distance_pct",
        "status":"EXTRACTOR_PREREGISTERED",
        "source_authority":"profile.resistance_levels + same-as-of reference close",
        "semantics":"Nearest resistance by absolute price distance; signed as (resistance-reference)/reference.",
        "future_access":False,
    },
    {
        "feature_id":"F051",
        "name":"institutional_volume_state",
        "status":"FIELD_LEVEL_FLATTENING_PREREGISTERED",
        "source_authority":"profile.institutional_volume",
        "semantics":"Schema census then scalar field whitelist only; no free-form/opaque payload encoding.",
        "future_access":False,
    },
    {
        "feature_id":"F070",
        "name":"relative_strength_vs_spy_proxy",
        "status":"EXTRACTOR_PREREGISTERED",
        "source_authority":"frozen symbol daily prefix + frozen SPY daily prefix",
        "semantics":"Two scalar features later: trailing 13w and 26w symbol return minus SPY return, using only sessions <= as_of.",
        "future_access":False,
    },
    {
        "feature_id":"F071",
        "name":"relative_strength_vs_sector",
        "status":"BLOCKED_PENDING_PIT_SECTOR_AUTHORITY",
        "source_authority":"none yet",
        "semantics":"Must remain unavailable until historical point-in-time sector membership and benchmark authority is certified.",
        "future_access":False,
    },
    {
        "feature_id":"F080",
        "name":"symbol_drawdown_from_52w_peak",
        "status":"EXTRACTOR_PREREGISTERED",
        "source_authority":"frozen symbol daily prefix",
        "semantics":"close_asof/max(close over prior 252 available sessions inclusive)-1.",
        "future_access":False,
    },
    {
        "feature_id":"F081",
        "name":"distance_from_52w_low",
        "status":"EXTRACTOR_PREREGISTERED",
        "source_authority":"frozen symbol daily prefix",
        "semantics":"close_asof/min(close over prior 252 available sessions inclusive)-1.",
        "future_access":False,
    },
]

TARGETS=[
    {
        "target_id":"T_ABS_RET",
        "name":"absolute_forward_return",
        "horizons":HORIZONS,
        "formula":"symbol_close[t+h]/symbol_close[t]-1",
        "partition":"DEVELOPMENT_ONLY",
    },
    {
        "target_id":"T_REL_SPY_RET",
        "name":"market_relative_forward_return",
        "horizons":HORIZONS,
        "formula":"symbol_forward_return - SPY_forward_return over same session horizon",
        "partition":"DEVELOPMENT_ONLY",
    },
    {
        "target_id":"T_DIRECTION",
        "name":"direction_label",
        "horizons":HORIZONS,
        "formula":"UP if absolute_forward_return>0; DOWN if <0; ZERO if ==0",
        "partition":"DEVELOPMENT_ONLY",
    },
]

class AuthorityError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw).expanduser()
    if p.is_absolute(): return p.resolve()
    return (root/p).resolve()

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--matrix-authority-json",default="reports/m77_19_8_2_development_only_feature_matrix_materialization_schema_validation.json")
    ap.add_argument("--output-json",default="reports/m77_19_8_3_blocked_feature_extractor_authority_development_target_matrix_preregistration.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_3_blocked_feature_extractor_registry.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    fp=resolve(root,args.feature_authority_json)
    mp=resolve(root,args.matrix_authority_json)
    fa=load_json(fp); ma=load_json(mp)

    if fa.get("version")!=EXPECTED_FEATURE_VERSION or fa.get("status")!="READY":
        raise AuthorityError("M77.19.8.1 authority invalid")
    if ma.get("version")!=EXPECTED_MATRIX_VERSION or ma.get("status")!="READY":
        raise AuthorityError("M77.19.8.2 authority invalid")
    if ma.get("materialized_row_count")!=303689:
        raise AuthorityError("Development matrix row-count authority mismatch")
    if ma.get("materialized_symbol_count")!=524:
        raise AuthorityError("Development matrix symbol-count authority mismatch")
    if ma.get("scope_protection",{}).get("outcome_or_target_data_read") is not False:
        raise AuthorityError("M77.19.8.2 unexpectedly read targets")
    if ma.get("scope_protection",{}).get("validation_matrix_materialized") is not False:
        raise AuthorityError("Validation matrix must remain absent")
    if ma.get("scope_protection",{}).get("final_holdout_matrix_materialized") is not False:
        raise AuthorityError("Final Holdout matrix must remain absent")

    blocked=[x for x in ma.get("schema_summary") or [] if x.get("materialization_state")=="AUTHORITY_BLOCKED_NULL_WITH_MISSINGNESS"]
    blocked_ids=sorted(x["feature_id"] for x in blocked)
    extractor_ids=sorted(x["feature_id"] for x in EXTRACTORS)
    if blocked_ids!=extractor_ids:
        raise AuthorityError(f"blocked feature authority mismatch: {blocked_ids} != {extractor_ids}")
    if len(EXTRACTORS)!=10:
        raise AuthorityError("expected exactly 10 blocked feature extractors")
    if any(x.get("future_access") is not False for x in EXTRACTORS):
        raise AuthorityError("future access must be prohibited")

    report={
        "version":VERSION,
        "status":"READY",
        "feature_authority_sha256":sha256_file(fp),
        "matrix_authority_sha256":sha256_file(mp),
        "development_matrix_authority":{
            "symbol_count":524,
            "row_count":303689,
            "development_end":DEV_END,
        },
        "blocked_feature_extractor_count":len(EXTRACTORS),
        "extractors":EXTRACTORS,
        "sector_relative_strength_state":"BLOCKED_PENDING_PIT_SECTOR_AUTHORITY",
        "target_preregistration":{
            "targets":TARGETS,
            "horizons":HORIZONS,
            "join_key":["symbol","as_of"],
            "feature_partition":"DEVELOPMENT_ONLY",
            "target_partition":"DEVELOPMENT_ONLY",
            "forward_sessions_must_follow_frozen_SPY_session_calendar":True,
            "target_maturity_required":True,
            "target_rows_without_full_horizon_are_not_matured":True,
            "future_data_authorized_for_target_labeling_only":True,
            "future_data_authorized_for_features":False,
        },
        "schema_census_requirements":{
            "timeframe_states_schema_census_required_before_F012_materialization":True,
            "institutional_volume_schema_census_required_before_F051_materialization":True,
            "unregistered_nested_fields_prohibited":True,
            "opaque_payload_embedding_prohibited":True,
        },
        "research_governance":{
            "feature_backfill_performed":False,
            "outcome_or_target_file_opened":False,
            "target_matrix_materialized":False,
            "development_target_scoring_performed":False,
            "validation_data_opened":False,
            "final_holdout_data_opened":False,
            "standardization_fit":False,
            "imputation_fit":False,
            "feature_selection_performed":False,
            "model_training_performed":False,
            "model_scoring_performed":False,
        },
        "production_governance":{
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_8_4_BLOCKED_FEATURE_SCHEMA_CENSUS_AND_DEVELOPMENT_FEATURE_BACKFILL_AUTHORITY",
    }

    oj=resolve(root,args.output_json)
    oc=resolve(root,args.output_csv)
    atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=["feature_id","name","status","source_authority","semantics","future_access"])
        w.writeheader();w.writerows(EXTRACTORS)

    print("=== M77.19.8.3 BLOCKED FEATURE EXTRACTOR AUTHORITY & DEVELOPMENT TARGET MATRIX PREREGISTRATION ===")
    print("status: READY")
    print("development_symbol_count: 524")
    print("development_row_count: 303689")
    print("blocked_feature_extractor_count:",len(EXTRACTORS))
    for x in EXTRACTORS:
        print(f"{x['feature_id']} {x['name']}: {x['status']}")
    print("target_horizons:",HORIZONS)
    print("target_ids:",[x["target_id"] for x in TARGETS])
    print("feature_backfill_performed: False")
    print("outcome_or_target_file_opened: False")
    print("target_matrix_materialized: False")
    print("validation_data_opened: False")
    print("final_holdout_data_opened: False")
    print("model_training_performed: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_4_BLOCKED_FEATURE_SCHEMA_CENSUS_AND_DEVELOPMENT_FEATURE_BACKFILL_AUTHORITY")
    print("report:",oj)
    print("csv:",oc)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
