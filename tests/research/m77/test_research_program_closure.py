
import json
from pathlib import Path
import trading_ai.research.m77.research_program_closure as m
from trading_ai.research.m77.research_program_closure import ClosureConfig, run_closure, REGISTRY

def _mk(root,base,pid):
    d=root/base
    (d/"snapshots").mkdir(parents=True,exist_ok=True)
    (d/"matured").mkdir(parents=True,exist_ok=True)
    (d/"FROZEN_PROSPECTIVE_PROTOCOL.json").write_text(json.dumps({"protocol_id":pid}))
    (d/"snapshots/2026-08-28.json").write_text("{}")

def _seed(root):
    for base,pid in [
        ("data/positive_selection_shadow","PSVE-CANDIDATE-001"),
        ("data/management_geometry_shadow","MGE-CANDIDATE-001"),
        ("data/candidate_quality_management_interaction_shadow","CQMI-CANDIDATE-001"),
        ("data/cross_sectional_capital_priority_shadow","CPRE-CANDIDATE-001"),
        ("data/capacity_aware_capital_allocation_shadow","CACA-CANDIDATE-001"),
    ]:_mk(root,base,pid)

def test_drv_is_production_certified():
    row=[r for r in REGISTRY if r[0]=="M77.23"][0]
    assert row[2]=="PRODUCTION_CERTIFIED"

def test_negative_sequence_closed():
    rejected={r[0] for r in REGISTRY if r[2]=="REJECTED_DEVELOPMENT_HYPOTHESIS"}
    for x in ("M77.31","M77.32","M77.33","M77.34","M77.35","M77.36","M77.37"):
        assert x in rejected

def test_closure_status(tmp_path,monkeypatch):
    _seed(tmp_path)
    monkeypatch.setattr(m,"_launchd",lambda:{"available":True,"healthy":True,"last_exit_code":"0"})
    r=run_closure(ClosureConfig(str(tmp_path)))
    assert r["historical_exploration_status"]=="COMPLETE"
    assert r["prospective_protocol_count"]==5
    assert r["prospective_pending_count"]==5
    assert r["overall_operational_health"]=="HEALTHY"

def test_outputs_written(tmp_path,monkeypatch):
    _seed(tmp_path)
    monkeypatch.setattr(m,"_launchd",lambda:{"available":False,"healthy":False})
    run_closure(ClosureConfig(str(tmp_path)))
    out=tmp_path/"reports/m77/m77_41_research_program_closure"
    for f in ("M77_RESEARCH_PROGRAM_STATUS.json","M77_EVIDENCE_REGISTRY.json","M77_EVIDENCE_REGISTRY.csv","M77_RESEARCH_PROGRAM_CLOSURE_REPORT.md"):
        assert (out/f).exists()

def test_governance_fail_closed(tmp_path,monkeypatch):
    _seed(tmp_path)
    monkeypatch.setattr(m,"_launchd",lambda:{"available":False,"healthy":False})
    r=run_closure(ClosureConfig(str(tmp_path)))
    assert r["automatic_production_promotion"] is False
    assert r["automatic_retraining"] is False
    assert r["new_historical_edge_discovery_permitted"] is False
