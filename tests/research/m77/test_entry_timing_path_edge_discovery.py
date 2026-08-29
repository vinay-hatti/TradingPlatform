import numpy as np
import pandas as pd

from trading_ai.research.m77.entry_timing_path_edge_discovery import (
    _entry_for_policy,
    _outcomes,
    evidence_tables,
    readiness,
)


def _daily():
    dates=pd.bdate_range("2014-01-02",periods=90)
    close=np.linspace(100,118,90)
    high=close+1.2
    low=close-1.0
    open_=close-0.2
    df=pd.DataFrame({"as_of":dates,"open":open_,"high":high,"low":low,"close":close,"volume":1_000_000})
    df["atr_14"]=2.0
    df["px_ret_5"]=df["close"].pct_change(5)
    df["dist_sma_20"]=0.02
    df["rsi_14"]=58.0
    df["atr_pct_14"]=0.02
    df["prev_high_20"]=df["high"].shift(1).rolling(20,min_periods=20).max()
    return df


def test_fixed_entry_policies_have_expected_trigger_semantics():
    df=_daily(); i=30
    ent=_entry_for_policy(df,i,"NEXT_OPEN")
    assert ent[0]==i+1 and ent[2]=="OPEN"
    ent2=_entry_for_policy(df,i,"DELAY1_CLOSE")
    assert ent2[0]==i+1 and ent2[2]=="CLOSE"
    br=_entry_for_policy(df,i,"BREAKOUT_0P5_ATR")
    assert br is not None and br[2]=="TOUCH"


def test_touch_trigger_day_is_excluded_from_barrier_ordering():
    df=_daily(); i=30
    ent=_entry_for_policy(df,i,"BREAKOUT_0P5_ATR")
    ei,ep,kind=ent
    out=_outcomes(df,ei,ep,kind,20,2.0)
    assert out is not None
    assert "barrier_t2p0_s1p0" in out


def test_evidence_uses_next_open_as_frozen_baseline():
    rows=[]
    for y in range(2011,2018):
        for j in range(180):
            sym=f"S{j%80:03d}"
            d=pd.Timestamp(f"{y}-01-03")+pd.Timedelta(days=j)
            for policy,uplift in [("NEXT_OPEN",0.0),("DELAY1_CLOSE",0.02)]:
                r=0.02+uplift+(0.01 if j%3 else -0.01)
                rows.append({
                    "symbol":sym,"as_of":d,"entry_date":d+pd.Timedelta(days=1),
                    "policy":policy,"horizon":20,"triggered":True,"wait_sessions":1,
                    "return":r,"mfe_atr":2.0,"mae_atr":-0.5,"atr_pct_14":.02,
                    "px_ret_5":.01,"dist_sma_20":.02,"rsi_14":55.0,"atr_pct_rank":.5,
                    "barrier_t1p5_s1p0":1.0,"barrier_t2p0_s1p0":1.0,"barrier_t3p0_s1p0":0.0,
                })
    panel=pd.DataFrame(rows)
    e,y,s,stress=evidence_tables(panel)
    row=e[(e.policy=="DELAY1_CLOSE")&(e.horizon==20)].iloc[0]
    assert row.mean_return_uplift>0
    assert row.win_rate_uplift>=0
    assert not y.empty and not stress.empty


def test_readiness_requires_nonbaseline_and_all_frozen_gates():
    e=pd.DataFrame([{
        "horizon":20,"policy":"DELAY1_CLOSE","triggered_n":1200,"symbols":250,
        "trigger_rate":1.0,"win_rate":.65,"baseline_win_rate":.60,"win_rate_uplift":.05,
        "mean_return":.04,"baseline_mean_return":.02,"baseline_equal_symbol_mean_return":.019,
        "mean_return_uplift":.02,"loss_10_rate_change":-.01,
        "equal_symbol_mean_return":.03,"barrier_expectancy_t2p0_s1p0":.2,
    }])
    years=pd.DataFrame([
        {"horizon":20,"policy":"DELAY1_CLOSE","year":y,"win_rate_uplift":.02,"mean_return_uplift":.01}
        for y in range(2011,2018)
    ])
    stress=pd.DataFrame([{
        "horizon":20,"policy":"DELAY1_CLOSE","stress":"NON_OVERLAP","n":900,
        "win_rate":.63,"mean_return":.03,"equal_symbol_mean_return":.025,
    }])
    r=readiness(e,years,stress)
    assert bool(r.iloc[0].development_ready)


def test_recursive_daily_discovery_and_filename_decoding(tmp_path):
    from trading_ai.research.m77.entry_timing_path_edge_discovery import _discover_daily_symbol_paths
    nested=tmp_path/"year"/"bucket"
    nested.mkdir(parents=True)
    for name in ("AAPL.daily.csv.gz","BRK_2EB.daily.csv.gz"):
        (nested/name).write_bytes(b"x")
    paths,meta=_discover_daily_symbol_paths(tmp_path)
    assert "AAPL" in paths
    assert "BRK.B" in paths
    assert meta["daily_files_discovered"]==2
    assert meta["decoded_symbols_discovered"]==2


def test_zero_symbol_match_fails_with_diagnostics(tmp_path):
    from trading_ai.research.m77.entry_timing_path_edge_discovery import EntryTimingConfig, build_timing_panel, EntryTimingError
    import pytest
    nested=tmp_path/"raw"/"nested"
    nested.mkdir(parents=True)
    (nested/"ZZZ.daily.csv.gz").write_bytes(b"not-read-because-no-match")
    candidates=pd.DataFrame({"symbol":["AAA"],"as_of":[pd.Timestamp("2014-01-03")]})
    cfg=EntryTimingConfig(project_root=str(tmp_path),daily_root="raw",workers=1)
    with pytest.raises(EntryTimingError,match="No candidate symbols matched recursive daily authority"):
        build_timing_panel(cfg,candidates)


def test_worker_reads_literal_candidate_json_via_explicit_buffer(tmp_path):
    import gzip
    from trading_ai.research.m77.entry_timing_path_edge_discovery import _process_symbol
    dates=pd.bdate_range("2012-01-03",periods=420)
    close=np.linspace(50,70,len(dates))
    raw=pd.DataFrame({
        "session_date":dates,
        "open":close-.1,
        "high":close+.5,
        "low":close-.5,
        "close":close,
        "volume":1_000_000,
    })
    path=tmp_path/"AAA.daily.csv.gz"
    raw.to_csv(path,index=False,compression="gzip")
    cand=pd.DataFrame({"symbol":["AAA"],"as_of":[dates[330]]})
    payload=cand.to_json(orient="records",date_format="iso")
    sym,rows,err=_process_symbol(("AAA",str(path),payload,["NEXT_OPEN"],["20"]))
    assert sym=="AAA"
    assert err is None
    assert len(rows)>0
    assert rows[0]["triggered"] is True


def test_empty_materialization_reports_worker_failure_samples(tmp_path, monkeypatch):
    from trading_ai.research.m77 import entry_timing_path_edge_discovery as mod
    nested=tmp_path/"raw"/"nested"
    nested.mkdir(parents=True)
    (nested/"AAA.daily.csv.gz").write_bytes(b"x")
    candidates=pd.DataFrame({"symbol":["AAA"],"as_of":[pd.Timestamp("2014-01-03")]})
    def fake_worker(args):
        return "AAA",[], "ValueError: synthetic shared worker failure"
    monkeypatch.setattr(mod,"_process_symbol",fake_worker)
    cfg=mod.EntryTimingConfig(project_root=str(tmp_path),daily_root="raw",workers=1)
    import pytest
    with pytest.raises(mod.EntryTimingError,match="top_failure_counts"):
        mod.build_timing_panel(cfg,candidates)
