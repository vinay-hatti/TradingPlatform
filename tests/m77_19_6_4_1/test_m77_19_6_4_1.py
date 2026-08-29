import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"scripts/run_m77_19_6_4_1_replay_authority_resolution_adapter_recovery.py"
s=importlib.util.spec_from_file_location("m",P); m=importlib.util.module_from_spec(s); assert s and s.loader; s.loader.exec_module(m)

def test_cadences(): assert m.CADENCES==("DAILY","WEEKLY","MONTHLY")
def test_sample(): assert m.DEFAULT_SAMPLE_PER_CADENCE==48
def test_normalize(): assert m.normalize_cadence("1d")=="DAILY" and m.normalize_cadence("1w")=="WEEKLY" and m.normalize_cadence("1mo")=="MONTHLY"
def test_detect(): assert m.detect(["symbol","replay_date"],("ticker","symbol"))=="symbol"
def test_sha(): assert m.sha256_json({"a":1})==m.sha256_json({"a":1})
def test_name_bonus(): assert m.cadence_name_bonus("foo_m77_9_daily.json","DAILY")==100
def test_name_bonus_wrong(): assert m.cadence_name_bonus("foo_weekly.json","DAILY")==0
def test_flatten_valid_record():
    x={"symbol":"A","replay_date":"2025-01-01","direction":"BULLISH","overall_score":80,"confidence":90}
    assert len(m.flatten_records(x))==1
def test_flatten_run_metadata_not_observation():
    x={"run_id":"x","started_at":"2025-01-01","status":"READY"}
    assert m.flatten_records(x)==[]
def test_normalize_observation():
    x={"symbol":"A","replay_date":"2025-01-01","direction":"BULLISH","overall_score":80,"confidence":90}
    y=m.normalize_observation(x,"DAILY")
    assert y["symbol"]=="A" and y["frozen_output"]["overall_score"]==80
