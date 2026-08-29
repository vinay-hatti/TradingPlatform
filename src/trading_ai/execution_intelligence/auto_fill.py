from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import os
from sqlalchemy import select
from sqlalchemy.orm import Session
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.execution_workspace.service import ExecutionWorkspaceService
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel, BrokerOrderModel
from trading_ai.broker.ibkr.models import IbkrPaperConnectionConfig
from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport
from trading_ai.broker.ibkr.order_service import IbkrPaperOrderService
from .service import ExecutionIntelligenceService
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from .policy import load_execution_intelligence_policy

WORKING_STATES={"SUBMITTED","ACKNOWLEDGED","PARTIALLY_FILLED"}

class AutomaticEntryFillManager:
    VERSION="M73.0.8-ADAPTIVE-ENTRY-WORKING-ORDER-LIFETIME-1.0+M74.12-ADAPTIVE-MARKET-STATE-CHASE+M74.13-AUTONOMOUS-POSITION-BOOTSTRAP-1.0"
    def __init__(self,session:Session):self.s=session
    def _broker_sync_once(self,portfolio_id):
        binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
        if not binding:raise KeyError(f'IBKR binding not found for {portfolio_id}')
        transport=IbapiPaperOrderTransport();service=IbkrPaperOrderService(lambda:__import__('trading_ai.database.session',fromlist=['SessionLocal']).SessionLocal(),transport)
        try:
            transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False))
            return service.synchronize(portfolio_id)
        finally:
            transport.disconnect()
    @staticmethod
    def _intent_id_from_broker_order(row):
        raw=dict(row.raw_json or {});req=dict(raw.get('request') or {});meta=dict(req.get('metadata') or {})
        explicit=str(meta.get('execution_intent_id') or '').strip()
        if explicit:return explicit
        for value in (row.aggregate_id,row.client_order_id):
            text=str(value or '')
            marker='XI-'
            if marker in text:
                return text[text.index(marker):].replace('M59-CLIENT-','').replace('M59-','')
        return ''
    def _platform_fills_needing_bootstrap(self,portfolio_id):
        cooldown=max(15,int(os.getenv('TRADING_AI_M74_13_BOOTSTRAP_RETRY_SECONDS','60')))
        now_dt=datetime.now(timezone.utc);pending=[]
        rows=list(self.s.scalars(select(BrokerOrderModel).where(BrokerOrderModel.portfolio_id==portfolio_id)))
        for row in rows:
            status=str(row.status or '').upper().replace(' ','')
            has_fill=status=='FILLED' or float(row.filled_quantity or 0)>0
            if not has_fill:continue
            intent_id=self._intent_id_from_broker_order(row)
            if not intent_id:continue
            managed=self.s.scalar(select(ManagedPositionModel).where(ManagedPositionModel.portfolio_id==portfolio_id,ManagedPositionModel.execution_id==intent_id,ManagedPositionModel.state.notin_(['CLOSED','CANCELLED','SUPERSEDED'])))
            if managed is not None and not bool((managed.metadata_json or {}).get('broker_discovered')):
                continue
            raw=dict(row.raw_json or {});last=str(raw.get('m74_13_last_bootstrap_attempt_at') or '')
            if last:
                try:
                    age=(now_dt-datetime.fromisoformat(last.replace('Z','+00:00'))).total_seconds()
                    if age<cooldown:continue
                except Exception:pass
            pending.append(row)
        return pending
    def _position_bootstrap_sync_once(self,portfolio_id,orders):
        if not orders:return None
        stamp=datetime.now(timezone.utc).isoformat()
        ids=[]
        for row in orders:
            ids.append(row.broker_order_record_id);row.raw_json={**dict(row.raw_json or {}),'m74_13_last_bootstrap_attempt_at':stamp}
        self.s.commit()
        from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
        from trading_ai.database.session import SessionLocal
        result=BrokerPortfolioSynchronizationService(SessionLocal).synchronize(portfolio_id,actor='M74_13_AUTO_BOOTSTRAP',connect_broker=True)
        self.s.expire_all()
        return {'triggered_by_broker_order_records':ids,'result':result}
    def cycle(self,portfolio_id="PAPER-PRIMARY"):
        policy=load_execution_intelligence_policy()
        if not policy.automatic_fill_management_enabled:
            return {"version":self.VERSION,"status":"DISABLED","historical_intents_repaired":0,"working_entries":0,"requested":0,"actions":{},"errors":[]}
        actions=Counter();errors=[];repaired=0
        try:
            sync=self._broker_sync_once(portfolio_id)
            self.s.expire_all()
        except Exception as exc:
            return {"version":self.VERSION,"status":"DEGRADED","broker_sync":None,"historical_intents_repaired":0,"working_entries":0,"requested":0,"actions":{"BROKER_SYNC_ERROR":1},"errors":[f"BROKER_SYNC: {type(exc).__name__}: {exc}"]}
        bootstrap_sync=None
        try:
            pending=self._platform_fills_needing_bootstrap(portfolio_id)
            if pending:
                bootstrap_sync=self._position_bootstrap_sync_once(portfolio_id,pending);actions['POSITION_BOOTSTRAP_SYNC']+=1
        except Exception as exc:
            self.s.rollback();errors.append(f"POSITION_BOOTSTRAP: {type(exc).__name__}: {exc}");actions['POSITION_BOOTSTRAP_ERROR']+=1
        intents=list(self.s.scalars(select(ExecutionIntentModel).where(ExecutionIntentModel.portfolio_id==portfolio_id,ExecutionIntentModel.state.in_(WORKING_STATES))))
        eligible=[];ws=ExecutionWorkspaceService(self.s)
        for original in intents:
            iid=original.execution_intent_id
            try:
                before=original.state
                truth=ws.reconcile_entry_with_broker_truth(iid,"M73_ENTRY_FILL_AUTO",policy.working_order_max_age_seconds)
                after=self.s.get(ExecutionIntentModel,iid)
                if after and after.state!=before:repaired+=1
                reason=str(truth.get('reason') or 'UNKNOWN')
                if truth.get('cancel_required'):
                    m=self.s.get(ExecutionIntentModel,iid)
                    if m and m.state in WORKING_STATES:
                        ws.cancel(iid,m.version,"M73_ENTRY_FILL_AUTO",reason)
                        actions[reason]+=1
                elif truth.get('eligible'):
                    eligible.append(iid)
                else:
                    actions[reason]+=1
            except Exception as exc:
                self.s.rollback();errors.append(f"{iid}: {type(exc).__name__}: {exc}");actions["RECONCILE_ERROR"]+=1
        for iid in eligible:
            try:
                m=self.s.get(ExecutionIntentModel,iid)
                if not m or m.state not in WORKING_STATES:continue
                assessment=ExecutionIntelligenceService(self.s).assess_working(iid,"M73_ENTRY_FILL_AUTO","Automatic bounded entry-fill assessment after broker-truth reconciliation")
                action=str(assessment.get("recommended_action") or "CONTINUE");action_reason=str(assessment.get('action_reason') or (assessment.get('evidence') or {}).get('action_reason') or action)
                if action=="REPRICE":
                    result=ws.reprice_working(iid,m.version,"M73_ENTRY_FILL_AUTO","Automatic adaptive monotonic chase inside frozen approval envelope",automatic=True)
                    entry_result=dict(result.get('entry_fill_result') or {})
                    actions[str(entry_result.get('action') or 'REPRICE')]+=1
                elif action=="CANCEL":
                    m=self.s.get(ExecutionIntentModel,iid)
                    if m and m.state in WORKING_STATES:ws.cancel(iid,m.version,"M73_ENTRY_FILL_AUTO",action_reason)
                    actions[action_reason]+=1
                else:
                    actions[action_reason]+=1
            except Exception as exc:
                self.s.rollback();errors.append(f"{iid}: {type(exc).__name__}: {exc}");actions["ERROR"]+=1
        return {"version":self.VERSION,"status":"READY" if not errors else "DEGRADED","broker_sync":sync,"position_bootstrap_sync":bootstrap_sync,"historical_intents_repaired":repaired,"working_entries":len(eligible),"requested":len(intents),"actions":dict(actions),"errors":errors}
