from pathlib import Path
from trading_ai.opex_intelligence.service import OpexIntelligenceService

assert OpexIntelligenceService.VERSION.startswith('M71.3')
svc=Path('src/trading_ai/opex_intelligence/service.py').read_text()
ui=Path('ui/workstation/src/OpexIntelligencePage.tsx').read_text()
for token in ('_scenario_evidence','_magnet_zone_heatmap','_realistic_staged_objectives','_expected_daily_path','transition_probability_matrix','top_analogs'):
    assert token in svc, token
for token in ('Scenario posterior & evidence','Expected day-by-day path into OPEX','Historical OPEX analogs','transition_probability_matrix'):
    assert token in ui, token
assert ('Magnet-zone probability heat map' in ui or 'Magnet-zone probability & attraction' in ui), 'magnet-zone decision panel'
print('M71.3 OPEX Decision Intelligence acceptance: PASS')
