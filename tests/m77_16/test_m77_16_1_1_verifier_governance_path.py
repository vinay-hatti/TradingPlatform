from pathlib import Path
import json,py_compile

ROOT=Path(__file__).resolve().parents[2]
C=ROOT/"config/m77/m77_16_1_mundane_market_chart_authority.json"

def test_config_governance_path():
    x=json.loads(C.read_text())
    assert x["governance"]["production_authority_effect"] is False
    assert x["governance"]["database_writes"] is False

def test_authority_script_compile():
    p=ROOT/"scripts/run_m77_16_1_mundane_market_chart_authority.py"
    py_compile.compile(str(p),doraise=True)
