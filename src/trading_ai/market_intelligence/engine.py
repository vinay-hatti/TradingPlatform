from __future__ import annotations
import math
from datetime import date
from typing import Any
import numpy as np
import pandas as pd

SECTOR_ETFS={
'Information Technology':'XLK','Financials':'XLF','Health Care':'XLV','Consumer Discretionary':'XLY','Communication Services':'XLC','Industrials':'XLI','Consumer Staples':'XLP','Energy':'XLE','Utilities':'XLU','Real Estate':'XLRE','Materials':'XLB'
}
def clamp(x,lo=0,hi=100): return float(max(lo,min(hi,float(x))))
def safe(v,d=0.0):
    try:
        x=float(v); return d if math.isnan(x) or math.isinf(x) else x
    except Exception:return d

def returns_matrix(price_rows:list[dict[str,Any]],lookback:int=60)->pd.DataFrame:
    if not price_rows:return pd.DataFrame()
    df=pd.DataFrame(price_rows); df['date']=pd.to_datetime(df['date']);
    px=df.pivot_table(index='date',columns='symbol',values='close',aggfunc='last').sort_index().tail(lookback+1)
    return px.pct_change(fill_method=None).dropna(how='all')

def correlation_analytics(ret:pd.DataFrame,sectors:dict[str,str])->dict[str,Any]:
    if ret.shape[0]<20 or ret.shape[1]<2:
        return {'status':'STALE','regime':'UNKNOWN','confidence':0.0,'warnings':['Insufficient return history for pairwise correlation.'],'pairs':[],'sector_correlations':[]}
    corr=ret.corr(min_periods=max(10,int(ret.shape[0]*.5)))
    vals=corr.where(np.triu(np.ones(corr.shape),1).astype(bool)).stack().dropna()
    avg=safe(vals.mean()); med=safe(vals.median()); disp=safe(ret.std().mean()*math.sqrt(252)*100)
    regime='LOW_CORRELATION' if avg<.25 else 'NORMAL_CORRELATION' if avg<.5 else 'HIGH_CORRELATION' if avg<.75 else 'PANIC_CORRELATION'
    pairs=[{'symbol_a':a,'symbol_b':b,'correlation':round(float(v),4)} for (a,b),v in vals.sort_values(ascending=False).head(250).items()]
    sector_rows=[]
    for sector in sorted(set(sectors.values())):
        syms=[s for s in ret.columns if sectors.get(s)==sector]
        if len(syms)<2:continue
        c=ret[syms].corr(); x=c.where(np.triu(np.ones(c.shape),1).astype(bool)).stack().dropna()
        sector_rows.append({'sector':sector,'average_correlation':round(safe(x.mean()),4),'median_correlation':round(safe(x.median()),4),'symbol_count':len(syms)})
    confidence=clamp(40+min(ret.shape[0],60)/60*30+min(ret.shape[1],500)/500*30)
    return {'status':'READY','lookback_days':int(ret.shape[0]),'symbol_count':int(ret.shape[1]),'average_pairwise_correlation':round(avg,4),'median_pairwise_correlation':round(med,4),'cross_sectional_dispersion_annualized_pct':round(disp,2),'regime':regime,'confidence':round(confidence,2),'pairs':pairs,'sector_correlations':sector_rows,'provenance':'COMPUTED','source_tables':['price_history']}

def sector_breadth(price_rows:list[dict[str,Any]],membership:dict[str,dict[str,Any]])->list[dict[str,Any]]:
    df=pd.DataFrame(price_rows)
    if df.empty:return []
    df['date']=pd.to_datetime(df['date']); rows=[]
    for sector in sorted({m['sector'] for m in membership.values() if m.get('sector')}):
        syms=[s for s,m in membership.items() if m.get('sector')==sector]
        part=df[df.symbol.isin(syms)].sort_values(['symbol','date'])
        metrics=[]
        for symbol,g in part.groupby('symbol'):
            g=g.tail(220); c=g.close.astype(float); v=g.volume.astype(float)
            if len(c)<21:continue
            r1=c.iloc[-1]/c.iloc[-2]-1; r5=c.iloc[-1]/c.iloc[-6]-1 if len(c)>5 else 0; r20=c.iloc[-1]/c.iloc[-21]-1
            ema20=c.ewm(span=20,adjust=False).mean().iloc[-1]; sma50=c.tail(50).mean(); sma200=c.tail(200).mean() if len(c)>=200 else np.nan
            ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean(); macd=ema12.iloc[-1]-ema26.iloc[-1]
            delta=c.diff(); gain=delta.clip(lower=0).tail(14).mean(); loss=-delta.clip(upper=0).tail(14).mean(); rsi=100 if loss==0 else 100-100/(1+gain/loss)
            metrics.append({'r1':r1,'r5':r5,'r20':r20,'above20':c.iloc[-1]>ema20,'above50':c.iloc[-1]>sma50,'above200':bool(c.iloc[-1]>sma200) if not np.isnan(sma200) else False,'macd':macd>0,'rsi':rsi>50,'adv':r1>0,'vol':v.iloc[-1],'upvol':v.iloc[-1] if r1>0 else 0,'downvol':v.iloc[-1] if r1<0 else 0,'high':c.iloc[-1]>=c.tail(20).max(),'low':c.iloc[-1]<=c.tail(20).min()})
        if not metrics:continue
        m=pd.DataFrame(metrics); n=len(m); pct=lambda col:float(m[col].mean()*100)
        breadth=clamp(np.mean([pct('above20'),pct('above50'),pct('above200'),pct('macd'),pct('rsi')]))
        momentum=clamp(50+safe(m.r5.mean())*500+safe(m.r20.mean())*250)
        rs=safe(m.r20.mean())
        label='LEADING' if breadth>=65 and momentum>=60 else 'IMPROVING' if momentum>=52 else 'WEAKENING' if breadth>=45 else 'LAGGING'
        rows.append({'sector':sector,'sector_etf':SECTOR_ETFS.get(sector,''),'constituent_count':n,'advancers':int(m.adv.sum()),'decliners':int((~m.adv).sum()),'pct_above_ema20':round(pct('above20'),2),'pct_above_sma50':round(pct('above50'),2),'pct_above_sma200':round(pct('above200'),2),'pct_macd_positive':round(pct('macd'),2),'pct_rsi_above_50':round(pct('rsi'),2),'new_highs_20d':int(m.high.sum()),'new_lows_20d':int(m.low.sum()),'up_volume':round(safe(m.upvol.sum()),2),'down_volume':round(safe(m.downvol.sum()),2),'equal_weight_return_1d':round(safe(m.r1.mean())*100,2),'equal_weight_return_5d':round(safe(m.r5.mean())*100,2),'equal_weight_return_20d':round(rs*100,2),'breadth_score':round(breadth,2),'momentum_score':round(momentum,2),'rotation_label':label,'provenance':'COMPUTED','confidence':round(clamp(50+n/20*50),2)})
    return rows

def market_internals(price_rows:list[dict[str,Any]])->dict[str,Any]:
    df=pd.DataFrame(price_rows)
    if df.empty:return {'status':'MISSING'}
    df['date']=pd.to_datetime(df.date); closes=df.pivot_table(index='date',columns='symbol',values='close').sort_index(); volumes=df.pivot_table(index='date',columns='symbol',values='volume').reindex(closes.index)
    ret=closes.pct_change(fill_method=None); adv=(ret>0).sum(axis=1); dec=(ret<0).sum(axis=1); unchanged=(ret==0).sum(axis=1); net=adv-dec; ad_line=net.cumsum()
    upvol=volumes.where(ret>0).sum(axis=1); downvol=volumes.where(ret<0).sum(axis=1); trin=(adv/dec.replace(0,np.nan))/(upvol/downvol.replace(0,np.nan))
    ratio=adv/(adv+dec).replace(0,np.nan); ema19=ratio.ewm(span=19).mean(); ema39=ratio.ewm(span=39).mean(); mcc=(ema19-ema39)*1000; summ=mcc.cumsum()
    latest=closes.iloc[-1]; highs=(latest>=closes.tail(252).max()).sum(); lows=(latest<=closes.tail(252).min()).sum()
    zweig=float(ratio.tail(10).mean()*100)
    return {'status':'READY','advancers':int(adv.iloc[-1]),'decliners':int(dec.iloc[-1]),'unchanged':int(unchanged.iloc[-1]),'advance_decline_ratio':round(safe(adv.iloc[-1]/max(dec.iloc[-1],1)),3),'advance_decline_line':round(safe(ad_line.iloc[-1]),2),'up_volume':round(safe(upvol.iloc[-1]),2),'down_volume':round(safe(downvol.iloc[-1]),2),'up_down_volume_ratio':round(safe(upvol.iloc[-1]/max(downvol.iloc[-1],1)),3),'trin':round(safe(trin.iloc[-1],1),3),'new_52w_highs':int(highs),'new_52w_lows':int(lows),'new_high_low_ratio':round(highs/max(lows,1),3),'mcclellan_oscillator':round(safe(mcc.iloc[-1]),2),'mcclellan_summation':round(safe(summ.iloc[-1]),2),'zweig_breadth_thrust':round(zweig,2),'breadth_thrust':zweig>=61.5,'breadth_deterioration':zweig<40,'tick_index':None,'tick_status':'DATA_BLOCKED','provenance':'COMPUTED','source_tables':['price_history']}

def sentiment_ensemble(overview:dict[str,Any],corr:dict[str,Any],internals:dict[str,Any],sectors:list[dict[str,Any]],dealer:list[dict[str,Any]])->dict[str,Any]:
    vals={
      'trend':safe(overview.get('trend_score'),50),'breadth':safe(overview.get('breadth_score'),50),'momentum':safe(overview.get('momentum_score'),50),'volatility':clamp(100-safe(overview.get('regime_transition_probability',30))),
      'liquidity':safe(overview.get('liquidity_score'),50),'dealer_positioning':clamp(np.mean([safe(x.get('institutional_positioning_score'),50) for x in dealer]) if dealer else 50),
      'sector_rotation':clamp(np.mean([safe(x.get('breadth_score'),50) for x in sectors]) if sectors else 50),'credit':safe(overview.get('credit_score'),50),'rates':safe(overview.get('rates_score'),50),'dollar':safe(overview.get('dollar_score'),50),
      'cross_asset':safe(overview.get('risk_on_score'),50),'options_positioning':safe(overview.get('options_score'),50),'correlation':clamp(100-safe(corr.get('average_pairwise_correlation'),.5)*100),'market_internals':clamp(50+(safe(internals.get('advance_decline_ratio'),1)-1)*20+(safe(internals.get('up_down_volume_ratio'),1)-1)*10)
    }
    weights={'trend':.12,'breadth':.12,'momentum':.08,'volatility':.08,'liquidity':.08,'dealer_positioning':.1,'sector_rotation':.08,'credit':.06,'rates':.05,'dollar':.04,'cross_asset':.06,'options_positioning':.05,'correlation':.04,'market_internals':.04}
    comps=[]; total=0
    for k,v in vals.items():
        c=v*weights[k];total+=c; comps.append({'name':k,'score':round(v,2),'weight':weights[k],'contribution':round(c,2),'direction':'BULLISH' if v>=58 else 'BEARISH' if v<=42 else 'NEUTRAL','confidence':round(clamp(60+abs(v-50)/2),2),'provenance':'MODEL_DERIVED'})
    overall=clamp(total)
    return {'overall_sentiment_score':round(overall,2),'risk_appetite_score':round(overall,2),'fear_score':round(100-overall,2),'sentiment_label':'BULLISH' if overall>=60 else 'BEARISH' if overall<=40 else 'NEUTRAL','components':comps,'confidence':round(np.mean([x['confidence'] for x in comps]),2),'provenance':'MODEL_DERIVED'}

def dealer_changes(rows:list[dict[str,Any]])->list[dict[str,Any]]:
    by={}
    for r in rows:by.setdefault(r['symbol'],[]).append(r)
    out=[]
    for symbol,items in by.items():
        items=sorted(items,key=lambda x:str(x.get('snapshot_timestamp') or x.get('as_of_date')))
        cur=items[-1]; prev=items[-2] if len(items)>1 else None
        def delta(k):return safe(cur.get(k))-safe(prev.get(k)) if prev else 0.0
        agreement=clamp(50+min(abs(safe(cur.get('net_gamma_exposure'))),1e9)/1e9*15+min(abs(safe(cur.get('net_delta_exposure'))),1e9)/1e9*15+safe(cur.get('confidence_score'),.5)*20)
        out.append({'symbol':symbol,'snapshot_timestamp':cur.get('snapshot_timestamp'),'positioning_score':safe(cur.get('institutional_positioning_score'),50),'positioning_label':cur.get('positioning_label'),'gamma_regime':cur.get('gamma_regime'),'confidence':safe(cur.get('confidence_score')),'model_agreement_score':round(agreement,2),'dealer_conviction_score':round(clamp(abs(safe(cur.get('institutional_positioning_score'),50)-50)*2*safe(cur.get('confidence_score'),.5)),2),'positioning_score_change':round(delta('institutional_positioning_score'),2),'net_gamma_change':round(delta('net_gamma_exposure'),2),'net_delta_change':round(delta('net_delta_exposure'),2),'net_vanna_change':round(delta('net_vanna_exposure'),2),'net_charm_change':round(delta('net_charm_exposure'),2),'call_wall_migration':round(delta('primary_call_wall'),2),'put_wall_migration':round(delta('primary_put_wall'),2),'gamma_flip_migration':round(delta('gamma_flip'),2),'range_probability':safe(cur.get('range_probability')),'breakout_probability':safe(cur.get('breakout_probability')),'breakdown_probability':safe(cur.get('breakdown_probability')),'provenance':'ESTIMATED','estimator_family':'OI_GREEKS_FLOW_ENSEMBLE','warning':'Estimated from public options data; not observed dealer inventory.'})
    return out

def risk_dashboard(corr,sentiment,internals,sectors,dealer,overview)->dict[str,Any]:
    dims={
      'breadth_risk':100-safe(overview.get('breadth_score'),50),'correlation_risk':safe(corr.get('average_pairwise_correlation'),.5)*100,'volatility_risk':safe(overview.get('volatility_risk'),50),'liquidity_risk':100-safe(overview.get('liquidity_score'),50),'dealer_risk':100-(np.mean([safe(x.get('confidence'),.5) for x in dealer])*100 if dealer else 50),'sector_concentration_risk':clamp(max([safe(x.get('breadth_score'),50) for x in sectors] or [50])-np.mean([safe(x.get('breadth_score'),50) for x in sectors] or [50])+40),'momentum_exhaustion_risk':safe(overview.get('regime_transition_probability'),40),'regime_transition_risk':safe(overview.get('regime_transition_probability'),40),'credit_risk':100-safe(overview.get('credit_score'),50),'rates_risk':100-safe(overview.get('rates_score'),50),'dollar_risk':100-safe(overview.get('dollar_score'),50),'data_risk':100-safe(overview.get('confidence_score'),50)
    }
    score=clamp(np.mean(list(dims.values()))); alerts=[]
    for k,v in dims.items():
        if v>=60:alerts.append({'severity':'HIGH' if v>=75 else 'MEDIUM','category':k,'score':round(v,2),'affected_instruments':['MARKET'],'evidence':f'{k.replace("_"," ").title()} scored {v:.1f}.','trading_implication':'Reduce conviction, size, or concentration until the component improves.','confidence':round(100-v/4,2),'freshness':'CURRENT','provenance':'MODEL_DERIVED'})
    return {'market_risk_score':round(score,2),'risk_regime':'HIGH' if score>=65 else 'ELEVATED' if score>=50 else 'NORMAL','components':{k:round(v,2) for k,v in dims.items()},'alerts':alerts,'provenance':'MODEL_DERIVED'}

def opportunities(sectors,dealer,sentiment,risk,overview)->list[dict[str,Any]]:
    out=[]
    if sectors:
        ranked=sorted(sectors,key=lambda x:safe(x.get('breadth_score'))+safe(x.get('momentum_score')),reverse=True)
        for kind,row,direction,strategy in [('BEST_BULLISH_SECTOR',ranked[0],'CALL','LONG_PREMIUM'),('BEST_BEARISH_SECTOR',ranked[-1],'PUT','LONG_PREMIUM')]:
            score=clamp((safe(row.get('breadth_score'))+safe(row.get('momentum_score')))/2-risk.get('market_risk_score',50)*.15+(10 if direction=='CALL' and sentiment.get('overall_sentiment_score',50)>55 else 0))
            out.append({'type':kind,'instrument':row.get('sector_etf') or row.get('sector'),'sector':row.get('sector'),'direction':direction,'strategy_family':strategy,'score':round(score,2),'confidence':row.get('confidence',60),'supporting_factors':[row.get('rotation_label'),f"Breadth {row.get('breadth_score')}",f"Momentum {row.get('momentum_score')}"],'conflicting_factors':[],'freshness':'CURRENT'})
    for d in sorted(dealer,key=lambda x:safe(x.get('dealer_conviction_score')),reverse=True)[:3]:
        out.append({'type':'DEALER_ALIGNMENT','instrument':d['symbol'],'direction':'CALL' if safe(d.get('positioning_score'))>=50 else 'PUT','strategy_family':'DIRECTIONAL','score':d.get('dealer_conviction_score'),'confidence':safe(d.get('confidence'))*100,'supporting_factors':[d.get('positioning_label'),d.get('gamma_regime')],'conflicting_factors':[d.get('warning')],'freshness':'CURRENT'})
    return sorted(out,key=lambda x:safe(x.get('score')),reverse=True)
