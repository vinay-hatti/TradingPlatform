from pathlib import Path

from trading_ai.broker.ibkr.price_normalization import (
    is_price_on_increment,
    normalize_limit_price,
    normalize_signed_combo_price,
)


def test_single_leg_buy_and_sell_snap_to_legal_ibkr_tick_without_worsening_limit():
    buy = normalize_limit_price(13.125, "BUY", [{"low_edge": 0, "increment": 0.05}], 0.01)
    sell = normalize_limit_price(13.125, "SELL", [{"low_edge": 0, "increment": 0.05}], 0.01)
    assert buy["normalized_price"] == 13.10
    assert sell["normalized_price"] == 13.15
    assert is_price_on_increment(buy["normalized_price"], buy["increment"])
    assert is_price_on_increment(sell["normalized_price"], sell["increment"])


def test_combo_net_debit_and_credit_use_signed_economic_rounding():
    debit = normalize_signed_combo_price(10.912, [{"low_edge": 0, "increment": 0.05}], 0.01)
    credit = normalize_signed_combo_price(-2.187, [{"low_edge": 0, "increment": 0.05}], 0.01)
    assert debit["normalized_price"] == 10.90
    assert debit["economic_side"] == "NET_DEBIT"
    assert credit["normalized_price"] == -2.20
    assert credit["economic_side"] == "NET_CREDIT"
    assert debit["valid"] and credit["valid"]


def test_market_rule_band_is_reselected_after_snap():
    # 0.999 uses .001; >=1.00 uses .05. The normalization must validate the
    # resulting price against the band at the resulting price, not only input.
    rules = [
        {"low_edge": 0, "increment": 0.001},
        {"low_edge": 1.0, "increment": 0.05},
    ]
    out = normalize_limit_price(1.023, "BUY", rules, 0.01)
    assert out["normalized_price"] == 1.0
    assert out["increment"] == 0.05
    assert out["valid"]


def test_transport_has_final_fail_closed_gate_for_single_and_combo_submit_and_modify():
    text = Path("src/trading_ai/broker/ibkr/order_transport.py").read_text()
    assert "normalize_contract_limit_price" in text
    assert "normalize_combo_limit_price" in text
    assert text.count("_assert_valid_normalization") >= 4
    assert "refusing to transmit without broker price validation" in text
    assert "IBKR exposed no usable order price increment" in text
    assert "IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY" in text
    assert "transmit=False" in text
    assert "app.placeOrder" in text


def test_workspace_uses_transport_validated_bag_price_after_submit_and_reprice():
    text = Path("src/trading_ai/execution_workspace/service.py").read_text()
    assert "service.submit_combo(request)" in text
    assert "transport.modify_combo_order(row.broker_order_id,request)" in text
    assert "last_outbound_price_validation" in text
    assert "broker_normalized_limit_price" in text
    assert "ibkr_price_normalization" in text


def test_persistence_records_actual_transmitted_price_and_validation_evidence():
    text = Path("src/trading_ai/broker/ibkr/order_service.py").read_text()
    assert "last_outbound_price_validation" in text
    assert "actual_limit" in text
    assert "broker_price_validation" in text
