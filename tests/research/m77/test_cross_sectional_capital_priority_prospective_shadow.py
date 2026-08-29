import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.cross_sectional_capital_priority_prospective_shadow import (
    FROZEN_GATES,
    CapitalPriorityShadowConfig,
    _eligible_ranked,
    _same_day_uplift,
    evaluate_prospective,
    record_shadow_snapshot,
    write_frozen_protocol,
)

def _authority(day="2026-08-27"):
    records={}
    for i in range(10):
        records[f"S{i:02d}"]={
            "probability_up":0.50+i/100,
            "cross_section_rank":i+1,
            "cross_section_percentile":(i+1)/10,
            "veto":False,
            "trade_builder_ready_long":True,
        }
    records["VETO"]={"probability_up":0.99,"veto":True,"trade_builder_ready_long":True}
    records["NOTREADY"]={"probability_up":1.00,"veto":False,"trade_builder_ready_long":False}
    return {
        "feature_parity_valid":True,
        "production_scope":"TRADE_BUILDER_READY_LONG_ONLY",
        "market_as_of_date":day,
        "stock_scanner_run_id":"run-1",
        "generated_at":"2026-08-27T20:00:00+00:00",
        "model_fingerprint":"abc",
        "records":records,
    }

def _history(start="2026-01-02",periods=180):
    dates=pd.bdate_range(start,periods=periods)
    close=np.linspace(100,120,periods)
    return pd.DataFrame({
        "session_date":[x.date() for x in dates],
        "open":close-.1,"high":close+1.0,"low":close-1.0,"close":close,
    })

def test_ranker_freezes_top3_and_full_complement():
    rows=_eligible_ranked(_authority())
    assert len(rows)==10
    selected=[r for r in rows if r["selected_top3"]]
    assert [r["symbol"] for r in selected]==["S09","S08","S07"]
    assert [r["probability_up_rank"] for r in selected]==[1,2,3]
    assert sum(not r["selected_top3"] for r in rows)==7

def test_snapshot_contains_entire_ranked_cohort(monkeypatch,tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority()))
    h=_history(periods=120)
    shift=(pd.Timestamp("2026-08-27")-pd.Timestamp(h.iloc[-1]["session_date"])).days
    h["session_date"]=[(pd.Timestamp(d)+pd.Timedelta(days=shift)).date() for d in h["session_date"]]
    monkeypatch.setattr(
        "trading_ai.research.m77.cross_sectional_capital_priority_prospective_shadow._load_ohlc",
        lambda *args,**kwargs:{f"S{i:02d}":h for i in range(10)},
    )
    r=record_shadow_snapshot(CapitalPriorityShadowConfig(project_root=str(tmp_path)))
    assert r["status"]=="FROZEN"
    assert r["eligible_count"]==10
    assert r["selected_count"]==3
    assert r["atr_ready_count"]==10
    snap=json.loads((tmp_path/"data/cross_sectional_capital_priority_shadow/snapshots/2026-08-27.json").read_text())
    assert len(snap["records"])==10
    assert sum(x["selected_top3"] for x in snap["records"])==3

def test_snapshot_is_immutable(monkeypatch,tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority()))
    h=_history(periods=120)
    shift=(pd.Timestamp("2026-08-27")-pd.Timestamp(h.iloc[-1]["session_date"])).days
    h["session_date"]=[(pd.Timestamp(d)+pd.Timedelta(days=shift)).date() for d in h["session_date"]]
    monkeypatch.setattr(
        "trading_ai.research.m77.cross_sectional_capital_priority_prospective_shadow._load_ohlc",
        lambda *args,**kwargs:{f"S{i:02d}":h for i in range(10)},
    )
    first=record_shadow_snapshot(CapitalPriorityShadowConfig(project_root=str(tmp_path)))
    a=_authority(); a["stock_scanner_run_id"]="run-2"; p.write_text(json.dumps(a))
    second=record_shadow_snapshot(CapitalPriorityShadowConfig(project_root=str(tmp_path)))
    assert first["status"]=="FROZEN"
    assert second["status"]=="ALREADY_FROZEN"
    assert second["stock_scanner_run_id"]=="run-1"

def test_pre_boundary_is_skipped(tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority("2026-08-26")))
    r=record_shadow_snapshot(CapitalPriorityShadowConfig(project_root=str(tmp_path)))
    assert r["status"]=="SKIPPED_PRE_BOUNDARY"

def test_same_day_uplift_uses_selected_vs_rank4plus():
    f=pd.DataFrame({
        "market_as_of_date":pd.to_datetime(["2026-08-27"]*6+["2026-08-28"]*6),
        "selected_top3":[True,True,True,False,False,False]*2,
        "r_multiple":[.4,.3,.2,.1,.0,-.1,.6,.5,.4,.2,.1,.0],
    })
    u=_same_day_uplift(f)
    assert u["dates"]==2
    assert u["equal_date_mean_uplift_r"]>0
    assert u["matched_size_weighted_mean_uplift_r"]>0

def test_frozen_protocol_refuses_topk_change(tmp_path):
    path=write_frozen_protocol(tmp_path)
    payload=json.loads(path.read_text())
    assert payload["top_k"]==3
    assert payload["snapshot_full_eligible_ranked_cohort"] is True
    payload["top_k"]=5
    path.write_text(json.dumps(payload))
    with pytest.raises(Exception):
        write_frozen_protocol(tmp_path)

def test_empty_evaluation_accumulates(tmp_path):
    r=evaluate_prospective(CapitalPriorityShadowConfig(project_root=str(tmp_path)))
    assert r["certification_verdict"]=="NOT_ENOUGH_PROSPECTIVE_EVIDENCE"
    assert r["matured_selected_observations"]==0
    assert FROZEN_GATES["minimum_matured_selected_observations"]==250


def test_ingestion_hook_preserves_existing_shadows_and_adds_cpre():
    root=Path(__file__).resolve().parents[3]
    src=(root/"scripts/ingest_options_data.py").read_text()
    assert "positive_selection_prospective_shadow" in src
    assert "management_geometry_prospective_shadow" in src
    assert "candidate_quality_management_interaction_prospective_shadow" in src
    assert "cross_sectional_capital_priority_prospective_shadow" in src
    assert "cross_sectional_capital_priority_shadow_warning" in src
