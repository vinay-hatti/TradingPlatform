from __future__ import annotations
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.dynamic_position_management.service import DynamicPositionManagementService


def scalar(session, sql):
    return session.execute(text(sql)).scalar_one()


def main():
    with SessionLocal() as session:
        managed=scalar(session,"SELECT COUNT(*) FROM managed_positions")
        active=scalar(session,"SELECT COUNT(*) FROM managed_positions WHERE state IN ('OPEN','PARTIAL','HEDGED','ROLLED')")
        armed=scalar(session,"SELECT COUNT(*) FROM position_exit_instructions WHERE status='ARMED'")
        missing=scalar(session,"SELECT COUNT(*) FROM managed_positions WHERE state IN ('OPEN','PARTIAL','HEDGED','ROLLED') AND COALESCE(metadata_json->>'management_activation','')<>'ACTIVE'")
        print(f'Managed positions: {managed}')
        print(f'Active managed positions: {active}')
        print(f'Armed exit instructions: {armed}')
        print(f'Active positions missing management activation: {missing}')
        result=DynamicPositionManagementService(session).evaluate_all(portfolio_id='PAPER-PRIMARY',actor='m62-phase10-verifier',submit_automatic=False)
        print(f'Advisory verification cycle: requested={result.requested}, evaluated={result.evaluated}, triggered={result.triggered}, failed={result.failed}')
        for error in result.errors[:20]: print(f'Verification error: {error}')
        if result.failed or missing:
            raise SystemExit('Milestone 62 Phase 10 operational acceptance FAILED')
        print('Milestone 62 Phase 10 operational acceptance PASSED')

if __name__=='__main__':main()
