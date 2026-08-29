from __future__ import annotations
from datetime import datetime,timezone
import re
from trading_ai.execution_intelligence.provider import PolygonDirectExecutionQuoteProvider,ExecutionQuoteError


def _age(ts:str|None)->float:
    if not ts:return 1e9
    try:
        dt=datetime.fromisoformat(str(ts).replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return max(0.0,(datetime.now(timezone.utc)-dt).total_seconds())
    except Exception:return 1e9


def polygon_option_symbol_from_local_symbol(local_symbol:str|None)->str|None:
    """Convert an IBKR OCC-style localSymbol into Polygon option identity.

    Example: ``SPX   260918C07725000`` -> ``O:SPX260918C07725000``.
    The local symbol's YYMMDD is the option/OCC identity date and is intentionally
    preferred over IBKR's separate last-trading/expiry field for products such as SPX.
    """
    compact=re.sub(r'\s+','',str(local_symbol or '').upper())
    m=re.fullmatch(r'([A-Z0-9.]{1,8})(\d{6})([CP])(\d{8})',compact)
    if not m:return None
    return f"O:{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"


class M73LiveQuoteService:
    def __init__(self,provider=None):self.provider=provider or PolygonDirectExecutionQuoteProvider()
    def snapshot(self,symbol:str,legs:list[dict],max_age_seconds:float)->dict:
        live=[];ages=[];underlying_candidates=[]
        net_mid=0.0;net_exec_close=0.0;delta=gamma=theta=vega=0.0;ivs=[]
        # Quote exact option legs first. This lets index options (SPX/NDX/RUT) supply
        # underlying_asset.price even when Polygon's stocks snapshot endpoint is not valid.
        for leg in legs:
            option_symbol=str(leg.get('option_symbol') or '').strip()
            if not option_symbol:
                option_symbol=polygon_option_symbol_from_local_symbol(leg.get('local_symbol')) or ''
            if not option_symbol:continue
            q=self.provider.option_quote(symbol,option_symbol).to_dict();side=str(leg.get('side','BUY')).upper();ratio=max(1,int(float(leg.get('quantity',1) or 1)));sign=1 if side=='BUY' else -1
            mid=float(q.get('midpoint') or q.get('last') or 0);bid=float(q.get('bid') or 0);ask=float(q.get('ask') or 0)
            close_px=bid if side=='BUY' else ask
            net_mid+=sign*ratio*mid;net_exec_close+=sign*ratio*close_px
            delta+=sign*ratio*float(q.get('delta') or 0);gamma+=sign*ratio*float(q.get('gamma') or 0);theta+=sign*ratio*float(q.get('theta') or 0);vega+=sign*ratio*float(q.get('vega') or 0)
            if q.get('implied_volatility') is not None:ivs.append(float(q['implied_volatility']))
            if q.get('underlying_price') is not None and float(q.get('underlying_price') or 0)>0:underlying_candidates.append(float(q['underlying_price']))
            age=_age(q.get('quote_timestamp'));ages.append(age);live.append({**leg,**q,'option_symbol':option_symbol,'quote_age_seconds':age,'close_execution_price':close_px})

        underlying_error=None;index_error=None;uq=None
        # Prefer the exact option snapshot's underlying_asset.price when available. This is
        # both contract-consistent and avoids unnecessary cross-asset endpoint calls.
        if underlying_candidates:
            px=sum(underlying_candidates)/len(underlying_candidates)
            ts=min((x.get('quote_timestamp') for x in live if x.get('quote_timestamp')),default=None)
            uq={'instrument':str(symbol).upper(),'instrument_type':'UNDERLYING_FROM_OPTION_SNAPSHOT','bid':0.0,'ask':0.0,'midpoint':px,'last':px,'quote_timestamp':ts,'received_at':datetime.now(timezone.utc).isoformat()}
        else:
            try:
                uq=self.provider.underlying_quote(symbol).to_dict()
                ages.append(_age(uq.get('quote_timestamp')))
            except ExecutionQuoteError as exc:
                underlying_error=str(exc)
                # SPX/NDX/RUT and other index underlyings are not valid stock tickers.
                # Fall back generically to Polygon's indices snapshot using I:<symbol>.
                try:
                    uq=self.provider.index_quote(symbol).to_dict()
                    ages.append(_age(uq.get('quote_timestamp')))
                except ExecutionQuoteError as idx_exc:
                    index_error=str(idx_exc)
                    raise ExecutionQuoteError(
                        f'Polygon underlying lookup failed for {symbol}; stock={underlying_error}; index={index_error}'
                    ) from idx_exc
        underlying_price=float((uq or {}).get('midpoint') or (uq or {}).get('last') or 0)
        if underlying_price<=0:raise ExecutionQuoteError(f'Polygon returned no underlying price for {symbol}')
        max_age=max(ages or [1e9]);fresh=max_age<=max_age_seconds
        return {'source':'POLYGON_DIRECT','received_at':datetime.now(timezone.utc).isoformat(),'underlying':uq,'underlying_price':underlying_price,'underlying_fallback_used':bool(underlying_candidates or underlying_error),'underlying_quote_error':underlying_error,'index_quote_error':index_error,'live_legs':live,'option_mark':abs(net_mid),'close_executable_mark':abs(net_exec_close),'delta':delta,'gamma':gamma,'theta':theta,'vega':vega,'implied_volatility':sum(ivs)/len(ivs) if ivs else None,'max_quote_age_seconds':max_age,'quote_fresh':fresh}
