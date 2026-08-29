from __future__ import annotations
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))

from trading_ai.stock_intelligence.decision_intelligence import InstitutionalDecisionAssessment, InstitutionalDecisionIntelligenceEngine

checks=[]
def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)

check('base_m76_2_version_preserved', InstitutionalDecisionIntelligenceEngine.VERSION == 'M76.2-IDI-1.0')
a=InstitutionalDecisionAssessment(explainability={'version':'M76.2.1-EXPLAINABILITY-1.0'}).finalize()
check('explainability_contract', a.explainability.get('version') == 'M76.2.1-EXPLAINABILITY-1.0')
backend=(root/'src/trading_ai/stock_intelligence/decision_intelligence.py').read_text()
check('top_percent', '"top_percent"' in backend)
check('rank_label', '"rank_label"' in backend)
check('readiness_breakdown', '"decision_readiness"' in backend and '"components"' in backend)
scanner=(root/'ui/workstation/src/StockIntelligenceScannerPage.tsx').read_text()
for marker in ('Trade quality breakdown','Decision readiness breakdown','Capital priority breakdown','Freshness & barrier diagnostics','P(Target 3 before stop)'):
    check('scanner_'+marker.lower().replace(' ','_').replace('(','').replace(')',''), marker in scanner)
io=(root/'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
for marker in ('Decision intelligence explainability','Trade quality breakdown','Decision readiness breakdown','Capital priority breakdown','Target 3 before stop'):
    check('io_'+marker.lower().replace(' ','_'), marker in io)
print('M76.2.1 Decision Intelligence Explainability & Ranking verification: PASSED')
for item in checks:
    print('  PASS', item)
