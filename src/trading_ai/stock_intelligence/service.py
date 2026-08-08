from datetime import datetime,timezone
from .profile import *
from .multi_timeframe import MultiTimeframeTrendStructureService
from .levels import LevelIntelligenceService
from .participation import ParticipationEngine
from .breakout import BreakoutIntelligenceEngine
from .context import StockContextIntegrationService
from .scoring import StockOpportunityScoringEngine
from .position_intelligence import PositionIntelligenceEngine
from .structure_zones import InstitutionalStructureZoneEngine
class StockIntelligenceService:
    def __init__(self):self.mt=MultiTimeframeTrendStructureService();self.levels=LevelIntelligenceService();self.part=ParticipationEngine();self.bo=BreakoutIntelligenceEngine();self.ctx=StockContextIntegrationService();self.scorer=StockOpportunityScoringEngine();self.structure_zones=InstitutionalStructureZoneEngine();self.position=PositionIntelligenceEngine()
    def analyze(self,symbol,data_by_timeframe,snapshot_timestamp=None,external_context=None):
        mt=self.mt.analyze(data_by_timeframe); p=StockIntelligenceProfile(symbol,snapshot_timestamp or datetime.now(timezone.utc).isoformat(),timeframe_states=mt['states'],direction=mt['direction'],structure=mt['structure'],alignment_score=mt['alignment_score'],confidence=mt['confidence'],primary_timeframe=mt['primary_timeframe'],warnings=mt['warnings'])
        lv=self.levels.analyze(data_by_timeframe); p.support_levels=lv['support_levels'];p.resistance_levels=lv['resistance_levels'];p.demand_zones=lv['demand_zones'];p.supply_zones=lv['supply_zones']
        primary=data_by_timeframe[p.primary_timeframe];p.participation=self.part.analyze(primary);p.breakout=self.bo.analyze(primary,p.support_levels,p.resistance_levels)
        e=external_context or {};p.context=self.ctx.integrate(p.direction,**e);p.structure_zones=self.structure_zones.build(p);p.scores=self.scorer.score(p);p.categories=[p.scores.primary_category];p.trade_plan=self.position.build(p);return p.finalize()
