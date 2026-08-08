import math
from trading_ai.stock_intelligence import *
def rows(n=120,start=100,step=.5,vol=1000):
 return [{'open':start+i*step-.1,'high':start+i*step+.5,'low':start+i*step-.5,'close':start+i*step,'volume':vol+i*5} for i in range(n)]
def down():return rows(step=-.5)
def test_01_polygon_lineage():
 p=StockIntelligenceProfile('X','t');p.finalize();assert p.provider=='polygon'
def test_02_nonpolygon_rejected():
 import pytest
 with pytest.raises(ValueError):StockIntelligenceProfile('X','t',provider='yahoo').finalize()
def test_03_bullish():assert 'BULLISH' in TimeframeStateEngine().analyze('1d',rows()).direction
def test_04_bearish():assert 'BEARISH' in TimeframeStateEngine().analyze('1d',down()).direction
def test_05_insufficient():
 import pytest
 with pytest.raises(ValueError):TimeframeStateEngine().analyze('1d',rows(10))
def test_06_multitimeframe():assert MultiTimeframeTrendStructureService().analyze({'1d':rows(),'1w':rows(step=.8)})['alignment_score']>50
def test_07_missing_tf():assert MultiTimeframeTrendStructureService().analyze({'1d':rows()})['primary_timeframe']=='1d'
def test_08_atr_positive():assert TimeframeStateEngine().analyze('1d',rows()).atr>0
def test_09_hash_stable():assert stable_hash({'a':1})==stable_hash({'a':1})
def test_10_level_support():assert SupportResistanceEngine().analyze('1d',rows())[0]
def test_11_level_resistance():assert SupportResistanceEngine().analyze('1d',rows())[1]
def test_12_levels_deterministic():
 e=SupportResistanceEngine();assert [x.price for x in e.analyze('1d',rows())[0]]==[x.price for x in e.analyze('1d',rows())[0]]
def test_13_zones():
 s,r=SupportResistanceEngine().analyze('1d',rows());assert SupplyDemandEngine().analyze('1d',rows(),s,r)
def test_14_level_multi():assert LevelIntelligenceService().analyze({'1d':rows(),'1w':rows(step=.8)})['support_levels']
def test_15_zone_bounds():
 s,r=SupportResistanceEngine().analyze('1d',rows());z=SupplyDemandEngine().analyze('1d',rows(),s,r)[0];assert z.lower_bound<=z.upper_bound
def test_16_level_strength():assert SupportResistanceEngine().analyze('1d',rows())[0][0].strength>0
def test_17_participation():assert ParticipationEngine().analyze(rows()).score>=0
def test_18_accumulation_state():assert ParticipationEngine().analyze(rows(step=1,vol=2000)).state in [x.value for x in ParticipationState]
def test_19_distribution_state():assert ParticipationEngine().analyze(down()).state in [x.value for x in ParticipationState]
def test_20_part_evidence():assert 'cmf' in ParticipationEngine().analyze(rows()).evidence
def test_21_deterioration_bounded():assert 0<=ParticipationEngine().analyze(rows()).deterioration_risk<=100
def test_22_part_insufficient():assert 'warning' in ParticipationEngine().analyze(rows(5)).evidence
def test_23_breakout_profile():assert BreakoutIntelligenceEngine().analyze(rows()).state in [x.value for x in BreakoutState]
def test_24_breakdown_profile():assert BreakoutIntelligenceEngine().analyze(down()).state in [x.value for x in BreakoutState]
def test_25_break_probs():
 b=BreakoutIntelligenceEngine().analyze(rows());assert 0<=b.follow_through_probability<=95
def test_26_failure_probs():assert BreakoutIntelligenceEngine().analyze(rows()).failure_probability>=5
def test_27_break_hash_input():assert stable_hash(BreakoutIntelligenceEngine().analyze(rows()).__dict__)
def test_28_break_insufficient():assert 'warning' in BreakoutIntelligenceEngine().analyze(rows(5)).evidence
def test_29_context_bull():assert StockContextIntegrationService().integrate('BULLISH').score>=0
def test_30_context_bear():assert StockContextIntegrationService().integrate('BEARISH').score>=0
def test_31_context_adjustment():assert -12<=StockContextIntegrationService().integrate('BULLISH').adjustment<=12
def test_32_context_missing_warn():assert StockContextIntegrationService().integrate('BULLISH').evidence['warnings']
def test_33_context_hash():assert stable_hash(StockContextIntegrationService().integrate('BULLISH').__dict__)
def test_34_context_confidence():assert StockContextIntegrationService().integrate('BULLISH').confidence>0
def profile(step=.5):return StockIntelligenceService().analyze('X',{'1d':rows(step=step),'1w':rows(step=step*.8)},'t')
def test_35_score_exists():assert profile().scores is not None
def test_36_bull_dominates():
 p=profile();assert p.scores.bullish>p.scores.bearish
def test_37_bear_dominates():
 p=profile(-.5);assert p.scores.bearish>p.scores.bullish
def test_38_ranking():
 a=profile(.5);a.symbol='A';b=profile(.2);b.symbol='B';assert len(StockOpportunityRankingService().rank([a,b]))==2
def test_39_final_hash():assert profile().state_hash
def test_40_categories():assert profile().categories
