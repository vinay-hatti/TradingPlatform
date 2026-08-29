from datetime import datetime,timezone
from .profile import *
from .multi_timeframe import MultiTimeframeTrendStructureService
from .levels import LevelIntelligenceService
from .participation import ParticipationEngine
from .volume_intelligence import InstitutionalVolumeIntelligenceEngine
from .breakout import BreakoutIntelligenceEngine
from .context import StockContextIntegrationService
from .scoring import StockOpportunityScoringEngine
from .position_intelligence import PositionIntelligenceEngine
from .structure_zones import InstitutionalStructureZoneEngine
from .decision_intelligence import InstitutionalDecisionIntelligenceEngine
class StockIntelligenceService:
    def __init__(self):self.mt=MultiTimeframeTrendStructureService();self.levels=LevelIntelligenceService();self.part=ParticipationEngine();self.volume=InstitutionalVolumeIntelligenceEngine();self.bo=BreakoutIntelligenceEngine();self.ctx=StockContextIntegrationService();self.scorer=StockOpportunityScoringEngine();self.structure_zones=InstitutionalStructureZoneEngine();self.position=PositionIntelligenceEngine();self.decision=InstitutionalDecisionIntelligenceEngine()
    def analyze(self,symbol,data_by_timeframe,snapshot_timestamp=None,external_context=None):
        mt=self.mt.analyze(data_by_timeframe); p=StockIntelligenceProfile(symbol,snapshot_timestamp or datetime.now(timezone.utc).isoformat(),timeframe_states=mt['states'],direction=mt['direction'],structure=mt['structure'],alignment_score=mt['alignment_score'],confidence=mt['confidence'],primary_timeframe=mt['primary_timeframe'],warnings=mt['warnings'])
        lv=self.levels.analyze(data_by_timeframe); p.support_levels=lv['support_levels'];p.resistance_levels=lv['resistance_levels'];p.demand_zones=lv['demand_zones'];p.supply_zones=lv['supply_zones']
        primary=data_by_timeframe[p.primary_timeframe];p.participation=self.part.analyze(primary);p.breakout=self.bo.analyze(primary,p.support_levels,p.resistance_levels);p.institutional_volume=self.volume.analyze(primary,breakout_state=p.breakout.state,structure=p.structure)
        e=external_context or {};p.context=self.ctx.integrate(p.direction,**e);p.structure_zones=self.structure_zones.build(p);p.scores=self.scorer.score(p);p.categories=[p.scores.primary_category];p.trade_plan=self.position.build(p)
        from trading_ai.trade_plan_certification import certify_stock_trade_plan
        certification=certify_stock_trade_plan(p,p.trade_plan);p.trade_plan.reference_market=dict(certification.get('reference_market') or {});p.trade_plan.certification=certification;p.trade_plan.finalize();p.decision_intelligence=self.decision.assess(p);return p.finalize()
