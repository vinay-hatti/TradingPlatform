from pathlib import Path
import subprocess, sys

mandatory=[
 'scripts/test_probability_calibration.py',
 'scripts/test_segmented_probability_calibration.py',
 'scripts/test_probability_calibration_integration.py',
 'scripts/test_phase6_decision_run_result_fix.py',
 'scripts/test_probability_calibration_ranking.py',
 'scripts/test_probability_calibration_reporting.py',
 'scripts/test_probability_calibration_governance.py',
 'scripts/test_probability_calibration_governance_reporting.py',
]
failed=[]
for script in mandatory:
    if not Path(script).exists(): failed.append(f'MISSING:{script}'); continue
    result=subprocess.run([sys.executable,script])
    if result.returncode: failed.append(script)
if failed: raise SystemExit('Phase 6 regression failures: '+', '.join(failed))
print('Milestone 29 Phase 6 regression assertions passed.')
