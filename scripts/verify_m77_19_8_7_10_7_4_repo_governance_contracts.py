#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
def j(p):
 with open(p,encoding='utf-8') as f:return json.load(f)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--project-root',default='/Users/vinay.hatti/TradingPlatform'); a=ap.parse_args(); r=Path(a.project_root)
 d=j(r/'reports/m77_19_8_7_9_mf1_vs_mf2_development_evidence_stability_validation_advancement_gate.json'); v=j(r/'reports/m77_19_8_7_10_authorized_model_family_validation_only_evaluation_authority.json'); p=j(r/'reports/m77_19_8_7_10_7_frozen_mf1_mf2_validation_scoring_stability_preregistration_gate.json'); t=j(r/'reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json')
 c=d.get('development_advancement_criteria') or {}; assert c.get('criteria_frozen_before_validation_open') is True; assert c.get('minimum_mean_balanced_accuracy')==0.505; assert c.get('minimum_single_fold_balanced_accuracy')==0.495; assert c.get('maximum_fold_std_balanced_accuracy')==0.015; assert c.get('minimum_positive_fold_count')==3
 assert v.get('final_holdout_context_open_authorized') is False and v.get('final_holdout_outcomes_open_authorized') is False; assert p.get('final_holdout_open_authorized') is False and p.get('model_family_champion_selection_authorized') is False
 s=t.get('selection_and_metrics') or {}; assert s.get('validation_used_for_selection') is False and s.get('final_holdout_used_for_selection') is False
 print('=== M77.19.8.7.10.7.4 REPO GOVERNANCE CONTRACT AUDIT ==='); print('status: READY'); print('development_to_validation_criteria_frozen: True'); print('validation_used_for_selection: False'); print('final_holdout_used_for_selection: False'); print('final_holdout_authorized_upstream: False'); return 0
if __name__=='__main__': raise SystemExit(main())
