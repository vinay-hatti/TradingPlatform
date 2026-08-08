from __future__ import annotations
import json, os
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from math import log, sqrt
from statistics import mean, pstdev
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from uuid import uuid4
from sqlalchemy import desc, select
from trading_ai.market.models import PriceHistory
from .models import FuturesContractModel, FuturesBarModel, FuturesIntelligenceSnapshotModel

PRODUCT_INDEX={'ES':'SPX','NQ':'NDX','RTY':'RUT'}

def safe(v,d=0.):
    try:return float(v)
    except:return d

def clamp(v,lo=0.,hi=100.):return max(lo,min(hi,float(v)))

class PolygonFuturesProvider:
    """Polygon/Massive U.S. futures REST provider.

    Polygon rebranded to Massive; the current official futures REST base is
    https://api.massive.com. Keep the base URL configurable for account/API migration.
    """
    def __init__(self,api_key=None,base_url=None,timeout=30):
        self.api_key=api_key or os.getenv('POLYGON_API_KEY') or os.getenv('MASSIVE_API_KEY')
        self.base_url=(base_url or os.getenv('POLYGON_FUTURES_BASE_URL') or os.getenv('MASSIVE_FUTURES_BASE_URL') or 'https://api.massive.com').rstrip('/')
        self.timeout=timeout
        if not self.api_key: raise RuntimeError('POLYGON_API_KEY (or MASSIVE_API_KEY) is required for futures ingestion')
    def _redacted_url(self, url):
        p=urlparse(url);q=[]
        for k,v in parse_qsl(p.query,keep_blank_values=True):
            q.append((k,'***REDACTED***' if k.lower() in {'apikey','api_key'} else v))
        return urlunparse((p.scheme,p.netloc,p.path,p.params,urlencode(q),p.fragment))
    def _request_json(self,url):
        req=Request(url,headers={'User-Agent':'TradingPlatform-M71.2'})
        try:
            with urlopen(req,timeout=self.timeout) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            try: body=e.read().decode(errors='replace')
            except Exception: body=''
            raise RuntimeError(f"Massive futures HTTP {e.code}: {body or e.reason}; request={self._redacted_url(url)}") from e
        except URLError as e:
            raise RuntimeError(f"Massive futures request failed: {e.reason}; request={self._redacted_url(url)}") from e
    def _get(self,path,params=None):
        params=dict(params or {});params['apiKey']=self.api_key
        url=f"{self.base_url}{path}?{urlencode(params)}"
        return self._request_json(url)
    def _next(self,url):
        p=urlparse(url);q=dict(parse_qsl(p.query));q['apiKey']=self.api_key
        u=urlunparse((p.scheme,p.netloc,p.path,p.params,urlencode(q),p.fragment))
        return self._request_json(u)
    def contracts(self,product_code,as_of=None,active=True):
        # Keep the contracts query to the parameters confirmed by the provider API.
        # Do not depend on server-side sort/large-limit syntax; normalize and sort locally.
        p={'product_code':product_code}
        if as_of:p['date']=as_of
        if active is not None:p['active']=str(bool(active)).lower()
        data=self._get('/futures/v1/contracts',p);rows=list(data.get('results') or [])
        while data.get('next_url'):
            data=self._next(data['next_url']);rows.extend(data.get('results') or [])
        rows=[x for x in rows if x.get('ticker')]
        rows.sort(key=lambda x:(int(x.get('days_to_maturity') or 999999),str(x.get('ticker'))))
        return rows
    def snapshots(self,product_code):
        data=self._get('/futures/v1/snapshot',{'product_code':product_code,'limit':100})
        rows=list(data.get('results') or [])
        while data.get('next_url'):
            data=self._next(data['next_url']); rows.extend(data.get('results') or [])
        return rows
    def select_front_contract(self,product_code,as_of=None,min_days_to_maturity=5):
        as_of=as_of or date.today().isoformat();rows=self.contracts(product_code,as_of,True)
        singles=[x for x in rows if (x.get('type') in (None,'','single')) and x.get('ticker')]
        viable=[x for x in singles if int(x.get('days_to_maturity') or 0)>=min_days_to_maturity]
        pool=viable or singles
        if not pool: raise RuntimeError(f'No active futures contract found for {product_code} on {as_of}')
        # For the current date prefer the highest-volume eligible contract when the
        # snapshot entitlement is available. This handles quarterly rolls better
        # than a hard-coded calendar ticker. Fall back to nearest eligible maturity.
        if as_of == date.today().isoformat():
            try:
                snaps={x.get('ticker'):x for x in self.snapshots(product_code)}
                ranked=[]
                for x in pool[:6]:
                    ss=snaps.get(x.get('ticker')) or {}; vol=safe((ss.get('session') or {}).get('volume'))
                    ranked.append((vol,-int(x.get('days_to_maturity') or 99999),x))
                if ranked and max(z[0] for z in ranked)>0:return max(ranked,key=lambda z:(z[0],z[1]))[2]
            except Exception:
                pass
        return sorted(pool,key=lambda x:(int(x.get('days_to_maturity') or 99999),str(x.get('ticker'))))[0]
    def aggregates(self,ticker,resolution='1min',start=None,end=None,limit=50000):
        p={'resolution':resolution,'limit':limit}
        if start:p['window_start.gte']=start
        if end:p['window_start.lte']=end
        data=self._get(f'/futures/v1/aggs/{ticker}',p);rows=list(data.get('results') or [])
        while data.get('next_url'):
            data=self._next(data['next_url']);rows.extend(data.get('results') or [])
        return rows

class FuturesIntelligenceService:
    VERSION='M71.2-FUTURES-1.0'
    def __init__(self,session_factory,provider=None):self.session_factory=session_factory;self.provider=provider
    def _provider(self):return self.provider or PolygonFuturesProvider()
    def ingest(self,products=('ES','NQ','RTY'),start=None,end=None,resolutions=('1min','1session'),min_days_to_maturity=5):
        provider=self._provider();end=end or date.today().isoformat();start=start or (date.fromisoformat(end)-timedelta(days=10)).isoformat();summary=[]
        with self.session_factory() as s:
            for product in products:
                contract=provider.select_front_contract(product,end,min_days_to_maturity);ticker=contract['ticker']
                reg=s.get(FuturesContractModel,ticker)
                vals=dict(product_code=product,as_of_date=end,first_trade_date=contract.get('first_trade_date'),last_trade_date=contract.get('last_trade_date'),settlement_date=contract.get('settlement_date'),days_to_maturity=contract.get('days_to_maturity'),trading_venue=contract.get('trading_venue'),active=1,payload_json=contract)
                if reg:
                    for k,v in vals.items():setattr(reg,k,v)
                else:s.add(FuturesContractModel(ticker=ticker,**vals))
                count=0
                for resolution in resolutions:
                    rows=provider.aggregates(ticker,resolution,start,end)
                    for r in rows:
                        ns=str(r.get('window_start'))
                        key=s.execute(select(FuturesBarModel).where(FuturesBarModel.ticker==ticker,FuturesBarModel.resolution==resolution,FuturesBarModel.window_start_ns==ns)).scalars().first()
                        vals2=dict(product_code=product,ticker=ticker,resolution=resolution,window_start_ns=ns,session_end_date=r.get('session_end_date'),open=safe(r.get('open')),high=safe(r.get('high')),low=safe(r.get('low')),close=safe(r.get('close')),volume=safe(r.get('volume')),dollar_volume=safe(r.get('dollar_volume')),transactions=int(r.get('transactions') or 0),settlement_price=r.get('settlement_price'),source='POLYGON_FUTURES',payload_json=r)
                        if key:
                            for k,v in vals2.items():setattr(key,k,v)
                        else:s.add(FuturesBarModel(id=f'm712-fbar-{uuid4().hex}',**vals2))
                        count+=1
                summary.append({'product_code':product,'ticker':ticker,'bars_upserted':count,'start':start,'end':end})
            s.commit()
        intelligence=self.refresh(products)
        return {'status':'READY','provider':'POLYGON_FUTURES','base_url':provider.base_url,'products':summary,'intelligence':intelligence}
    def refresh(self,products=('ES','NQ','RTY')):
        out=[];now=datetime.now(timezone.utc)
        with self.session_factory() as s:
            for product in products:
                reg=s.execute(select(FuturesContractModel).where(FuturesContractModel.product_code==product,FuturesContractModel.active==1).order_by(desc(FuturesContractModel.as_of_date))).scalars().first()
                if not reg:continue
                bars=s.execute(select(FuturesBarModel).where(FuturesBarModel.product_code==product,FuturesBarModel.ticker==reg.ticker,FuturesBarModel.resolution=='1min').order_by(desc(FuturesBarModel.window_start_ns)).limit(5000)).scalars().all()
                bars=list(reversed(bars))
                if len(bars)<20:continue
                closes=[safe(b.close) for b in bars if safe(b.close)>0];last=closes[-1];rets=[log(closes[i]/closes[i-1]) for i in range(1,len(closes)) if closes[i-1]>0]
                rv=(pstdev(rets[-390:])*sqrt(390*252)*100) if len(rets)>=30 else 0.
                v=sum(safe(b.volume) for b in bars[-1440:]);dv=sum(safe(b.dollar_volume) for b in bars[-1440:]);vwap=dv/v if v>0 and dv>0 else mean(closes[-60:])
                mom5=(last/closes[-min(6,len(closes))]-1)*100 if len(closes)>5 else 0.;mom60=(last/closes[-min(61,len(closes))]-1)*100 if len(closes)>60 else 0.
                trend=clamp(50+mom5*18+mom60*8+(8 if last>vwap else -8))
                index=PRODUCT_INDEX[product];cash=s.execute(select(PriceHistory).where(PriceHistory.symbol==index).order_by(desc(PriceHistory.date))).scalars().first();cash_close=safe(getattr(cash,'close',0));basis=((last/cash_close)-1)*100 if cash_close>0 else None
                # CT session convention: 17:00-08:29 overnight; 08:30-15:00 cash/RTH proxy.
                def hour(b):
                    try:return datetime.fromtimestamp(int(b.window_start_ns)/1e9,tz=timezone.utc).astimezone(ZoneInfo('America/Chicago')).hour
                    except:return -1
                recent=bars[-1440:];overn=[b for b in recent if hour(b)>=22 or hour(b)<14];rth=[b for b in recent if 14<=hour(b)<=21]
                oh=max((safe(b.high) for b in overn),default=None);ol=min((safe(b.low) for b in overn),default=None);rh=max((safe(b.high) for b in rth),default=None);rl=min((safe(b.low) for b in rth),default=None)
                momentum=clamp(50+mom5*22+mom60*10);confirm=clamp(.55*trend+.25*momentum+.20*(65 if last>vwap else 35));state='BULLISH' if confirm>=60 else 'BEARISH' if confirm<=40 else 'NEUTRAL'
                payload={'version':self.VERSION,'product_code':product,'ticker':reg.ticker,'index_symbol':index,'last_price':round(last,4),'vwap':round(vwap,4),'overnight_high':oh,'overnight_low':ol,'rth_high':rh,'rth_low':rl,'trend_score':round(trend,2),'momentum_score':round(momentum,2),'realized_volatility':round(rv,2),'basis_pct':None if basis is None else round(basis,4),'confirmation_score':round(confirm,2),'state':state,'bar_count':len(bars),'source':'POLYGON_FUTURES','limitations':['OHLCV-derived confirmation; aggressor-side/order-book metrics require trade/quote/depth entitlement and a later microstructure extension.']}
                s.add(FuturesIntelligenceSnapshotModel(snapshot_id=f'm712-fintel-{uuid4().hex}',product_code=product,ticker=reg.ticker,snapshot_timestamp=now.isoformat(),last_price=last,vwap=vwap,overnight_high=oh,overnight_low=ol,rth_high=rh,rth_low=rl,trend_score=trend,momentum_score=momentum,realized_volatility=rv,basis_pct=basis,confirmation_score=confirm,state=state,payload_json=payload));out.append(payload)
            s.commit()
        return {'status':'READY' if out else 'DEGRADED','snapshots':out,'version':self.VERSION}
    def latest_map(self):
        out={}
        with self.session_factory() as s:
            for p in PRODUCT_INDEX:
                row=s.execute(select(FuturesIntelligenceSnapshotModel).where(FuturesIntelligenceSnapshotModel.product_code==p).order_by(desc(FuturesIntelligenceSnapshotModel.snapshot_timestamp))).scalars().first()
                if row:out[p]=row.payload_json
        return out
