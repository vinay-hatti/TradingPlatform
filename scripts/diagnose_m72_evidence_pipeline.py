#!/usr/bin/env python3
import json
from sqlalchemy import select
from trading_ai.database.session import SessionLocal
from trading_ai.performance_learning.models import PerformanceObservationModel,PredictionOutcomeModel,PredictionRegistryModel,TradeOutcomeModel
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.execution_intelligence.models import ExecutionLearningSampleModel,ExecutionOrderTelemetryModel
from trading_ai.broker.ibkr.database_models import BrokerExecutionModel,BrokerOrderModel
from trading_ai.opex_intelligence.models import OpexForecastOutcomeModel,OpexForecastSnapshotModel

ROUTED={'SUBMITTED','PRESUBMITTED','AWAITING_BROKER_ACK','FILLED','CANCELLED','CANCELED','INACTIVE'}
TERMINAL={'FILLED','CANCELLED','CANCELED','REJECTED','INACTIVE'}

def main():
    portfolio_id='PAPER-PRIMARY'
    with SessionLocal() as s:
        trade=list(s.scalars(select(TradeOutcomeModel).where(TradeOutcomeModel.portfolio_id==portfolio_id)))
        obs=list(s.scalars(select(PerformanceObservationModel).where(PerformanceObservationModel.portfolio_id==portfolio_id)))
        preds=list(s.scalars(select(PredictionRegistryModel)));outs=list(s.scalars(select(PredictionOutcomeModel)))
        intents=list(s.scalars(select(ExecutionIntentModel).where(ExecutionIntentModel.portfolio_id==portfolio_id)))
        orders=list(s.scalars(select(BrokerOrderModel).where(BrokerOrderModel.portfolio_id==portfolio_id)))
        executions=list(s.scalars(select(BrokerExecutionModel).where(BrokerExecutionModel.portfolio_id==portfolio_id)))
        telemetry=list(s.scalars(select(ExecutionOrderTelemetryModel)));samples=list(s.scalars(select(ExecutionLearningSampleModel)))
        opex=list(s.scalars(select(OpexForecastSnapshotModel)));opex_out=list(s.scalars(select(OpexForecastOutcomeModel)))
    realized=[x for x in trade if x.outcome in {'WIN','LOSS','FLAT'} and x.closed_at]
    t_ids={x.execution_intent_id for x in telemetry}
    never_routed=[x for x in intents if x.execution_intent_id not in t_ids and not x.submitted_at and str(x.state or '').upper() not in ROUTED]
    routed_missing=[x for x in intents if x.execution_intent_id not in t_ids and (x.submitted_at or str(x.state or '').upper() in ROUTED)]
    filled_orders=[x for x in orders if str(x.status or '').upper()=='FILLED' or float(x.filled_quantity or 0)>0 or float(x.average_fill_price or 0)>0]
    if filled_orders and not executions: sync_state='EXECUTION_HISTORY_INCOMPLETE'
    elif executions: sync_state='EXECUTIONS_AVAILABLE'
    else: sync_state='NO_FILLS_AVAILABLE'
    by_position={}
    for x in trade: by_position[x.position_id]=by_position.get(x.position_id,0)+1
    duplicate_groups=sum(1 for n in by_position.values() if n>1)
    payload={'portfolio_id':portfolio_id,'trade':{'outcomes_total':len(trade),'unique_positions':len(by_position),'duplicate_position_groups':duplicate_groups,'realized_closed':len(realized),'observations':len(obs),'unbridged_realized':max(0,len(realized)-len(obs))},'prediction_learning':{'predictions':len(preds),'prediction_outcomes':len(outs),'realized_prediction_ids':len({x.prediction_id for x in outs})},'execution':{'intents':len(intents),'broker_orders':len(orders),'terminal_broker_orders':sum(1 for x in orders if str(x.status or '').upper() in TERMINAL),'filled_broker_orders':len(filled_orders),'broker_executions':len(executions),'telemetry':len(telemetry),'learning_samples':len(samples),'never_routed_intents':len(never_routed),'routed_without_telemetry':len(routed_missing),'broker_execution_sync_state':sync_state,'needs_ibkr_sync':sync_state=='EXECUTION_HISTORY_INCOMPLETE'},'opex':{'forecasts':len(opex),'outcomes':len(opex_out)}}
    print(json.dumps(payload,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
