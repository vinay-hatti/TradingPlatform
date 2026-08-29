#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile,statistics
from pathlib import Path
VERSION="M77.19.8.7.10.7.4-VALIDATION-EVIDENCE-STABILITY-FINAL-HOLDOUT-ADVANCEMENT-GATE-1.0"
class GateError(RuntimeError): pass
def resolve(root,p):
 p=Path(p).expanduser(); return p.resolve() if p.is_absolute() else (root/p).resolve()
def load_json(p):
 with Path(p).open('r',encoding='utf-8') as f:return json.load(f)
def sha256_file(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()
def atomic_json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.',suffix='.tmp'); os.close(fd)
 try:
  with open(tmp,'w',encoding='utf-8') as f: json.dump(obj,f,indent=2,sort_keys=True); f.write('\n')
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
def scan_rules(obj,path=''):
 out=[]
 if isinstance(obj,dict):
  for k,v in obj.items():
   p=f'{path}.{k}' if path else k; kl=k.lower()
   if 'holdout' in kl and any(x in kl for x in ('criteria','threshold','minimum','maximum','rule','advance','stability')): out.append({'path':p,'value':v})
   out.extend(scan_rules(v,p))
 elif isinstance(obj,list):
  for i,v in enumerate(obj): out.extend(scan_rules(v,f'{path}[{i}]'))
 return out
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--project-root',default='/Users/vinay.hatti/TradingPlatform')
 ap.add_argument('--validation-scoring-json',default='reports/m77_19_8_7_10_7_3_6_memory_bound_isolated_frozen_validation_scoring.json')
 ap.add_argument('--development-advancement-json',default='reports/m77_19_8_7_9_mf1_vs_mf2_development_evidence_stability_validation_advancement_gate.json')
 ap.add_argument('--validation-scope-json',default='reports/m77_19_8_7_10_authorized_model_family_validation_only_evaluation_authority.json')
 ap.add_argument('--validation-preregistration-json',default='reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json')
 ap.add_argument('--training-gate-json',default='reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json')
 ap.add_argument('--output-json',default='reports/m77_19_8_7_10_7_4_validation_evidence_stability_final_holdout_advancement_gate.json')
 ap.add_argument('--output-csv',default='reports/m77_19_8_7_10_7_4_validation_evidence_registry.csv')
 a=ap.parse_args(); root=Path(a.project_root).resolve()
 paths=[resolve(root,x) for x in (a.validation_scoring_json,a.development_advancement_json,a.validation_scope_json,a.validation_preregistration_json,a.training_gate_json)]
 for p in paths:
  if not p.exists(): raise GateError(f'required authority missing: {p}')
 sp,dp,vp,pp,tp=paths; scoring,dev,scope,pre,train=map(load_json,paths)
 if scoring.get('status')!='READY' or scoring.get('validation_scoring_performed') is not True: raise GateError('Validation scoring report not READY/completed')
 for k in ('validation_model_retuning_performed','model_family_champion_selected','final_holdout_opened','production_authority_effect'):
  if scoring.get(k) is not False: raise GateError(f'Validation scoring governance violated: {k}')
 if any(x.get('status')!='READY' for x in (dev,scope,pre,train)): raise GateError('upstream authority not READY')
 if scope.get('final_holdout_context_open_authorized') is not False or scope.get('final_holdout_outcomes_open_authorized') is not False: raise GateError('Final Holdout already authorized upstream')
 if pre.get('final_holdout_open_authorized') is not False or pre.get('model_family_champion_selection_authorized') is not False: raise GateError('10.7 preregistration governance violated')
 sel=train.get('selection_and_metrics') or {}
 if sel.get('validation_used_for_selection') is not False or sel.get('final_holdout_used_for_selection') is not False: raise GateError('8.6 selection governance changed')
 authorized=scope.get('authorized_validation_scope') or {}; expected={(f,int(h)) for f,hs in authorized.items() for h in hs}
 metrics=scoring.get('family_horizon_metrics') or []; actual={(x.get('family'),int(x.get('horizon'))) for x in metrics}
 if actual!=expected: raise GateError(f'Validation evidence scope mismatch expected={sorted(expected)} actual={sorted(actual)}')
 c=dev.get('development_advancement_criteria') or {}
 ref={'minimum_mean_balanced_accuracy':float(c['minimum_mean_balanced_accuracy']),'minimum_single_fold_balanced_accuracy':float(c['minimum_single_fold_balanced_accuracy']),'maximum_fold_std_balanced_accuracy':float(c['maximum_fold_std_balanced_accuracy']),'minimum_positive_fold_count':int(c['minimum_positive_fold_count']),'use_for_final_holdout_authorization':False,'reason':'CRITERIA_WERE_PREREGISTERED_FOR_DEVELOPMENT_TO_VALIDATION_NOT_VALIDATION_TO_FINAL_HOLDOUT'}
 rule_evidence=[]
 for name,obj in {'development_advancement':dev,'validation_scope':scope,'validation_preregistration':pre,'training_gate':train}.items():
  for x in scan_rules(obj): rule_evidence.append({'source':name,**x})
 substantive=[x for x in rule_evidence if not any(x['path'].endswith(s) for s in ('final_holdout_open_authorized','final_holdout_context_open_authorized','final_holdout_outcomes_open_authorized','final_holdout_used_for_selection','final_holdout_used'))]
 rows=[]; famsum={}
 for fam in sorted(authorized):
  vals=[]
  for x in sorted([m for m in metrics if m.get('family')==fam],key=lambda z:int(z['horizon'])):
   ba=float(x['balanced_accuracy']); vals.append(ba); rows.append({'family':fam,'horizon':int(x['horizon']),'balanced_accuracy':ba,'above_chance_0_500':ba>0.5,'meets_development_mean_reference_0_505':ba>=ref['minimum_mean_balanced_accuracy'],'meets_development_single_fold_floor_reference_0_495':ba>=ref['minimum_single_fold_balanced_accuracy'],'reference_only_not_holdout_gate':True})
  famsum[fam]={'mean_balanced_accuracy':statistics.fmean(vals),'std_balanced_accuracy_population':statistics.pstdev(vals),'minimum_balanced_accuracy':min(vals),'maximum_balanced_accuracy':max(vals),'above_chance_horizon_count':sum(v>0.5 for v in vals),'horizon_count':len(vals),'all_horizons_above_chance':all(v>0.5 for v in vals),'all_horizons_meet_development_mean_reference':all(v>=ref['minimum_mean_balanced_accuracy'] for v in vals),'descriptive_only':True}
 if substantive:
  status='BLOCKED_PREEXISTING_FINAL_HOLDOUT_RULE_REQUIRES_EXPLICIT_BINDING'; reason='PREEXISTING_HOLDOUT_RULE_LIKE_FIELDS_FOUND_BUT_NOT_BOUND'; next_step='BUILD_M77_19_8_7_10_7_4_1_EXACT_PREEXISTING_FINAL_HOLDOUT_RULE_BINDING_AUTHORITY'
 else:
  status='BLOCKED_FINAL_HOLDOUT_ADVANCEMENT_CRITERIA_NOT_PREREGISTERED_BEFORE_VALIDATION'; reason='NO_PREVALIDATION_VALIDATION_TO_FINAL_HOLDOUT_ACCEPTANCE_CRITERIA_FOUND'; next_step='REVIEW_M77_19_8_7_10_7_4_AND_EXPLICITLY_AUTHORIZE_A_NON_OUTCOME_DEPENDENT_FINAL_HOLDOUT_PROTOCOL_OR_CLOSE_RESEARCH_BRANCH'
 report={'version':VERSION,'status':status,'validation_scoring_sha256':sha256_file(sp),'development_advancement_sha256':sha256_file(dp),'validation_scope_sha256':sha256_file(vp),'validation_preregistration_sha256':sha256_file(pp),'training_gate_sha256':sha256_file(tp),'authorized_validation_scope':authorized,'validation_family_stability_evidence':famsum,'validation_horizon_evidence':rows,'development_advancement_criteria_reference_only':ref,'preexisting_final_holdout_rule_like_evidence':rule_evidence,'substantive_preexisting_final_holdout_advancement_rule_count':len(substantive),'final_holdout_advancement_blocking_reason':reason,'post_validation_threshold_definition_authorized':False,'outcome_driven_family_selection_authorized':False,'validation_used_for_family_selection':False,'model_family_champion_selection_authorized':False,'model_family_champion_selected':False,'final_holdout_open_authorized':False,'final_holdout_context_open_authorized':False,'final_holdout_outcomes_open_authorized':False,'final_holdout_opened':False,'MF1_retuning_authorized':False,'MF2_retuning_authorized':False,'MF3_reopened':False,'production_model_change_authorized':False,'production_authority_effect':False,'next_step':next_step}
 atomic_json(resolve(root,a.output_json),report)
 with resolve(root,a.output_csv).open('w',encoding='utf-8',newline='') as f:
  fields=['family','horizon','balanced_accuracy','above_chance_0_500','meets_development_mean_reference_0_505','meets_development_single_fold_floor_reference_0_495','reference_only_not_holdout_gate']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
 print('=== M77.19.8.7.10.7.4 VALIDATION EVIDENCE STABILITY & FINAL HOLDOUT ADVANCEMENT GATE ==='); print('status:',status)
 for fam,s in famsum.items(): print(f"{fam}: mean={s['mean_balanced_accuracy']:.9f} std={s['std_balanced_accuracy_population']:.9f} min={s['minimum_balanced_accuracy']:.9f} above_chance={s['above_chance_horizon_count']}/{s['horizon_count']}")
 print('substantive_preexisting_final_holdout_advancement_rule_count:',len(substantive)); print('final_holdout_advancement_blocking_reason:',reason); print('post_validation_threshold_definition_authorized: False'); print('validation_used_for_family_selection: False'); print('model_family_champion_selected: False'); print('final_holdout_open_authorized: False'); print('final_holdout_opened: False'); print('production_authority_effect: False'); print('next_step:',next_step); print('report:',resolve(root,a.output_json)); print('csv:',resolve(root,a.output_csv)); return 0
if __name__=='__main__': raise SystemExit(main())
