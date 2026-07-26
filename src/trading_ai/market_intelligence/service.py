from __future__ import annotations
import csv,json
from datetime import datetime,timezone,date
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.persistence_normalization import native_params, strict_json_dumps, to_native
from .contracts import MarketIntelligenceSnapshot
from .engine import returns_matrix,correlation_analytics,sector_breadth,market_internals,sentiment_ensemble,dealer_changes,risk_dashboard,opportunities,clamp,safe,SECTOR_ETFS

class MarketIntelligenceService:
    VERSION='m46.1'
    def __init__(self,session_factory=SessionLocal,canonical_csv='data/universe/us_listed_equities_etfs.csv'):
        self.session_factory=session_factory; self.canonical_csv=Path(canonical_csv)
    def _membership(self):
        out={}
        if not self.canonical_csv.exists():return out
        with self.canonical_csv.open(newline='',encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if str(r.get('active','True')).lower() not in {'true','1','yes'}:continue
                s=(r.get('symbol') or '').strip(); sector=(r.get('sector') or '').strip()
                if s and sector:out[s]={'symbol':s,'company_name':r.get('security') or s,'sector':sector,'sector_etf':SECTOR_ETFS.get(sector,''),'source':r.get('source') or 'canonical_universe','as_of_date':r.get('as_of_date')}
        return out
    def build(self,universe_name='canonical',persist=True,snapshot_timestamp=None):
        now=snapshot_timestamp or datetime.now(timezone.utc); membership=self._membership(); symbols=list(membership)
        with self.session_factory() as s:
            rows=[dict(r._mapping) for r in s.execute(text('SELECT symbol,date,close,volume FROM price_history WHERE symbol = ANY(:symbols) ORDER BY date'),{'symbols':symbols})]
            latest_overview=s.execute(text('SELECT payload_json FROM market_overview_snapshot ORDER BY snapshot_timestamp DESC LIMIT 1')).scalar_one_or_none()
            overview=json.loads(latest_overview) if latest_overview else {}
            dealer=[dict(r._mapping) for r in s.execute(text('SELECT *, as_of_date::text AS snapshot_timestamp FROM dealer_position_snapshot ORDER BY symbol,as_of_date'))]
        ret=returns_matrix(rows,60); corr=correlation_analytics(ret,{k:v['sector'] for k,v in membership.items()}); sectors=sector_breadth(rows,membership); internals=market_internals(rows); dealer_e=dealer_changes(dealer)
        ov={'trend_score':safe(overview.get('trend_score'),50),'breadth_score':safe(overview.get('breadth_score'),50),'momentum_score':safe(overview.get('momentum_score'),50),'risk_on_score':safe(overview.get('risk_on_score'),50),'liquidity_score':safe(overview.get('liquidity_participation',{}).get('liquidity_score'),50),'confidence_score':safe(overview.get('confidence_score'),50),'regime_transition_probability':70 if overview.get('regime_transition_risk')=='HIGH' else 45 if overview.get('regime_transition_risk')=='MEDIUM' else 25,'volatility_risk':65 if overview.get('volatility_regime')=='EXPANDING' else 35,'credit_score':50,'rates_score':50,'dollar_score':50,'options_score':safe(overview.get('sentiment_score'),50)}
        sentiment=sentiment_ensemble(ov,corr,internals,sectors,dealer_e); risk=risk_dashboard(corr,sentiment,internals,sectors,dealer_e,ov); opp=opportunities(sectors,dealer_e,sentiment,risk,ov)
        asof=max([str(r['date']) for r in rows],default=str(date.today()))
        scanner={'snapshot_timestamp':now.isoformat(),'as_of_date':asof,'status':'FRESH','correlation_regime':corr.get('regime'),'average_pairwise_correlation':corr.get('average_pairwise_correlation'),'sentiment_score':sentiment.get('overall_sentiment_score'),'sentiment_label':sentiment.get('sentiment_label'),'market_risk_score':risk.get('market_risk_score'),'risk_regime':risk.get('risk_regime'),'sector_context':{x['sector']:x for x in sectors},'opportunities':opp,'confidence':round((safe(corr.get('confidence'))+safe(sentiment.get('confidence'))+safe(overview.get('confidence_score'),50))/3,2)}
        warnings=[]
        if internals.get('tick_status')=='DATA_BLOCKED':warnings.append('Exchange TICK index is DATA_BLOCKED because no authoritative intraday tick dataset is persisted.')
        warnings.append('Dealer positioning is ESTIMATED from public options OI, Greeks and flow proxies; it is not observed dealer inventory.')
        snap=MarketIntelligenceSnapshot(now,asof,universe_name,corr,sentiment,sectors,dealer_e,internals,overview.get('volatility_options',{}),overview.get('liquidity_participation',{}),risk,opp,scanner,{'calculation_version':self.VERSION,'source_tables':['price_history','dealer_position_snapshot','market_overview_snapshot','canonical_universe_csv'],'sector_membership_completeness_pct':round(len(membership)/max(len(symbols),1)*100,2),'provenance_policy':['COMPUTED','MODEL_DERIVED','ESTIMATED'],'true_dealer_inventory':'DATA_BLOCKED','exchange_tick':'DATA_BLOCKED'},warnings)
        if persist:self.persist(snap,membership)
        return snap
    def persist(self,snap,membership):
        p=to_native(snap.to_dict()); membership=to_native(membership); ts=to_native(snap.snapshot_timestamp); d=date.fromisoformat(snap.as_of_date)
        with self.session_factory() as s:
            for m in membership.values():
                s.execute(text('''INSERT INTO sector_membership(symbol,effective_from,company_name,sector,industry,sub_industry,sector_etf,classification_source,effective_to,is_active,confidence,last_verified_at,payload_json) VALUES(:symbol,:ef,:name,:sector,NULL,NULL,:etf,:src,NULL,true,1.0,:ts,:payload) ON CONFLICT(symbol,effective_from) DO UPDATE SET company_name=EXCLUDED.company_name,sector=EXCLUDED.sector,sector_etf=EXCLUDED.sector_etf,classification_source=EXCLUDED.classification_source,last_verified_at=EXCLUDED.last_verified_at,payload_json=EXCLUDED.payload_json'''),{'symbol':m['symbol'],'ef':date.fromisoformat(m.get('as_of_date') or snap.as_of_date),'name':m['company_name'],'sector':m['sector'],'etf':m['sector_etf'],'src':m['source'],'ts':ts,'payload':strict_json_dumps(m,default=str)})
            s.execute(text('''INSERT INTO market_intelligence_snapshot(snapshot_timestamp,as_of_date,universe_name,source_snapshot_timestamp,confidence,provenance,calculation_version,payload_json,created_at) VALUES(:ts,:d,:u,:ts,:c,'MODEL_DERIVED',:v,:p,:ts) ON CONFLICT(snapshot_timestamp) DO UPDATE SET payload_json=EXCLUDED.payload_json,confidence=EXCLUDED.confidence'''),{'ts':ts,'d':d,'u':snap.universe_name,'c':safe(p['scanner_context'].get('confidence')),'v':self.VERSION,'p':strict_json_dumps(p,default=str)})
            c=p['correlation']
            if c.get('status')=='READY':
                s.execute(text('''INSERT INTO correlation_snapshot(snapshot_timestamp,universe_name,as_of_date,lookback_days,average_pairwise_correlation,median_pairwise_correlation,dispersion,correlation_regime,sample_size,confidence,provenance,payload_json) VALUES(:ts,:u,:d,:l,:a,:m,:x,:r,:n,:c,'COMPUTED',:p) ON CONFLICT(snapshot_timestamp,universe_name) DO UPDATE SET payload_json=EXCLUDED.payload_json'''),{'ts':ts,'u':snap.universe_name,'d':d,'l':c['lookback_days'],'a':c['average_pairwise_correlation'],'m':c['median_pairwise_correlation'],'x':c['cross_sectional_dispersion_annualized_pct'],'r':c['regime'],'n':c['symbol_count'],'c':c['confidence'],'p':strict_json_dumps(c)})
                for x in c.get('pairs',[]):s.execute(text('''INSERT INTO correlation_pair_snapshot(snapshot_timestamp,symbol_a,symbol_b,as_of_date,lookback_days,correlation,confidence,provenance) VALUES(:ts,:a,:b,:d,:l,:v,:c,'COMPUTED') ON CONFLICT DO NOTHING'''),{'ts':ts,'a':x['symbol_a'],'b':x['symbol_b'],'d':d,'l':c['lookback_days'],'v':x['correlation'],'c':c['confidence']})
            for x in p['sector_breadth']:s.execute(text('''INSERT INTO sector_breadth_snapshot(snapshot_timestamp,sector,as_of_date,sector_etf,constituent_count,breadth_score,momentum_score,rotation_label,confidence,provenance,payload_json) VALUES(:ts,:sector,:d,:etf,:n,:b,:m,:r,:c,'COMPUTED',:p) ON CONFLICT DO NOTHING'''),{'ts':ts,'sector':x['sector'],'d':d,'etf':x['sector_etf'],'n':x['constituent_count'],'b':x['breadth_score'],'m':x['momentum_score'],'r':x['rotation_label'],'c':x['confidence'],'p':strict_json_dumps(x)})
            sm=p['sentiment'];s.execute(text('''INSERT INTO market_sentiment_snapshot(snapshot_timestamp,as_of_date,overall_sentiment_score,risk_appetite_score,fear_score,sentiment_label,confidence,provenance,payload_json) VALUES(:ts,:d,:o,:r,:f,:l,:c,'MODEL_DERIVED',:p) ON CONFLICT DO NOTHING'''),{'ts':ts,'d':d,'o':sm['overall_sentiment_score'],'r':sm['risk_appetite_score'],'f':sm['fear_score'],'l':sm['sentiment_label'],'c':sm['confidence'],'p':strict_json_dumps(sm)})
            for x in sm['components']:s.execute(text('''INSERT INTO sentiment_component_snapshot(snapshot_timestamp,component_name,as_of_date,score,weight,contribution,direction,confidence,provenance,payload_json) VALUES(:ts,:n,:d,:s,:w,:co,:di,:c,'MODEL_DERIVED',:p) ON CONFLICT DO NOTHING'''),{'ts':ts,'n':x['name'],'d':d,'s':x['score'],'w':x['weight'],'co':x['contribution'],'di':x['direction'],'c':x['confidence'],'p':strict_json_dumps(x)})
            for x in p['dealer_ensemble']:s.execute(text('''INSERT INTO dealer_position_change_snapshot(snapshot_timestamp,symbol,as_of_date,positioning_score,dealer_conviction_score,confidence,provenance,payload_json) VALUES(:ts,:s,:d,:p,:v,:c,'ESTIMATED',:j) ON CONFLICT DO NOTHING'''),{'ts':ts,'s':x['symbol'],'d':d,'p':x['positioning_score'],'v':x['dealer_conviction_score'],'c':x['confidence'],'j':strict_json_dumps(x)})
            r=p['risk'];s.execute(text('''INSERT INTO market_risk_snapshot(snapshot_timestamp,as_of_date,score,regime,confidence,provenance,payload_json) VALUES(:ts,:d,:s,:r,:c,'MODEL_DERIVED',:p) ON CONFLICT DO NOTHING'''),{'ts':ts,'d':d,'s':r['market_risk_score'],'r':r['risk_regime'],'c':safe(p['scanner_context'].get('confidence')),'p':strict_json_dumps(r)})
            for i,x in enumerate(p['opportunities'],1):s.execute(text('''INSERT INTO market_opportunity_snapshot(snapshot_timestamp,opportunity_rank,as_of_date,opportunity_type,instrument,direction,strategy_family,score,confidence,provenance,payload_json) VALUES(:ts,:i,:d,:t,:n,:di,:sf,:s,:c,'MODEL_DERIVED',:p) ON CONFLICT DO NOTHING'''),{'ts':ts,'i':i,'d':d,'t':x['type'],'n':x['instrument'],'di':x['direction'],'sf':x['strategy_family'],'s':safe(x['score']),'c':safe(x['confidence']),'p':strict_json_dumps(x)})
            s.commit()
    def latest(self):
        with self.session_factory() as s:
            row=s.execute(text('SELECT payload_json FROM market_intelligence_snapshot ORDER BY snapshot_timestamp DESC LIMIT 1')).scalar_one_or_none()
            return json.loads(row) if row else None
    def scanner_context(self):
        x=self.latest(); return (x or {}).get('scanner_context',{})
