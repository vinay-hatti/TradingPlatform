from pathlib import Path
from trading_ai.opex_intelligence.service import OpexIntelligenceService

assert OpexIntelligenceService.VERSION.startswith('M71.3.1-'), OpexIntelligenceService.VERSION
svc=Path('src/trading_ai/opex_intelligence/service.py').read_text()
ui=Path('ui/workstation/src/OpexIntelligencePage.tsx').read_text()
for token in ('_coherent_scenarios','_path_ladder','acceptance_probability','attraction_score','terminal_base_zone','current_decision_zone','p25','p75'):
    assert token in svc, token
for token in ('Current-to-target path ladder','Acceptance','Primary attraction score','P25','Median','P75','Current decision zone','Terminal base zone'):
    assert token in ui, token
print('M71.3.1 OPEX consistency hardening acceptance: PASS')

# M71.3.1 V3 regression: actionable must be assigned before its bounds are read.
source = Path('src/trading_ai/opex_intelligence/service.py').read_text()
assign_pos = source.find("staged,actionable=self._realistic_staged_objectives")
read_pos = source.find("alo=actionable['low']; ahi=actionable['high']")
assert assign_pos >= 0 and read_pos > assign_pos, (assign_pos, read_pos)
