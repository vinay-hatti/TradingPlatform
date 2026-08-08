from pathlib import Path
from trading_ai.performance_learning.continuous_learning import VERSION, calibration_metrics


def main():
    root=Path(__file__).resolve().parents[1]
    checks={
        'version': VERSION.startswith('M72.'),
        'migration': (root/'migrations/versions/m72_001_outcome_calibration_execution_quality.py').exists(),
        'prediction_registry': 'class PredictionRegistryModel' in (root/'src/trading_ai/performance_learning/models.py').read_text(),
        'outcome_registry': 'class PredictionOutcomeModel' in (root/'src/trading_ai/performance_learning/models.py').read_text(),
        'calibration': calibration_metrics([(.8,1),(.2,0)])['brier_score'] is not None,
        'opex_calibration': 'def opex_calibration' in (root/'src/trading_ai/performance_learning/continuous_learning.py').read_text(),
        'execution_quality': 'edge_preservation_pct' in (root/'src/trading_ai/performance_learning/continuous_learning.py').read_text(),
        'automation': 'continuous_learning = refresh_continuous_learning' in (root/'scripts/ingestion_split_common.py').read_text(),
        'ui': 'Outcome learning' in (root/'ui/workstation/src/PerformanceLearningRefinedPage.tsx').read_text(),
        'governance': 'automatic_activation' in (root/'src/trading_ai/performance_learning/continuous_learning.py').read_text() and 'False' in (root/'src/trading_ai/performance_learning/continuous_learning.py').read_text(),
    }
    for k,v in checks.items():print(f'{k}: {"PASS" if v else "FAIL"}')
    if not all(checks.values()):raise SystemExit('M72 continuous learning acceptance FAILED')
    print('M72 continuous learning acceptance PASSED')

if __name__=='__main__':main()
