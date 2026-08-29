import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.candidate_quality_management_interaction_prospective_shadow import (
    FROZEN_GATES,
    InteractionShadowConfig,
    _eligible_ranked,
    _mature_one,
    evaluate_prospective,
    record_shadow_snapshot,
    write_frozen_protocol,
)


def _authority(day="2026-08-27"):
    records={}
    for i in range(20):
        records[f"S{i:02d}"]={
            "probability_up":0.50+i/100,
            "cross_section_rank":i+1,
            "cross_section_percentile":(i+1)/20,
            "veto":False,
            "trade_builder_ready_long":True,
        }
    records["VETO"]={"probability_up":0.1,"veto":True,"trade_builder_ready_long":True}
    records["NOTREADY"]={"probability_up":0.99,"veto":False,"trade_builder_ready_long":False}
    return {
        "feature_parity_valid":True,
        "production_scope":"TRADE_BUILDER_READY_LONG_ONLY",
        "market_as_of_date":day,
        "stock_scanner_run_id":"run-1",
        "generated_at":"2026-08-27T20:00:00+00:00",
        "model_fingerprint":"abc",
        "records":records,
    }


def _history(start="2026-01-02", periods=180):
    dates=pd.bdate_range(start,periods=periods)
    close=np.linspace(100,120,periods)
    return pd.DataFrame({
        "session_date":[x.date() for x in dates],
        "open":close-.1,
        "high":close+1.0,
        "low":close-1.0,
        "close":close,
    })


def test_ranked_selector_is_exact_top20_of_drv_pass_population():
    rows,n=_eligible_ranked(_authority())
    assert len(rows)==20
    assert n==4
    selected=[x for x in rows if x["selected_top20"]]
    assert len(selected)==4
    assert selected[0]["symbol"]=="S19"
    assert selected[-1]["symbol"]=="S16"


def test_snapshot_freezes_top20_and_atr(monkeypatch,tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority()))
    h=_history(periods=120)
    shift=(pd.Timestamp("2026-08-27")-pd.Timestamp(h.iloc[-1]["session_date"])).days
    h["session_date"]=[(pd.Timestamp(d)+pd.Timedelta(days=shift)).date() for d in h["session_date"]]
    monkeypatch.setattr(
        "trading_ai.research.m77.candidate_quality_management_interaction_prospective_shadow._load_ohlc",
        lambda *args,**kwargs:{f"S{i:02d}":h for i in range(16,20)},
    )
    r=record_shadow_snapshot(InteractionShadowConfig(project_root=str(tmp_path)))
    assert r["status"]=="FROZEN"
    assert r["eligible_count"]==20
    assert r["selected_count"]==4
    assert r["atr_ready_count"]==4
    snap=json.loads((tmp_path/"data/candidate_quality_management_interaction_shadow/snapshots/2026-08-27.json").read_text())
    assert {x["symbol"] for x in snap["records"]}=={"S16","S17","S18","S19"}


def test_first_snapshot_is_immutable(monkeypatch,tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority()))
    h=_history(periods=120)
    shift=(pd.Timestamp("2026-08-27")-pd.Timestamp(h.iloc[-1]["session_date"])).days
    h["session_date"]=[(pd.Timestamp(d)+pd.Timedelta(days=shift)).date() for d in h["session_date"]]
    monkeypatch.setattr(
        "trading_ai.research.m77.candidate_quality_management_interaction_prospective_shadow._load_ohlc",
        lambda *args,**kwargs:{f"S{i:02d}":h for i in range(16,20)},
    )
    first=record_shadow_snapshot(InteractionShadowConfig(project_root=str(tmp_path)))
    a=_authority();a["stock_scanner_run_id"]="run-2";p.write_text(json.dumps(a))
    second=record_shadow_snapshot(InteractionShadowConfig(project_root=str(tmp_path)))
    assert first["status"]=="FROZEN"
    assert second["status"]=="ALREADY_FROZEN"
    assert second["stock_scanner_run_id"]=="run-1"


def test_pre_boundary_not_recorded(tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority("2026-08-26")))
    r=record_shadow_snapshot(InteractionShadowConfig(project_root=str(tmp_path)))
    assert r["status"]=="SKIPPED_PRE_BOUNDARY"


def test_mature_one_reuses_5_by_3_by_60_executable_semantics():
    h=_history(periods=100)
    asof=h.iloc[10]["session_date"]
    out=_mature_one({"candidate_atr":2.0},asof,h)
    assert out is not None
    assert out["entry_date"]==h.iloc[11]["session_date"].isoformat()
    assert abs(out["target_price"]-(h.iloc[11]["open"]+10.0))<1e-12
    assert abs(out["stop_price"]-(h.iloc[11]["open"]-6.0))<1e-12


def test_frozen_protocol_refuses_selector_change(tmp_path):
    path=write_frozen_protocol(tmp_path)
    payload=json.loads(path.read_text())
    assert payload["top_fraction"]==0.20
    assert payload["target_atr"]==5.0
    assert payload["stop_atr"]==3.0
    payload["top_fraction"]=0.10
    path.write_text(json.dumps(payload))
    with pytest.raises(Exception):
        write_frozen_protocol(tmp_path)


def test_empty_evaluation_accumulates(tmp_path):
    r=evaluate_prospective(InteractionShadowConfig(project_root=str(tmp_path)))
    assert r["certification_verdict"]=="NOT_ENOUGH_PROSPECTIVE_EVIDENCE"
    assert r["matured_observations"]==0
    assert FROZEN_GATES["minimum_matured_observations"]==250


def test_ingestion_hook_preserves_parent_shadows():
    root=Path(__file__).resolve().parents[3]
    src=(root/"scripts/ingest_options_data.py").read_text()
    assert "positive_selection_prospective_shadow" in src
    assert "management_geometry_prospective_shadow" in src
    assert "candidate_quality_management_interaction_prospective_shadow" in src
    assert "candidate_quality_management_interaction_shadow_warning" in src
