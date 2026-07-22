from datetime import date
from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import PolygonOptionChainSnapshotProvider, PolygonSnapshotPolicy

class Response:
    status_code=200
    def raise_for_status(self): pass
    def json(self): return {"results":[{"details":{"ticker":"O:AAPL260821C00250000","contract_type":"call","expiration_date":"2026-08-21","strike_price":250},"last_quote":{"bid":5.1,"ask":5.4},"last_trade":{"price":5.25},"day":{"volume":120},"open_interest":1500,"implied_volatility":0.35,"greeks":{"delta":0.45,"gamma":0.02,"theta":-0.08,"vega":0.15},"underlying_asset":{"price":250.0}}]}
class Session:
    def get(self,*args,**kwargs): return Response()

def main():
    provider=PolygonOptionChainSnapshotProvider("key",as_of_date=date(2026,7,20),policy=PolygonSnapshotPolicy(minimum_dte=0,maximum_dte=365,minimum_open_interest=1,requests_per_second=1000),session=Session(),sleep=lambda _:None)
    batches=list(provider.iter_batches(symbols=["AAPL"],batch_size=100))
    assert len(batches)==1 and len(batches[0].records)==1
    assert batches[0].batch_id=="polygon:2026-07-20:AAPL:1"
    print("Milestone 35 Phase 3 Polygon provider assertions passed.")
if __name__=="__main__": main()
