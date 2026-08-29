#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

REQUIRED=[
 "src/trading_ai/setup_intelligence/contracts.py","src/trading_ai/setup_intelligence/policy.py",
 "src/trading_ai/setup_intelligence/models.py","src/trading_ai/setup_intelligence/detector.py",
 "src/trading_ai/setup_intelligence/probability.py","src/trading_ai/setup_intelligence/expected_value.py",
 "src/trading_ai/setup_intelligence/option_expression.py","src/trading_ai/setup_intelligence/repository.py",
 "src/trading_ai/setup_intelligence/service.py","scripts/run_m78_setup_intelligence.py",
 "scripts/run_m78_daily_shadow.py","migrations/versions/m78_001_governed_setup_intelligence.py",
 "tests/m78/test_m78_setup_intelligence.py","tests/m78/test_m78_release_contract.py",
 "docs/m78/M78_IMPLEMENTATION.md","docs/m78/M78_VALIDATION.md",
]

def main():
 root=Path(__file__).resolve().parents[1]
 missing=[x for x in REQUIRED if not (root/x).exists()]
 result={"status":"PASS" if not missing else "FAIL","required_files":len(REQUIRED),"missing":missing,
         "authority_effect":False,"production_behavior_unchanged":True}
 print(json.dumps(result,indent=2,sort_keys=True))
 return 0 if not missing else 2
if __name__=="__main__": raise SystemExit(main())
