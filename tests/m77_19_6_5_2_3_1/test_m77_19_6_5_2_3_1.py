import importlib.util, datetime as dt
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"scripts/run_m77_19_6_5_2_3_1_monthly_forensic_probe_semantic_adapter_repair.py"
s=importlib.util.spec_from_file_location("m",P); m=importlib.util.module_from_spec(s); assert s and s.loader; s.loader.exec_module(m)

class Scores:
    def __init__(self, score, primary_category):
        self.score=score; self.primary_category=primary_category
class Profile:
    def __init__(self,direction,confidence,score,cat):
        self.direction=direction; self.confidence=confidence; self.scores=Scores(score,cat)

def test_flatten_discovers_nested_score():
    f=m.flatten(Profile("BULLISH",85.38,10.0,"BULLISH"))
    assert f[("scores","score")]==10.0
    assert f[("scores","primary_category")]=="BULLISH"

def test_adapter_can_certify_score_not_overall_score():
    profiles=[m.flatten(Profile("BULLISH",85.38,10.0,"BULLISH")),m.flatten(Profile("BEARISH",85.38,20.0,"BEARISH"))]
    stored=[{"direction":"BULLISH","confidence":85.62,"overall_score":10.1,"primary_category":"BULLISH"},
            {"direction":"BEARISH","confidence":85.62,"overall_score":20.2,"primary_category":"BEARISH"}]
    summary={"direction_match_pct":100.0,"primary_category_match_pct":100.0,"max_score_abs_error":0.2,"max_confidence_abs_error":0.24}
    a,e=m.certify_adapter(profiles,stored,summary)
    assert a["overall_score"]==("scores","score")
    assert a["primary_category"]==("scores","primary_category")

def test_exact_is_strict():
    e={"direction_match":True,"primary_category_match":True,"score_abs_error":0.0,"confidence_abs_error":0.0}
    assert m.exact(e)
    e["score_abs_error"]=1e-8
    assert not m.exact(e)

def test_candidate_sessions():
    ss=[dt.date(2022,10,d) for d in (24,25,26,27,28,31)]
    assert m.candidate_sessions(dt.date(2022,10,31),ss)[:2]==[dt.date(2022,10,31),dt.date(2022,10,28)]

def test_tolerance_unchanged():
    assert m.NUMERIC_TOLERANCE==1e-9

def test_prior_date_is_not_substituted_for_evaluation_date():
    text=P.read_text()
    assert "profile=native.call_profile(svc,str(ident[\"symbol\"]),cut_rows,nominal,session_set,300,750)" in text
