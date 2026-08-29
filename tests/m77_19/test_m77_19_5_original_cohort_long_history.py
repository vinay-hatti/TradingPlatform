from pathlib import Path
import json,py_compile
R=Path("scripts/run_m77_19_5_original_cohort_long_history_authority.py");C=Path("config/m77/m77_19_5_original_cohort_long_history.json")
def test_compile():py_compile.compile(str(R),doraise=True)
def test_policy():
 x=json.loads(C.read_text());assert x["provider"]=="POLYGON";assert x["governance"]["database_read_only"] is True;assert x["governance"]["database_writes"] is False;assert x["governance"]["production_price_history_writes"] is False;assert "survivorship" in x["important_limitation"].lower()
