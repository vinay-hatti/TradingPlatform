from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Mapping
from .realtime_market_data_profile import MarketDataSourceProfile, NormalizedQuote, NormalizedTrade

def _value(obj, name, default=None): return obj.get(name, default) if isinstance(obj, Mapping) else getattr(obj, name, default)
def safe_float(value, default=0.0):
    try: return default if value in (None, "", "None", "nan") else float(value)
    except (TypeError, ValueError): return default
def parse_timestamp(value, default=None):
    if value is None: return default
    if isinstance(value, datetime): parsed=value
    elif isinstance(value, (int,float)):
        n=float(value); a=abs(n)
        if a>1e17: n/=1e9
        elif a>1e14: n/=1e6
        elif a>1e11: n/=1e3
        parsed=datetime.fromtimestamp(n, tz=timezone.utc)
    else:
        text=str(value).strip()
        if text.endswith('Z'): text=text[:-1]+'+00:00'
        parsed=datetime.fromisoformat(text)
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
def normalize_source(value):
    if value is None or isinstance(value, MarketDataSourceProfile): return value
    if isinstance(value, Mapping):
        return MarketDataSourceProfile(provider=str(value.get('provider','UNKNOWN')), feed=value.get('feed'), venue=value.get('venue'), connection_id=value.get('connection_id'), sequence_number=value.get('sequence_number'), metadata=dict(value.get('metadata',{}) or {}))
    return MarketDataSourceProfile(provider=str(value))

class RealTimeMarketDataNormalizer:
    def normalize_quote(self, event, received_at=None):
        received=parse_timestamp(_value(event,'received_timestamp'), received_at or datetime.now(timezone.utc))
        exchange=parse_timestamp(_value(event,'exchange_timestamp'), received)
        provider=parse_timestamp(_value(event,'provider_timestamp'))
        bid=safe_float(_value(event,'bid_price')); ask=safe_float(_value(event,'ask_price'))
        bid_size=safe_float(_value(event,'bid_size')); ask_size=safe_float(_value(event,'ask_size'))
        midpoint=(bid+ask)/2 if bid or ask else 0.0; spread=ask-bid; spread_pct=spread/midpoint if midpoint>0 else 0.0
        return NormalizedQuote(symbol=str(_value(event,'symbol','')).strip().upper(), asset_class=str(_value(event,'asset_class','EQUITY')).strip().upper(), bid_price=bid, ask_price=ask, bid_size=bid_size, ask_size=ask_size, midpoint=midpoint, spread=spread, spread_pct=spread_pct, exchange_timestamp=exchange.isoformat(), provider_timestamp=provider.isoformat() if provider else None, received_timestamp=received.isoformat(), event_age_seconds=(received-exchange).total_seconds(), bid_exchange=_value(event,'bid_exchange',_value(event,'exchange')), ask_exchange=_value(event,'ask_exchange',_value(event,'exchange')), conditions=tuple(_value(event,'conditions',()) or ()), source=normalize_source(_value(event,'source')), metadata=dict(_value(event,'metadata',{}) or {}))
    def normalize_trade(self, event, received_at=None):
        received=parse_timestamp(_value(event,'received_timestamp'), received_at or datetime.now(timezone.utc)); exchange=parse_timestamp(_value(event,'exchange_timestamp'), received); provider=parse_timestamp(_value(event,'provider_timestamp'))
        price=safe_float(_value(event,'price')); size=safe_float(_value(event,'size'))
        return NormalizedTrade(symbol=str(_value(event,'symbol','')).strip().upper(), asset_class=str(_value(event,'asset_class','EQUITY')).strip().upper(), price=price, size=size, notional=price*size, exchange_timestamp=exchange.isoformat(), provider_timestamp=provider.isoformat() if provider else None, received_timestamp=received.isoformat(), event_age_seconds=(received-exchange).total_seconds(), exchange=_value(event,'exchange'), conditions=tuple(_value(event,'conditions',()) or ()), source=normalize_source(_value(event,'source')), metadata=dict(_value(event,'metadata',{}) or {}))
