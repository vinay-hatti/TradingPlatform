from __future__ import annotations
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))

from trading_ai.stock_intelligence.decision_intelligence import (
    InstitutionalDecisionIntelligenceEngine,
    InstitutionalDecisionAssessment,
    BarrierProbabilityAssessment,
)

checks = []
def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)

check('version', InstitutionalDecisionIntelligenceEngine.VERSION == 'M76.2-IDI-1.0')
check('assessment_model', hasattr(InstitutionalDecisionAssessment, 'finalize'))
check('barrier_model', BarrierProbabilityAssessment().calibration_status == 'UNCALIBRATED')

publication = (root/'src/trading_ai/stock_intelligence/publication.py').read_text()
for marker in ('institutional_trade_quality','decision_readiness','capital_priority','barrier_target_1_probability','decision_intelligence'):
    check(f'publication_{marker}', marker in publication)

ingestion = (root/'src/trading_ai/institutional_options/opportunity_ingestion.py').read_text()
check('institutional_options_handoff', 'institutional_decision_intelligence' in ingestion)
check('barrier_evidence', 'Barrier prior:' in ingestion)

scanner = (root/'ui/workstation/src/StockIntelligenceScannerPage.tsx').read_text()
check('scanner_idi', 'Institutional decision intelligence' in scanner)
check('scanner_evidence_registry', 'Institutional evidence registry' in scanner)
check('scanner_shadow_learning', 'Learning mode' in scanner)

institutional = (root/'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
check('institutional_options_ui', 'M76.2 institutional decision intelligence' in institutional)

print('M76.2 Institutional Decision Intelligence verification: PASSED')
for item in checks:
    print('  PASS', item)
