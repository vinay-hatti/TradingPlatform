from trading_ai.portfolio_risk_allocation.service import clamp
def test_clamp(): assert clamp(120)==100 and clamp(-1)==0 and clamp(50)==50
def test_m64_router_registered():
 from pathlib import Path
 text=(Path(__file__).resolve().parents[2]/'src/trading_ai/production_api/app.py').read_text()
 assert 'portfolio_risk_allocation_router' in text
def test_m64_models_registered():
 from trading_ai.database.base import Base
 import trading_ai.database.models
 assert 'portfolio_risk_allocation_snapshots' in Base.metadata.tables
 assert 'portfolio_fit_assessments' in Base.metadata.tables
