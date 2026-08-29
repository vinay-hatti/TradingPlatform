from pathlib import Path
import json,py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_6_4_polygon_coverage_symbol_lineage_resolution.py"
C=ROOT/"config/m77/m77_15_6_4_polygon_coverage_lineage.json"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_qqq_lineage_is_frozen():
    x=json.loads(C.read_text())
    seg=x["diagnostic_scope"]["QQQ"]["expected_segments"]
    assert seg[0]["ticker"]=="QQQ"
    assert seg[1]["ticker"]=="QQQQ"
    assert seg[1]["from"]=="2004-12-01"
    assert seg[1]["through"]=="2011-03-22"
    assert seg[2]["ticker"]=="QQQ"
    assert seg[2]["from"]=="2011-03-23"

def test_iwm_inception_reference_is_frozen():
    x=json.loads(C.read_text())
    assert x["diagnostic_scope"]["IWM"]["known_fund_inception_date"]=="2000-05-22"

def test_diagnostic_only():
    x=R.read_text()
    assert '"diagnostic_only":True' in x
    assert '"canonical_authorities_mutated":False' in x
    assert '"production_price_history_writes":False' in x
    assert '"production_authority_effect":False' in x

def test_qqq_stitch_is_deterministic():
    x=R.read_text()
    assert 'd <= "2004-11-30"' in x
    assert 'd <= "2011-03-22"' in x
    assert 'src="QQQQ"' in x

def test_no_threshold_relaxation():
    x=R.read_text()
    assert '"no_threshold_relaxation":True' in x
