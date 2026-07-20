from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.ui.models.paper_commands import GovernedActor
from trading_ai.ui.models.strategy_studio import (
    ExperimentRequest, ExperimentVariant, PromotionRequest,
    ShadowDeploymentRequest, StrategyDraftRequest, StrategyParameter,
)
from trading_ai.ui.services.strategy_studio_service import StrategyStudioService

def main():
    actor=GovernedActor(
        user_id="strategy-admin",session_id="s1",roles=["STRATEGY_ADMIN"],
        permissions=["strategy.shadow.deploy","strategy.experiment.create","strategy.promote"])
    with TemporaryDirectory() as d:
        svc=StrategyStudioService(Path(d)/"state.json",Path(d)/"audit.jsonl")
        request=StrategyDraftRequest(
            strategy_id="options_momentum",display_name="Options Momentum",
            description="Version one",tags=["test"],actor=actor,
            parameters=[
                StrategyParameter(name="rsi_period",value=14,value_type="int",minimum=2,maximum=100),
                StrategyParameter(name="min_confidence",value=.65,value_type="float",minimum=0,maximum=1),
            ])
        v1=svc.create_version(request)
        assert v1.status=="VALIDATED" and v1.version_number==1
        v2=svc.create_version(request)
        assert v2.version_number==2 and v2.checksum==v1.checksum

        shadow=svc.create_shadow(ShadowDeploymentRequest(
            strategy_id="options_momentum",version_id=v1.version_id,symbols=["AAPL"],
            allocation_pct=0,start_reason="Paper shadow validation",actor=actor))
        assert shadow.status=="SHADOW"

        exp=svc.create_experiment(ExperimentRequest(
            experiment_name="RSI comparison",strategy_id="options_momentum",
            variants=[
                ExperimentVariant(label="A",version_id=v1.version_id,traffic_pct=50),
                ExperimentVariant(label="B",version_id=v2.version_id,traffic_pct=50),
            ],minimum_observations=10,actor=actor))
        assert exp.status=="RUNNING"
        try:
            svc.promote(exp.experiment_id,PromotionRequest(
                version_id=v1.version_id,reason="Too early",
                confirmation_token="CONFIRM-STRATEGY-123",actor=actor))
            raise AssertionError("promotion should require observations")
        except ValueError:
            pass

    print("All Milestone 33 Phase 6 Strategy Studio assertions passed.")

if __name__=="__main__":
    main()
