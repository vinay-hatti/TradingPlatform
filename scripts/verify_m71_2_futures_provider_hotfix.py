from __future__ import annotations
import os
from trading_ai.futures_intelligence.service import PolygonFuturesProvider

class Probe(PolygonFuturesProvider):
    def __init__(self):
        super().__init__(api_key="secret-test-key", base_url="https://api.massive.com")
        self.calls=[]
    def _get(self,path,params=None):
        self.calls.append((path,dict(params or {})))
        if path.endswith("/contracts"):
            return {"results":[
                {"ticker":"ESZ6","product_code":"ES","type":"single","days_to_maturity":130},
                {"ticker":"ESU6","product_code":"ES","type":"single","days_to_maturity":39},
            ]}
        if "/aggs/" in path:
            return {"results":[]}
        return {"results":[]}

p=Probe()
rows=p.contracts("ES","2026-08-08",True)
assert rows[0]["ticker"]=="ESU6", rows
path,params=p.calls[0]
assert path=="/futures/v1/contracts"
assert params=={"product_code":"ES","date":"2026-08-08","active":"true"}, params
p.aggregates("ESU6","1min","2026-05-10","2026-08-08")
_,aparams=p.calls[-1]
assert "sort" not in aparams, aparams
redacted=p._redacted_url("https://api.massive.com/x?apiKey=secret-test-key&product_code=ES")
assert "secret-test-key" not in redacted and "REDACTED" in redacted, redacted
print("M71.2 futures provider hotfix acceptance: PASS")
