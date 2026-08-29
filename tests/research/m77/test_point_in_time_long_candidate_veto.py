import gzip, json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.edge_discovery_lab import EdgeLabError
from trading_ai.research.m77.point_in_time_long_candidate_veto import (
    LongCandidateVetoConfig, _extract_profile_record, reconstruct_long_candidate_authority, run_lab,
)


def profile(symbol="AAA", as_of="2012-01-06", direction="BULLISH", decision="ELIGIBLE", lifecycle="ACTIONABLE", ready=True):
    return {
        "symbol": symbol, "as_of": as_of, "direction": direction, "confidence": 82, "overall_score": 78,
        "profile": {
            "symbol": symbol, "direction": direction, "confidence": 82, "overall_score": 78, "structure": "TREND",
            "scores": {"overall": 79, "bullish": 80, "bearish": 20, "confidence": 82, "options_suitability": 75, "primary_category": "BULLISH"},
            "decision_intelligence": {"decision": decision, "decision_readiness": 74, "overall_trade_quality": 77, "capital_priority": 76,
                                      "institutional_grade": "B", "opportunity_lifecycle": lifecycle},
            "trade_plan": {"certification": {"status": "PASS", "publishable": True, "trade_builder_ready": ready,
                                                "entry_execution": {"trade_builder_ready": ready}}},
        }
    }


def test_profile_native_population_reconstruction():
    r=_extract_profile_record(profile())
    assert r["pop_native_bullish"]
    assert r["pop_primary_category_bullish"]
    assert r["pop_idi_eligible_or_prioritize"]
    assert not r["pop_idi_prioritize"]
    assert r["pop_lifecycle_actionable"]
    assert r["pop_certified_trade_builder_ready"]


def test_bearish_profile_never_enters_bullish_populations():
    r=_extract_profile_record(profile(direction="BEARISH", decision="PRIORITIZE"))
    assert not any(v for k,v in r.items() if k.startswith("pop_"))


def test_config_forbids_validation_and_final_holdout():
    with pytest.raises(EdgeLabError):
        LongCandidateVetoConfig(project_root="/tmp", development_predictions="research_data/m77_21_3/validation_predictions.csv.gz").validate()
    with pytest.raises(EdgeLabError):
        LongCandidateVetoConfig(project_root="/tmp", pit_profiles_root="final_holdout/profiles").validate()


def test_reconstruction_reads_jsonl_and_builds_top_decile(tmp_path):
    root=tmp_path/"profiles"; root.mkdir()
    for i in range(20):
        obj=profile(symbol=f"S{i:02d}")
        obj["profile"]["scores"]["overall"]=i
        with gzip.open(root/f"S{i:02d}.jsonl.gz","wt") as fh: fh.write(json.dumps(obj)+"\n")
    out=tmp_path/"out"
    df=reconstruct_long_candidate_authority(root,out)
    assert len(df)==20
    assert df["pop_bullish_top_decile_score"].sum()==3  # average-rank percentile >= .90 includes 18,19,20 ranks
    assert (out/"checkpoints/pit_long_candidate_authority.csv.gz").exists()


def test_end_to_end_development_only_runner(tmp_path):
    profiles=tmp_path/"research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay/weekly/profiles"; profiles.mkdir(parents=True)
    dates=pd.date_range("2011-01-07",periods=12,freq="7D")
    syms=[f"S{i:03d}" for i in range(60)]
    # one profile file per symbol, matching production authority layout
    for si,sym in enumerate(syms):
        with gzip.open(profiles/f"{sym}.jsonl.gz","wt") as fh:
            for dt in dates:
                decision="PRIORITIZE" if si<20 else "ELIGIBLE"
                fh.write(json.dumps(profile(sym,dt.strftime("%Y-%m-%d"),decision=decision))+"\n")
    rows=[]
    integ=[]
    for dt in dates:
        for i,sym in enumerate(syms):
            # bottom-probability names are deliberately future losers
            ret=-0.15 if i<3 else 0.03
            rows.append({"symbol":sym,"as_of":dt,"horizon":20,"test_year":dt.year,"probability_up":i/60,
                         "fwd_ret_20":ret,"mfe_atr_20":1.0 if ret<0 else 2.5,"mae_atr_20":-2.0 if ret<0 else -0.5})
            integ.append({"symbol":sym,"as_of":dt,"horizon":20,"raw_authority_present":True,"interval_integrity_clean":True,
                          "source_return_matches_raw":True,"interval_integrity_event_count":0})
    pp=tmp_path/"research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"; pp.parent.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(pp,index=False,compression="gzip")
    ip=tmp_path/"research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz"; ip.parent.mkdir(parents=True)
    pd.DataFrame(integ).to_csv(ip,index=False,compression="gzip")
    summary=run_lab(LongCandidateVetoConfig(project_root=str(tmp_path)))
    assert summary["status"]=="COMPLETE"
    assert summary["validation_rows_read"]==0 and summary["final_holdout_rows_read"]==0
    out=tmp_path/"research_data/m77_22_3/point_in_time_long_candidate_veto"
    ev=pd.read_csv(out/"candidate_long_bearish_veto_evidence.csv")
    x=ev[(ev.population=="pop_native_bullish")&(ev.horizon==20)&np.isclose(ev.tail_fraction,0.05)].iloc[0]
    assert x.loss_10_rate_reduction>0
    assert x.severe_loss_capture_lift_vs_random>1
    assert (out/"PIT_LONG_CANDIDATE_DOWNSIDE_RISK_VETO_REPORT.md").exists()
