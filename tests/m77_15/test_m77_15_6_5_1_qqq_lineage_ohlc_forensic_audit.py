from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_6_5_1_qqq_lineage_ohlc_forensic_audit.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_diagnostic_only():
    x=R.read_text()
    assert '"diagnostic_only":True' in x
    assert '"automatic_repair":False' in x
    assert '"source_value_mutation":False' in x
    assert '"lineage_mutation":False' in x
    assert '"production_authority_effect":False' in x

def test_source_and_neighbor_evidence():
    x=R.read_text()
    assert "neighbors" in x
    assert 'for sym in ("QQQ","QQQQ")' in x
    assert "matching_violation_dates" in x
