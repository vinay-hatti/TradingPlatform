from pathlib import Path
from trading_ai.opex_intelligence.service import INDEXES, is_monthly_opex
root=Path(__file__).resolve().parents[1]
assert INDEXES==("SPX","NDX","RUT")
required=[
 "src/trading_ai/opex_intelligence/models.py","src/trading_ai/opex_intelligence/service.py","src/trading_ai/opex_intelligence/router.py",
 "ui/workstation/src/OpexIntelligencePage.tsx","migrations/versions/m71_001_opex_intelligence.py"]
for rel in required: assert (root/rel).exists(),rel
app=(root/"src/trading_ai/production_api/app.py").read_text(); assert "opex_intelligence_router" in app and "include_router(opex_intelligence_router)" in app
ing=(root/"scripts/ingestion_split_common.py").read_text(); assert "refresh_opex_intelligence" in ing and "opex_intelligence = refresh_opex_intelligence" in ing
ui=(root/"ui/workstation/src/WorkspaceChrome.tsx").read_text(); assert "analytics-opex" in ui
print("M71 OPEX Intelligence acceptance: PASS")
