from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_6_5_2_source_anomaly_quarantine_recertification.py"
C=ROOT/"config/m77/m77_15_6_5_2_source_anomaly_quarantine.json"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_frozen_source_anomaly():
    x=json.loads(C.read_text())
    q=x["frozen_quarantine"]
    assert len(q)==1
    assert q[0]["date"]=="2004-07-28"
    assert q[0]["source_ticker"]=="QQQ"
    assert q[0]["reason"]=="SOURCE_OHLC_INVALID_LOW_ZERO"
    assert q[0]["source_low"]==0.0

def test_no_imputation_or_mutation():
    x=json.loads(C.read_text())
    p=x["quarantine_policy"]
    assert p["source_values_mutated"] is False
    assert p["raw_source_mutated"] is False
    assert p["lineage_mutated"] is False
    assert p["price_imputation"] is False
    assert p["quarantined_session_removed_from_all_common_authority_targets"] is True

def test_cross_target_session_quarantine():
    x=R.read_text()
    assert "cert_dates=[d for d in common if d not in quarantine_dates]" in x
    assert "CONFIRMED_POLYGON_SOURCE_OHLC_ANOMALY_NOT_LINEAGE_STITCH_DEFECT" in x

def test_isolation():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"production_price_history_writes":False' in x
    assert '"production_authority_effect":False' in x
