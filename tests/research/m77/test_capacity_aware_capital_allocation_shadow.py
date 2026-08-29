import json
from pathlib import Path
import pandas as pd

from trading_ai.research.m77.capacity_aware_capital_allocation_shadow import (
    CapacityAwareShadowConfig, PROTOCOL_ID, _protocol_payload,
    freeze_protocol, record_snapshot, evaluate
)

def _write_inputs(tmp_path, date="2026-08-28", available=5):
    root=Path(tmp_path)
    d=root/"data/capacity_aware_capital_allocation_shadow"
    d.mkdir(parents=True,exist_ok=True)
    pd.DataFrame([
        {"symbol":"A","market_as_of_date":date,"probability_up":.90,"trade_builder_ready":True,"drv_pass":True},
        {"symbol":"B","market_as_of_date":date,"probability_up":.80,"trade_builder_ready":True,"drv_pass":True},
        {"symbol":"C","market_as_of_date":date,"probability_up":.70,"trade_builder_ready":True,"drv_pass":True},
        {"symbol":"D","market_as_of_date":date,"probability_up":.60,"trade_builder_ready":True,"drv_pass":True},
        {"symbol":"E","market_as_of_date":date,"probability_up":.50,"trade_builder_ready":True,"drv_pass":True},
        {"symbol":"F","market_as_of_date":date,"probability_up":.40,"trade_builder_ready":False,"drv_pass":True},
    ]).to_csv(d/"live_candidate_snapshot.csv",index=False)
    (d/"live_capacity_state.json").write_text(json.dumps({
        "market_as_of_date":date,"total_slots":8,"occupied_slots":8-available,"available_slots":available
    }))

def test_protocol_has_no_fixed_challenger_capacity():
    p=_protocol_payload()
    assert p["challenger_policy"]["capacity_source"]=="LIVE_GOVERNED_AVAILABLE_CAPACITY_AT_SNAPSHOT_TIME"
    assert "top_k" not in p["challenger_policy"]

def test_freeze_is_immutable(tmp_path):
    cfg=CapacityAwareShadowConfig(project_root=str(tmp_path))
    a=freeze_protocol(cfg);b=freeze_protocol(cfg)
    assert a["status"]=="FROZEN"
    assert b["status"]=="ALREADY_FROZEN"

def test_record_control_top3_challenger_uses_available_capacity(tmp_path):
    _write_inputs(tmp_path,available=5)
    cfg=CapacityAwareShadowConfig(project_root=str(tmp_path))
    freeze_protocol(cfg)
    r=record_snapshot(cfg)
    assert r["status"]=="RECORDED"
    assert r["control_selected"]==3
    assert r["challenger_selected"]==5

def test_record_skips_pre_boundary(tmp_path):
    _write_inputs(tmp_path,date="2026-08-27",available=5)
    cfg=CapacityAwareShadowConfig(project_root=str(tmp_path))
    freeze_protocol(cfg)
    r=record_snapshot(cfg)
    assert r["status"]=="SKIPPED_PRE_BOUNDARY"

def test_first_snapshot_is_immutable(tmp_path):
    _write_inputs(tmp_path,available=4)
    cfg=CapacityAwareShadowConfig(project_root=str(tmp_path))
    freeze_protocol(cfg)
    a=record_snapshot(cfg);b=record_snapshot(cfg)
    assert a["status"]=="RECORDED"
    assert b["status"]=="ALREADY_RECORDED_IMMUTABLE"

def test_evaluate_without_maturity_accumulates(tmp_path):
    cfg=CapacityAwareShadowConfig(project_root=str(tmp_path))
    freeze_protocol(cfg)
    e=evaluate(cfg)
    assert e["certification_verdict"]=="NOT_ENOUGH_PROSPECTIVE_EVIDENCE"
    assert e["production_authority_effect"] is False

def test_protocol_never_changes_production():
    p=_protocol_payload()
    assert p["production_capital_allocation_effect"] is False
    assert p["automatic_retraining"] is False


def test_cpre_binding_preserves_frozen_ranked_cohort(tmp_path, monkeypatch):
    import trading_ai.research.m77.capacity_aware_capital_allocation_shadow as m
    root=Path(tmp_path)
    cpre_dir=root/"data/cross_sectional_capital_priority_shadow/snapshots"
    cpre_dir.mkdir(parents=True,exist_ok=True)
    cpre={
        "protocol_id":"CPRE-CANDIDATE-001",
        "population":"TRADE_BUILDER_READY_LONG_AND_DRVE_PASS",
        "ranker":"PROBABILITY_UP_DESCENDING",
        "immutable_first_snapshot_per_market_date":True,
        "market_as_of_date":"2026-08-28",
        "stock_scanner_run_id":"stock-scan-cpre",
        "source_model_fingerprint":"abc",
        "frozen_at":"2026-08-28T14:21:18+00:00",
        "records":[
            {"symbol":"AIZ","probability_up":.605,"probability_up_rank":1,"selected_top3":True},
            {"symbol":"MMM","probability_up":.604,"probability_up_rank":2,"selected_top3":True},
            {"symbol":"ELV","probability_up":.589,"probability_up_rank":3,"selected_top3":True},
            {"symbol":"AMGN","probability_up":.588,"probability_up_rank":4,"selected_top3":False},
        ],
    }
    (cpre_dir/"2026-08-28.json").write_text(json.dumps(cpre))
    monkeypatch.setattr(m,"_latest_ready_portfolio_allocation",lambda portfolio_id:{
        "publication_id":"PUB-1","publication_name":"current_portfolio_allocation",
        "portfolio_id":"PAPER-PRIMARY","risk_snapshot_id":"RISK-1",
        "optimization_snapshot_id":"OPT-1","published_at":"2026-08-28T20:56:44+00:00",
        "status":"READY","payload_json":{
            "policy_version":"M64.TEST","resolved_optimizer_policy":{"max_new_positions":100,"max_new_positions_source":"test"},
            "objective":{"selected_count":4,"rejected_count":2},
            "target_portfolio":{"selected_opportunity_count":4},
            "optimization_proof":{"selected_count":4,"optimality_proven":True},
            "risk_budgets":{"portfolio":{"net_liquidation":1000000,"new_capital_limit":50000,"new_capital_remaining":45000,"portfolio_heat_pct":4,"portfolio_heat_limit_pct":20,"buying_power":3000000},"limits":{"symbol_pct":10}},
            "current_portfolio":{"capital_committed":70000},
        }
    })
    cfg=m.CapacityAwareShadowConfig(project_root=str(root),auto_bind_live_authority=True)
    m.freeze_protocol(cfg)
    out=m.record_snapshot(cfg)
    assert out["status"]=="RECORDED"
    assert out["challenger_selected"]==4
    snap=json.loads((root/"data/capacity_aware_capital_allocation_shadow/snapshots/2026-08-28.json").read_text())
    assert [r["symbol"] for r in snap["eligible_ranked_cohort"]]==["AIZ","MMM","ELV","AMGN"]
    assert snap["authority_binding"]["candidate_authority_run_id"]=="stock-scan-cpre"
    assert snap["authority_binding"]["capacity_publication_id"]=="PUB-1"
    assert snap["capacity_authority"]["capacity_measure"]=="M64_EXACT_OPTIMIZER_FEASIBLE_SELECTED_COUNT_SLOT_EQUIVALENT"
    assert snap["capacity_authority"]["new_capital_remaining"]==45000
    assert snap["capacity_authority"]["candidate_and_capacity_scanner_run_equality_required"] is False


def test_capacity_binding_rejects_different_market_date():
    import trading_ai.research.m77.capacity_aware_capital_allocation_shadow as m
    row={
        "publication_id":"PUB-X","publication_name":"current_portfolio_allocation","portfolio_id":"PAPER-PRIMARY",
        "risk_snapshot_id":"R","optimization_snapshot_id":"O","published_at":"2026-08-27T20:00:00+00:00",
        "payload_json":{"objective":{"selected_count":1},"optimization_proof":{"selected_count":1},"target_portfolio":{"selected_opportunity_count":1}}
    }
    try:
        m._capacity_from_publication(row,"2026-08-28")
    except m.CapacityAwareShadowError as exc:
        assert "market-date mismatch" in str(exc)
    else:
        raise AssertionError("expected fail-closed market-date mismatch")


def test_frozen_protocol_payload_unchanged_by_binding_patch():
    p=_protocol_payload()
    assert p["version"]=="M77.40.0-FROZEN-PROSPECTIVE-CAPACITY-AWARE-CAPITAL-ALLOCATION-SHADOW-1.0"
    assert p["protocol_id"]==PROTOCOL_ID
