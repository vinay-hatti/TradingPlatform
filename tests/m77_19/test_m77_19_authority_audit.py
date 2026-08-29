from pathlib import Path
import json,py_compile
R=Path("scripts/run_m77_19_multi_cadence_long_history_authority_audit.py")
C=Path("config/m77/m77_19_multi_cadence_authority_audit.json")
def test_compile():py_compile.compile(str(R),doraise=True)
def test_governance():
 x=json.loads(C.read_text());assert x["long_history"]["sessions"]==5773;assert "NO_FABRICATED_HISTORICAL_PIT_REGIMES" in x["prohibitions"];assert x["governance"]["read_only"] is True
