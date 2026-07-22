from __future__ import annotations
import hashlib, json
from dataclasses import replace
from pathlib import Path
from typing import Any
from .policy import ExecutionOrchestrationPolicy
from .profile import ExecutionEvent, ExecutionOrder, ExecutionWorkflowResult, utc_now_iso
from .serialization import read_json, write_json_atomic

class ExecutionOrchestrationService:
    def __init__(self, policy: ExecutionOrchestrationPolicy|None=None):
        self.policy=policy or ExecutionOrchestrationPolicy(); self.policy.validate()

    @staticmethod
    def _fingerprint(value: Any) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()[:20].upper()

    def _load_queue(self,path:Path)->dict[str,Any]:
        payload=read_json(path)
        payload.setdefault('orders',[]); payload.setdefault('updated_at',utc_now_iso())
        return payload

    def ingest_handoff(self,handoff_file:Path,queue_file:Path)->tuple[list[ExecutionOrder],list[ExecutionEvent]]:
        handoff=read_json(handoff_file); queue=self._load_queue(queue_file)
        existing={str(x.get('execution_order_id')):x for x in queue['orders']}
        created=[]; events=[]
        for raw in handoff.get('orders',[])[:self.policy.maximum_orders_per_run]:
            stable=self._fingerprint({'portfolio_id':handoff.get('portfolio_id','PRIMARY'),'client_order_id':raw.get('client_order_id'),'source_candidate_id':raw.get('source_candidate_id'),'symbol':raw.get('symbol'),'strategy':raw.get('strategy')})
            oid=f'M38-ORDER-{stable}'
            if oid in existing: continue
            order=ExecutionOrder(execution_order_id=oid,client_order_id=str(raw.get('client_order_id',oid)),portfolio_id=str(handoff.get('portfolio_id','PRIMARY')),symbol=str(raw.get('symbol','')).upper(),strategy=str(raw.get('strategy','UNKNOWN')).upper(),direction=str(raw.get('direction','UNKNOWN')).upper(),contracts=max(1,int(raw.get('contracts',1))),capital_limit=max(0.0,float(raw.get('capital_limit',0.0))),source_candidate_id=str(raw.get('source_candidate_id','')),metadata={'source_handoff':str(handoff_file),'handoff_id':handoff.get('handoff_id')})
            created.append(order); existing[oid]=order.to_dict()
            events.append(ExecutionEvent(event_id=f'M38-EVENT-{self._fingerprint([oid,"INTAKE"])}',execution_order_id=oid,event_type='HANDOFF_INGESTED',from_status='NONE',to_status=order.status,details={'source_handoff':str(handoff_file)}))
        queue['orders']=list(existing.values()); queue['updated_at']=utc_now_iso(); write_json_atomic(queue_file,queue)
        return created,events

    def apply_risk_control(self,queue_file:Path,risk_control_file:Path,event_file:Path)->dict[str,Any]:
        queue=self._load_queue(queue_file); risk=read_json(risk_control_file)
        control=str(risk.get('trading_control',risk.get('risk_status','UNKNOWN'))).upper()
        allow=bool(risk.get('allow_new_risk',control in self.policy.allowed_controls))
        events_payload=read_json(event_file); events=list(events_payload.get('events',[])); seen={x.get('event_id') for x in events}
        updated=[]; counts={'released':0,'blocked':0,'review':0}
        for raw in queue['orders']:
            if raw.get('status') not in {'PENDING_PRETRADE_RISK','RISK_REVIEW_REQUIRED','RISK_BLOCKED','APPROVED'}:
                updated.append(raw); continue
            before=str(raw.get('status'))
            if control in self.policy.hard_block_controls or not allow:
                after='RISK_BLOCKED'; approval='BLOCKED'; counts['blocked']+=1
            elif control=='ALLOW_WITH_WARNING' and self.policy.require_manual_approval_for_warning:
                after='RISK_REVIEW_REQUIRED'; approval='PENDING'; counts['review']+=1
            elif self.policy.allow_auto_release_when_risk_allows:
                after='RELEASED_TO_BROKER'; approval='AUTO_APPROVED'; counts['released']+=1
            else:
                after='APPROVED'; approval='RISK_APPROVED'; counts['review']+=1
            raw={**raw,'status':after,'risk_status':control,'approval_status':approval,'updated_at':utc_now_iso(),'metadata':{**raw.get('metadata',{}),'risk_assessment_id':risk.get('assessment_id'),'blocking_breach_ids':risk.get('blocking_breach_ids',[])}}
            updated.append(raw)
            eid=f'M38-EVENT-{self._fingerprint([raw["execution_order_id"],before,after,control])}'
            if eid not in seen:
                events.append(ExecutionEvent(eid,raw['execution_order_id'],'RISK_CONTROL_APPLIED',before,after,details={'trading_control':control}).to_dict()); seen.add(eid)
        queue['orders']=updated; queue['updated_at']=utc_now_iso(); write_json_atomic(queue_file,queue); write_json_atomic(event_file,{'events':events,'updated_at':utc_now_iso()})
        return {'trading_control':control,'allow_new_risk':allow,**counts,'order_count':len(updated)}

    def approve(self,queue_file:Path,event_file:Path,execution_order_id:str,approved_by:str)->dict[str,Any]:
        queue=self._load_queue(queue_file); events_payload=read_json(event_file); events=list(events_payload.get('events',[]))
        found=None; updated=[]
        for raw in queue['orders']:
            if raw.get('execution_order_id')!=execution_order_id: updated.append(raw); continue
            if raw.get('status')=='RISK_BLOCKED': raise ValueError('Risk-blocked order cannot be approved')
            before=str(raw.get('status')); raw={**raw,'status':'RELEASED_TO_BROKER','approval_status':'MANUALLY_APPROVED','updated_at':utc_now_iso(),'metadata':{**raw.get('metadata',{}),'approved_by':approved_by}}
            found=raw; updated.append(raw)
            eid=f'M38-EVENT-{self._fingerprint([execution_order_id,"MANUAL_APPROVAL",approved_by])}'
            if not any(x.get('event_id')==eid for x in events): events.append(ExecutionEvent(eid,execution_order_id,'MANUAL_APPROVAL',before,'RELEASED_TO_BROKER',details={'approved_by':approved_by}).to_dict())
        if found is None: raise KeyError(execution_order_id)
        queue['orders']=updated; queue['updated_at']=utc_now_iso(); write_json_atomic(queue_file,queue); write_json_atomic(event_file,{'events':events,'updated_at':utc_now_iso()}); return found

    def reconcile_broker_state(self,queue_file:Path,event_file:Path,broker_state_file:Path)->dict[str,int]:
        queue=self._load_queue(queue_file); states=read_json(broker_state_file).get('orders',[]); by_client={str(x.get('client_order_id')):x for x in states}
        events_payload=read_json(event_file); events=list(events_payload.get('events',[])); changed=0; updated=[]
        for raw in queue['orders']:
            state=by_client.get(str(raw.get('client_order_id')))
            if not state: updated.append(raw); continue
            broker_status=str(state.get('status','UNKNOWN')).upper(); mapped={'ACCEPTED':'SUBMITTED','WORKING':'WORKING','PARTIALLY_FILLED':'PARTIALLY_FILLED','FILLED':'FILLED','CANCELED':'CANCELED','REJECTED':'REJECTED','EXPIRED':'EXPIRED'}.get(broker_status,raw.get('status'))
            before=str(raw.get('status'))
            new={**raw,'status':mapped,'broker_order_id':state.get('broker_order_id',raw.get('broker_order_id')),'filled_quantity':float(state.get('filled_quantity',raw.get('filled_quantity',0.0)) or 0.0),'average_fill_price':state.get('average_fill_price',raw.get('average_fill_price')),'updated_at':utc_now_iso()}
            updated.append(new)
            if before!=mapped:
                changed+=1; eid=f'M38-EVENT-{self._fingerprint([raw["execution_order_id"],before,mapped,state.get("updated_at")])}'
                if not any(x.get('event_id')==eid for x in events): events.append(ExecutionEvent(eid,raw['execution_order_id'],'BROKER_RECONCILIATION',before,mapped,details={'broker_order_id':new.get('broker_order_id')}).to_dict())
        queue['orders']=updated; queue['updated_at']=utc_now_iso(); write_json_atomic(queue_file,queue); write_json_atomic(event_file,{'events':events,'updated_at':utc_now_iso()})
        return {'orders':len(updated),'changed':changed}

    def run(self,handoff_file:Path,risk_control_file:Path,output_dir:Path)->ExecutionWorkflowResult:
        output_dir.mkdir(parents=True,exist_ok=True); queue_file=output_dir/'execution_queue.json'; event_file=output_dir/'execution_events.json'
        created,intake_events=self.ingest_handoff(handoff_file,queue_file)
        ep=read_json(event_file); merged=list(ep.get('events',[])); ids={x.get('event_id') for x in merged}
        for event in intake_events:
            if event.event_id not in ids: merged.append(event.to_dict()); ids.add(event.event_id)
        write_json_atomic(event_file,{'events':merged,'updated_at':utc_now_iso()})
        control=self.apply_risk_control(queue_file,risk_control_file,event_file)
        result=ExecutionWorkflowResult(run_id=f'M38-RUN-{self._fingerprint([str(handoff_file),str(risk_control_file),read_json(queue_file)])}',status='BLOCKED' if control['blocked'] else ('REVIEW_REQUIRED' if control['review'] else 'READY'),trading_control=control['trading_control'],intake_count=len(created),released_count=control['released'],blocked_count=control['blocked'],review_count=control['review'],queue_file=str(queue_file),event_file=str(event_file),execution_control_file=str(risk_control_file),warnings=tuple(['NO_NEW_ORDERS'] if not created else []))
        write_json_atomic(output_dir/'workflow_result.json',result.to_dict()); return result
