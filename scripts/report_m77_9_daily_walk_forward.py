#!/usr/bin/env python3
import argparse,json
from pathlib import Path
P=Path('reports/m77/m77_9_daily_walk_forward_certification.json')
def main():
 p=argparse.ArgumentParser(); p.add_argument('--artifact',default=str(P)); p.add_argument('--show-certified',action='store_true'); a=p.parse_args(); j=json.loads(Path(a.artifact).read_text())
 print('=== M77.9 DAILY MODEL REPLAY & WALK-FORWARD CERTIFICATION ==='); print('Version:',j.get('version')); print('Status:',j.get('status')); print('Production authority effect:',j.get('production_authority_effect'))
 print('\n--- COVERAGE ---'); [print(f'{k}: {v}') for k,v in (j.get('coverage') or {}).items()]
 print('\n--- SUMMARY ---'); [print(f'{k}: {v}') for k,v in (j.get('summary') or {}).items()]
 print('\n--- ACCEPTANCE ---'); [print(f'{k}: {v}') for k,v in (j.get('acceptance') or {}).items()]
 if a.show_certified:
  print('\n--- CERTIFIED DAILY COHORTS ---'); xs=[x for x in j.get('cohort_certification',[]) if x.get('certified')]
  if not xs: print('NONE')
  for x in xs: print(f"{x['horizon_sessions']}d | {x['regime']} | {x['direction']} | {x['score_band']} | {x['confidence_band']} | full={x['passed_full']}/{x['selected_full']} total={x['passed_total']}/{x['selected_total']}")
 print('\nNext step:',j.get('next_step'))
if __name__=='__main__': main()
