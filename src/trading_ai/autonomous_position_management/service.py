
from __future__ import annotations
from datetime import date,datetime,time,timedelta,timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import func,select,text
from sqlalchemy.orm import Session
from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.dynamic_position_management.service import DynamicPositionManagementService
from trading_ai.portfolio_intelligence.models import ManagedPositionModel,PositionEventModel
from trading_ai.position_management.database_models import PositionExitInstructionModel
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
from .models import M73PositionManagerModel,M73ManagementDecisionModel,M73ExitReservationModel,M73ReplayEventModel
from .policy import load_m73_policy
from .quotes import M73LiveQuoteService,polygon_option_symbol_from_local_symbol

ACTIVE={'OPEN','PARTIAL','HEDGED','ROLLED'}
TERMINAL_INSTRUCTION={'FILLED','CANCELLED','CANCELED','REJECTED','FAILED','SUPERSEDED','COMPLETED'}

def now():return datetime.now(timezone.utc).isoformat()
def _f(v,d=None):
    try:return float(v)
    except (TypeError,ValueError):return d

class AutonomousPositionManagementService:
    VERSION='M64.2-GOVERNED-DEBIT-RISK+MANDATORY-PRE-EXPIRATION-EXIT-1.0'
    def __init__(self,session:Session,quote_service=None):self.s=session;self.policy=load_m73_policy();self.quotes=quote_service

    EXPIRATION_GUARD_LABEL='EXPIRATION_GUARD_EXIT'
    EXPIRATION_EXIT_TRADING_DAYS=1

    @staticmethod
    def _easter_sunday(year:int)->date:
        # Anonymous Gregorian algorithm; used only to derive Good Friday.
        a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3
        h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32+2*e+2*i-h-k)%7;m=(a+11*h+22*l)//451
        month=(h+l-7*m+114)//31;day=((h+l-7*m+114)%31)+1
        return date(year,month,day)

    @classmethod
    def _market_holidays(cls,year:int)->set[date]:
        def observed(d:date)->date:
            if d.weekday()==5:return d-timedelta(days=1)
            if d.weekday()==6:return d+timedelta(days=1)
            return d
        def nth_weekday(month:int,weekday:int,n:int)->date:
            d=date(year,month,1)
            return d+timedelta(days=((weekday-d.weekday())%7)+7*(n-1))
        def last_weekday(month:int,weekday:int)->date:
            d=date(year+1,1,1)-timedelta(days=1) if month==12 else date(year,month+1,1)-timedelta(days=1)
            return d-timedelta(days=(d.weekday()-weekday)%7)
        holidays={
            observed(date(year,1,1)),
            nth_weekday(1,0,3),
            nth_weekday(2,0,3),
            cls._easter_sunday(year)-timedelta(days=2),
            last_weekday(5,0),
            observed(date(year,6,19)),
            observed(date(year,7,4)),
            nth_weekday(9,0,1),
            nth_weekday(11,3,4),
            observed(date(year,12,25)),
        }
        # New Year's observed may fall in the prior calendar year.
        holidays.add(observed(date(year+1,1,1)))
        return holidays

    @classmethod
    def _previous_market_session(cls,expiry:date,sessions:int=1)->date:
        d=expiry
        remaining=max(1,int(sessions))
        while remaining>0:
            d-=timedelta(days=1)
            if d.weekday()<5 and d not in cls._market_holidays(d.year):
                remaining-=1
        return d

    def _expiration_guard_spec(self,p)->dict|None:
        tp=self.s.get(TradePlanModel,p.trade_plan_id)
        legs=list(tp.legs_json or []) if tp else self._broker_discovered_leg(p)
        expiries=[]
        for leg in legs:
            raw=str(leg.get('expiry') or leg.get('ibkr_expiry') or '')[:10]
            try:expiries.append(date.fromisoformat(raw))
            except Exception:pass
        if not expiries:return None
        earliest=min(expiries)
        exit_date=self._previous_market_session(earliest,self.EXPIRATION_EXIT_TRADING_DAYS)
        multi=len(legs)>1
        return {
            'earliest_expiry':earliest.isoformat(),
            'exit_on_or_before_date':exit_date.isoformat(),
            'minimum_trading_days_before_expiry':self.EXPIRATION_EXIT_TRADING_DAYS,
            'execution_scope':'FULL_STRATEGY' if multi else 'SINGLE_LEG',
            'exit_method':'ATOMIC_BAG' if multi else 'SINGLE_LEG',
            'strategy_level_exit':bool(multi),
            'includes_short_legs':any(str(x.get('side') or '').upper()=='SELL' for x in legs),
            'leg_count':len(legs),
        }

    def _ensure_expiration_guard(self,p,actor,quantity:int)->int:
        spec=self._expiration_guard_spec(p)
        if spec is None or quantity<=0:return 0
        active=[x for x in self._instructions(p.position_id) if x.status not in TERMINAL_INSTRUCTION and str((x.payload or {}).get('label') or '')==self.EXPIRATION_GUARD_LABEL]
        payload={
            'label':self.EXPIRATION_GUARD_LABEL,
            'trigger_type':'EXPIRATION_GUARD_DATE',
            'trigger_value':spec['exit_on_or_before_date'],
            'mandatory_exit':True,
            'governed_risk_basis':'PRE_EXPIRATION_DEFINED_RISK',
            'm64_2':True,
            'trade_plan_id':p.trade_plan_id,
            **spec,
        }
        if active:
            row=active[0];row.quantity=max(1,int(quantity));row.payload={**dict(row.payload or {}),**payload,'updated_at':now()}
            return 0
        generation=1+max([int((x.payload or {}).get('management_generation') or 0) for x in self._instructions(p.position_id)] or [0])
        self.s.add(PositionExitInstructionModel(instruction_id=f'PXI-{uuid4().hex.upper()}',assessment_id=f'M64-2-{p.position_id}',position_id=p.position_id,action='CLOSE',quantity=max(1,int(quantity)),status='ARMED',payload={**payload,'management_generation':generation,'armed_at':now(),'activation_reason':'MANDATORY_PRE_EXPIRATION_EXIT_POLICY'},created_at=now()))
        meta=dict(p.metadata_json or {})
        meta['expiration_exit_policy']={**spec,'label':self.EXPIRATION_GUARD_LABEL,'status':'ARMED','updated_at':now()}
        p.metadata_json=meta;p.version+=1;p.updated_at=now()
        self._event(p,'M64_2_EXPIRATION_GUARD_ARMED',actor,'Armed mandatory full-position exit before earliest option expiration',payload)
        return 1
    def _quote_service(self):
        if self.quotes is None:self.quotes=M73LiveQuoteService()
        return self.quotes
    def ensure_managers(self,portfolio_id='PAPER-PRIMARY',actor='m73-lifecycle')->dict:
        rows=list(self.s.scalars(select(ManagedPositionModel).where(ManagedPositionModel.portfolio_id==portfolio_id,ManagedPositionModel.state.in_(ACTIVE))))
        created=recovered=armed=0
        for p in rows:
            m=self.s.scalar(select(M73PositionManagerModel).where(M73PositionManagerModel.position_id==p.position_id))
            meta=dict(p.metadata_json or {})
            broker_discovered = bool(meta.get('broker_discovered')) or str(p.trade_plan_id or '').startswith('BROKER-DISCOVERED:')
            desired_mode = str(meta.get('automation_mode') or self.policy.default_automation_mode).upper()
            if broker_discovered: desired_mode='ADVISORY'
            elif desired_mode == 'ADVISORY': desired_mode='FULLY_AUTOMATIC'
            if m is None:
                m=M73PositionManagerModel(manager_id=f'M73-MGR-{uuid4().hex.upper()}',position_id=p.position_id,portfolio_id=p.portfolio_id,state='ACTIVE',automation_mode=desired_mode,protection_state='UNVERIFIED',heartbeat_at=now(),activated_at=now(),recovered_at=None,last_decision='HOLD',conviction_score=50.0,thesis_integrity=.5,metadata_json={'version':self.VERSION,'actor':actor});self.s.add(m);created+=1
                meta['automation_mode']=desired_mode;meta['m73_manager_id']=m.manager_id;meta['m73_management']='ACTIVE';meta.setdefault('paper_only',True);p.metadata_json=meta;p.version+=1;p.updated_at=now();self._event(p,'M73_MANAGER_ACTIVATED',actor,'Activated autonomous position manager',{'manager_id':m.manager_id,'automation_mode':desired_mode})
            else:
                m.heartbeat_at=now()
                if m.state!='ACTIVE':m.state='ACTIVE';m.recovered_at=now();recovered+=1
                if str(m.automation_mode or '').upper() != desired_mode:
                    previous_mode=m.automation_mode
                    m.automation_mode=desired_mode
                    m.metadata_json={**dict(m.metadata_json or {}),'automation_mode_promoted_at':now(),'previous_automation_mode':previous_mode,'promotion_reason':'M74_6_1_INSTITUTIONAL_POSITION_PROMOTION'}
                    meta['automation_mode']=desired_mode;p.metadata_json=meta;p.version+=1;p.updated_at=now();self._event(p,'M74_6_1_MANAGER_AUTOMATION_PROMOTED',actor,'Aligned manager automation mode with recovered institutional position lineage',{'previous_mode':previous_mode,'new_mode':desired_mode})
            instructions = self._instructions(p.position_id)
            active_instructions = [x for x in instructions if x.status not in TERMINAL_INSTRUCTION]
            authoritative_quantity = self._authoritative_quantity(p)
            # Broker quantity is the safety authority. Resize/cancel any still-active
            # instruction generation immediately so a partial exit can never over-close.
            self._resize_instructions(p, authoritative_quantity)
            instructions = self._instructions(p.position_id)
            active_instructions = [x for x in instructions if x.status not in TERMINAL_INSTRUCTION]
            if authoritative_quantity > 0 and not active_instructions:
                newly_armed = self._arm_from_plan(p, actor, quantity=authoritative_quantity)
                if newly_armed:
                    armed += newly_armed
                    md = dict(m.metadata_json or {})
                    md["last_rearmed_at"] = now()
                    md["last_rearmed_quantity"] = authoritative_quantity
                    md["last_rearmed_reason"] = "OPEN_BROKER_QUANTITY_WITHOUT_ACTIVE_EXIT_INSTRUCTIONS"
                    md["fill_adoption_source"] = "IBKR_BROKER_TRUTH"
                    m.metadata_json = md
                    self._event(
                        p,
                        "M73_EXIT_INSTRUCTIONS_REARMED",
                        actor,
                        "Re-armed autonomous exit instructions for broker-confirmed open quantity",
                        {"quantity": authoritative_quantity, "prior_instruction_count": len(instructions), "fill_adoption_source": "IBKR_BROKER_TRUTH"},
                    )
            # M64.2 mandatory expiry guard is independently enforced even when other exits already exist.
            if authoritative_quantity > 0:
                armed += self._ensure_expiration_guard(p, actor, authoritative_quantity)
            self._verify_protection(p,m)
            # M74.13 explicit ownership/bootstrap registry.  Institutional lineage
            # is not considered fully autonomous until the manager is active and at
            # least one non-terminal governed exit rule exists for broker truth qty.
            instructions = self._instructions(p.position_id)
            active_instructions = [x for x in instructions if x.status not in TERMINAL_INSTRUCTION]
            meta = dict(p.metadata_json or {})
            ownership = dict(meta.get('position_ownership') or {})
            if broker_discovered:
                ownership = {**ownership, 'origin': ownership.get('origin') or 'EXTERNAL_OR_UNVERIFIED', 'owner': 'MANUAL', 'status': ownership.get('status') or 'UNVERIFIED', 'lifecycle': 'MANUAL', 'bootstrap_state': 'MANUAL_REQUIRED', 'last_bootstrap_check_at': now()}
            else:
                bootstrap_ok = authoritative_quantity > 0 and str(m.state or '').upper() == 'ACTIVE' and desired_mode == 'FULLY_AUTOMATIC' and bool(active_instructions)
                prior_bootstrap = str(ownership.get('bootstrap_state') or '')
                ownership = {**ownership, 'origin': 'PLATFORM', 'owner': 'EXECUTION_WORKSPACE', 'status': 'VERIFIED', 'lifecycle': 'AUTONOMOUS', 'bootstrap_state': 'AUTO_MANAGED' if bootstrap_ok else 'AUTO_BOOTSTRAPPING', 'active_exit_count': len(active_instructions), 'manager_id': m.manager_id, 'manager_state': m.state, 'automation_mode': desired_mode, 'last_bootstrap_check_at': now()}
                if bootstrap_ok and prior_bootstrap != 'AUTO_MANAGED':
                    self._event(p,'M74_13_AUTONOMOUS_BOOTSTRAP_COMPLETED',actor,'Verified platform ownership and armed autonomous position management',{'manager_id':m.manager_id,'active_exit_count':len(active_instructions),'authoritative_quantity':authoritative_quantity})
            meta['position_ownership']=ownership
            meta['m74_13_bootstrap_state']=ownership.get('bootstrap_state')
            p.metadata_json=meta
            if authoritative_quantity > 0 and m.protection_state == 'UNPROTECTED':
                md=dict(m.metadata_json or {});md['governance_fault']='OPEN_PLATFORM_MANAGED_POSITION_WITHOUT_ACTIVE_EXIT_POLICY';md['governance_fault_at']=now();m.metadata_json=md
        self.s.commit();return {'version':self.VERSION,'positions':len(rows),'managers_created':created,'managers_recovered':recovered,'positions_armed':armed}
    def ensure_position(self,position_id:str,actor='m73-fill-activation')->dict:
        p=self.s.get(ManagedPositionModel,position_id)
        if not p:raise KeyError('Managed position not found')
        return self.ensure_managers(p.portfolio_id,actor)
    def _arm_from_plan(self,p,actor,quantity=None):
        meta=dict(p.metadata_json or {});mg=dict(meta.get('dynamic_management') or {})
        if not mg:
            # Advanced trade plans do not own a generic metadata_json column; dynamic
            # management lineage is carried on the managed position during platform handoff.
            tp=self.s.get(TradePlanModel,p.trade_plan_id);mg={} if tp else {}
        if not mg:return 0
        qty=max(1,int(round(_f(quantity, _f(p.mark_json.get('quantity'),1)) or 1)));items=[];stop=mg.get('current_underlying_stop',mg.get('underlying_stop'))
        if stop is not None:items.append(('STRUCTURAL_STOP','CLOSE',qty,{'label':'STRUCTURAL_STOP','trigger_type':'UNDERLYING_PRICE','trigger_value':stop,'trailing_policy':mg.get('trailing_policy')}))
        targets=[x for x in (mg.get('underlying_targets') or []) if _f(x) is not None];frac=float(mg.get('partial_profit_fraction') or .33)
        remaining=qty
        for i,t in enumerate(targets[:3],1):
            q=remaining if i==len(targets[:3]) else min(remaining,max(1,int(round(qty*frac))));remaining=max(0,remaining-q)
            if q>0:items.append((f'TARGET_{i}','CLOSE' if i==len(targets[:3]) else 'SCALE_OUT',q,{'label':f'TARGET_{i}','trigger_type':'UNDERLYING_PRICE','trigger_value':float(t),'target_index':i}))
        tp=self.s.get(TradePlanModel,p.trade_plan_id)
        legs=list(tp.legs_json or []) if tp else []
        short_legs=[leg for leg in legs if str(leg.get('side') or '').upper()=='SELL']
        assignment_rule=str(mg.get('assignment_risk_rule') or '').upper()
        if short_legs and assignment_rule:
            assignment_days=max(1,int(mg.get('assignment_risk_days_to_expiry') or mg.get('theta_exit_days_to_expiry') or 5))
            items.append(('SHORT_LEG_ASSIGNMENT_EXIT','CLOSE',qty,{'label':'SHORT_LEG_ASSIGNMENT_EXIT','trigger_type':'SHORT_LEG_DTE','trigger_value':assignment_days,'assignment_risk_rule':assignment_rule,'execution_scope':'FULL_STRATEGY','exit_method':'ATOMIC_BAG','short_leg_count':len(short_legs)}))
        if mg.get('theta_exit_days_to_expiry') is not None:items.append(('THETA_EXIT','CLOSE',qty,{'label':'THETA_EXIT','trigger_type':'DTE','trigger_value':mg['theta_exit_days_to_expiry'],'execution_scope':'FULL_STRATEGY' if len(legs)>1 else 'SINGLE_LEG','exit_method':'ATOMIC_BAG' if len(legs)>1 else 'SINGLE_LEG'}))
        if mg.get('volatility_exit_rule'):items.append(('VOLATILITY_EXIT','CLOSE',qty,{'label':'VOLATILITY_EXIT','trigger_type':'VOLATILITY_RULE','trigger_value':mg['volatility_exit_rule'],'execution_scope':'FULL_STRATEGY' if len(legs)>1 else 'SINGLE_LEG','exit_method':'ATOMIC_BAG' if len(legs)>1 else 'SINGLE_LEG'}))
        if mg.get('emergency_option_stop_pct') is not None:items.append(('EMERGENCY_OPTION_STOP','CLOSE',qty,{'label':'EMERGENCY_OPTION_STOP','trigger_type':'OPTION_LOSS_PCT','trigger_value':mg['emergency_option_stop_pct'],'execution_scope':'FULL_STRATEGY' if len(legs)>1 else 'SINGLE_LEG','exit_method':'ATOMIC_BAG' if len(legs)>1 else 'SINGLE_LEG'}))
        if len(legs)>1:
            items=[(label,action,q,{**payload,'execution_scope':'FULL_STRATEGY','exit_method':'ATOMIC_BAG'}) for label,action,q,payload in items]
        generation=1+max([int((x.payload or {}).get('management_generation') or 0) for x in self._instructions(p.position_id)] or [0])
        for label,action,q,payload in items:self.s.add(PositionExitInstructionModel(instruction_id=f'PXI-{uuid4().hex.upper()}',assessment_id=f'M73-{p.position_id}',position_id=p.position_id,action=action,quantity=int(q),status='ARMED',payload={**payload,'m73':True,'trade_plan_id':p.trade_plan_id,'management_generation':generation,'activation_reason':'OPEN_BROKER_QUANTITY_WITHOUT_ACTIVE_EXIT_INSTRUCTIONS'},created_at=now()))
        if items:self._event(p,'M73_EXIT_INSTRUCTIONS_ARMED',actor,'Armed dynamic position-management instructions',{'count':len(items)})
        return 1 if items else 0
    def _verify_protection(self,p,m):
        armed=[x for x in self._instructions(p.position_id) if x.status not in TERMINAL_INSTRUCTION]
        emergency=any((x.payload or {}).get('label') in {'STRUCTURAL_STOP','EMERGENCY_OPTION_STOP'} for x in armed)
        m.protection_state='PLATFORM_PROTECTED' if emergency else 'UNPROTECTED'
        expiration_guard=next((x for x in armed if (x.payload or {}).get('label')==self.EXPIRATION_GUARD_LABEL),None)
        md=dict(m.metadata_json or {});md['active_instruction_count']=len(armed);md['emergency_rule_present']=emergency;md['expiration_guard_present']=bool(expiration_guard);md['expiration_exit_on_or_before']=(expiration_guard.payload or {}).get('exit_on_or_before_date') if expiration_guard else None;m.metadata_json=md
    def _authoritative_quantity(self,p)->int:
        rows=list(self.s.scalars(select(BrokerCurrentPositionModel).where(BrokerCurrentPositionModel.portfolio_id==p.portfolio_id,BrokerCurrentPositionModel.active.is_(True),BrokerCurrentPositionModel.managed_position_id==p.position_id)))
        if rows:
            meta=dict(p.metadata_json or {});ratios=dict(meta.get('broker_leg_ratios') or {})
            units=[]
            for r in rows:
                ratio=max(1,int(ratios.get(str(r.contract_id),1) or 1))
                units.append(abs(float(r.signed_quantity or 0))/ratio)
            return max(0,int(round(min(units)))) if units else 0
        return max(0,int(round(_f(p.mark_json.get('quantity'),0) or 0)))
    def _resize_instructions(self,p,qty):
        active=[x for x in self._instructions(p.position_id) if x.status in {'ARMED','SUBMISSION_FAILED','PENDING_APPROVAL','TRIGGERED_ADVISORY'}]
        targets=[x for x in active if str((x.payload or {}).get('label','')).startswith('TARGET_')];remaining=qty
        for x in sorted(targets,key=lambda z:int((z.payload or {}).get('target_index') or 99)):
            x.quantity=max(0,min(int(x.quantity),remaining));remaining=max(0,remaining-int(x.quantity))
        for x in active:
            if x not in targets:x.quantity=max(0,min(int(x.quantity),qty))
            if x.quantity<=0:x.status='CANCELLED';pl=dict(x.payload or {});pl['cancel_reason']='NO_REMAINING_BROKER_QUANTITY';pl['cancelled_at']=now();x.payload=pl
    @staticmethod
    def _market_session_state(at:datetime|None=None)->str:
        dt=(at or datetime.now(timezone.utc)).astimezone(ZoneInfo('America/New_York'))
        if dt.weekday()>=5:return 'MARKET_CLOSED'
        # Deliberately allow through 16:15 ET to cover index/ETF option products.
        # Exchange holidays remain fail-closed as stale-data degradation rather than
        # being guessed from an incomplete embedded holiday calendar.
        local_t=dt.time().replace(tzinfo=None)
        return 'MARKET_OPEN' if time(9,30)<=local_t<=time(16,15) else 'MARKET_CLOSED'
    def _broker_discovered_leg(self,p)->list[dict]:
        row=self.s.scalar(select(BrokerCurrentPositionModel).where(BrokerCurrentPositionModel.managed_position_id==p.position_id,BrokerCurrentPositionModel.active.is_(True)))
        if row is None:return []
        option_symbol=polygon_option_symbol_from_local_symbol(row.local_symbol) if str(row.security_type).upper()=='OPT' else None
        if not option_symbol:return []
        compact=option_symbol[2:] if option_symbol.startswith('O:') else option_symbol
        # OCC identity YYMMDD immediately precedes C/P + strike. Preserve IBKR expiry
        # independently because it may represent last-trading date (e.g. SPX).
        import re
        m=re.fullmatch(r'([A-Z0-9.]{1,8})(\d{6})([CP])(\d{8})',compact)
        occ_expiry=None
        if m:
            yy,mm,dd=m.group(2)[:2],m.group(2)[2:4],m.group(2)[4:6]
            occ_expiry=f'20{yy}-{mm}-{dd}'
        return [{'option_symbol':option_symbol,'local_symbol':row.local_symbol,'side':'BUY' if float(row.signed_quantity or 0)>=0 else 'SELL','quantity':max(1,int(round(abs(float(row.signed_quantity or 0))))),'expiry':occ_expiry,'ibkr_expiry':row.expiry,'strike':row.strike,'right':row.right,'contract_id':row.contract_id,'source':'IBKR_BROKER_DISCOVERED'}]
    def _build_live_market(self,p)->dict:
        tp=self.s.get(TradePlanModel,p.trade_plan_id);legs=list(tp.legs_json or []) if tp else self._broker_discovered_leg(p)
        if not legs:
            raise RuntimeError('M73 has no canonical executable option identity for position')
        q=self._quote_service().snapshot(p.symbol,legs,self.policy.max_quote_age_seconds)
        if not q['quote_fresh']:
            state=self._market_session_state()
            if state=='MARKET_CLOSED':
                return {'source':'POLYGON_DIRECT','market_session_state':'MARKET_CLOSED','market_closed_idle':True,'quote_age_seconds':q['max_quote_age_seconds'],'live_legs':q['live_legs'],'underlying_price':q['underlying_price'],'option_mark':q['option_mark'],'underlying_fallback_used':q.get('underlying_fallback_used',False)}
            raise RuntimeError(f"M73 refuses stale market snapshot: age={q['max_quote_age_seconds']:.2f}s policy={self.policy.max_quote_age_seconds:.2f}s")
        initial_iv=_f((p.metadata_json or {}).get('entry_implied_volatility'));iv=q.get('implied_volatility');ivchg=(iv-initial_iv)/initial_iv if initial_iv and iv is not None else None
        entry=max(_f(p.entry_value,0) or 0,.01);qty=max(1,self._authoritative_quantity(p));mv=abs(float(q.get('option_mark') or 0))*qty*100;upnl=mv-entry;dte=None
        expiries=[]
        for leg in legs:
            try:expiries.append(date.fromisoformat(str(leg.get('expiry'))[:10]))
            except Exception:pass
        if expiries:dte=min((x-date.today()).days for x in expiries)
        short_leg_dtes=[];short_leg_symbols=[]
        for leg in legs:
            if str(leg.get('side') or '').upper()!='SELL':continue
            short_leg_symbols.append(str(leg.get('option_symbol') or leg.get('local_symbol') or ''))
            try:short_leg_dtes.append((date.fromisoformat(str(leg.get('expiry'))[:10])-date.today()).days)
            except Exception:pass
        short_leg_dte=min(short_leg_dtes) if short_leg_dtes else None
        strategy_lifecycle={'strategy':str(p.strategy or ''),'multi_leg':len(legs)>1,'leg_count':len(legs),'short_leg_count':len(short_leg_symbols),'short_leg_symbols':short_leg_symbols,'short_leg_dte':short_leg_dte,'short_leg_monitored':bool(short_leg_symbols),'assignment_risk_rule':str((p.metadata_json or {}).get('dynamic_management',{}).get('assignment_risk_rule') or ''),'assignment_risk_days_to_expiry':int((p.metadata_json or {}).get('dynamic_management',{}).get('assignment_risk_days_to_expiry') or (p.metadata_json or {}).get('dynamic_management',{}).get('theta_exit_days_to_expiry') or 5) if short_leg_symbols else None,'exit_execution_method':'ATOMIC_BAG' if len(legs)>1 else 'SINGLE_LEG','short_leg_roll_enabled':False,'short_leg_policy':'CLOSE_FULL_STRATEGY_BEFORE_ASSIGNMENT_RISK' if short_leg_symbols else 'NOT_APPLICABLE'}
        if short_leg_dte is not None and short_leg_dte<=int(strategy_lifecycle['assignment_risk_days_to_expiry'] or 5):strategy_lifecycle['next_autonomous_action']='CLOSE_FULL_STRATEGY_BEFORE_ASSIGNMENT_RISK'
        elif short_leg_symbols:strategy_lifecycle['next_autonomous_action']='MONITOR_SHORT_LEG'
        else:strategy_lifecycle['next_autonomous_action']='MONITOR_POSITION'
        return {'source':'POLYGON_DIRECT','market_session_state':'MARKET_OPEN','market_closed_idle':False,'underlying_price':q['underlying_price'],'underlying_high':None,'underlying_low':None,'previous_low':None,'previous_high':None,'option_mark':q['option_mark'],'days_to_expiry':dte,'short_leg_dte':short_leg_dte,'strategy_lifecycle':strategy_lifecycle,'implied_volatility':iv,'iv_change_pct':ivchg,'quote_age_seconds':q['max_quote_age_seconds'],'live_legs':q['live_legs'],'mark':{'mark_price':q['option_mark'],'quantity':qty,'market_value':mv,'unrealized_pnl':upnl,'unrealized_return_pct':upnl/entry*100,'delta':q['delta'],'gamma':q['gamma'],'theta':q['theta'],'vega':q['vega'],'days_to_expiry':dte}}
    def _intelligence(self,p,market):
        meta=dict(p.metadata_json or {});health=dict(p.health_json or {});mg=dict(meta.get('dynamic_management') or {})
        trend=_f(meta.get('trend_score'),_f(health.get('trend_score'),50)) or 50;dealer=_f(meta.get('dealer_score'),50) or 50;portfolio=_f(meta.get('portfolio_fit_score'),50) or 50
        # M68.2 uses only exact, non-abstaining directional authority.  Signal
        # strength is not direction; translate the signed score into alignment
        # with the position and otherwise contribute a neutral 50.
        inf=dict(meta.get('inflection_intelligence') or {});inf_lineage=dict(inf.get('lineage') or {});position_lineage=dict(meta.get('m62_lineage') or {});position_run=str(position_lineage.get('stock_scanner_run_id') or '');inflection=50.0
        inf_exact=(inf.get('coverage_status')=='CURRENT_EXACT' and inf.get('disposition')!='ABSTAIN' and (not position_run or str(inf_lineage.get('stock_scanner_run_id') or '')==position_run))
        if inf_exact:
            signed=_f(inf.get('directional_score'),0) or 0;position_sign=-1 if str(p.direction).upper().startswith('BEAR') else 1 if str(p.direction).upper().startswith('BULL') else 0;inflection=max(0,min(100,50+position_sign*signed/2)) if position_sign else 50
        # M71.4 OPEX remains evidence-only.  An unapproved or merely present
        # opex_score must never influence autonomous position management.
        opex_status=str(meta.get('opex_governance_status') or 'ABSTAIN').upper()
        opex=(_f(meta.get('opex_score'),50) or 50) if opex_status=='HUMAN_APPROVED' else 50
        ret=_f(market.get('mark',{}).get('unrealized_return_pct'),0) or 0;theta_penalty=min(25,max(0,-_f(market.get('mark',{}).get('theta'),0) or 0)*5);dte=market.get('days_to_expiry');time_score=80 if dte is None else max(20,min(100,dte*5))
        components={'TREND':(trend,.22),'DEALER':(dealer,.15),'INFLECTION':(inflection,.18),'PORTFOLIO':(portfolio,.10),'OPEX':(opex,.10),'TIME':(time_score,.10),'PNL':(max(0,min(100,50+ret)),.15)}
        contributions=[];score=0
        for name,(val,w) in components.items():score+=val*w;contributions.append({'factor':name,'score':round(val,2),'weight':w,'contribution':round(val*w,2)})
        score=max(0,min(100,score-theta_penalty));thesis=max(0,min(1,score/100))
        return round(score,2),round(thesis,4),contributions
    def _decision(self,p,market,conviction,thesis):
        mg=dict((p.metadata_json or {}).get('dynamic_management') or {});stop=_f(mg.get('current_underlying_stop',mg.get('underlying_stop')));targets=[float(x) for x in (mg.get('underlying_targets') or []) if _f(x) is not None];price=_f(market.get('underlying_price'));direction=str(p.direction).upper();next_target=None
        if price is not None:
            next_target=next((x for x in sorted(targets) if x>price),None) if direction in {'BULLISH','CALL'} else next((x for x in sorted(targets,reverse=True) if x<price),None)
        if thesis<.35:return 'EMERGENCY_EXIT',.95,stop,next_target,'Trade thesis integrity fell below governed emergency threshold'
        if thesis<.50:return 'EXIT',.88,stop,next_target,'Trade thesis materially deteriorated'
        if thesis<.62:return 'REDUCE',.78,stop,next_target,'Trade thesis weakened; reduce risk'
        if conviction>=78:return 'TRAIL',.80,stop,next_target,'High conviction supports holding while tightening risk'
        return 'HOLD',max(.55,thesis),stop,next_target,'No governed exit condition currently dominates'
    def _record_decision(self,p,mgr,action,confidence,conviction,thesis,stop,target,evidence,explanation):
        row=M73ManagementDecisionModel(decision_id=f'M73-DEC-{uuid4().hex.upper()}',position_id=p.position_id,manager_id=mgr.manager_id,cycle_timestamp=now(),action=action,confidence=float(confidence),conviction_score=conviction,thesis_integrity=thesis,current_stop=stop,current_target=target,evidence_json=evidence,explanation=explanation);self.s.add(row)
        seq=(self.s.scalar(select(func.max(M73ReplayEventModel.sequence_no)).where(M73ReplayEventModel.position_id==p.position_id)) or 0)+1
        self.s.add(M73ReplayEventModel(event_id=f'M73-RPL-{uuid4().hex.upper()}',position_id=p.position_id,event_timestamp=row.cycle_timestamp,sequence_no=seq,event_type='MANAGEMENT_DECISION',payload_json={'action':action,'confidence':confidence,'conviction':conviction,'thesis_integrity':thesis,'evidence':evidence,'explanation':explanation}))
    def _reserve_one_exit(self,p)->None:
        active=list(self.s.scalars(select(M73ExitReservationModel).where(M73ExitReservationModel.position_id==p.position_id,M73ExitReservationModel.status.in_(['RESERVED','SUBMITTED','PARTIAL']))))
        if active:
            # suppress every other trigger while an exit is working
            for x in self._instructions(p.position_id):
                if x.instruction_id!=active[0].instruction_id and x.status=='READY_FOR_AUTOMATIC_SUBMISSION':x.status='ARMED'
            return
    def run_cycle(self,portfolio_id='PAPER-PRIMARY',actor='m73-autonomous-manager',submit_automatic=True,limit=250)->dict:
        if not self.policy.enabled:return {'version':self.VERSION,'status':'DISABLED'}
        activation=self.ensure_managers(portfolio_id,actor);rows=list(self.s.scalars(select(ManagedPositionModel).where(ManagedPositionModel.portfolio_id==portfolio_id,ManagedPositionModel.state.in_(ACTIVE)).limit(limit)));evaluated=failed=0;errors=[];actions={}
        for p in rows:
            try:
                mgr=self.s.scalar(select(M73PositionManagerModel).where(M73PositionManagerModel.position_id==p.position_id));qty=self._authoritative_quantity(p);self._resize_instructions(p,qty)
                if qty<=0:continue
                live=self._build_live_market(p);meta=dict(p.metadata_json or {});meta['m73_live_market']=live;meta['strategy_lifecycle']=dict(live.get('strategy_lifecycle') or {});meta['last_m73_quote_at']=now();p.metadata_json=meta
                if live.get('market_closed_idle'):
                    mgr.heartbeat_at=now();mgr.last_decision='MARKET_CLOSED_IDLE';mgr.metadata_json={**dict(mgr.metadata_json or {}),'market_session_state':'MARKET_CLOSED','last_quote_age_seconds':live.get('quote_age_seconds'),'current_quantity':qty}
                    evaluated+=1;actions['MARKET_CLOSED_IDLE']=actions.get('MARKET_CLOSED_IDLE',0)+1;self._verify_protection(p,mgr);self.s.commit();continue
                conviction,thesis,contrib=self._intelligence(p,live);action,conf,stop,target,explain=self._decision(p,live,conviction,thesis)
                mgr.heartbeat_at=now();mgr.last_decision=action;mgr.conviction_score=conviction;mgr.thesis_integrity=thesis;mgr.metadata_json={**dict(mgr.metadata_json or {}),'last_quote_age_seconds':live['quote_age_seconds'],'current_quantity':qty,'decision_decomposition':contrib}
                self._record_decision(p,mgr,action,conf,conviction,thesis,stop,target,{'market':live,'decomposition':contrib},explain);self._reserve_one_exit(p)
                # M62 is still the trigger/routing implementation, but now reads the M73 fresh snapshot and uses a single trigger per cycle.
                result=DynamicPositionManagementService(self.s).evaluate_position(p.position_id,actor=actor,submit_automatic=submit_automatic);evaluated+=1;actions[action]=actions.get(action,0)+1
                self._verify_protection(p,mgr);self.s.commit()
            except Exception as exc:self.s.rollback();failed+=1;errors.append(f'{p.position_id}: {type(exc).__name__}: {exc}')
        return {'version':self.VERSION,'status':'READY' if failed==0 else 'DEGRADED','activation':activation,'requested':len(rows),'evaluated':evaluated,'failed':failed,'actions':actions,'errors':errors}
    def dashboard(self,portfolio_id='PAPER-PRIMARY')->dict:
        managers=list(self.s.scalars(select(M73PositionManagerModel).where(M73PositionManagerModel.portfolio_id==portfolio_id)));decisions=list(self.s.scalars(select(M73ManagementDecisionModel).order_by(M73ManagementDecisionModel.cycle_timestamp.desc()).limit(50)));unprotected=sum(1 for x in managers if x.protection_state=='UNPROTECTED');working=sum(1 for x in self.s.scalars(select(PositionExitInstructionModel)) if x.status in {'SUBMITTED','ACKNOWLEDGED','PARTIAL','REPRICE_PENDING'})
        return {'version':self.VERSION,'portfolio_id':portfolio_id,'managed_positions':len(managers),'healthy':sum(1 for x in managers if x.state=='ACTIVE' and x.protection_state!='UNPROTECTED'),'unprotected':unprotected,'working_exit_orders':working,'average_conviction':round(sum(x.conviction_score for x in managers)/len(managers),2) if managers else 0,'managers':[{'manager_id':x.manager_id,'position_id':x.position_id,'state':x.state,'automation_mode':x.automation_mode,'protection_state':x.protection_state,'heartbeat_at':x.heartbeat_at,'last_decision':x.last_decision,'conviction_score':x.conviction_score,'thesis_integrity':x.thesis_integrity} for x in managers],'recent_decisions':[{'decision_id':x.decision_id,'position_id':x.position_id,'cycle_timestamp':x.cycle_timestamp,'action':x.action,'confidence':x.confidence,'conviction_score':x.conviction_score,'thesis_integrity':x.thesis_integrity,'explanation':x.explanation} for x in decisions]}
    def _instructions(self,position_id):return list(self.s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id==position_id).order_by(PositionExitInstructionModel.id)))
    def _event(self,p,event,actor,reason,payload):self.s.add(PositionEventModel(event_id=f'PE-{uuid4().hex.upper()}',position_id=p.position_id,position_version=p.version,event_type=event,actor=actor,reason=reason,event_timestamp=now(),payload_json=payload))
