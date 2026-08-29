#!/usr/bin/env python
from __future__ import annotations
import argparse, json
from trading_ai.database.session import SessionLocal
from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService


def main():
    p=argparse.ArgumentParser(description='M64.2 arm/refresh mandatory pre-expiration exits for all active managed option positions')
    p.add_argument('--portfolio-id',default='PAPER-PRIMARY')
    a=p.parse_args()
    with SessionLocal() as session:
        result=AutonomousPositionManagementService(session).ensure_managers(a.portfolio_id,actor='m64.2-expiration-guard-repair')
        print(json.dumps(result,indent=2,default=str))

if __name__=='__main__':main()
