from uuid import uuid4
from dataclasses import asdict
from .models import *
class StockIntelligenceRepository:
    def __init__(self,session):self.session=session
    def save_profile(self,run_id,candidate_id,p):
        common={'scanner_run_id':run_id,'candidate_id':candidate_id,'symbol':p.symbol,'snapshot_timestamp':p.snapshot_timestamp}
        self.session.add(StockScannerCandidateModel(id=candidate_id,category=p.scores.primary_category,score=p.scores.overall,payload_json=asdict(p),**common))
        for tf,x in p.timeframe_states.items():self.session.add(StockScannerTimeframeStateModel(id=str(uuid4()),timeframe=tf,direction=x.direction,structure=x.structure,payload_json=asdict(x),**common))
        for x in p.support_levels+p.resistance_levels:
            contributors=list(dict.fromkeys((x.contributing_timeframes or [x.timeframe])))
            payload=asdict(x);payload['primary_timeframe']=x.timeframe;payload['contributing_timeframes']=contributors
            self.session.add(StockSupportResistanceLevelModel(id=str(uuid4()),timeframe=x.timeframe,primary_timeframe=x.timeframe,contributing_timeframes=contributors,level_type=x.level_type,price=x.price,strength=x.strength,payload_json=payload,**common))
        for x in p.demand_zones+p.supply_zones:
            contributors=list(dict.fromkeys((x.contributing_timeframes or [x.timeframe])))
            payload=asdict(x);payload['primary_timeframe']=x.timeframe;payload['contributing_timeframes']=contributors
            self.session.add(StockSupplyDemandZoneModel(id=str(uuid4()),timeframe=x.timeframe,primary_timeframe=x.timeframe,contributing_timeframes=contributors,zone_type=x.zone_type,lower_bound=x.lower_bound,upper_bound=x.upper_bound,strength=x.strength,payload_json=payload,**common))
        for x in p.structure_zones:
            payload=asdict(x)
            self.session.add(StockInstitutionalStructureZoneModel(
                id=str(uuid4()),zone_type=x.zone_type,lower_bound=x.lower_bound,upper_bound=x.upper_bound,
                representative_price=x.representative_price,strength=x.strength,confluence_score=x.confluence_score,
                primary_timeframe=x.primary_timeframe,contributing_timeframes=x.contributing_timeframes,
                components=x.components,payload_json=payload,**common,
            ))
        if p.participation:self.session.add(StockAccumulationDistributionSnapshotModel(id=str(uuid4()),state=p.participation.state,score=p.participation.score,payload_json=asdict(p.participation),**common))
        if p.breakout:self.session.add(StockBreakoutSnapshotModel(id=str(uuid4()),state=p.breakout.state,confirmation=p.breakout.confirmation,payload_json=asdict(p.breakout),**common))
        if p.context:self.session.add(StockContextSnapshotModel(id=str(uuid4()),context_score=p.context.score,context_adjustment=p.context.adjustment,payload_json=asdict(p.context),**common))
        if p.scores:self.session.add(StockOpportunityScoreSnapshotModel(id=str(uuid4()),primary_category=p.scores.primary_category,overall_score=p.scores.overall,confidence=p.scores.confidence,payload_json=asdict(p.scores),**common))

        if p.trade_plan:
            from .profile import PositionIntelligenceProfile
            payload=asdict(p.trade_plan)
            exit_payload=payload.get('exit',{})
            self.session.add(StockPositionIntelligenceSnapshotModel(id=str(uuid4()),action=exit_payload.get('action','HOLD'),thesis_integrity=float(exit_payload.get('thesis_integrity',0)),management_quality=float(payload.get('management_quality',0)),payload_json=payload,**common))
        self.session.flush();return p

    def save_outcome(self, observation):
        from dataclasses import asdict
        from .models import StockOutcomeObservationModel
        payload=asdict(observation)
        row=StockOutcomeObservationModel(
            id=observation.observation_id,
            scanner_run_id=observation.scanner_run_id,
            candidate_id=observation.candidate_id,
            symbol=observation.symbol,
            snapshot_timestamp=observation.published_at,
            outcome=observation.outcome,
            setup_category=observation.setup_category,
            market_regime=observation.market_regime,
            strategy=observation.strategy,
            prediction_probability=observation.prediction_probability,
            realized_return_pct=observation.realized_return_pct,
            management_policy=observation.management_policy,
            payload_json=payload,
        )
        self.session.merge(row);self.session.flush();return observation

    def save_attribution(self, scanner_run_id, snapshot_timestamp, attribution_type, profile):
        from dataclasses import asdict
        from .models import StockOutcomeAttributionSnapshotModel
        row=StockOutcomeAttributionSnapshotModel(
            id=str(uuid4()), scanner_run_id=scanner_run_id, candidate_id=None, symbol='*',
            snapshot_timestamp=snapshot_timestamp, attribution_type=attribution_type,
            attribution_key=profile.key, observation_count=profile.observation_count,
            payload_json=asdict(profile),
        )
        self.session.add(row);self.session.flush();return profile

    def save_calibration(self, scanner_run_id, snapshot_timestamp, model_family, model_version, profile):
        from dataclasses import asdict
        from .models import StockProbabilityCalibrationSnapshotModel
        row=StockProbabilityCalibrationSnapshotModel(
            id=str(uuid4()), scanner_run_id=scanner_run_id, candidate_id=None, symbol='*',
            snapshot_timestamp=snapshot_timestamp, model_family=model_family,
            model_version=model_version, observation_count=profile.observation_count,
            brier_score=profile.brier_score, expected_calibration_error=profile.expected_calibration_error,
            payload_json=asdict(profile),
        )
        self.session.add(row);self.session.flush();return profile

    def save_management_policy_performance(self, scanner_run_id, snapshot_timestamp, profile):
        from dataclasses import asdict
        from .models import StockManagementPolicyPerformanceModel
        row=StockManagementPolicyPerformanceModel(
            id=str(uuid4()), scanner_run_id=scanner_run_id, candidate_id=None, symbol='*',
            snapshot_timestamp=snapshot_timestamp, policy_name=profile.policy_name,
            observation_count=profile.observation_count, expectancy_pct=profile.expectancy_pct,
            score=profile.score, payload_json=asdict(profile),
        )
        self.session.add(row);self.session.flush();return profile
