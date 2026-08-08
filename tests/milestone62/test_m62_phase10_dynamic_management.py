from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.dynamic_position_management.service import DynamicPositionManagementService
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.position_management.database_models import PositionExitInstructionModel


def position(mode='ADVISORY'):
    return ManagedPositionModel(
        position_id='POS-P10', portfolio_id='PAPER-PRIMARY', trade_plan_id='TP-P10',
        opportunity_id='OPP-P10', intelligence_id=None, execution_id='XI-P10', symbol='ALL',
        strategy='BULL_CALL_SPREAD', direction='BULLISH', state='OPEN', version=1,
        opened_at='2026-08-05T00:00:00+00:00', closed_at=None, entry_value=500,
        realized_pnl=0, mark_json={'mark_price':5,'quantity':1,'market_value':500,'unrealized_pnl':0,'unrealized_return_pct':0},
        health_json={'confidence':.8}, decision_json={'action':'HOLD'},
        metadata_json={'paper_only':True,'automation_mode':mode,'dynamic_management':{'underlying_stop':265.64,'underlying_targets':[306.91,326.26,355.28],'trailing_policy':'UNDERLYING_HIGHER_LOW','emergency_option_stop_pct':.55}},
        created_by='test', created_at='2026-08-05T00:00:00+00:00', updated_at='2026-08-05T00:00:00+00:00')


class StubService(DynamicPositionManagementService):
    def _market_snapshot(self, position, management):
        return {'underlying_price':260.0,'underlying_high':262.0,'underlying_low':259.0,'previous_low':270.0,'previous_high':280.0,'option_mark':2.0,'days_to_expiry':20,'implied_volatility':.3,'iv_change_pct':0,
                'mark':{'mark_price':2.0,'quantity':1,'market_value':200,'unrealized_pnl':-300,'unrealized_return_pct':-60,'delta':0,'gamma':0,'theta':0,'vega':0,'days_to_expiry':20}}
    def _submit_exit(self, position, instruction, actor):
        return {'status':'SUBMITTED','aggregate_id':'EXIT-1'}


def setup(mode='ADVISORY'):
    engine=create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    s=Session(engine); p=position(mode);s.add(p)
    s.add(PositionExitInstructionModel(instruction_id='PXI-STOP',assessment_id='XI-P10',position_id=p.position_id,action='CLOSE',quantity=1,status='ARMED',payload={'label':'STRUCTURAL_STOP','trigger_type':'UNDERLYING_PRICE','trigger_value':265.64},created_at='2026-08-05T00:00:00+00:00'))
    s.commit();return s


def test_advisory_trigger_is_persisted_without_submission():
    s=setup('ADVISORY'); result=StubService(s).evaluate_position('POS-P10');s.commit()
    instruction=s.scalar(select(PositionExitInstructionModel))
    assert result.status=='ACTION_TRIGGERED'
    assert instruction.status=='TRIGGERED_ADVISORY'


def test_fully_automatic_trigger_submits_paper_exit():
    s=setup('FULLY_AUTOMATIC'); result=StubService(s).evaluate_position('POS-P10');s.commit()
    instruction=s.scalar(select(PositionExitInstructionModel))
    assert result.triggered_instructions[0]['status']=='SUBMITTED'
    assert instruction.status=='SUBMITTED'
    assert instruction.payload['broker_submission']['status']=='SUBMITTED'


def test_automation_mode_is_governed_and_versioned():
    s=setup('ADVISORY'); payload=StubService(s).set_mode('POS-P10','SEMI_AUTOMATIC','tester','Require approval')
    assert payload['version']==2
    assert payload['metadata']['automation_mode']=='SEMI_AUTOMATIC'
