from pathlib import Path
from trading_ai.execution_intelligence.policy import load_execution_intelligence_policy
from trading_ai.execution_intelligence.models import ExecutionOrderTelemetryModel,ExecutionFillEventModel,WorkingOrderAssessmentModel,ExecutionLearningSampleModel
from trading_ai.production_api.app import create_production_app
from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport

def main():
    p=load_execution_intelligence_policy();app=create_production_app();paths=set(app.openapi().get('paths',{}).keys())
    required={'/api/v1/execution-intelligence/policy','/api/v1/execution-intelligence/dashboard','/api/v1/execution-intelligence/intents/{intent_id}/preflight','/api/v1/execution-intelligence/intents/{intent_id}/working-assessment','/api/v1/execution-workspace/intents/{id}/reprice'}
    missing=sorted(required-paths);assert not missing,f'Missing M70 API paths: {missing}'
    assert p.quote_stability_samples>=1;assert 0<=p.initial_limit_aggression_pct<=100;assert p.maximum_reprices>=0
    assert callable(getattr(IbapiPaperOrderTransport,'modify_order',None));assert callable(getattr(IbapiPaperOrderTransport,'modify_combo_order',None))
    assert ExecutionOrderTelemetryModel.__tablename__=='execution_order_telemetry';assert ExecutionFillEventModel.__tablename__=='execution_fill_events';assert WorkingOrderAssessmentModel.__tablename__=='execution_working_order_assessments';assert ExecutionLearningSampleModel.__tablename__=='execution_learning_samples'
    migration=Path('migrations/versions/m70_003_execution_intelligence_completion.py');assert migration.exists();assert "down_revision='m70_002'" in migration.read_text()
    print('M70 institutional execution intelligence acceptance PASSED');print(p.as_dict())
if __name__=='__main__':main()
