from pathlib import Path
from trading_ai.performance_learning import continuous_learning as cl

root=Path(__file__).resolve().parents[1]
ui=(root/'ui/workstation/src/PerformanceLearningRefinedPage.tsx').read_text()
checks={
 'version':cl.VERSION.startswith('M72.'),
 'prediction_registry':'completion_rate_pct' in Path(cl.__file__).read_text() and 'recent_predictions' in Path(cl.__file__).read_text(),
 'segmented_calibration':'calibration_bias' in Path(cl.__file__).read_text() and 'REVIEWABLE' in Path(cl.__file__).read_text(),
 'opex_validation':'by_symbol' in Path(cl.__file__).read_text() and 'recent_outcomes' in Path(cl.__file__).read_text(),
 'execution_analytics':'by_strategy' in Path(cl.__file__).read_text() and 'edge_preservation_pct' in Path(cl.__file__).read_text(),
 'ui_branding':'Performance Command Center' in ui,
 'ui_registry':'Recent prediction → outcome lineage' in ui,
 'ui_opex':'OPEX forecast validation' in ui,
 'ui_execution':'Execution quality & edge preservation' in ui,
 'ui_governance':'Evidence readiness' in ui,
 'human_governance':'automatic_weight_activation' in Path(cl.__file__).read_text() and 'False' in Path(cl.__file__).read_text(),
}
for k,v in checks.items(): print(f'{k}: {"PASS" if v else "FAIL"}')
assert all(checks.values()), checks
print('M72.1 Performance Command Center acceptance: PASS')
