from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from trading_ai.stock_intelligence.volume_response_classifier import InstitutionalVolumeResponseClassifier

def base_payload():
    return {
        "primary_timeframe":"1d",
        "timeframe_states":{"1d":{"close":100.0}},
        "trade_plan":{"reference_market":{"price":100.0}},
        "resistance_levels":[{"price":100.5}],
        "support_levels":[{"price":95.0}],
        "participation":{"state":"ACCUMULATION"},
        "breakout":{"state":"NONE"},
        "institutional_volume":{
            "signal":"SELLING_ABSORPTION","regime":"CLIMACTIC",
            "relative_volume_1d":4.0,"persistence_score":85.0,"absorption_score":80.0,
            "accumulation_score":75.0,"distribution_score":65.0,
            "breakout_confirmation_score":0.0,"breakdown_confirmation_score":0.0,
            "close_location_value":-0.30,
            "evidence":{"price_change_1d":0.001,"range_ratio_vs_20d_median":0.9,
                        "signed_volume_flow_20d":0.25,"cmf_20d":0.12,
                        "climactic_volume":True,"absorption_side":"SELLING"},
        },
    }

def test_ea_like_absorption_near_resistance_is_qualified():
    x=InstitutionalVolumeResponseClassifier().classify(base_payload())
    assert x["classification"]=="SELLING_ABSORPTION_AT_RESISTANCE"
    assert x["directional_implication"]=="CONSTRUCTIVE_AWAITING_BREAKOUT_CONFIRMATION"
    assert x["resistance_distance_pct"]==0.5

def test_distribution_at_resistance():
    p=base_payload()
    p["participation"]["state"]="DISTRIBUTION"
    p["institutional_volume"]["distribution_score"]=85
    p["institutional_volume"]["accumulation_score"]=60
    p["institutional_volume"]["close_location_value"]=-0.70
    p["institutional_volume"]["evidence"]["price_change_1d"]=-0.01
    x=InstitutionalVolumeResponseClassifier().classify(p)
    assert x["classification"] in {"BREAKOUT_REJECTION","DISTRIBUTION_AT_RESISTANCE"}
    assert x["directional_implication"]=="BEARISH_WARNING"

def test_breakout_acceptance():
    p=base_payload()
    p["breakout"]["state"]="BREAKOUT_CONFIRMED"
    p["institutional_volume"]["breakout_confirmation_score"]=85
    p["institutional_volume"]["close_location_value"]=0.7
    x=InstitutionalVolumeResponseClassifier().classify(p)
    assert x["classification"]=="BREAKOUT_ACCEPTANCE"
    assert x["directional_implication"]=="BULLISH_CONFIRMATION"

def test_governance_is_zero_effect():
    x=InstitutionalVolumeResponseClassifier().classify(base_payload())
    g=x["governance"]
    assert g["presentation_only"] is True
    assert g["stock_intelligence_score_effect"] is False
    assert g["ranking_effect"] is False
    assert g["trade_plan_certification_effect"] is False
    assert g["m64_allocation_effect"] is False
    assert g["execution_effect"] is False

def test_service_generation_path_not_modified():
    s=(ROOT/"src/trading_ai/stock_intelligence/service.py").read_text()
    assert "InstitutionalVolumeResponseClassifier" not in s
