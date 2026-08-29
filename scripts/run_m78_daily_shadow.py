#!/usr/bin/env python3
"""Idempotent daily M78 shadow orchestration.

Capture setup state -> attach any already-mature M77 labels -> score with the
explicitly activated shadow model if present. Training/approval/activation and
certification are never automatic.
"""
from __future__ import annotations
import json
from trading_ai.database.session import SessionLocal
from trading_ai.setup_intelligence.service import SetupIntelligenceService


def main():
    with SessionLocal() as session:
        svc=SetupIntelligenceService(session)
        capture=svc.capture()
        outcomes=svc.materialize_outcomes()
        prediction=svc.predict_latest()
        result={"status":"READY","capture":capture,"outcomes":outcomes,"prediction":prediction,
                "automatic_training":False,"automatic_activation":False,"automatic_certification":False,"authority_effect":False}
    print(json.dumps(result,indent=2,sort_keys=True,default=str)); return 0

if __name__=="__main__": raise SystemExit(main())
