from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_16_vedic_predictive_hypotheses_ii.py"
C=ROOT/"config/m77/m77_16_vedic_predictive_hypotheses_ii.json"
def test_compile(): py_compile.compile(str(R),doraise=True)
def test_23_year_gate():
    x=json.loads(C.read_text()); assert x["authority"]["common_start"]=="2003-09-10"; assert x["authority"]["expected_common_sessions"]==5773
def test_long_history_mapping():
    x=json.loads(C.read_text()); assert x["authority"]["long_history_instruments"]["SPX"]["instrument"]=="SPY"; assert x["authority"]["long_history_instruments"]["NDX"]["instrument"]=="QQQ_LINEAGE"; assert x["authority"]["long_history_instruments"]["RUT"]["instrument"]=="IWM"
def test_canonical_rut_still_required():
    x=json.loads(C.read_text()); assert x["authority"]["canonical_recent_confirmation"]["RUT"]=="RUT"; assert "Canonical RUT" in x["authority"]["scope_note"]
def test_four_hypotheses():
    x=json.loads(C.read_text()); assert set(x["hypotheses"])=={"H1_JUPITER_RAHU_EXPANSION","H2_SOLAR_INGRESS_SANKRANTI","H3_RAHU_KETU_FINANCIAL_HOUSE_AXIS","H4_JUPITER_ATICHARI_VELOCITY"}
def test_h3_fail_closed():
    x=json.loads(C.read_text()); assert x["hypotheses"]["H3_RAHU_KETU_FINANCIAL_HOUSE_AXIS"]["status"]=="BLOCKED_PENDING_MARKET_CHART_AUTHORITY"
def test_no_prod():
    x=R.read_text(); assert "SessionLocal" not in x; assert "from trading_ai.database" not in x; assert '"production_authority_effect":False' in x
