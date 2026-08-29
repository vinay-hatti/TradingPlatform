from pathlib import Path
from trading_ai.broker.ibkr.price_normalization import normalize_limit_price, select_price_increment, snap_limit_price
from trading_ai.execution_intelligence.auto_fill import AutomaticEntryFillManager

root=Path(__file__).resolve().parents[1]
transport=(root/'src/trading_ai/broker/ibkr/order_transport.py').read_text()
workspace=(root/'src/trading_ai/execution_workspace/service.py').read_text()
checks={
 'version':AutomaticEntryFillManager.VERSION.startswith('M73.0.'),
 'market_rule_request':'reqMarketRule' in transport and 'def marketRule' in transport,
 'contract_detail_market_rules':'marketRuleIds' in transport and 'validExchanges' in transport and 'minTick' in transport,
 'initial_submit_normalized':'price_normalization=transport.normalize_option_limit_price' in workspace and "'ibkr_price_normalization':price_normalization" in workspace,
 'automatic_reprice_normalized':(
     'price_normalization=transport.normalize_option_limit_price' in workspace
     and "normalized=float(price_normalization['normalized_price'])" in workspace
     and 'monotonic_broker_candidate' in workspace
     and 'advance_coarse_tick' in workspace
     and "'ibkr_price_normalization':price_normalization" in workspace
 ),
 'transport_safety_net':'normalized=self.normalize_option_limit_price' in transport,
 'buy_floor':snap_limit_price(10.4075,0.05,'BUY')==10.4,
 'sell_ceiling':snap_limit_price(4.2934,0.05,'SELL')==4.3,
 'price_band':select_price_increment(10.4075,[{'low_edge':0,'increment':0.01},{'low_edge':3,'increment':0.05}],0.01)==0.05,
}
for k,v in checks.items(): print(f'{k}: {"PASS" if v else "FAIL"}')
assert all(checks.values()),checks
print('M73.0.5 IBKR Minimum-Tick Price Normalization verifier: PASS')
