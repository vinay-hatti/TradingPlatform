from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from trading_ai.downside_risk_veto.live_authority import select_bottom_tail
from trading_ai.downside_risk_veto.service import (
    CHAMPION_ID,
    REASON_AUTH_MISSING,
    REASON_NON_LONG,
    REASON_PASS,
    REASON_VETO,
    DownsideRiskVetoService,
)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def champion(root: Path, fingerprint="fp-1"):
    p=root/'data/downside_risk_veto/champion/DRVE-CHAMPION-001.json'
    write_json(p,{'champion_id':CHAMPION_ID,'final_holdout_certified':True,'model_fingerprint':fingerprint})
    return p


def authority(root: Path, *, veto: bool, fingerprint="fp-1", run="RUN-1"):
    p=root/'data/downside_risk_veto/current_authority.json'
    write_json(p,{
        'champion_id':CHAMPION_ID,'model_fingerprint':fingerprint,'feature_parity_valid':True,
        'generated_at':datetime.now(timezone.utc).isoformat(),'stock_scanner_run_id':run,
        'records':{'ABC':{'probability_up':0.04,'cross_section_percentile':0.005,'veto':veto}},
        'certification_evidence':{'severe_loss_capture_lift_vs_random':3.9042586750788644},
    })
    return p


def test_non_long_is_not_applicable_even_in_enforce(tmp_path):
    d=DownsideRiskVetoService(project_root=tmp_path,mode='ENFORCE').evaluate(symbol='ABC',direction='BEARISH',stock_scanner_run_id='RUN-1',trade_builder_ready=True)
    assert d.authorized is True and d.blocked is False and d.applicable is False
    assert REASON_NON_LONG in d.reason_codes


def test_enforce_missing_authority_fails_closed(tmp_path):
    d=DownsideRiskVetoService(project_root=tmp_path,mode='ENFORCE').evaluate(symbol='ABC',direction='BULLISH',stock_scanner_run_id='RUN-1',trade_builder_ready=True)
    assert d.blocked is True and d.authorized is False
    assert REASON_AUTH_MISSING in d.reason_codes


def test_enforce_veto_blocks_exact_symbol(tmp_path):
    champion(tmp_path);authority(tmp_path,veto=True)
    d=DownsideRiskVetoService(project_root=tmp_path,mode='ENFORCE').evaluate(symbol='ABC',direction='BULLISH',stock_scanner_run_id='RUN-1',trade_builder_ready=True)
    assert d.blocked is True and REASON_VETO in d.reason_codes
    assert d.cross_section_percentile == 0.005


def test_enforce_pass_allows_exact_symbol(tmp_path):
    champion(tmp_path);authority(tmp_path,veto=False)
    d=DownsideRiskVetoService(project_root=tmp_path,mode='ENFORCE').evaluate(symbol='ABC',direction='BULLISH',stock_scanner_run_id='RUN-1',trade_builder_ready=True)
    assert d.blocked is False and d.authorized is True and REASON_PASS in d.reason_codes


def test_shadow_reports_veto_without_blocking(tmp_path):
    champion(tmp_path);authority(tmp_path,veto=True)
    d=DownsideRiskVetoService(project_root=tmp_path,mode='SHADOW').evaluate(symbol='ABC',direction='BULLISH',stock_scanner_run_id='RUN-1',trade_builder_ready=True)
    assert d.status == 'SHADOW_VETO' and d.blocked is False and d.authorized is True


def test_bottom_one_percent_membership_is_deterministic():
    df=pd.DataFrame({'symbol':[f'S{i:03d}' for i in range(250)],'probability_up':[i/250 for i in range(250)]})
    out=select_bottom_tail(df,0.01)
    assert int(out.veto.sum()) == 3
    assert out.loc[out.veto,'symbol'].tolist() == ['S000','S001','S002']


def test_production_integration_source_contracts_present():
    root=Path(__file__).resolve().parents[3]
    handoff=(root/'src/trading_ai/institutional_options/handoff.py').read_text()
    router=(root/'src/trading_ai/institutional_options/router.py').read_text()
    ui=(root/'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    ingestion=(root/'scripts/ingest_options_data.py').read_text()
    assert 'DownsideRiskVetoService().evaluate' in handoff
    assert 'DRV' in (root/'src/trading_ai/downside_risk_veto/service.py').read_text()
    assert 'payload["downside_risk_veto"]' in router
    assert 'Downside risk veto' in ui
    assert 'refresh_live_authority' in ingestion


def test_final_holdout_certification_identity_is_frozen():
    from trading_ai.downside_risk_veto.champion import EXPECTED_FINAL_PREREGISTRATION_SHA256
    assert EXPECTED_FINAL_PREREGISTRATION_SHA256 == '6231916aa4f7eba1eb3e038a56bb32ee67aeb84539923dd933bc51e200ac0568'


def test_polygon_daily_microstructure_extracts_exact_vwap_and_transactions(monkeypatch):
    import sys, types
    import trading_ai.downside_risk_veto.live_authority as mod

    class Agg:
        ticker="ABC"
        vwap=123.45
        transactions=6789

    class Client:
        def __init__(self, **kwargs): pass
        def get_grouped_daily_aggs(self, **kwargs):
            assert kwargs["date"]=="2026-08-21"
            assert kwargs["adjusted"] is True
            return [Agg()]
        def close(self): pass

    fake=types.SimpleNamespace(RESTClient=Client)
    monkeypatch.setitem(sys.modules,"polygon",fake)

    monkeypatch.setenv("POLYGON_API_KEY","test-key")

    rows,meta=mod._polygon_daily_microstructure("2026-08-21",["ABC"])
    assert rows["ABC"]["vwap"]==123.45
    assert rows["ABC"]["transactions"]==6789.0
    assert meta["called"] is True
    assert meta["matched_symbols"]==1
    assert meta["vwap_present"]==1
    assert meta["transactions_present"]==1


def test_polygon_daily_microstructure_normalizes_dot_dash_ticker(monkeypatch):
    import sys, types
    import trading_ai.downside_risk_veto.live_authority as mod

    class Agg:
        ticker="BRK.B"
        vwap=400.0
        transactions=1000

    class Client:
        def __init__(self, **kwargs): pass
        def get_grouped_daily_aggs(self, **kwargs): return [Agg()]
        def close(self): pass

    monkeypatch.setitem(sys.modules,"polygon",types.SimpleNamespace(RESTClient=Client))
    monkeypatch.setenv("POLYGON_API_KEY","test-key")

    rows,meta=mod._polygon_daily_microstructure("2026-08-21",["BRK-B"])
    assert rows["BRK-B"]["provider_ticker"]=="BRK.B"
    assert meta["missing_symbols"]==[]


def test_live_authority_source_contract_includes_exact_polygon_microstructure_features():
    root=Path(__file__).resolve().parents[3]
    source=(root/'src/trading_ai/downside_risk_veto/live_authority.py').read_text()
    assert '_polygon_daily_microstructure' in source
    assert 'tech["vwap"]' in source
    assert 'tech["transactions"]' in source
    assert 'if sym not in microstructure' in source
    assert 'POLYGON_GROUPED_DAILY_AGGREGATES' in source
