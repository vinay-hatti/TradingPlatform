#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,re
from pathlib import Path

VERSION="M77.20.1-PIT-SECTOR-MEMBERSHIP-BENCHMARK-SOURCE-AUTHORITY-CENSUS-1.0"
class CensusError(RuntimeError):pass

def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def text(p):return Path(p).read_text(encoding="utf-8")
def csv_census(p):
    with Path(p).open("r",encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    dates=sorted({(r.get("as_of_date") or "").strip() for r in rows if (r.get("as_of_date") or "").strip()})
    sectors=sorted({(r.get("sector") or "").strip() for r in rows if (r.get("sector") or "").strip()})
    return {"row_count":len(rows),"distinct_as_of_dates":dates,"distinct_as_of_date_count":len(dates),
            "sector_count":len(sectors),"all_rows_have_as_of_date":all(bool((r.get("as_of_date") or "").strip()) for r in rows)}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--cycle2-json",default="reports/m77_20_0_prospective_edge_cycle2_preregistration_consumed_holdout_lock_authority.json")
    ap.add_argument("--canonical-csv",default="data/universe/us_listed_equities_etfs.csv")
    ap.add_argument("--market-service-source",default="src/trading_ai/market_intelligence/service.py")
    ap.add_argument("--market-model-source",default="src/trading_ai/market_intelligence/database_models.py")
    ap.add_argument("--trend-service-source",default="src/trading_ai/trend_intelligence/service.py")
    ap.add_argument("--market-engine-source",default="src/trading_ai/market_intelligence/engine.py")
    ap.add_argument("--historical-analytics-source",default="src/trading_ai/historical_underlying_replay/analytics.py")
    ap.add_argument("--daily-sector-source",default="src/trading_ai/daily/sectors.py")
    ap.add_argument("--sector-config-json",default="config/sectors.json")
    ap.add_argument("--migration-source",default="migrations/versions/m46_001_market_intelligence.py")
    ap.add_argument("--output-json",default="reports/m77_20_1_pit_sector_membership_benchmark_source_authority_census.json")
    ap.add_argument("--output-csv",default="reports/m77_20_1_sector_source_census_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    paths={k:R(root,v) for k,v in {
      "cycle2":a.cycle2_json,"canonical_csv":a.canonical_csv,"market_service":a.market_service_source,
      "market_model":a.market_model_source,"trend_service":a.trend_service_source,"market_engine":a.market_engine_source,
      "historical_analytics":a.historical_analytics_source,"daily_sector":a.daily_sector_source,
      "sector_config":a.sector_config_json,"migration":a.migration_source}.items()}
    for k,p in paths.items():
        if not p.exists():raise CensusError(f"required source missing: {k}={p}")

    c2=J(paths["cycle2"])
    if c2.get("status")!="READY" or c2.get("cycle")!="M77.20_PROSPECTIVE_EDGE_CYCLE2":raise CensusError("M77.20.0 authority invalid")
    if (c2.get("execution_state") or {}).get("prospective_outcomes_opened") is not False:raise CensusError("prospective outcomes already opened")
    if (c2.get("pit_sector_contract") or {}).get("historical_current_mapping_backfill_prohibited") is not True:raise CensusError("PIT-sector guardrail missing")

    cc=csv_census(paths["canonical_csv"])
    ms=text(paths["market_service"]); mm=text(paths["market_model"]); ts=text(paths["trend_service"])
    me=text(paths["market_engine"]); ha=text(paths["historical_analytics"]); ds=text(paths["daily_sector"])
    cfg=J(paths["sector_config"]); mig=text(paths["migration"])

    # Structural checks against actual repo implementation.
    for token in ("effective_from","effective_to","classification_source","is_active"):
        if token not in mm or token not in mig:raise CensusError(f"sector_membership temporal field missing: {token}")
    if "self.canonical_csv" not in ms or "as_of_date" not in ms or "INSERT INTO sector_membership" not in ms:
        raise CensusError("market service canonical->sector_membership producer contract changed")
    if "SECTOR_ETFS" not in ts or "canonical_csv" not in ts:raise CensusError("trend sector mapping contract changed")
    if "SECTOR_ETFS" not in me:raise CensusError("market intelligence sector benchmark map missing")
    if "Historical PIT sector membership unavailable" not in ha:raise CensusError("historical PIT-sector denial missing")
    if "SECTOR_MAP" not in ds or not isinstance(cfg,dict):raise CensusError("legacy static sector map contract changed")

    # Current canonical CSV is a single dated snapshot in the supplied repo; not a history.
    canonical_is_multi_snapshot = cc["distinct_as_of_date_count"] > 1
    historical_pit_from_canonical = canonical_is_multi_snapshot

    candidates=[
      {"source_id":"CANONICAL_UNIVERSE_CSV","location":a.canonical_csv,"source_type":"CURRENT_DATED_SNAPSHOT",
       "has_symbol":True,"has_sector":True,"has_effective_from_semantics":True,"has_effective_to_semantics":False,
       "historical_multi_snapshot_evidence":canonical_is_multi_snapshot,"historical_pit_membership_authority":historical_pit_from_canonical,
       "prospective_capture_eligible":True,
       "reason":"All repo rows share one as_of_date; valid as a dated snapshot, not historical membership history."},
      {"source_id":"SECTOR_MEMBERSHIP_TABLE_SCHEMA","location":"sector_membership","source_type":"TEMPORAL_CAPABLE_DATABASE_SCHEMA",
       "has_symbol":True,"has_sector":True,"has_effective_from_semantics":True,"has_effective_to_semantics":True,
       "historical_multi_snapshot_evidence":False,"historical_pit_membership_authority":False,
       "prospective_capture_eligible":True,
       "reason":"Schema supports temporal records, but repo producer derives them from current canonical CSV; storage capability is not historical source evidence."},
      {"source_id":"MARKET_INTELLIGENCE_MEMBERSHIP_PRODUCER","location":a.market_service_source,"source_type":"CURRENT_CANONICAL_SNAPSHOT_DERIVATION",
       "has_symbol":True,"has_sector":True,"has_effective_from_semantics":True,"has_effective_to_semantics":False,
       "historical_multi_snapshot_evidence":False,"historical_pit_membership_authority":False,
       "prospective_capture_eligible":True,
       "reason":"Writes sector_membership effective_from from canonical CSV as_of_date; does not reconstruct historical membership."},
      {"source_id":"TREND_INTELLIGENCE_MAPPING","location":a.trend_service_source,"source_type":"CURRENT_STATIC_SECTOR_AND_BENCHMARK_MAPPING",
       "has_symbol":True,"has_sector":True,"has_effective_from_semantics":False,"has_effective_to_semantics":False,
       "historical_multi_snapshot_evidence":False,"historical_pit_membership_authority":False,
       "prospective_capture_eligible":True,
       "reason":"Reads current canonical sector and static SECTOR_ETFS mapping; no historical membership intervals."},
      {"source_id":"MARKET_INTELLIGENCE_SECTOR_ETFS","location":a.market_engine_source,"source_type":"STATIC_SECTOR_BENCHMARK_MAP",
       "has_symbol":False,"has_sector":True,"has_effective_from_semantics":False,"has_effective_to_semantics":False,
       "historical_multi_snapshot_evidence":False,"historical_pit_membership_authority":False,
       "prospective_capture_eligible":True,
       "reason":"Useful current benchmark map only; contains no symbol membership or benchmark effective-date history."},
      {"source_id":"LEGACY_DAILY_SECTOR_MAP","location":a.daily_sector_source,"source_type":"SMALL_STATIC_SYMBOL_SECTOR_MAP",
       "has_symbol":True,"has_sector":True,"has_effective_from_semantics":False,"has_effective_to_semantics":False,
       "historical_multi_snapshot_evidence":False,"historical_pit_membership_authority":False,
       "prospective_capture_eligible":False,
       "reason":"Static hard-coded subset with no dates/provenance history."},
      {"source_id":"LEGACY_SECTOR_CONFIG","location":a.sector_config_json,"source_type":"SMALL_STATIC_SYMBOL_SECTOR_CONFIG",
       "has_symbol":True,"has_sector":True,"has_effective_from_semantics":False,"has_effective_to_semantics":False,
       "historical_multi_snapshot_evidence":False,"historical_pit_membership_authority":False,
       "prospective_capture_eligible":False,
       "reason":"Static JSON subset with no dates/provenance history."},
      {"source_id":"HISTORICAL_REPLAY_ANALYTICS","location":a.historical_analytics_source,"source_type":"EXPLICIT_NEGATIVE_AUTHORITY",
       "has_symbol":False,"has_sector":False,"has_effective_from_semantics":False,"has_effective_to_semantics":False,
       "historical_multi_snapshot_evidence":False,"historical_pit_membership_authority":False,
       "prospective_capture_eligible":False,
       "reason":"Explicitly states historical PIT sector membership unavailable and prohibits sector-certification claim."},
    ]
    historical=[x for x in candidates if x["historical_pit_membership_authority"]]
    prospective=[x for x in candidates if x["prospective_capture_eligible"]]

    benchmark_contract={
      "current_static_sector_etf_mapping_present":True,
      "current_mapping_sources":[a.trend_service_source,a.market_engine_source],
      "historical_benchmark_effective_date_authority_present":False,
      "benchmark_inception_history_authority_present":False,
      "pre_inception_substitution_authorized":False,
      "historical_F071_benchmark_authority_certified":False,
      "prospective_benchmark_mapping_capture_eligible":True,
    }
    conclusion="BLOCKED_NO_REPO_CERTIFIED_HISTORICAL_PIT_SECTOR_MEMBERSHIP_SOURCE"
    report={
      "version":VERSION,"status":"READY",
      "cycle2_authority_sha256":H(paths["cycle2"]),
      "repo_source_sha256":{k:H(p) for k,p in paths.items() if k!="cycle2"},
      "canonical_csv_census":cc,
      "source_candidate_count":len(candidates),
      "historical_pit_authority_candidate_count":len(historical),
      "prospective_capture_candidate_count":len(prospective),
      "source_candidates":candidates,
      "benchmark_contract":benchmark_contract,
      "historical_pit_sector_membership_authority_certified":False,
      "historical_F071_materialization_authorized":False,
      "development_F071_materialization_authorized":False,
      "previous_validation_F071_materialization_authorized":False,
      "consumed_final_holdout_F071_materialization_authorized":False,
      "prospective_membership_snapshot_capture_authorized":True,
      "prospective_sector_benchmark_snapshot_capture_authorized":True,
      "prospective_outcomes_opened":False,
      "F071_formula_materialization_performed":False,
      "production_authority_effect":False,
      "census_conclusion":conclusion,
      "next_step":"BUILD_M77_20_2_EXTERNAL_HISTORICAL_PIT_SECTOR_SOURCE_DECISION_OR_PROSPECTIVE_ONLY_RESEARCH_DESIGN_GATE",
    }
    oj=R(root,a.output_json);oc=R(root,a.output_csv);oj.parent.mkdir(parents=True,exist_ok=True)
    oj.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    fields=["source_id","location","source_type","has_symbol","has_sector","has_effective_from_semantics","has_effective_to_semantics",
            "historical_multi_snapshot_evidence","historical_pit_membership_authority","prospective_capture_eligible","reason"]
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(candidates)

    print("=== M77.20.1 PIT SECTOR MEMBERSHIP & BENCHMARK SOURCE AUTHORITY CENSUS ===")
    print("status: READY")
    print("canonical_csv_row_count:",cc["row_count"])
    print("canonical_csv_distinct_as_of_dates:",cc["distinct_as_of_dates"])
    print("canonical_csv_distinct_as_of_date_count:",cc["distinct_as_of_date_count"])
    print("sector_membership_table_temporal_capable: True")
    print("sector_membership_current_producer_source: CANONICAL_UNIVERSE_CSV")
    print("historical_pit_authority_candidate_count:",len(historical))
    print("prospective_capture_candidate_count:",len(prospective))
    print("historical_pit_sector_membership_authority_certified: False")
    print("historical_benchmark_effective_date_authority_present: False")
    print("benchmark_inception_history_authority_present: False")
    print("historical_F071_materialization_authorized: False")
    print("prospective_membership_snapshot_capture_authorized: True")
    print("prospective_sector_benchmark_snapshot_capture_authorized: True")
    print("prospective_outcomes_opened: False")
    print("production_authority_effect: False")
    print("census_conclusion:",conclusion)
    print("next_step:",report["next_step"])
    print("report:",oj);print("csv:",oc)
if __name__=="__main__":main()
