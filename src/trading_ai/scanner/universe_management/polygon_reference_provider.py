from __future__ import annotations
from .provider_contracts import UniverseProvider, UniverseProviderResult, utc_now
from .universe_profile import SecurityProfile

class PolygonReferenceUniverseProvider(UniverseProvider):
    def __init__(self, api_key: str | None = None, *, client=None) -> None:
        if client is None:
            if not api_key: raise ValueError("Polygon API key is required when client is not injected.")
            from polygon import RESTClient
            client = RESTClient(api_key)
        self.client=client
    @property
    def name(self) -> str: return "POLYGON"
    def fetch(self) -> UniverseProviderResult:
        items=[]
        for row in self.client.list_tickers(market="stocks", active=True, limit=1000):
            ticker=getattr(row,"ticker","")
            if not ticker: continue
            exchange={"XNAS":"NASDAQ","XNYS":"NYSE","XASE":"NYSE_AMERICAN","ARCX":"NYSE_ARCA","BATS":"CBOE"}.get(getattr(row,"primary_exchange",None),"")
            if not exchange: continue
            kind=str(getattr(row,"type","") or "").upper()
            asset_type="ETF" if kind in {"ETF","ETV"} else "EQUITY"
            items.append(SecurityProfile(symbol=ticker,name=getattr(row,"name","") or "",exchange=exchange,asset_type=asset_type,active=bool(getattr(row,"active",True)),tradable=True,source=self.name,metadata={"polygon_type":kind}))
        return UniverseProviderResult(self.name, utc_now(), tuple(items), metadata={"record_count":len(items)})
