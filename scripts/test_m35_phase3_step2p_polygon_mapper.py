from datetime import date
from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import PolygonOptionSnapshotMapper

def main():
    payload={"details":{"ticker":"O:AAPL260821C00250000","contract_type":"call","expiration_date":"2026-08-21","strike_price":250},"last_quote":{"bid":5.1,"ask":5.4},"last_trade":{"price":5.25},"day":{"volume":120},"open_interest":1500,"implied_volatility":0.35,"greeks":{"delta":0.45,"gamma":0.02,"theta":-0.08,"vega":0.15},"underlying_asset":{"price":250.0}}
    record=PolygonOptionSnapshotMapper().map("AAPL",date(2026,7,20),payload)
    assert record.identity.underlying_symbol=="AAPL"
    assert record.identity.option_side.value=="CALL"
    assert record.bid==5.1 and record.open_interest==1500 and record.delta==0.45
    print("Milestone 35 Phase 3 Polygon mapper assertions passed.")
if __name__=="__main__": main()
