import json
from pathlib import Path

import pandas as pd

from trading_ai.research.m77.positive_selection_prospective_shadow import (
    FROZEN_GATES,
    PROSPECTIVE_NOT_BEFORE,
    ShadowConfig,
    _freeze_cross_section,
    evaluate_prospective,
    record_shadow_snapshot,
    write_frozen_protocol,
)


def _authority(day="2026-08-27"):
    records={}
    for i in range(20):
        records[f"S{i:02d}"]={
            "probability_up":0.50+i/100,
            "cross_section_percentile":0.5,
            "cross_section_rank":i+1,
            "veto":False,
            "trade_builder_ready_long":True,
        }
    records["VETO"]={"probability_up":.1,"veto":True,"trade_builder_ready_long":True}
    records["NOTREADY"]={"probability_up":.99,"veto":False,"trade_builder_ready_long":False}
    return {
        "feature_parity_valid":True,
        "production_scope":"TRADE_BUILDER_READY_LONG_ONLY",
        "market_as_of_date":day,
        "stock_scanner_run_id":"run-1",
        "generated_at":"2026-08-27T20:00:00+00:00",
        "model_fingerprint":"abc",
        "records":records,
    }


def test_freeze_cross_section_selects_top10_after_drv_pass():
    rows=_freeze_cross_section(_authority())
    assert len(rows)==20
    assert sum(bool(x["selected_top10"]) for x in rows)==2
    assert rows[0]["symbol"]=="S19"


def test_record_snapshot_freezes_top10_and_excludes_veto(tmp_path):
    root=tmp_path
    p=root/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority()))
    result=record_shadow_snapshot(ShadowConfig(project_root=str(root)))
    assert result["status"]=="FROZEN"
    assert result["candidate_count"]==20
    assert result["selected_count"]==2
    snap=json.loads((root/"data/positive_selection_shadow/snapshots/2026-08-27.json").read_text())
    assert sum(bool(x["selected_top10"]) for x in snap["records"])==2
    assert all(x["symbol"]!="VETO" for x in snap["records"])


def test_first_snapshot_per_date_is_immutable(tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    a=_authority()
    p.write_text(json.dumps(a))
    first=record_shadow_snapshot(ShadowConfig(project_root=str(tmp_path)))
    a["stock_scanner_run_id"]="run-2"
    a["records"]["S00"]["probability_up"]=.999
    p.write_text(json.dumps(a))
    second=record_shadow_snapshot(ShadowConfig(project_root=str(tmp_path)))
    assert first["status"]=="FROZEN"
    assert second["status"]=="ALREADY_FROZEN"
    assert second["stock_scanner_run_id"]=="run-1"


def test_pre_boundary_is_not_recorded(tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority("2026-08-26")))
    r=record_shadow_snapshot(ShadowConfig(project_root=str(tmp_path)))
    assert r["status"]=="SKIPPED_PRE_BOUNDARY"
    assert not (tmp_path/"data/positive_selection_shadow/snapshots/2026-08-26.json").exists()


def test_frozen_protocol_refuses_semantic_replacement(tmp_path):
    path=write_frozen_protocol(tmp_path)
    payload=json.loads(path.read_text())
    assert payload["top_fraction"]==0.10
    assert payload["horizon_sessions"]==60
    payload["top_fraction"]=0.20
    path.write_text(json.dumps(payload))
    import pytest
    with pytest.raises(Exception):
        write_frozen_protocol(tmp_path)


def test_evaluate_requires_minimum_prospective_evidence(tmp_path):
    result=evaluate_prospective(ShadowConfig(project_root=str(tmp_path)))
    assert result["certification_verdict"]=="NOT_ENOUGH_PROSPECTIVE_EVIDENCE"
    assert result["matured_selected_observations"]==0
    assert FROZEN_GATES["minimum_selected_observations"]==300


def test_ingestion_hook_is_shadow_only():
    root=Path(__file__).resolve().parents[3]
    src=(root/"scripts/ingest_options_data.py").read_text()
    assert "positive_selection_prospective_shadow" in src
    assert "positive_selection_shadow_warning" in src
    assert "record_shadow_snapshot" in src
