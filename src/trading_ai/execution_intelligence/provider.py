from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
import json,math,time
from urllib.parse import quote,urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from trading_ai.options.tls_context import create_verified_ssl_context,resolve_ca_bundle,TLSConfigurationError

class ExecutionQuoteError(RuntimeError):pass

def _num(v,default=0.0):
    try:
        f=float(v);return f if math.isfinite(f) else default
    except (TypeError,ValueError):return default

def _ts(v):
    if v in (None,'',0):return None
    try:
        raw=int(v)
        if raw>10**17: raw=raw/1_000_000_000
        elif raw>10**14: raw=raw/1_000_000
        elif raw>10**11: raw=raw/1_000
        return datetime.fromtimestamp(raw,tz=timezone.utc).isoformat()
    except Exception:return str(v)

@dataclass(frozen=True)
class DirectQuote:
    instrument:str; instrument_type:str; bid:float; ask:float; midpoint:float; bid_size:float; ask_size:float; last:float; quote_timestamp:str|None; received_at:str; implied_volatility:float|None=None; delta:float|None=None; gamma:float|None=None; theta:float|None=None; vega:float|None=None; open_interest:int|None=None; volume:int|None=None; underlying_price:float|None=None; raw:dict|None=None
    def to_dict(self):return asdict(self)

class PolygonDirectExecutionQuoteProvider:
    BASE_URL='https://api.polygon.io'
    def __init__(self,api_key=None,timeout_seconds=5.0):
        if api_key is None:
            from trading_ai.config.settings import settings
            api_key=settings.polygon_api_key
        if not api_key:raise ExecutionQuoteError('POLYGON_API_KEY is not configured')
        self.api_key=api_key;self.timeout=float(timeout_seconds)
        try:self.ssl_context=create_verified_ssl_context();self.ca_bundle=str(resolve_ca_bundle())
        except TLSConfigurationError as e:raise ExecutionQuoteError(str(e)) from e
    def _get(self,path,params=None):
        q=dict(params or {});q['apiKey']=self.api_key
        url=f'{self.BASE_URL}{path}?{urlencode(q)}'
        req=Request(url,headers={'Accept':'application/json','User-Agent':'TradingPlatform-M70/1.0'})
        try:
            with urlopen(req,timeout=self.timeout,context=self.ssl_context) as r:return json.loads(r.read().decode())
        except HTTPError as e:
            body=e.read().decode(errors='replace');raise ExecutionQuoteError(f'Polygon HTTP {e.code}: {body[:400]}') from e
        except (URLError,TimeoutError) as e:raise ExecutionQuoteError(f'Polygon direct quote failed: {e}') from e
    def option_quote(self,underlying,option_symbol):
        payload=self._get(f'/v3/snapshot/options/{quote(str(underlying).upper(),safe=":")}/{quote(str(option_symbol).upper(),safe=":")}')
        r=payload.get('results') or payload.get('result') or {}
        if isinstance(r,list):r=r[0] if r else {}
        details=r.get('details') or {};q=r.get('last_quote') or {};trade=r.get('last_trade') or {};day=r.get('day') or {};g=r.get('greeks') or {};ua=r.get('underlying_asset') or {}
        bid=_num(q.get('bid'));ask=_num(q.get('ask'));mid=(bid+ask)/2 if bid>0 and ask>=bid else 0.0;last=_num(trade.get('price') or day.get('close') or r.get('fmv'))
        if mid<=0 and last<=0:raise ExecutionQuoteError(f'Polygon returned no executable price for {option_symbol}')
        return DirectQuote(str(option_symbol).upper(),'OPTION',bid,ask,mid,_num(q.get('bid_size')),_num(q.get('ask_size')),last,_ts(q.get('last_updated') or q.get('sip_timestamp') or q.get('participant_timestamp') or r.get('updated')),datetime.now(timezone.utc).isoformat(),_num(r.get('implied_volatility'),None),_num(g.get('delta'),None),_num(g.get('gamma'),None),_num(g.get('theta'),None),_num(g.get('vega'),None),int(_num(r.get('open_interest'),0)),int(_num(day.get('volume'),0)),_num(ua.get('price'),None),r)
    def underlying_quote(self,symbol):
        payload=self._get(f'/v2/snapshot/locale/us/markets/stocks/tickers/{quote(str(symbol).upper())}')
        r=(payload.get('ticker') or payload.get('results') or {});q=r.get('lastQuote') or r.get('last_quote') or {};trade=r.get('lastTrade') or r.get('last_trade') or {};day=r.get('day') or {}
        bid=_num(q.get('p') or q.get('bid'));ask=_num(q.get('P') or q.get('ask'));mid=(bid+ask)/2 if bid>0 and ask>=bid else 0.0;last=_num(trade.get('p') or trade.get('price') or day.get('c') or day.get('close'))
        if mid<=0 and last<=0:raise ExecutionQuoteError(f'Polygon returned no underlying price for {symbol}')
        return DirectQuote(str(symbol).upper(),'UNDERLYING',bid,ask,mid,_num(q.get('s') or q.get('bid_size')),_num(q.get('S') or q.get('ask_size')),last,_ts(q.get('t') or r.get('updated')),datetime.now(timezone.utc).isoformat(),raw=r)
