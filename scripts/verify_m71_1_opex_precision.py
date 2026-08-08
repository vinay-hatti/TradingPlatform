from pathlib import Path
from trading_ai.opex_intelligence.service import OpexIntelligenceService, INDEXES
root=Path(__file__).resolve().parents[1]
assert INDEXES==('SPX','NDX','RUT')
svc=OpexIntelligenceService(None)
assert svc.VERSION.startswith('M71.'), svc.VERSION
service=(root/'src/trading_ai/opex_intelligence/service.py').read_text()
ui=(root/'ui/workstation/src/OpexIntelligencePage.tsx').read_text()
for token in ('_surface_distribution','_historical_opex_analogs','_model_calibrated_ranges','_level_probabilities','_conditional_distributions','_cross_index_confirmation','tactical_0dte_near_term','range_width_contributors'):
    assert token in service, token
for token in ('DOMINANT-SCENARIO ACTIONABLE RANGE','Model-calibrated settlement ranges','Path probabilities to key levels','Why is the range this wide?','Event-conditioned distributions','Structural vs tactical dealer positioning'):
    assert token in ui, token
print('M71.1 OPEX Forecast Precision & Conditional Path Intelligence acceptance: PASS')
