import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.management_geometry_prospective_shadow import (
    FROZEN_GATES,
    ManagementShadowConfig,
    _atr14_at_market_date,
    _mature_one,
    evaluate_prospective,
    record_shadow_snapshot,
    write_frozen_protocol,
)


def _authority(day="2026-08-27"):
    records={}
    for i in range(12):
        records[f"S{i:02d}"]={
            "probability_up":0.5+i/100,
            "cross_section_rank":i+1,
            "cross_section_percentile":(i+1)/12,
            "veto":False,
            "trade_builder_ready_long":True,
        }
    records["VETO"]={"probability_up":0.1,"veto":True,"trade_builder_ready_long":True}
    records["NOTREADY"]={"probability_up":0.9,"veto":False,"trade_builder_ready_long":False}
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


def test_atr_is_point_in_time_and_positive():
    h=_history(periods=80)
    d=h.iloc[-1]["session_date"]
    atr=_atr14_at_market_date(h,d)
    assert atr is not None and atr>0


def test_snapshot_freezes_only_trade_builder_ready_drv_pass(monkeypatch,tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority()))

    history={}
    for i in range(12):
        h=_history(periods=120)
        # Make exact prospective market date exist.
        shift=(pd.Timestamp("2026-08-27")-pd.Timestamp(h.iloc[-1]["session_date"])).days
        h["session_date"]=[(pd.Timestamp(d)+pd.Timedelta(days=shift)).date() for d in h["session_date"]]
        history[f"S{i:02d}"]=h
    monkeypatch.setattr(
        "trading_ai.research.m77.management_geometry_prospective_shadow._load_ohlc",
        lambda *args,**kwargs:history,
    )
    r=record_shadow_snapshot(ManagementShadowConfig(project_root=str(tmp_path)))
    assert r["status"]=="FROZEN"
    assert r["candidate_count"]==12
    assert r["atr_ready_count"]==12
    snap=json.loads((tmp_path/"data/management_geometry_shadow/snapshots/2026-08-27.json").read_text())
    assert len(snap["records"])==12
    assert all(x["candidate_atr"]>0 for x in snap["records"])


def test_first_snapshot_per_market_date_is_immutable(monkeypatch,tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority()))
    h=_history(periods=120)
    shift=(pd.Timestamp("2026-08-27")-pd.Timestamp(h.iloc[-1]["session_date"])).days
    h["session_date"]=[(pd.Timestamp(d)+pd.Timedelta(days=shift)).date() for d in h["session_date"]]
    monkeypatch.setattr(
        "trading_ai.research.m77.management_geometry_prospective_shadow._load_ohlc",
        lambda *args,**kwargs:{f"S{i:02d}":h for i in range(12)},
    )
    first=record_shadow_snapshot(ManagementShadowConfig(project_root=str(tmp_path)))
    a=_authority();a["stock_scanner_run_id"]="run-2";p.write_text(json.dumps(a))
    second=record_shadow_snapshot(ManagementShadowConfig(project_root=str(tmp_path)))
    assert first["status"]=="FROZEN"
    assert second["status"]=="ALREADY_FROZEN"
    assert second["stock_scanner_run_id"]=="run-1"


def test_pre_boundary_is_not_recorded(tmp_path):
    p=tmp_path/"data/downside_risk_veto/current_authority.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_authority("2026-08-26")))
    r=record_shadow_snapshot(ManagementShadowConfig(project_root=str(tmp_path)))
    assert r["status"]=="SKIPPED_PRE_BOUNDARY"


def test_mature_one_uses_next_open_and_frozen_5_by_3_geometry():
    h=_history(periods=100)
    asof=h.iloc[10]["session_date"]
    rec={"candidate_atr":2.0}
    out=_mature_one(rec,asof,h)
    assert out is not None
    assert out["entry_date"]==h.iloc[11]["session_date"].isoformat()
    assert abs(out["target_price"]-(h.iloc[11]["open"]+10.0))<1e-12
    assert abs(out["stop_price"]-(h.iloc[11]["open"]-6.0))<1e-12


def test_frozen_protocol_refuses_semantic_change(tmp_path):
    path=write_frozen_protocol(tmp_path)
    payload=json.loads(path.read_text())
    assert payload["target_atr"]==5.0
    assert payload["stop_atr"]==3.0
    payload["target_atr"]=4.0
    path.write_text(json.dumps(payload))
    with pytest.raises(Exception):
        write_frozen_protocol(tmp_path)


def test_empty_evaluation_accumulates(tmp_path):
    r=evaluate_prospective(ManagementShadowConfig(project_root=str(tmp_path)))
    assert r["certification_verdict"]=="NOT_ENOUGH_PROSPECTIVE_EVIDENCE"
    assert r["matured_observations"]==0
    assert FROZEN_GATES["minimum_matured_observations"]==300


def test_ingestion_hook_is_shadow_only():
    root=Path(__file__).resolve().parents[3]
    src=(root/"scripts/ingest_options_data.py").read_text()
    assert "management_geometry_prospective_shadow" in src
    assert "management_geometry_shadow_warning" in src
    assert "record_management_geometry_shadow" in src
