from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(path):
 p=subprocess.run([sys.executable,str(ROOT/path)],cwd=ROOT,text=True,capture_output=True)
 return p.returncode==0,(p.stdout+p.stderr).strip()
def main():
 tests=[
 ('Phase 1','scripts/test_trend_intelligence.py'),('Phase 2','scripts/test_trend_transition_intelligence.py'),('Phase 3','scripts/test_trend_forecasting.py'),('Phase 4','scripts/test_institutional_trend_intelligence.py'),('Phase 5','scripts/test_trend_platform_integration.py'),('Phase 6','scripts/test_m52_phase6_operations.py')]
 print('='*57); print('Milestone 52 Acceptance Validation'); print('='*57)
 failed=[]
 for name,path in tests:
  if not (ROOT/path).exists(): ok=False; detail='test file missing'
  else: ok,detail=run(path)
  print(f'{name:20} {"PASS" if ok else "FAIL"}')
  if not ok: failed.append((name,path,detail[-1000:]))
 print('-'*57); print(f'Overall Status       {"PASS" if not failed else "FAIL"}')
 if failed:
  for name,path,detail in failed: print(f'\n[{name}] {path}\n{detail}')
  return 1
 return 0
if __name__=='__main__': raise SystemExit(main())
