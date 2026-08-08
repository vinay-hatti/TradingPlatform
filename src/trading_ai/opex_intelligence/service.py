from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from math import exp, log, sqrt
from statistics import NormalDist, mean, median, pstdev
from uuid import uuid4
from sqlalchemy import desc, select
from trading_ai.institutional_market_structure.database_models import (
    DealerPositionSnapshotModel,
    DealerExpirationProfileModel,
    DealerStrikeProfileModel,
    IVSurfaceSnapshotModel,
)
from trading_ai.market.models import PriceHistory
from trading_ai.market_overview.database_models import MarketOverviewSnapshotModel
from trading_ai.option_valuation_intelligence.models import OptionValuationEventModel
from trading_ai.futures_intelligence.service import FuturesIntelligenceService, PRODUCT_INDEX
from .models import OpexForecastSnapshotModel, OpexForecastPublicationModel, OpexForecastOutcomeModel

INDEXES = ('SPX', 'NDX', 'RUT')
NORMAL = NormalDist()

def clamp(x, lo=0., hi=100.): return max(lo, min(hi, float(x)))
def safe(x, d=0.):
    try: return float(x)
    except: return d

def is_monthly_opex(d: date) -> bool: return d.weekday() == 4 and 15 <= d.day <= 21

def cycle_type(d: date) -> str:
    if is_monthly_opex(d) and d.month in (3, 6, 9, 12): return 'QUARTERLY_OPEX'
    if is_monthly_opex(d): return 'MONTHLY_OPEX'
    return 'WEEKLY_EXPIRY'

def quantile(values, q: float):
    vals = sorted(float(x) for x in values if x is not None)
    if not vals: return None
    if len(vals) == 1: return vals[0]
    q = max(0., min(1., q)); pos = q * (len(vals) - 1); lo = int(pos); hi = min(len(vals) - 1, lo + 1); w = pos - lo
    return vals[lo] * (1 - w) + vals[hi] * w

class OpexIntelligenceService:
    VERSION = 'M71.3.1-OPEX-CONSISTENCY-HARDENING-1.0'
    def __init__(self, session_factory): self.session_factory = session_factory

    def refresh(self, cycles: int = 3, symbols=INDEXES):
        try: self.realize_outcomes()
        except Exception: pass
        now = datetime.now(timezone.utc); results = []
        with self.session_factory() as s:
            overview = s.execute(select(MarketOverviewSnapshotModel).order_by(desc(MarketOverviewSnapshotModel.snapshot_timestamp))).scalars().first()
            contexts = {}
            for symbol in symbols:
                snap = s.execute(select(DealerPositionSnapshotModel).where(DealerPositionSnapshotModel.symbol == symbol).order_by(desc(DealerPositionSnapshotModel.as_of_date))).scalars().first()
                if not snap: continue
                prices = s.execute(select(PriceHistory).where(PriceHistory.symbol == symbol).order_by(desc(PriceHistory.date)).limit(1400)).scalars().all()
                contexts[symbol] = {'snap': snap, 'prices': list(reversed(prices)), 'trend': self._trend(list(reversed(prices)))}
            cross_index = self._cross_index_confirmation({k: v['trend'] for k, v in contexts.items()}, overview)
            try: futures_map = FuturesIntelligenceService(self.session_factory).latest_map()
            except Exception: futures_map = {}

            for symbol, ctx in contexts.items():
                snap = ctx['snap']; prices = ctx['prices']; trend = ctx['trend']
                expiries = s.execute(select(DealerExpirationProfileModel).where(DealerExpirationProfileModel.symbol == symbol, DealerExpirationProfileModel.as_of_date == snap.as_of_date).order_by(DealerExpirationProfileModel.expiry)).scalars().all()
                monthly = [x for x in expiries if x.expiry >= snap.as_of_date and is_monthly_opex(x.expiry)][:cycles]
                if not monthly: monthly = [x for x in expiries if x.expiry >= snap.as_of_date][:cycles]
                previous = s.execute(select(DealerPositionSnapshotModel).where(DealerPositionSnapshotModel.symbol == symbol, DealerPositionSnapshotModel.as_of_date < snap.as_of_date).order_by(desc(DealerPositionSnapshotModel.as_of_date))).scalars().first()
                tactical = [x for x in expiries if 0 <= int(x.dte) <= 2]
                for ep in monthly:
                    strikes = s.execute(select(DealerStrikeProfileModel).where(DealerStrikeProfileModel.symbol == symbol, DealerStrikeProfileModel.as_of_date == snap.as_of_date, DealerStrikeProfileModel.expiry == ep.expiry).order_by(DealerStrikeProfileModel.strike)).scalars().all()
                    prior_ep = s.execute(select(DealerExpirationProfileModel).where(DealerExpirationProfileModel.symbol == symbol, DealerExpirationProfileModel.expiry == ep.expiry, DealerExpirationProfileModel.as_of_date < snap.as_of_date).order_by(desc(DealerExpirationProfileModel.as_of_date))).scalars().first()
                    prior_strikes = []
                    if prior_ep:
                        prior_strikes = s.execute(select(DealerStrikeProfileModel).where(DealerStrikeProfileModel.symbol == symbol, DealerStrikeProfileModel.as_of_date == prior_ep.as_of_date, DealerStrikeProfileModel.expiry == ep.expiry).order_by(DealerStrikeProfileModel.strike)).scalars().all()
                    surface = s.execute(select(IVSurfaceSnapshotModel).where(IVSurfaceSnapshotModel.symbol == symbol, IVSurfaceSnapshotModel.as_of_date == snap.as_of_date, IVSurfaceSnapshotModel.expiry == ep.expiry).order_by(IVSurfaceSnapshotModel.strike)).scalars().all()
                    events = s.execute(select(OptionValuationEventModel).where(OptionValuationEventModel.status == 'ACTIVE', OptionValuationEventModel.event_date >= str(snap.as_of_date), OptionValuationEventModel.event_date <= str(ep.expiry))).scalars().all()
                    prior_forecast = s.execute(select(OpexForecastSnapshotModel).where(OpexForecastSnapshotModel.symbol == symbol, OpexForecastSnapshotModel.expiration == str(ep.expiry)).order_by(desc(OpexForecastSnapshotModel.forecast_timestamp))).scalars().first()
                    payload = self._forecast(snap, previous, ep, prior_ep, strikes, trend, events, now, surface=surface, prices=prices, prior_forecast=prior_forecast, prior_strikes=prior_strikes, tactical_expiries=tactical, cross_index=cross_index, overview=overview, futures_map=futures_map)
                    fid = f"m711-opex-{uuid4().hex}"
                    row = OpexForecastSnapshotModel(
                        forecast_id=fid, symbol=symbol, expiration=str(ep.expiry), cycle_type=payload['cycle_type'], dte=ep.dte,
                        forecast_timestamp=now.isoformat(), source_as_of_date=str(snap.as_of_date), spot=snap.spot_price,
                        range50_low=payload['ranges']['50']['low'], range50_high=payload['ranges']['50']['high'],
                        range68_low=payload['ranges']['68']['low'], range68_high=payload['ranges']['68']['high'],
                        range90_low=payload['ranges']['90']['low'], range90_high=payload['ranges']['90']['high'],
                        magnet=payload['magnet']['price'], magnet_probability=payload['magnet']['probability'], support=payload['levels']['support'], resistance=payload['levels']['resistance'],
                        gamma_flip_current=snap.gamma_flip, gamma_flip_forecast=payload['migration']['gamma_flip']['forecast'], call_wall_current=snap.primary_call_wall, call_wall_forecast=payload['migration']['call_wall']['forecast'], put_wall_current=snap.primary_put_wall, put_wall_forecast=payload['migration']['put_wall']['forecast'], dealer_pressure=payload['dealer']['pressure_score'], confidence=payload['confidence']['overall'], payload_json=payload)
                    s.add(row); results.append({'forecast_id': fid, **payload})
            pub = s.execute(select(OpexForecastPublicationModel).where(OpexForecastPublicationModel.publication_name == 'current_opex_intelligence')).scalars().first()
            pp = {'version': self.VERSION, 'symbols': list(symbols), 'forecast_ids': [x['forecast_id'] for x in results]}
            if pub:
                pub.status = 'READY' if results else 'DEGRADED'; pub.published_at = now.isoformat(); pub.forecast_count = len(results); pub.payload_json = pp
            else:
                s.add(OpexForecastPublicationModel(publication_id=f'm711-pub-{uuid4().hex}', publication_name='current_opex_intelligence', status='READY' if results else 'DEGRADED', published_at=now.isoformat(), forecast_count=len(results), payload_json=pp))
            s.commit()
        return {'status': 'READY' if results else 'DEGRADED', 'built': len(results), 'symbols': list(symbols), 'cycles': cycles, 'published_at': now.isoformat(), 'version': self.VERSION}

    def dashboard(self, symbol: str | None = None, history_limit: int = 8):
        with self.session_factory() as s:
            latest_pub = s.execute(select(OpexForecastPublicationModel).where(OpexForecastPublicationModel.publication_name == 'current_opex_intelligence')).scalars().first()
            q = select(OpexForecastSnapshotModel)
            if symbol: q = q.where(OpexForecastSnapshotModel.symbol == symbol.upper())
            rows = s.execute(q.order_by(desc(OpexForecastSnapshotModel.forecast_timestamp))).scalars().all()
            latest = {}; history = defaultdict(list)
            for r in rows:
                key = (r.symbol, r.expiration); history[key].append(r.payload_json)
                if key not in latest: latest[key] = {'forecast_id': r.forecast_id, **r.payload_json}
            forecasts = list(latest.values()); forecasts.sort(key=lambda x: (x['symbol'], x['expiration']))
            for f in forecasts: f['history'] = history[(f['symbol'], f['expiration'])][:history_limit]
            return {'status': latest_pub.status if latest_pub else 'NOT_AVAILABLE', 'published_at': latest_pub.published_at if latest_pub else None, 'version': self.VERSION, 'forecasts': forecasts, 'cross_opex': self._cross_opex(forecasts), 'calibration': self._calibration(s)}

    def realize_outcomes(self):
        today = date.today(); created = 0
        with self.session_factory() as s:
            rows = s.execute(select(OpexForecastSnapshotModel).where(OpexForecastSnapshotModel.expiration < str(today))).scalars().all()
            for r in rows:
                if s.execute(select(OpexForecastOutcomeModel).where(OpexForecastOutcomeModel.forecast_id == r.forecast_id)).scalars().first(): continue
                px = s.execute(select(PriceHistory).where(PriceHistory.symbol == r.symbol, PriceHistory.date <= date.fromisoformat(r.expiration)).order_by(desc(PriceHistory.date))).scalars().first()
                if not px: continue
                settle = float(px.close); md = None if r.magnet is None else abs(settle - r.magnet) / settle * 100
                p = r.payload_json or {}; ar = p.get('actionable_range') or {}; mz = (p.get('magnet') or {}).get('zone') or {}
                extra = {'in_actionable_range': int(safe(ar.get('low'), 1e99) <= settle <= safe(ar.get('high'), -1e99)) if ar.get('low') is not None and ar.get('high') is not None else None,
                         'in_magnet_zone': int(safe(mz.get('low'), 1e99) <= settle <= safe(mz.get('high'), -1e99)) if mz.get('low') is not None and mz.get('high') is not None else None}
                s.add(OpexForecastOutcomeModel(outcome_id=f'm711-out-{uuid4().hex}', forecast_id=r.forecast_id, symbol=r.symbol, expiration=r.expiration, settlement_price=settle, in_50=int(r.range50_low <= settle <= r.range50_high), in_68=int(r.range68_low <= settle <= r.range68_high), in_90=int(r.range90_low <= settle <= r.range90_high), magnet_distance_pct=md, realized_at=datetime.now(timezone.utc).isoformat(), payload_json=extra)); created += 1
            s.commit()
        return {'status': 'READY', 'created': created}

    def _trend(self, prices):
        closes = [safe(x.close) for x in prices if x.close]
        if len(closes) < 21: return {'score': 50., 'direction': 'NEUTRAL', 'rv20': 20., 'momentum20': 0.}
        rets = [log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
        rv = (pstdev(rets[-20:]) * sqrt(252) * 100) if len(rets) >= 20 else 20
        ma20 = mean(closes[-20:]); ma60 = mean(closes[-60:]) if len(closes) >= 60 else ma20; mom = (closes[-1] / closes[-21] - 1) * 100
        score = clamp(50 + mom * 2 + (10 if ma20 > ma60 else -10))
        return {'score': score, 'direction': 'BULLISH' if score >= 57 else 'BEARISH' if score <= 43 else 'NEUTRAL', 'rv20': rv, 'momentum20': mom}

    def _surface_distribution(self, surface, spot):
        usable = defaultdict(list)
        for r in surface or []:
            mid = safe(getattr(r, 'mid', 0)); bid = safe(getattr(r, 'bid', 0)); ask = safe(getattr(r, 'ask', 0)); strike = safe(getattr(r, 'strike', 0)); typ = str(getattr(r, 'option_type', '')).upper()
            if strike > 0 and mid > 0 and ask >= bid >= 0 and typ in {'CALL', 'PUT', 'C', 'P'}: usable['CALL' if typ.startswith('C') else 'PUT'].append((strike, mid, safe(getattr(r, 'spread_pct', 0)), safe(getattr(r, 'implied_volatility', 0))))
        side = max(usable, key=lambda k: len(usable[k]), default=None)
        pts = sorted(usable.get(side, []))
        if len(pts) < 7: return {'status': 'INSUFFICIENT_DATA', 'point_count': len(pts), 'ranges': None, 'median': None, 'mode': None, 'quality': 0.}
        # Smooth one pass to reduce quote microstructure noise before the Breeden-Litzenberger finite-difference estimate.
        sm = []
        for i, (k, m, spr, iv) in enumerate(pts):
            mm = m if i in (0, len(pts) - 1) else (pts[i-1][1] + 2*m + pts[i+1][1]) / 4
            sm.append((k, mm, spr, iv))
        masses = []
        violations = 0
        for i in range(1, len(sm)-1):
            k0,c0,_,_ = sm[i-1]; k1,c1,spr,iv = sm[i]; k2,c2,_,_ = sm[i+1]
            if k1 <= k0 or k2 <= k1: continue
            sl = (c1-c0)/(k1-k0); sr = (c2-c1)/(k2-k1); second = 2*(sr-sl)/(k2-k0)
            if second < 0: violations += 1
            mass = max(0., second) * ((k2-k0)/2)
            if mass > 0: masses.append((k1, mass))
        total = sum(m for _,m in masses)
        if total <= 0 or len(masses) < 4: return {'status': 'INSUFFICIENT_CONVEXITY', 'point_count': len(pts), 'ranges': None, 'median': None, 'mode': None, 'quality': 0.}
        dist = [(k,m/total) for k,m in masses]
        def qtile(q):
            c=0
            for k,m in dist:
                c += m
                if c >= q: return k
            return dist[-1][0]
        ranges = {'50': {'low': round(qtile(.25),2), 'high': round(qtile(.75),2)}, '68': {'low': round(qtile(.16),2), 'high': round(qtile(.84),2)}, '90': {'low': round(qtile(.05),2), 'high': round(qtile(.95),2)}}
        avg_spread = mean(abs(x[2]) for x in pts if x[2] is not None) if pts else 0
        strike_span = (pts[-1][0]-pts[0][0])/max(spot,1)
        quality = clamp(45 + min(25, len(pts)*1.2) + min(20, strike_span*100) - min(25, avg_spread*100) - min(20, violations*2))
        return {'status': 'READY', 'method': 'BREEDEN_LITZENBERGER_FINITE_DIFFERENCE', 'option_side': side, 'point_count': len(pts), 'ranges': ranges, 'median': round(qtile(.5),2), 'mode': round(max(dist,key=lambda x:x[1])[0],2), 'quality': round(quality,2), 'density': [{'price': round(k,2), 'probability_mass': round(m*100,4)} for k,m in dist]}

    def _historical_opex_analogs(self, prices, dte, trend):
        rows = [x for x in prices if getattr(x, 'date', None) and safe(getattr(x, 'close', 0)) > 0]
        if len(rows) < 180: return {'status': 'INSUFFICIENT_DATA', 'sample_size': 0}
        dates = [x.date for x in rows]; closes = [safe(x.close) for x in rows]; horizon = max(3, min(63, round(max(1,dte)*252/365)))
        current_rv = safe(trend.get('rv20'),20); current_mom = safe(trend.get('momentum20'),0); analogs=[]
        for i in range(40, len(rows)-horizon):
            exp_date = dates[i+horizon]
            if not is_monthly_opex(exp_date): continue
            rs=[log(closes[j]/closes[j-1]) for j in range(i-19,i+1) if closes[j-1]>0]
            rv=pstdev(rs)*sqrt(252)*100 if len(rs)>=15 else 0; mom=(closes[i]/closes[i-20]-1)*100
            rv_gap=abs(rv-current_rv)/max(current_rv,5); mom_gap=abs(mom-current_mom)
            if rv_gap > .45 or mom_gap > 10: continue
            ret=(closes[i+horizon]/closes[i]-1); path=closes[i:i+horizon+1]; mfe=max(p/closes[i]-1 for p in path); mae=min(p/closes[i]-1 for p in path)
            similarity=clamp(100*exp(-(rv_gap*2.2 + abs(mom_gap)/8.0)))
            analogs.append({'expiration':str(exp_date),'return':ret,'mfe':mfe,'mae':mae,'rv20':rv,'momentum20':mom,'similarity_score':round(similarity,2)})
        if len(analogs)<5: return {'status':'INSUFFICIENT_DATA','sample_size':len(analogs)}
        rets=[a['return'] for a in analogs]; mfes=[a['mfe'] for a in analogs]; maes=[a['mae'] for a in analogs]
        ranked=sorted(analogs,key=lambda a:a.get('similarity_score',0),reverse=True)
        top=[]
        for rank,a in enumerate(ranked[:10],1):
            top.append({'rank':rank,'expiration':a['expiration'],'similarity_score':a['similarity_score'],'settlement_return_pct':round(a['return']*100,2),'max_upside_excursion_pct':round(a['mfe']*100,2),'max_downside_excursion_pct':round(a['mae']*100,2),'rv20':round(a['rv20'],2),'momentum20':round(a['momentum20'],2)})
        return {'status':'READY','sample_size':len(analogs),'return_quantiles':{'p05':round(quantile(rets,.05)*100,2),'p16':round(quantile(rets,.16)*100,2),'p25':round(quantile(rets,.25)*100,2),'p50':round(quantile(rets,.5)*100,2),'p75':round(quantile(rets,.75)*100,2),'p84':round(quantile(rets,.84)*100,2),'p95':round(quantile(rets,.95)*100,2)},'median_max_excursion_up_pct':round(median(mfes)*100,2),'median_max_excursion_down_pct':round(median(maes)*100,2),'top_analogs':top,'recent_analogs':analogs[-8:]}

    def _model_calibrated_ranges(self, spot, heuristic_ranges, surface_dist, analogs, event_abs, prior_forecast):
        weights=[]; sources=[]
        def add(name,ranges,w):
            if ranges and w>0: weights.append(w); sources.append((name,ranges,w))
        add('HEURISTIC_IMPLIED_REALIZED', heuristic_ranges, .35)
        if surface_dist.get('ranges'): add('OPTION_SURFACE_RND', surface_dist['ranges'], .45*surface_dist.get('quality',0)/100)
        if analogs.get('status')=='READY':
            q=analogs['return_quantiles']; ar={'50':{'low':spot*(1+q['p25']/100),'high':spot*(1+q['p75']/100)},'68':{'low':spot*(1+q['p16']/100),'high':spot*(1+q['p84']/100)},'90':{'low':spot*(1+q['p05']/100),'high':spot*(1+q['p95']/100)}}; add('HISTORICAL_OPEX_ANALOGS',ar,min(.30,.08+analogs['sample_size']/120))
        denom=sum(weights) or 1
        out={}
        for k in ('50','68','90'):
            lo=sum(r[k]['low']*w for _,r,w in sources)/denom; hi=sum(r[k]['high']*w for _,r,w in sources)/denom
            # Event uncertainty remains explicit in unconditional calibrated ranges; it is removed in conditional base-case ranges.
            widen = event_abs * {'50':.18,'68':.32,'90':.65}[k]
            lo -= widen; hi += widen
            out[k]={'low':round(lo,2),'high':round(hi,2)}
        posterior={'prior_used':False,'center_shift':0.,'width_change_pct':0.}
        if prior_forecast and prior_forecast.payload_json:
            pr=(prior_forecast.payload_json or {}).get('model_calibrated_ranges') or (prior_forecast.payload_json or {}).get('ranges')
            if pr and pr.get('68'):
                prior_center=(safe(pr['68']['low'])+safe(pr['68']['high']))/2; cur_center=(out['68']['low']+out['68']['high'])/2
                prior_width=max(1.,safe(pr['68']['high'])-safe(pr['68']['low'])); cur_width=max(1.,out['68']['high']-out['68']['low'])
                agreement=exp(-abs(cur_center-prior_center)/max(cur_width,.01)*3); prior_w=.20+.25*agreement
                for k in ('50','68','90'):
                    if pr.get(k): out[k]={'low':round((1-prior_w)*out[k]['low']+prior_w*safe(pr[k]['low']),2),'high':round((1-prior_w)*out[k]['high']+prior_w*safe(pr[k]['high']),2)}
                new_width=out['68']['high']-out['68']['low']; posterior={'prior_used':True,'prior_forecast_timestamp':prior_forecast.forecast_timestamp,'agreement_score':round(agreement*100,2),'center_shift':round(cur_center-prior_center,2),'width_change_pct':round((new_width-prior_width)/prior_width*100,2)}
        return out, {'sources':[{'name':n,'weight':round(w/denom*100,2)} for n,_,w in sources], **posterior}

    def _cross_index_confirmation(self, trends, overview):
        vals=[safe(v.get('score'),50) for v in trends.values()]
        if not vals: return {'score':50.,'state':'UNAVAILABLE','components':{}}
        dispersion=pstdev(vals) if len(vals)>1 else 0; bulls=sum(v>=57 for v in vals); bears=sum(v<=43 for v in vals); consensus=max(bulls,bears,len(vals)-bulls-bears)/len(vals)
        breadth=safe(getattr(overview,'breadth_score',50),50) if overview else 50; trend_score=safe(getattr(overview,'trend_score',50),50) if overview else mean(vals)
        score=clamp(100-dispersion*2)*.45 + consensus*100*.35 + (100-abs(trend_score-breadth))*.20
        state='BULLISH_CONFIRMED' if bulls==len(vals) else 'BEARISH_CONFIRMED' if bears==len(vals) else 'DIVERGENT' if dispersion>12 else 'MIXED'
        return {'score':round(score,2),'state':state,'components':{'index_trend_scores':{k:round(safe(v.get('score'),50),2) for k,v in trends.items()},'breadth_score':round(breadth,2),'market_trend_score':round(trend_score,2),'dispersion':round(dispersion,2)}}

    def _position_change(self, strikes, prior_strikes):
        cur_oi=sum(safe(getattr(x,'call_open_interest',0))+safe(getattr(x,'put_open_interest',0)) for x in strikes); prev_oi=sum(safe(getattr(x,'call_open_interest',0))+safe(getattr(x,'put_open_interest',0)) for x in prior_strikes); vol=sum(safe(getattr(x,'call_volume',0))+safe(getattr(x,'put_volume',0)) for x in strikes)
        delta=cur_oi-prev_oi if prior_strikes else None; pct=None if not prior_strikes or prev_oi<=0 else delta/prev_oi*100
        if delta is None: state='NO_PRIOR_OI'
        elif abs(delta) <= max(100,vol*.08): state='MIXED_OR_ROLL' if vol>cur_oi*.10 else 'STABLE'
        elif delta>0: state='LIKELY_OPENING'
        else: state='LIKELY_CLOSING'
        conf=35 if delta is None else clamp(50+min(35,abs(delta)/max(vol,1)*35))
        return {'state':state,'confidence':round(conf,2),'current_open_interest':round(cur_oi,2),'prior_open_interest':round(prev_oi,2) if prior_strikes else None,'open_interest_change':round(delta,2) if delta is not None else None,'open_interest_change_pct':round(pct,2) if pct is not None else None,'current_volume':round(vol,2),'method':'OI_CHANGE_PLUS_INTRADAY_VOLUME_INFERENCE'}

    def _touch_probability(self, spot, level, sigma_pct, dte, trend_score):
        if not level or level<=0 or spot<=0: return 0.
        sigma=max(.04,sigma_pct/100); t=max(1,dte)/252; z=abs(log(level/spot))/(sigma*sqrt(t)); p=clamp(2*(1-NORMAL.cdf(z))*100)
        aligned=(level>spot and trend_score>50) or (level<spot and trend_score<50); p*=1.12 if aligned else .90
        return clamp(p)

    def _level_probabilities(self, spot, dte, trend, levels, strikes, surface_dist):
        sigma=safe(trend.get('rv20'),20); smap={safe(x.strike):x for x in strikes}; candidates=[]; seen=set()
        for name,price in levels:
            if price is None or safe(price)<=0: continue
            p=round(safe(price),4)
            if any(abs(p-x)/max(spot,1)<.001 for x in seen): continue
            seen.add(p); hit=self._touch_probability(spot,p,sigma,dte,safe(trend.get('score'),50)); nearest=min(strikes,key=lambda x:abs(safe(x.strike)-p),default=None)
            pin=safe(getattr(nearest,'pin_score',50),50) if nearest else 50; liq=safe(getattr(nearest,'liquidity_score',50),50) if nearest else 50; gex=safe(getattr(nearest,'net_gamma_exposure',0),0) if nearest else 0
            if p<spot: hold=clamp(48+.22*pin+.12*liq+(8 if gex>0 else -4)-(safe(trend.get('score'),50)-50)*.15)
            else: hold=clamp(48+.22*pin+.12*liq+(8 if gex>0 else -4)+(safe(trend.get('score'),50)-50)*.15)
            accept=clamp(hit*(100-hold)/100); candidates.append({'label':name,'price':round(p,2),'side':'UPSIDE' if p>spot else 'DOWNSIDE' if p<spot else 'AT_SPOT','touch_probability':round(hit,2),'acceptance_probability':round(accept,2),'hold_probability':round(hold,2),'break_probability':round(100-hold,2)})
        for side in ('UPSIDE','DOWNSIDE'):
            side_rows=sorted([x for x in candidates if x['side']==side],key=lambda x:abs(x['price']-spot)); survival=1.
            for x in side_rows:
                x['first_touch_probability']=round(clamp(x['touch_probability']*survival),2); survival*=max(0.,1-x['touch_probability']/100*.72)
        for x in candidates:
            x.setdefault('first_touch_probability',round(x['touch_probability'],2))
        return sorted(candidates,key=lambda x:abs(x['price']-spot))

    def _magnet_zone(self, magnet, magnet_prob, mags, surface_dist, spot):
        if magnet is None: return {'low':None,'high':None,'probability':0.,'half_width':None}
        strikes=sorted({safe(x[0]) for x in mags if safe(x[0])>0}); spacings=[b-a for a,b in zip(strikes,strikes[1:]) if b>a]; spacing=median(spacings) if spacings else spot*.0025; half=max(spacing/2,spot*.0020)
        prob=0.
        if surface_dist.get('density'):
            prob=sum(safe(x['probability_mass']) for x in surface_dist['density'] if abs(safe(x['price'])-magnet)<=half)
        if prob<=0 and mags:
            total=sum(x[1] for x in mags) or 1; prob=sum(x[1] for x in mags if abs(x[0]-magnet)<=half)/total*100
        return {'low':round(magnet-half,2),'high':round(magnet+half,2),'probability':round(clamp(max(prob,magnet_prob)),2),'half_width':round(half,2)}

    def _conditional_distributions(self, model_ranges, center, event_move_pct, spot, bull_prob, bear_prob):
        base68=model_ranges['68']; base_width=(base68['high']-base68['low'])/2; event_abs=spot*event_move_pct/100
        if event_move_pct<=0: return [{'name':'NO_MAJOR_EVENT_SHOCK','probability':100.,'range':{'low':round(center-base_width*.72,2),'high':round(center+base_width*.72,2)},'condition':'Current positioning/regime persists'}]
        shock=clamp(18+event_move_pct*5,18,46); bull_share=safe(bull_prob)/(safe(bull_prob)+safe(bear_prob)+1e-9); bullp=shock*bull_share; bearp=shock-bullp; basep=100-shock
        return [
            {'name':'BASE_EVENT_OUTCOME','probability':round(basep,2),'range':{'low':round(center-base_width*.62,2),'high':round(center+base_width*.62,2)},'condition':'Event result does not materially reprice volatility or trend'},
            {'name':'BULLISH_EVENT_OUTCOME','probability':round(bullp,2),'range':{'low':round(center+event_abs*.15,2),'high':round(model_ranges['90']['high'],2)},'condition':'Positive event impulse plus upside acceptance'},
            {'name':'BEARISH_EVENT_OUTCOME','probability':round(bearp,2),'range':{'low':round(model_ranges['90']['low'],2),'high':round(center-event_abs*.15,2)},'condition':'Negative event impulse plus downside acceptance'},
        ]

    def _strike_spacing(self, strikes, spot):
        vals=sorted({safe(getattr(x,'strike',0)) for x in strikes if safe(getattr(x,'strike',0))>0 and abs(safe(getattr(x,'strike',0))-spot)/max(spot,1)<.12})
        diffs=[b-a for a,b in zip(vals,vals[1:]) if b>a]
        return median(diffs) if diffs else max(5.,spot*.0025)

    def _magnet_zone_heatmap(self, magnet, mags, surface_dist, spot, spacing):
        if magnet is None: return []
        density=surface_dist.get('density') or []
        total_attr=sum(safe(x[1]) for x in mags) or 1
        out=[]
        for mult,label in ((.6,'CORE'),(1.5,'PRIMARY'),(3.0,'EXTENDED')):
            half=max(spacing*mult,spot*.0015*mult)
            surface_mass=sum(safe(x.get('probability_mass')) for x in density if abs(safe(x.get('price'))-magnet)<=half)
            attr_mass=sum(safe(w) for p,w,_ in mags if abs(safe(p)-magnet)<=half)/total_attr*100 if mags else 0
            probability=clamp(.55*surface_mass+.45*attr_mass) if surface_mass>0 else clamp(attr_mass)
            # Attraction is deliberately distinct from terminal probability mass.
            attraction_score=clamp(.72*attr_mass+.28*min(100.,probability*6.0))
            out.append({'band':label,'low':round(magnet-half,2),'high':round(magnet+half,2),'probability':round(probability,2),'surface_mass':round(surface_mass,2),'attraction_mass':round(attr_mass,2),'attraction_score':round(attraction_score,2)})
        return out

    def _scenario_evidence(self, pressure, trend, overview, fut_score, cross_index, magnet_zone, surface_dist, event_total, tactical_pressure):
        breadth=safe(getattr(overview,'breadth_score',50),50) if overview else 50
        market_trend=safe(getattr(overview,'trend_score',50),50) if overview else safe(trend.get('score'),50)
        evidence=[
            ('DEALER_POSITIONING', clamp(pressure,-100,100), 1.00),
            ('TACTICAL_0DTE', clamp(tactical_pressure,-100,100), .60),
            ('UNDERLYING_TREND', (safe(trend.get('score'),50)-50)*2, .85),
            ('MARKET_TREND', (market_trend-50)*2, .65),
            ('BREADTH', (breadth-50)*2, .70),
            ('FUTURES_CONFIRMATION', (fut_score-50)*2, .90),
            ('CROSS_INDEX_CONFIRMATION', (safe((cross_index or {}).get('score'),50)-50)*2, .55),
        ]
        signed=sum(score*weight for _,score,weight in evidence)/sum(weight for _,_,weight in evidence)
        rows=[{'factor':name,'signed_score':round(score,2),'weight':round(weight,2),'weighted_contribution':round(score*weight,2),'direction':'BULLISH' if score>7 else 'BEARISH' if score<-7 else 'NEUTRAL'} for name,score,weight in evidence]
        rows.sort(key=lambda x:abs(x['weighted_contribution']),reverse=True)
        return {'net_directional_score':round(signed,2),'rows':rows,'range_support_score':round(clamp(safe(magnet_zone.get('probability'))*1.5),2),'surface_quality':round(safe(surface_dist.get('quality')),2),'event_shock_score':round(clamp(event_total*10),2)}

    def _coherent_scenarios(self, scenarios, path_levels, resistance, support):
        rows=[dict(x) for x in scenarios]
        by_label={x.get('label'):x for x in path_levels}
        bounds={}
        if resistance is not None and 'RESISTANCE' in by_label:
            r=by_label['RESISTANCE']; bounds['BULLISH_BREAKOUT']=min(safe(r.get('touch_probability')), safe(r.get('acceptance_probability')))
        if support is not None and 'SUPPORT' in by_label:
            r=by_label['SUPPORT']; bounds['BEARISH_BREAKDOWN']=min(safe(r.get('touch_probability')), safe(r.get('acceptance_probability')))
        removed=0.
        for x in rows:
            b=bounds.get(x.get('name'))
            if b is not None and safe(x.get('probability'))>b:
                removed += safe(x.get('probability'))-b
                x['probability']=round(max(0.,b),2)
                x['coherence_cap']=round(b,2)
        # Redistribute clipped mass only to non-directional outcomes, preserving directional caps.
        sinks=[x for x in rows if x.get('name') in ('PIN_RANGE','VOLATILITY_SHOCK')]
        sink_total=sum(safe(x.get('probability')) for x in sinks) or len(sinks) or 1
        for x in sinks:
            x['probability']=round(safe(x.get('probability'))+removed*(safe(x.get('probability'))/sink_total if sink_total else 1/len(sinks)),2)
        total=sum(safe(x.get('probability')) for x in rows) or 1
        # Final numerical normalization is applied to non-directional outcomes so caps stay hard.
        drift=100-total
        if sinks:
            sinks[0]['probability']=round(max(0.,safe(sinks[0].get('probability'))+drift),2)
        return rows

    def _path_ladder(self, spot, dominant, path_levels, staged):
        direction='UPSIDE' if dominant.get('name')=='BULLISH_BREAKOUT' else 'DOWNSIDE' if dominant.get('name')=='BEARISH_BREAKDOWN' else 'RANGE'
        out=[{'step':0,'label':'SPOT','price':round(spot,2),'probability':100.0,'state':'CURRENT'}]
        prior=100.0
        if direction in ('UPSIDE','DOWNSIDE'):
            levels=[x for x in path_levels if x.get('side')==direction]
            levels=sorted(levels,key=lambda x:abs(safe(x.get('price'))-spot))
            for x in levels:
                p=min(prior,safe(x.get('touch_probability'))); prior=p
                out.append({'step':len(out),'label':x.get('label'),'price':round(safe(x.get('price')),2),'probability':round(p,2),'state':'TOUCH'})
            for st in staged:
                p=min(prior,safe(st.get('conditional_probability'))); prior=p
                out.append({'step':len(out),'label':f"STAGE_{st.get('stage')}",'zone':{'low':st.get('low'),'high':st.get('high')},'probability':round(p,2),'state':'CONDITIONAL_ZONE'})
        elif staged:
            st=staged[0]; out.append({'step':1,'label':'PRIMARY_RANGE','zone':{'low':st.get('low'),'high':st.get('high')},'probability':round(min(100.,safe(st.get('conditional_probability'))),2),'state':'RANGE'})
        return out

    def _realistic_staged_objectives(self, dominant, spot, support, resistance, model_ranges, trend, strikes, analogs, magnet):
        spacing=self._strike_spacing(strikes,spot)
        daily_sigma=spot*max(.04,safe(trend.get('rv20'),20)/100)/sqrt(252)
        step=max(spacing,daily_sigma*.75,spot*.0025)
        half=max(spacing*.60,daily_sigma*.28,spot*.0015)
        prob=safe(dominant.get('probability'))
        name=dominant.get('name')
        stages=[]
        if name=='BULLISH_BREAKOUT':
            trigger=max(spot,safe(resistance,magnet or spot))
            s1=(trigger-half,trigger+half); s2=(s1[1],s1[1]+step); s3=(s2[1],s2[1]+step*1.35)
            cap=min(model_ranges['90']['high'],max(trigger+step*2.5,spot*(1+max(.008,safe(analogs.get('median_max_excursion_up_pct'),1.5)/100)*1.6)))
            raw=[s1,s2,s3]
            raw=[(a,min(b,cap)) for a,b in raw if a<cap]
        elif name=='BEARISH_BREAKDOWN':
            trigger=min(spot,safe(support,magnet or spot))
            s1=(trigger-half,trigger+half); s2=(s1[0]-step,s1[0]); s3=(s2[0]-step*1.35,s2[0])
            floor=max(model_ranges['90']['low'],min(trigger-step*2.5,spot*(1-max(.008,abs(safe(analogs.get('median_max_excursion_down_pct'),-1.5))/100)*1.6)))
            raw=[s1,s2,s3]
            raw=[(max(a,floor),b) for a,b in raw if b>floor]
        else:
            center=safe(magnet,(model_ranges['50']['low']+model_ranges['50']['high'])/2)
            raw=[(max(model_ranges['50']['low'],center-half),min(model_ranges['50']['high'],center+half))]
        decay=(1.0,.70,.40)
        for i,(a,b) in enumerate(raw[:3],1):
            stages.append({'stage':i,'low':round(min(a,b),2),'high':round(max(a,b),2),'conditional_probability':round(clamp(prob*decay[i-1]),2),'basis':{'strike_spacing':round(spacing,2),'daily_sigma_points':round(daily_sigma,2),'zone_half_width':round(half,2)}})
        if stages:
            action={'low':stages[0]['low'],'high':stages[min(1,len(stages)-1)]['high'],'scenario':name,'scenario_probability':round(prob,2),'conditional':True,'definition':'Conditional near-path decision zone derived from strike spacing, realized-volatility scale and historical OPEX excursion constraints; extreme statistical tails remain separate.'}
        else:
            action={'low':model_ranges['50']['low'],'high':model_ranges['50']['high'],'scenario':name,'scenario_probability':round(prob,2),'conditional':True,'definition':'Conditional near-path decision zone.'}
        return stages,action

    def _expected_daily_path(self, as_of, expiry, spot, dominant, staged, flows, event_rows, futures_confirmation, trend):
        start=date.fromisoformat(str(as_of)); end=expiry if isinstance(expiry,date) else date.fromisoformat(str(expiry))
        days=[]; cur=start
        while cur<=end and len(days)<22:
            if cur.weekday()<5: days.append(cur)
            cur+=timedelta(days=1)
        if not days: return []
        target=(staged[-1]['high']+staged[-1]['low'])/2 if staged else spot
        if dominant.get('name')=='PIN_RANGE' and staged: target=(staged[0]['high']+staged[0]['low'])/2
        event_by_date=defaultdict(list)
        for x in event_rows:
            try: event_by_date[date.fromisoformat(str(x['event'].event_date))].append(x)
            except: pass
        daily_sigma=spot*max(.04,safe(trend.get('rv20'),20)/100)/sqrt(252)
        fut_bias=(safe(futures_confirmation.get('score'),50)-50)/50
        flow_by_date={str(x.get('date')):x for x in flows}
        out=[]
        for i,d in enumerate(days):
            frac=i/max(1,len(days)-1); median_path=spot+(target-spot)*frac
            evs=event_by_date.get(d,[]); material=[x for x in evs if safe(x.get('weight'))>=.20 and safe(x.get('weighted_move_pct'))>=.15]
            ev_move=max([safe(x.get('weighted_move_pct')) for x in material]+[0])
            width=daily_sigma*sqrt(max(1,i+1))*(.62+.38*(1-safe(dominant.get('probability'))/100)) + spot*ev_move/100*.55
            median_path += daily_sigma*fut_bias*.12*sqrt(i+1)
            flow=flow_by_date.get(str(d),{}); charm=safe(flow.get('charm_index')); vanna=safe(flow.get('vanna_index'))
            days_to_expiry=(end-d).days
            if material: state='MACRO_EVENT'
            elif days_to_expiry<=2 and abs(charm)>=60: state='OPEX_CONVERGENCE'
            elif abs(charm)>=65 and abs(vanna)<35: state='VOLATILITY_COMPRESSION'
            elif abs(vanna)>=55: state='POSITIONING_DRIFT'
            elif median_path>spot+daily_sigma*.35: state='UPSIDE_PATH'
            elif median_path<spot-daily_sigma*.35: state='DOWNSIDE_PATH'
            else: state='BALANCED'
            drivers=[]
            if material: drivers.extend(sorted({x['type'] for x in material}))
            if abs(charm)>=50: drivers.append('CHARM')
            if abs(vanna)>=50: drivers.append('VANNA')
            if i==0 and futures_confirmation.get('ticker'): drivers.append('FUTURES')
            p25=median_path-width*.674; p75=median_path+width*.674
            out.append({'date':str(d),'trading_day':i,'expected':round(median_path,2),'median':round(median_path,2),'p25':round(p25,2),'p75':round(p75,2),'low':round(median_path-width,2),'high':round(median_path+width,2),'state':state,'drivers':drivers[:4],'event_move_pct':round(ev_move,2),'charm_index':round(charm,2),'vanna_index':round(vanna,2)})
        return out

    def _forecast(self, snap, previous, ep, prior_ep, strikes, trend, events, now, *, surface=None, prices=None, prior_forecast=None, prior_strikes=None, tactical_expiries=None, cross_index=None, overview=None, futures_map=None):
        spot=float(snap.spot_price); dte=max(1,int(ep.dte)); iv=safe(ep.atm_implied_volatility,safe(snap.atm_iv,.20)); em=safe(ep.expected_move,spot*iv*sqrt(dte/365)); rv_move=spot*(safe(trend['rv20'],20)/100)*sqrt(dte/252)
        event_rows=[]
        macro_types={'FOMC','CPI','PPI','GDP','EMPLOYMENT_SITUATION','JOLTS','PCE','PERSONAL_INCOME_AND_OUTLAYS','RETAIL_SALES','ISM','TREASURY'}
        for e in events:
            typ=str(getattr(e,'event_type','') or '').upper(); raw_move=safe(getattr(e,'forecast_move_pct',None) or getattr(e,'implied_move_pct',None) or getattr(e,'expected_move_pct',None))
            explicit=safe(getattr(e,'market_impact_score',0),0)
            if explicit>0: weight=clamp(explicit,0,100)/100
            elif typ in macro_types: weight=1.0
            elif typ=='EARNINGS': weight=.01
            else: weight=.20
            weighted=raw_move*weight
            event_rows.append({'event':e,'type':typ,'raw_move_pct':raw_move,'weight':weight,'weighted_move_pct':weighted})
        ranked_event_moves=sorted((x['weighted_move_pct'] for x in event_rows if x['weighted_move_pct']>0),reverse=True)[:20]; event_moves=ranked_event_moves; event_move=max(event_moves+[0.]); event_total=sqrt(sum(x*x for x in event_moves)); event_abs=spot*event_total/100
        base_width68=max(em,rv_move*.85); width68=max(base_width68,event_abs*.65); bias=((safe(snap.bull_probability)-safe(snap.bear_probability))/100)*.22+((safe(trend['score'])-50)/50)*.12
        center=spot+bias*width68; widths={'50':.674*width68,'68':width68,'90':1.645*width68}; ranges={k:{'low':round(center-w,2),'high':round(center+w,2)} for k,w in widths.items()}

        surface_dist=self._surface_distribution(surface or [],spot); analogs=self._historical_opex_analogs(prices or [],dte,trend); model_ranges,posterior=self._model_calibrated_ranges(spot,ranges,surface_dist,analogs,event_abs,prior_forecast)
        model_center=(model_ranges['50']['low']+model_ranges['50']['high'])/2

        mags=[]
        for x in strikes:
            dist=abs(x.strike-spot)/spot; proximity=exp(-dist*12); weight=max(.01,safe(x.pin_score)+safe(x.liquidity_score)*.25+log1p(safe(x.call_open_interest)+safe(x.put_open_interest))*3+log1p(abs(safe(x.net_gamma_exposure)))*1.5)*proximity; mags.append((x.strike,weight,x))
        mags.sort(key=lambda z:z[1],reverse=True); total=sum(x[1] for x in mags) or 1; magnet=mags[0][0] if mags else snap.magnet_strike; magnet_prob=clamp((mags[0][1]/total*100 if mags else safe(snap.range_probability)*.5),1,75); magnet_candidates=[{'price':round(p,2),'probability':round(clamp(w/total*100,0,100),2)} for p,w,_ in mags[:7]]; magnet_zone=self._magnet_zone(magnet,magnet_prob,mags,surface_dist,spot)
        strike_spacing=self._strike_spacing(strikes,spot); magnet_zone_heatmap=self._magnet_zone_heatmap(magnet,mags,surface_dist,spot,strike_spacing)
        puts=[x for x in strikes if x.strike<spot]; calls=[x for x in strikes if x.strike>spot]; support=max(puts,key=lambda x:(x.put_open_interest+max(0,-x.net_gamma_exposure),x.pin_score)).strike if puts else snap.primary_put_wall; resistance=max(calls,key=lambda x:(x.call_open_interest+max(0,x.net_gamma_exposure),x.pin_score)).strike if calls else snap.primary_call_wall

        def migrate(cur,prev,alt):
            if cur is None:return alt
            delta=0 if prev is None else safe(cur)-safe(prev,cur); return round(safe(cur)+delta*min(1.5,max(.25,dte/30)),2)
        gff=migrate(snap.gamma_flip,previous.gamma_flip if previous else None,magnet); cwf=migrate(snap.primary_call_wall,previous.primary_call_wall if previous else None,resistance); pwf=migrate(snap.primary_put_wall,previous.primary_put_wall if previous else None,support); mig=lambda cur,fc: clamp(55+min(25,abs(safe(fc)-safe(cur))/max(spot,.01)*700)) if cur and fc else 35

        scale=max(abs(safe(ep.net_gamma_exposure)),abs(safe(ep.net_delta_exposure)),1.); pressure=clamp(50+35*(safe(ep.net_delta_exposure)/scale)+20*(safe(ep.net_gamma_exposure)/scale),0,100)*2-100
        tac_gamma=sum(safe(x.net_gamma_exposure) for x in tactical_expiries or []); tac_delta=sum(safe(x.net_delta_exposure) for x in tactical_expiries or []); tac_scale=max(abs(tac_gamma),abs(tac_delta),1.); tactical_pressure=clamp(50+35*tac_delta/tac_scale+20*tac_gamma/tac_scale,0,100)*2-100 if tactical_expiries else 0.
        flows=[]; flow_dates=[]; fd=date.fromisoformat(str(snap.as_of_date))
        while fd<=ep.expiry and len(flow_dates)<16:
            if fd.weekday()<5: flow_dates.append(fd)
            fd+=timedelta(days=1)
        total_flow_days=max(1,len(flow_dates)-1)
        for i,flow_date in enumerate(flow_dates):
            rem=max(1,total_flow_days-i);decay=sqrt(max(1,total_flow_days)/rem);charm=safe(ep.net_charm_exposure)*decay;vanna=safe(ep.net_vanna_exposure)*sqrt(rem/max(1,total_flow_days));flows.append({'trading_day':i,'date':str(flow_date),'charm_exposure':round(charm,2),'vanna_exposure':round(vanna,2),'charm_index':round(clamp(50+50*charm/(abs(charm)+abs(vanna)+1))*2-100,2),'vanna_index':round(clamp(50+50*vanna/(abs(charm)+abs(vanna)+1))*2-100,2)})

        range_p=clamp((safe(snap.range_probability)+magnet_zone['probability'])/2); bull=clamp(safe(snap.breakout_probability)*(.55+.45*trend['score']/100)); bear=clamp(safe(snap.breakdown_probability)*(.55+.45*(100-trend['score'])/100)); shock=clamp(8+event_total*4+safe(snap.volatility_expansion_probability)*.08,5,30)
        product=next((p for p,idx in PRODUCT_INDEX.items() if idx==snap.symbol),None); fut=(futures_map or {}).get(product,{}) if product else {}; fut_score=safe(fut.get('confirmation_score'),50); fut_bias=(fut_score-50)/50
        scenario_evidence=self._scenario_evidence(pressure,trend,overview,fut_score,cross_index,magnet_zone,surface_dist,event_total,tactical_pressure)
        evidence_bias=safe(scenario_evidence.get('net_directional_score'))/100
        bull*=max(.45,1+.40*fut_bias+.35*evidence_bias); bear*=max(.45,1-.40*fut_bias-.35*evidence_bias); range_p*=max(.65,1-abs(evidence_bias)*.20-abs(fut_bias)*.20)
        shock*=max(.70,1+safe(scenario_evidence.get('event_shock_score'))/250)
        raw=[range_p,bull,bear,shock];sm=sum(raw) or 1
        scenarios=[{'name':'PIN_RANGE','probability':round(raw[0]/sm*100,2),'trigger':f'{model_ranges["68"]["low"]}-{model_ranges["68"]["high"]}','target':magnet},{'name':'BULLISH_BREAKOUT','probability':round(raw[1]/sm*100,2),'trigger':resistance,'target':round(model_ranges['90']['high'],2)},{'name':'BEARISH_BREAKDOWN','probability':round(raw[2]/sm*100,2),'trigger':support,'target':round(model_ranges['90']['low'],2)},{'name':'VOLATILITY_SHOCK','probability':round(raw[3]/sm*100,2),'trigger':'EVENT_OR_VOL_EXPANSION','target':None}]
        levels_for_path=[('SUPPORT',support),('RESISTANCE',resistance),('PRIMARY_MAGNET',magnet),('GAMMA_FLIP',gff),('CALL_WALL',cwf),('PUT_WALL',pwf)]; path_levels=self._level_probabilities(spot,dte,trend,levels_for_path,strikes,surface_dist)
        scenarios=self._coherent_scenarios(scenarios,path_levels,resistance,support)
        dominant=max(scenarios,key=lambda x:x['probability'])
        staged,actionable=self._realistic_staged_objectives(dominant,spot,support,resistance,model_ranges,trend,strikes,analogs,magnet)
        alo=actionable['low']; ahi=actionable['high']
        path_ladder=self._path_ladder(spot,dominant,path_levels,staged)
        conditional=self._conditional_distributions(model_ranges,model_center,event_total,spot,snap.bull_probability,snap.bear_probability)
        position_change=self._position_change(strikes,prior_strikes or [])
        fut_dir='BULLISH' if fut_score>=60 else 'BEARISH' if fut_score<=40 else 'NEUTRAL'
        dealer_dir='BULLISH' if pressure>15 else 'BEARISH' if pressure<-15 else 'NEUTRAL'
        if dealer_dir=='BEARISH' and fut_dir=='BULLISH': interaction='DEALER_SUPPLY_ABSORBED'
        elif dealer_dir=='BULLISH' and fut_dir=='BEARISH': interaction='DEALER_DEMAND_OVERRIDDEN'
        elif dealer_dir==fut_dir and dealer_dir!='NEUTRAL': interaction='CONFIRMED_'+dealer_dir
        else: interaction='MIXED'
        futures_confirmation={'product_code':product,'ticker':fut.get('ticker'),'state':fut_dir,'score':round(fut_score,2),'trend_score':fut.get('trend_score'),'momentum_score':fut.get('momentum_score'),'vwap':fut.get('vwap'),'last_price':fut.get('last_price'),'overnight_high':fut.get('overnight_high'),'overnight_low':fut.get('overnight_low'),'rth_high':fut.get('rth_high'),'rth_low':fut.get('rth_low'),'basis_pct':fut.get('basis_pct'),'realized_volatility':fut.get('realized_volatility'),'dealer_interaction':interaction,'source':fut.get('source','UNAVAILABLE')}
        expected_daily_path=self._expected_daily_path(snap.as_of_date,ep.expiry,spot,dominant,staged,flows,event_rows,futures_confirmation,trend)

        dataq=clamp((safe(snap.quote_coverage_pct)+safe(ep.liquidity_score))/2);dealer=clamp(safe(snap.confidence_score));trendc=clamp(65+abs(safe(trend['score'])-50)*.5);eventc=clamp(90-event_total*6,35,95);hist=clamp(45+min(35,analogs.get('sample_size',0)*2)) if analogs.get('status')=='READY' else 40;surfacec=safe(surface_dist.get('quality'),0);crossc=safe((cross_index or {}).get('score'),50)
        futuresc=fut_score if fut else 45.; conf=round(.20*dealer+.16*dataq+.12*trendc+.09*eventc+.13*hist+.12*surfacec+.07*crossc+.11*futuresc,2)

        contributions={'option_implied_volatility':em,'realized_volatility':rv_move*.85,'event_uncertainty':event_abs*.65,'dealer_positioning_uncertainty':width68*(1-magnet_zone['probability']/100)*.32,'trend_path_uncertainty':width68*(1-abs(safe(trend['score'])-50)/50)*.18,'model_calibration_uncertainty':width68*(1-hist/100)*.18}; csum=sum(max(0,x) for x in contributions.values()) or 1; contribution_pct={k:round(max(0,v)/csum*100,2) for k,v in contributions.items()}

        lower=model_ranges['68']['low']; upper=model_ranges['68']['high']; down_target=model_ranges['90']['low']; up_target=model_ranges['90']['high']; summary=f"68% model-calibrated modeled range for {snap.symbol} into {ep.expiry} is {lower:.0f}-{upper:.0f}. Dominant {dominant['name'].replace('_',' ').lower()} scenario is {dominant['probability']:.0f}% with near-path decision zone {alo:.0f}-{ahi:.0f}. "
        if fut: summary+=f"{product} futures confirmation is {fut_dir.lower()} ({fut_score:.0f}/100; {interaction.replace('_',' ').lower()}). "
        if magnet: summary+=f"Primary magnet is near {magnet:.0f}; the modeled magnet zone {magnet_zone['low']:.0f}-{magnet_zone['high']:.0f} carries {magnet_zone['probability']:.0f}% probability mass. "
        if support: summary+=f"A sustained break below {support:.0f} raises downside acceleration risk toward {down_target:.0f}. "
        if resistance: summary+=f"Acceptance above {resistance:.0f} raises upside extension probability toward {up_target:.0f}."

        return {
            'version':self.VERSION,'symbol':snap.symbol,'expiration':str(ep.expiry),'cycle_type':cycle_type(ep.expiry),'dte':dte,'forecast_timestamp':now.isoformat(),'source_as_of_date':str(snap.as_of_date),'spot':round(spot,2),
            'ranges':ranges,'unconditional_ranges':ranges,'model_calibrated_ranges':model_ranges,'actionable_range':actionable,'center':round(center,2),'model_center':round(model_center,2),
            'surface_distribution':surface_dist,'historical_opex_analogs':analogs,'posterior_update':posterior,'conditional_distributions':conditional,'staged_path_objectives':staged,'expected_daily_path':expected_daily_path,'scenario_evidence':scenario_evidence,'futures_confirmation':futures_confirmation,
            'magnet':{'price':None if magnet is None else round(magnet,2),'probability':round(magnet_prob,2),'candidates':magnet_candidates,'zone':magnet_zone,'zone_heatmap':magnet_zone_heatmap,'attraction_score':round(next((safe(x.get('attraction_score')) for x in magnet_zone_heatmap if x.get('band')=='PRIMARY'),0),2),'strike_spacing':round(strike_spacing,2)},
            'levels':{'support':None if support is None else round(support,2),'resistance':None if resistance is None else round(resistance,2),'breakdown_acceleration_target':round(down_target,2),'breakout_acceleration_target':round(up_target,2)},
            'path_distribution':{'levels':path_levels,'ladder':path_ladder,'method':'COHERENT_BARRIER_TREE_PLUS_STRUCTURE_HOLD_MODEL'},
            'migration':{'gamma_flip':{'current':snap.gamma_flip,'forecast':gff,'probability':round(mig(snap.gamma_flip,gff),2)},'call_wall':{'current':snap.primary_call_wall,'forecast':cwf,'probability':round(mig(snap.primary_call_wall,cwf),2)},'put_wall':{'current':snap.primary_put_wall,'forecast':pwf,'probability':round(mig(snap.primary_put_wall,pwf),2)}},
            'dealer':{'positioning_scope':'TARGET_EXPIRATION','gamma_regime':snap.gamma_regime,'net_gamma_exposure':safe(ep.net_gamma_exposure),'net_delta_exposure':safe(ep.net_delta_exposure),'net_vanna_exposure':safe(ep.net_vanna_exposure),'net_charm_exposure':safe(ep.net_charm_exposure),'pressure_score':round(pressure,2),'direction':'BUY_PRESSURE' if pressure>15 else 'SELL_PRESSURE' if pressure<-15 else 'BALANCED','position_change':position_change,
                      'tactical_0dte_near_term':{'expiration_count':len(tactical_expiries or []),'net_gamma_exposure':round(tac_gamma,2),'net_delta_exposure':round(tac_delta,2),'pressure_score':round(tactical_pressure,2),'direction':'BUY_PRESSURE' if tactical_pressure>15 else 'SELL_PRESSURE' if tactical_pressure<-15 else 'BALANCED'}},
            'daily_flows':flows,'trend':trend,'cross_index_confirmation':cross_index or {},'market_context':{'breadth_score':safe(getattr(overview,'breadth_score',50),50) if overview else 50,'trend_score':safe(getattr(overview,'trend_score',50),50) if overview else 50,'breadth_regime':getattr(overview,'breadth_regime','UNKNOWN') if overview else 'UNKNOWN','volatility_regime':getattr(overview,'volatility_regime','UNKNOWN') if overview else 'UNKNOWN'},
            'event_risk':{'event_count':len(events),'material_event_count':sum(1 for x in event_rows if x['weight']>=.2),'max_forecast_move_pct':event_move,'aggregate_forecast_move_pct':round(event_total,2),'method':'MARKET_IMPACT_WEIGHTED','events':[{'type':x['type'],'date':x['event'].event_date,'name':x['event'].release_name,'raw_forecast_move_pct':x['raw_move_pct'],'market_impact_weight':round(x['weight'],3),'weighted_move_pct':round(x['weighted_move_pct'],3)} for x in sorted(event_rows,key=lambda z:z['weighted_move_pct'],reverse=True)[:12]]},
            'scenarios':scenarios,'range_width_contributors':contribution_pct,
            'confidence':{'overall':conf,'components':{'dealer_positioning':round(dealer,2),'data_quality':round(dataq,2),'trend_agreement':round(trendc,2),'event_risk':round(eventc,2),'historical_calibration':round(hist,2),'option_surface_quality':round(surfacec,2),'cross_index_confirmation':round(crossc,2),'futures_confirmation':round(futuresc,2)}},'summary':summary}

    def _cross_opex(self, forecasts):
        by=defaultdict(list)
        for f in forecasts: by[f['symbol']].append(f)
        out=[]
        for sym,rows in by.items():
            rows.sort(key=lambda x:x['expiration']);nodes=[]
            for r in rows:
                probs={x['name']:safe(x['probability']) for x in r.get('scenarios',[])}
                nodes.append({'expiration':r['expiration'],'dte':r['dte'],'magnet':r['magnet']['price'],'magnet_zone_probability':safe((r.get('magnet') or {}).get('zone',{}).get('probability')),'range68':r.get('model_calibrated_ranges',r['ranges'])['68'],'current_decision_zone':r.get('actionable_range'),'terminal_base_zone':next((x.get('range') for x in r.get('conditional_distributions',[]) if x.get('name') in ('BASE_EVENT_OUTCOME','NO_MAJOR_EVENT_SHOCK')),r.get('model_calibrated_ranges',r['ranges']).get('50')),'gamma_flip':r['migration']['gamma_flip']['forecast'],'call_wall':r['migration']['call_wall']['forecast'],'put_wall':r['migration']['put_wall']['forecast'],'dealer_pressure':r['dealer']['pressure_score'],'dominant_scenario':max(r['scenarios'],key=lambda x:x['probability'])['name'],'scenario_probabilities':probs,'confidence':r['confidence']['overall']})
            transitions=[]
            states=('PIN_RANGE','BULLISH_BREAKOUT','BEARISH_BREAKDOWN','VOLATILITY_SHOCK')
            for a,b in zip(nodes,nodes[1:]):
                matrix=[]
                next_base={k:safe(b.get('scenario_probabilities',{}).get(k)) for k in states}
                for current in states:
                    vals={k:max(0.,next_base[k]+(12 if k==current else -4)) for k in states}; denom=sum(vals.values()) or 1
                    matrix.append({'from':current,'to_probabilities':{k:round(vals[k]/denom*100,2) for k in states}})
                transitions.append({'from_expiration':a['expiration'],'to_expiration':b['expiration'],'magnet_migration':None if a['magnet'] is None or b['magnet'] is None else round(b['magnet']-a['magnet'],2),'gamma_flip_migration':None if a['gamma_flip'] is None or b['gamma_flip'] is None else round(b['gamma_flip']-a['gamma_flip'],2),'pressure_change':round(b['dealer_pressure']-a['dealer_pressure'],2),'magnet_zone_probability_change':round(b['magnet_zone_probability']-a['magnet_zone_probability'],2),'regime_transition':f"{a['dominant_scenario']} → {b['dominant_scenario']}",'transition_probability_matrix':matrix,'matrix_method':'NEXT_CYCLE_POSTERIOR_WITH_REGIME_PERSISTENCE_PRIOR'})
            out.append({'symbol':sym,'nodes':nodes,'transitions':transitions})
        return out

    def _calibration(self,s):
        rows=s.execute(select(OpexForecastOutcomeModel)).scalars().all()
        if not rows:return {'sample_size':0,'coverage50':None,'coverage68':None,'coverage90':None,'average_magnet_distance_pct':None,'actionable_range_coverage':None,'magnet_zone_hit_rate':None}
        actionable=[(r.payload_json or {}).get('in_actionable_range') for r in rows if (r.payload_json or {}).get('in_actionable_range') is not None]; mz=[(r.payload_json or {}).get('in_magnet_zone') for r in rows if (r.payload_json or {}).get('in_magnet_zone') is not None]
        return {'sample_size':len(rows),'coverage50':round(mean(r.in_50 for r in rows)*100,2),'coverage68':round(mean(r.in_68 for r in rows)*100,2),'coverage90':round(mean(r.in_90 for r in rows)*100,2),'average_magnet_distance_pct':round(mean(r.magnet_distance_pct for r in rows if r.magnet_distance_pct is not None),3) if any(r.magnet_distance_pct is not None for r in rows) else None,'actionable_range_coverage':round(mean(actionable)*100,2) if actionable else None,'magnet_zone_hit_rate':round(mean(mz)*100,2) if mz else None}

def log1p(x):
    from math import log1p as l
    return l(max(0,x))
