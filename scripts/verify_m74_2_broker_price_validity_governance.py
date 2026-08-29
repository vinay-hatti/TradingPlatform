#!/usr/bin/env python3
from pathlib import Path

from trading_ai.broker.ibkr.price_normalization import (
    is_price_on_increment,
    normalize_limit_price,
    normalize_signed_combo_price,
)

single_buy = normalize_limit_price(13.125, "BUY", [{"low_edge": 0, "increment": 0.05}], 0.01)
single_sell = normalize_limit_price(13.125, "SELL", [{"low_edge": 0, "increment": 0.05}], 0.01)
combo_debit = normalize_signed_combo_price(10.912, [{"low_edge": 0, "increment": 0.05}], 0.01)
combo_credit = normalize_signed_combo_price(-2.187, [{"low_edge": 0, "increment": 0.05}], 0.01)

assert single_buy["normalized_price"] == 13.10
assert single_sell["normalized_price"] == 13.15
assert combo_debit["normalized_price"] == 10.90
assert combo_credit["normalized_price"] == -2.20
for row in (single_buy, single_sell, combo_debit, combo_credit):
    assert row["valid"]
    assert is_price_on_increment(row["normalized_price"], row["increment"])

transport = Path("src/trading_ai/broker/ibkr/order_transport.py").read_text()
workspace = Path("src/trading_ai/execution_workspace/service.py").read_text()
service = Path("src/trading_ai/broker/ibkr/order_service.py").read_text()
assert "normalize_combo_limit_price" in transport
assert "_assert_valid_normalization" in transport
assert "refusing to transmit" in transport
assert "TWS_STAGED_BAG_VALIDATION" in transport
assert "transmit=False" in transport
assert "keep_stage_for_transmit=True" in transport
assert "service.submit_combo(request)" in workspace
assert "last_outbound_price_validation" in workspace
assert "broker_normalized_limit_price" in workspace
assert "last_outbound_price_validation" in service
assert "broker_price_validation" in service
print("M74.2 broker-authoritative price validity governance verification: PASSED")
