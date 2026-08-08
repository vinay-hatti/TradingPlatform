from datetime import datetime,timezone
from trading_ai.execution_intelligence.policy import ExecutionIntelligencePolicy
from trading_ai.execution_intelligence.service import ExecutionIntelligenceService

def test_package_price_debit_and_credit():
 legs=[{'side':'BUY','quantity':1,'limit_price':5.0},{'side':'SELL','quantity':1,'limit_price':2.0}]
 assert ExecutionIntelligenceService.package_price(legs)==3.0
 legs=[{'side':'SELL','quantity':1,'limit_price':5.0},{'side':'BUY','quantity':1,'limit_price':2.0}]
 assert ExecutionIntelligenceService.package_price(legs)==-3.0

def test_policy_shape():
 p=ExecutionIntelligencePolicy();assert p.direct_polygon_enabled is True;assert p.max_quote_age_seconds==15.0;assert p.max_price_drift_pct==3.0

def test_smart_order_policy_defaults_are_governed():
 p=ExecutionIntelligencePolicy()
 assert p.initial_limit_aggression_pct==35.0
 assert p.maximum_reprices==4
 assert p.working_reprice_after_seconds==8.0
 assert p.working_order_max_age_seconds==180.0

def test_transport_supports_in_place_paper_reprice():
 from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport
 assert callable(getattr(IbapiPaperOrderTransport,'modify_order',None))
 assert callable(getattr(IbapiPaperOrderTransport,'modify_combo_order',None))
