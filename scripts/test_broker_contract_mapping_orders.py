from datetime import date, timedelta
from trading_ai.broker.broker_order_profile import BrokerOrderLeg, BrokerOrderRequest
from trading_ai.broker.broker_order_serialization import dumps
from trading_ai.broker.broker_order_service import BrokerOrderService
from trading_ai.broker.instrument_mapper import InstrumentMapper, build_occ_symbol

def main():
    future = date.today() + timedelta(days=45)
    mapper = InstrumentMapper(equity_symbol_map={"BRK.B":"BRK B"})
    equity = mapper.map({"asset_class":"EQUITY","symbol":"brk.b","exchange":"NYSE"})
    assert equity.allowed and equity.broker_symbol == "BRK B"
    option = mapper.map({"asset_class":"OPTION","underlying_symbol":"AAPL","expiration":future.isoformat(),"strike":200,"option_type":"CALL"})
    assert option.allowed and option.option is not None
    assert option.option.occ_symbol == build_occ_symbol("AAPL",future,"CALL",200)
    expired = mapper.map({"asset_class":"OPTION","underlying_symbol":"AAPL","expiration":(date.today()-timedelta(days=1)).isoformat(),"strike":200,"option_type":"PUT"})
    assert not expired.allowed and "OPTION_EXPIRED" in expired.rejection_reasons
    unsupported = mapper.map({"asset_class":"FUTURE","symbol":"ES"})
    assert not unsupported.allowed and "ASSET_CLASS_NOT_SUPPORTED" in unsupported.rejection_reasons

    service = BrokerOrderService()
    single = BrokerOrderRequest(
        client_order_id="order-001", account_id="PAPER-001", order_type="LIMIT", time_in_force="DAY", limit_price=5.25,
        legs=(BrokerOrderLeg("leg-1", option, "BUY_TO_OPEN", 1, "OPEN"),))
    result = service.validate(single, reserve_client_order_id=True)
    assert result.allowed and result.recommendation == "SUBMIT"
    duplicate = service.validate(single)
    assert not duplicate.allowed and "UNIQUE_CLIENT_ORDER_ID" in duplicate.rejection_reasons

    short_call = mapper.map({"asset_class":"OPTION","underlying_symbol":"AAPL","expiration":future.isoformat(),"strike":210,"option_type":"CALL"})
    vertical = BrokerOrderRequest(
        client_order_id="order-002", account_id="PAPER-001", order_type="LIMIT", time_in_force="DAY", limit_price=2.10,
        strategy_name="CALL_VERTICAL",
        legs=(
            BrokerOrderLeg("long-call", option, "BUY_TO_OPEN", 1, "OPEN"),
            BrokerOrderLeg("short-call", short_call, "SELL_TO_OPEN", 1, "OPEN"),
        ))
    vertical_result = service.validate(vertical)
    assert vertical_result.allowed and vertical_result.metadata["underlyings"] == ["AAPL"]
    market_spread = BrokerOrderRequest("order-003","PAPER-001","MARKET","DAY",vertical.legs)
    market_result = service.validate(market_spread)
    assert not market_result.allowed and "MULTI_LEG_MARKET_ORDER" in market_result.rejection_reasons
    missing_limit = BrokerOrderRequest("order-004","PAPER-001","LIMIT","DAY",single.legs)
    missing_result = service.validate(missing_limit)
    assert not missing_result.allowed and "LIMIT_PRICE" in missing_result.rejection_reasons
    payload = dumps(vertical_result)
    assert '"strategy_name": "CALL_VERTICAL"' in payload and '"recommendation": "SUBMIT"' in payload
    print("All instrument mapping, option contract and broker-order validation assertions passed.")

if __name__ == "__main__":
    main()
