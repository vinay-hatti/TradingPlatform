from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
S=ROOT/"scripts/run_intraday_active_universe_shadow.py"

def text(): return S.read_text()

def test_shadow_contract():
    x=text()
    assert "SHADOW_INTRADAY_DECISION" in x
    assert "SHADOW_EOD_FULL_UNIVERSE_AUTHORITY" in x
    assert '"production_effect":False' in x

def test_safety_sources():
    x=text()
    for v in ("OPEN_POSITION","WORKING_ORDER_OR_EXECUTION","broker_current_positions","portfolio_positions","broker_orders","execution_intents"):
        assert v in x

def test_core_etf_policy():
    x=text()
    for sym in ("SPY","QQQ","IWM","DIA","RSP","XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY","TLT","IEF","HYG","LQD","GLD","USO","SMH","XBI","KRE","XHB"):
        assert f'"{sym}"' in x
    assert "MANDATORY_CORE_ETF_REFERENCE" in x
    assert 'if cls=="ETF"' not in x

def test_discovery_is_combination_based():
    x=text()
    assert "STOCK_INTELLIGENCE_DISCOVERY_COMBINATION" in x
    assert "MULTI_DOMAIN_DISCOVERY_COMBINATION" in x
    assert 'elif score>=60:why[sym].add("STOCK_INTELLIGENCE_DISCOVERY_SCORE")' not in x

def test_opportunity_existence_not_standalone():
    x=text()
    assert 'for sym in opp:why[sym].add("ACTIVE_INSTITUTIONAL_OPPORTUNITY")' not in x
    assert "EXISTING_INSTITUTIONAL_OPPORTUNITY_CONTEXT" in x
    assert "OBSERVE_NOT_CERTIFY" in x

def test_runners_collect_after_ingestion():
    for n in ("run_morning.sh","run_intraday.sh","run_eod.sh"):
        x=(ROOT/"scripts/m69_6_scheduled"/n).read_text()
        assert "run_intraday_active_universe_shadow.py" in x
        assert x.index("ingest_") < x.index("run_intraday_active_universe_shadow.py")

def test_shadow_script_compiles():
    import py_compile
    py_compile.compile(str(S), doraise=True)

def test_cleanup_script_packaged():
    assert (ROOT/"scripts/cleanup_intraday_shadow_pre_1_3.py").exists()
