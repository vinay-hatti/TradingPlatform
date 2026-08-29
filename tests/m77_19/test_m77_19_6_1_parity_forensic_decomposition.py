from pathlib import Path
import json,py_compile
R=Path("scripts/run_m77_19_6_1_parity_forensic_decomposition.py")
C=Path("config/m77/m77_19_6_1_parity_forensic_decomposition.json")
def test_compile(): py_compile.compile(str(R),doraise=True)
def test_read_only():
 x=json.loads(C.read_text())["governance"]
 assert x["database_read_only"] is True
 assert x["database_writes"] is False
 assert x["production_price_history_writes"] is False
 assert x["full_long_history_reconstruction"] is False
def test_forensic_dimensions():
 x=json.loads(C.read_text())["forensic_dimensions"]
 assert "STATE_HASH_NONDETERMINISM" in x
 assert "OHLCV_INPUT_PARITY" in x
 assert "EXTERNAL_CONTEXT_DEPENDENCY" in x
