import { Fragment, useEffect, useState, type ReactNode } from 'react';
import { Activity, BriefcaseBusiness, ShieldCheck, Waypoints, ScanLine, LogOut, RadioTower, Search, ChevronDown, ChevronRight, Globe2 } from 'lucide-react';
import { platformApi } from './api';
import { useRemote } from './hooks';
import { asArray, firstNumber, money, pct } from './model';
import { Badge, Card, Freshness, JsonView, Metric, State, Table } from './components';

type ArtifactEnvelope = { data: any; metadata?: { stale?: boolean; age_seconds?: number | null } };
type Loader = (signal?: AbortSignal) => Promise<any>;

const numeric = (value: any, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

function candidateRankingReason(candidate: any) {
  const signal = String(candidate.signal || candidate.option_type || '').toUpperCase();
  const isCall = signal.includes('CALL') || signal.includes('BULL');
  const adjustment = numeric(candidate.dealer_score_adjustment);
  const positives: string[] = [];
  const constraints: string[] = [];
  const contractReasons: string[] = [];

  if (adjustment > 0.05) positives.push(`Dealer positioning added ${adjustment.toFixed(2)} points.`);
  if (adjustment < -0.05) constraints.push(`Dealer positioning reduced the score by ${Math.abs(adjustment).toFixed(2)} points.`);

  const positioning = String(candidate.positioning_label || '').replaceAll('_', ' ');
  if (positioning && positioning !== '—') {
    const bullish = positioning.includes('BULL');
    const bearish = positioning.includes('BEAR');
    if ((isCall && bullish) || (!isCall && bearish)) positives.push(`${positioning.toLowerCase()} positioning aligns with the trade direction.`);
    else if ((isCall && bearish) || (!isCall && bullish)) constraints.push(`${positioning.toLowerCase()} positioning conflicts with the trade direction.`);
  }

  const gammaRegime = String(candidate.gamma_regime || '').replaceAll('_', ' ');
  const rangeProbability = numeric(candidate.range_probability, -1);
  const breakoutProbability = numeric(isCall ? candidate.breakout_probability : candidate.breakdown_probability, -1);
  const volatilityExpansion = numeric(candidate.volatility_expansion_probability, -1);
  const hedgePressure = numeric(candidate.dealer_hedging_pressure);
  const wallDistance = numeric(isCall ? candidate.distance_to_call_wall_pct : candidate.distance_to_put_wall_pct, Number.NaN);

  if (gammaRegime.includes('NEGATIVE')) positives.push('Negative gamma can amplify directional movement.');
  if (gammaRegime.includes('POSITIVE')) constraints.push('Positive gamma can suppress long-premium breakout velocity.');
  if (rangeProbability >= 60) constraints.push(`Range probability is elevated at ${rangeProbability.toFixed(0)}%.`);
  else if (rangeProbability >= 0 && rangeProbability <= 40) positives.push(`Range probability is contained at ${rangeProbability.toFixed(0)}%.`);
  if (breakoutProbability >= 55) positives.push(`${isCall ? 'Breakout' : 'Breakdown'} probability is ${breakoutProbability.toFixed(0)}%.`);
  if (volatilityExpansion >= 55) positives.push(`Volatility-expansion probability is ${volatilityExpansion.toFixed(0)}%.`);
  if ((isCall && hedgePressure > 0.15) || (!isCall && hedgePressure < -0.15)) positives.push('Dealer hedging pressure supports the selected direction.');
  if ((isCall && hedgePressure < -0.15) || (!isCall && hedgePressure > 0.15)) constraints.push('Dealer hedging pressure opposes the selected direction.');
  if (Number.isFinite(wallDistance)) {
    if (Math.abs(wallDistance) <= 2) constraints.push(`${isCall ? 'Call' : 'Put'} wall is only ${Math.abs(wallDistance).toFixed(1)}% from spot.`);
    else positives.push(`${isCall ? 'Call' : 'Put'} wall leaves ${Math.abs(wallDistance).toFixed(1)}% of directional room.`);
  }

  if (candidate.expiry) contractReasons.push(`${candidate.dte ?? '—'} DTE contract expiring ${candidate.expiry}.`);
  if (candidate.contract_ticker || candidate.option_symbol || candidate.contract_symbol) contractReasons.push(`Selected contract: ${candidate.contract_ticker || candidate.option_symbol || candidate.contract_symbol}.`);
  if (numeric(candidate.reward_risk_ratio) > 0) contractReasons.push(`Modeled reward/risk is ${numeric(candidate.reward_risk_ratio).toFixed(2)}.`);
  if (numeric(candidate.option_entry) > 0) contractReasons.push(`Entry premium is ${money(candidate.option_entry)} with target ${money(candidate.target_price)} and stop ${money(candidate.stop_price)}.`);

  if (!positives.length) positives.push('Technical and contract-selection inputs produced a qualifying base score.');
  if (!constraints.length) constraints.push('No material ranking penalty was identified in the persisted dealer context.');

  return { positives, constraints, contractReasons };
}


function TrendIntelligenceCandidateCard({trade}:{trade:any}) {
  const total=numeric(trade.combined_trend_score_adjustment,numeric(trade.trend_score_adjustment));
  const status=trade.trend_context_status||trade.transition_context_status||'NOT_AVAILABLE';
  const available=status!=='DISABLED'&&status!=='MISSING'&&status!=='NOT_AVAILABLE';
  const signal=String(trade.signal||'').toUpperCase();
  const direction=signal.includes('PUT')?'bearish':'bullish';
  const explanation=available
    ? `The ${direction} candidate is aligned ${numeric(trade.signal_trend_alignment_score,50).toFixed(1)}% with the persisted trend model. Base trend contributed ${numeric(trade.base_trend_score_adjustment).toFixed(2)} points, transition intelligence contributed ${numeric(trade.transition_score_adjustment).toFixed(2)}, and the governed total trend adjustment was ${total.toFixed(2)}.`
    : 'No governed Trend Intelligence snapshot was available for this candidate; no trend adjustment should be inferred.';
  return <div className="trend-candidate-card">
    <div className="trend-card-heading"><div><h4>Trend Intelligence</h4><small>Milestone 52 decision attribution pinned to this scanner result.</small></div><Badge value={status}/></div>
    <div className="trend-score-strip">
      <div><span>Base trend</span><strong>{String(trade.intermediate_term_trend||trade.short_term_trend||'UNAVAILABLE').replaceAll('_',' ')}</strong><small>{String(trade.trend_stage||'UNAVAILABLE').replaceAll('_',' ')}</small></div>
      <div><span>Transition</span><strong>{String(trade.transition_state||'UNAVAILABLE').replaceAll('_',' ')}</strong><small>{String(trade.breakout_state||'UNAVAILABLE').replaceAll('_',' ')}</small></div>
      <div><span>Forecast</span><strong>{String(trade.forecast_direction||'UNAVAILABLE').replaceAll('_',' ')}</strong><small>Confidence {numeric(trade.forecast_confidence_score).toFixed(1)}</small></div>
      <div><span>Institutional</span><strong>{String(trade.participation_state||trade.participation_grade||'UNAVAILABLE').replaceAll('_',' ')}</strong><small>Participation {numeric(trade.participation_score,50).toFixed(1)}</small></div>
      <div><span>Total adjustment</span><strong className={total>=0?'positive-value':'negative-value'}>{total>=0?'+':''}{total.toFixed(2)}</strong><small>Base {numeric(trade.base_trend_score_adjustment).toFixed(2)} · Transition {numeric(trade.transition_score_adjustment).toFixed(2)} · Forecast {numeric(trade.forecast_score_adjustment).toFixed(2)}</small></div>
    </div>
    <div className="trend-detail-grid">
      <div><h5>Alignment & quality</h5><ul><li>Signal alignment: {numeric(trade.signal_trend_alignment_score,50).toFixed(1)}</li><li>Market alignment: {numeric(trade.market_trend_alignment_score,50).toFixed(1)}</li><li>Sector alignment: {numeric(trade.sector_trend_alignment_score,50).toFixed(1)}</li><li>Trend quality: {numeric(trade.trend_quality_score,50).toFixed(1)}</li><li>Relative strength: {trade.relative_strength_grade||'UNAVAILABLE'}</li></ul></div>
      <div><h5>Transition risk</h5><ul><li>Confirmation: {numeric(trade.transition_confirmation_score,50).toFixed(1)}</li><li>Reversal risk: {numeric(trade.reversal_risk_score).toFixed(1)}</li><li>Exhaustion risk: {numeric(trade.exhaustion_risk_score).toFixed(1)}</li><li>Volatility state: {String(trade.volatility_state||'UNAVAILABLE').replaceAll('_',' ')}</li><li>Channel position: {numeric(trade.channel_position_pct).toFixed(1)}%</li></ul></div>
      <div><h5>Forecast & institution</h5><ul><li>Continuation: {numeric(trade.continuation_probability,50).toFixed(1)}%</li><li>Reversal probability: {numeric(trade.reversal_probability,50).toFixed(1)}%</li><li>Institutional conviction: {numeric(trade.institutional_conviction_score,50).toFixed(1)}</li><li>Leadership: {numeric(trade.leadership_score,50).toFixed(1)}</li><li>Deterioration risk: {numeric(trade.deterioration_risk_score,50).toFixed(1)}</li></ul></div>
      <div><h5>Freshness & lineage</h5><ul><li>Base snapshot: {trade.trend_snapshot_date||'—'} ({trade.trend_snapshot_age_days??'—'} day(s))</li><li>Transition snapshot: {trade.transition_snapshot_date||'—'} ({trade.transition_snapshot_age_days??'—'} day(s))</li><li>Forecast snapshot: {trade.forecast_snapshot_date||'—'} ({trade.forecast_snapshot_age_days??'—'} day(s))</li><li>Institutional snapshot: {trade.institutional_snapshot_date||'—'} ({trade.institutional_snapshot_age_days??'—'} day(s))</li></ul></div>
    </div>
    <p className="trend-explanation">{explanation}</p>
    {(trade.trend_context_warning||trade.transition_context_warning||trade.forecast_context_warning||trade.institutional_context_warning)&&<p className="provider-warning">{[trade.trend_context_warning,trade.transition_context_warning,trade.forecast_context_warning,trade.institutional_context_warning].filter(Boolean).join(' ')}</p>}
  </div>
}

const artifact = (name: string, loader: Loader, render: (value: any) => ReactNode) =>
  function ArtifactPage() {
    const query = useRemote((signal) => loader(signal), []);
    const envelope = query.data as ArtifactEnvelope | null;
    return (
      <State loading={query.loading} error={query.error} onRetry={query.reload}>
        {envelope && (
          <>
            <div className="page-title">
              <div><h2>{name}</h2><p>Live governed state from the production API.</p></div>
              <Freshness stale={envelope.metadata?.stale} age={envelope.metadata?.age_seconds} />
            </div>
            {render(envelope.data)}
            <JsonView value={envelope.data} />
          </>
        )}
      </State>
    );
  };

export function Overview() {
  const query = useRemote((signal) => platformApi.overview(signal), []);
  return (
    <State loading={query.loading} error={query.error} onRetry={query.reload}>
      {query.data && (
        <>
          <div className="page-title"><div><h2>Command overview</h2><p>Operational posture across portfolio, risk, execution, and positions.</p></div></div>
          <div className="grid metrics">
            {Object.entries(query.data.data).map(([key, value]) => (
              <Metric
                key={key}
                label={key.replaceAll('_', ' ')}
                value={<Badge value={value.exists ? (value.stale ? 'STALE' : 'AVAILABLE') : 'MISSING'} />}
                detail={value.path}
              />
            ))}
          </div>
        </>
      )}
    </State>
  );
}

export const Portfolio = artifact('Portfolio', platformApi.portfolio, (data: any) => {
  const rows = asArray(data);
  return <><div className="grid metrics"><Metric label="Net liquidation" value={money(firstNumber(data, ['net_liquidation_value', 'equity', 'capital']))} /><Metric label="Cash" value={money(firstNumber(data, ['cash_balance', 'cash', 'available_cash']))} /><Metric label="Open positions" value={rows.length} /><Metric label="Capital utilized" value={pct(firstNumber(data, ['capital_utilization', 'utilization']))} /></div><Card title="Positions"><Table rows={rows} columns={[{ key: 'symbol', label: 'Symbol' }, { key: 'strategy', label: 'Strategy' }, { key: 'quantity', label: 'Qty' }, { key: 'market_value', label: 'Market value', render: row => money(firstNumber(row, ['market_value', 'current_value'])) }, { key: 'status', label: 'Status', render: row => <Badge value={row.status || row.position_status} /> }]} /></Card></>;
});

export const Risk = artifact('Portfolio risk', platformApi.risk, (data: any) => <><div className="grid metrics"><Metric label="Risk status" value={<Badge value={data.risk_status || data.status} />} /><Metric label="Trading control" value={<Badge value={data.trading_control} />} /><Metric label="Allow new risk" value={String(Boolean(data.allow_new_risk))} /><Metric label="Blocking breaches" value={(data.blocking_breach_ids || []).length} /></div><Card title="Recommendations"><ul className="recommendations">{(data.recommendations || ['No active recommendations']).map((item: string) => <li key={item}>{item}</li>)}</ul></Card></>);

export const Execution = artifact('Execution', platformApi.execution, (data: any) => {
  const rows = asArray(data);
  return <><div className="grid metrics"><Metric label="Orders" value={rows.length} /><Metric label="Released" value={rows.filter(row => String(row.status).includes('RELEASED')).length} /><Metric label="Filled" value={rows.filter(row => String(row.status).includes('FILLED')).length} /><Metric label="Blocked" value={rows.filter(row => String(row.status).includes('BLOCK')).length} /></div><Card title="Execution queue"><Table rows={rows} columns={[{ key: 'symbol', label: 'Symbol' }, { key: 'action', label: 'Action' }, { key: 'quantity', label: 'Qty' }, { key: 'status', label: 'Status', render: row => <Badge value={row.status} /> }, { key: 'broker_order_id', label: 'Broker order' }]} /></Card></>;
});

export const Positions = artifact('Position monitoring', platformApi.positions, (data: any) => {
  const rows = asArray(data);
  return <Card title="Position assessments"><Table rows={rows} columns={[{ key: 'symbol', label: 'Symbol' }, { key: 'decision', label: 'Decision', render: row => <Badge value={row.decision} /> }, { key: 'unrealized_return', label: 'Return', render: row => pct(firstNumber(row, ['unrealized_return', 'return_pct'])) }, { key: 'holding_days', label: 'Days' }, { key: 'urgency', label: 'Urgency', render: row => <Badge value={row.urgency} /> }]} /></Card>;
});

export const Exits = artifact('Exit intelligence', platformApi.exits, (data: any) => {
  const rows = asArray(data);
  return <Card title="Exit instructions"><Table rows={rows} columns={[{ key: 'symbol', label: 'Symbol' }, { key: 'action', label: 'Action' }, { key: 'quantity', label: 'Qty' }, { key: 'order_type', label: 'Type' }, { key: 'status', label: 'Status', render: row => <Badge value={row.status} /> }, { key: 'urgency', label: 'Urgency', render: row => <Badge value={row.urgency} /> }]} /></Card>;
});

export const nav = [
  ['overview', 'Overview', Activity],
  ['market', 'Market overview', Globe2],
  ['scanner', 'Daily scanner', Search],
  ['option-scanner', 'Option scanner', Search],
  ['portfolio', 'Portfolio', BriefcaseBusiness],
  ['risk', 'Risk', ShieldCheck],
  ['execution', 'Execution', Waypoints],
  ['positions', 'Positions', ScanLine],
  ['exits', 'Exits', LogOut],
  ['command', 'Command center', RadioTower],
] as const;

export function CommandCenter(){const [data,setData]=useState<any>(null);const [events,setEvents]=useState<any[]>([]);useEffect(()=>{fetch('/api/v1/realtime/snapshot',{headers:{'X-API-Key':sessionStorage.getItem('trading-ai-api-key')??''}}).then(r=>r.json()).then(setData);const key=sessionStorage.getItem('trading-ai-api-key')??'';const ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/realtime/stream?api_key=${encodeURIComponent(key)}`);ws.onmessage=e=>setEvents(v=>[JSON.parse(e.data),...v].slice(0,50));return()=>ws.close()},[]);return <section><h2>Operational Command Center</h2><div className="metrics"><article><b>{data?.connected_clients??0}</b><span>Live clients</span></article><article><b>{data?.open_alerts??0}</b><span>Open alerts</span></article><article><b>{data?.critical_alerts??0}</b><span>Critical alerts</span></article><article><b>{data?.events_published??0}</b><span>Events</span></article></div><div className="panel"><h3>Live event stream</h3><pre>{JSON.stringify(events,null,2)}</pre></div></section>}

type ScannerWorkspaceConfig = {
  workspaceKey: 'daily-scanner' | 'option-scanner';
  title: string;
  description: string;
  actionLabel: string;
};

type ScannerExperienceMode = 'basic' | 'advanced' | 'professional';

function ScannerWorkspacePage({config}:{config:ScannerWorkspaceConfig}){
  const [runs,setRuns]=useState<any[]>([]);const [selected,setSelected]=useState<any>(null);const [results,setResults]=useState<any>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [expandedTrade,setExpandedTrade]=useState<string|null>(null);
  const [universe,setUniverse]=useState('liquid-us-700');const [universes,setUniverses]=useState<any[]>([]);const [symbols,setSymbols]=useState('');const [minimumScore,setMinimumScore]=useState(60);const [top,setTop]=useState(10);const [expirationMode,setExpirationMode]=useState<'automatic'|'short'|'swing'|'medium'|'long'|'custom'|'fixed'>('automatic');const [minimumDte,setMinimumDte]=useState(14);const [maximumDte,setMaximumDte]=useState(90);const [maxPerExpiry,setMaxPerExpiry]=useState(3);const [refreshMode,setRefreshMode]=useState<'cache_only'|'refresh_missing'|'force_full'>('refresh_missing');const [ingestionScope,setIngestionScope]=useState<'underlying'|'options'|'all'>('all');const [autoRefresh,setAutoRefresh]=useState(true);const [minimumCoverage,setMinimumCoverage]=useState(98);const [maximumFailedSymbols,setMaximumFailedSymbols]=useState(10);const [continueOnDegraded,setContinueOnDegraded]=useState(true);
  const [experienceMode,setExperienceMode]=useState<ScannerExperienceMode>('advanced');
  const [preferencesReady,setPreferencesReady]=useState(false);
  useEffect(()=>{
    try{
      const raw=localStorage.getItem(`trading-ai:${config.workspaceKey}:scan-controls`);
      if(raw){
        const value=JSON.parse(raw);
        if(typeof value.universe==='string')setUniverse(value.universe);
        if(typeof value.symbols==='string')setSymbols(value.symbols);
        if(Number.isFinite(value.minimumScore))setMinimumScore(value.minimumScore);
        if(Number.isFinite(value.top))setTop(value.top);
        if(typeof value.expirationMode==='string')setExpirationMode(value.expirationMode);
        if(Number.isFinite(value.minimumDte))setMinimumDte(value.minimumDte);
        if(Number.isFinite(value.maximumDte))setMaximumDte(value.maximumDte);
        if(Number.isFinite(value.maxPerExpiry))setMaxPerExpiry(value.maxPerExpiry);
        if(typeof value.refreshMode==='string')setRefreshMode(value.refreshMode);
        if(typeof value.ingestionScope==='string')setIngestionScope(value.ingestionScope);
        if(typeof value.autoRefresh==='boolean')setAutoRefresh(value.autoRefresh);
        if(Number.isFinite(value.minimumCoverage))setMinimumCoverage(value.minimumCoverage);
        if(Number.isFinite(value.maximumFailedSymbols))setMaximumFailedSymbols(value.maximumFailedSymbols);
        if(typeof value.continueOnDegraded==='boolean')setContinueOnDegraded(value.continueOnDegraded);
        if(value.experienceMode==='basic'||value.experienceMode==='advanced'||value.experienceMode==='professional')setExperienceMode(value.experienceMode);
      }
    }catch{localStorage.removeItem(`trading-ai:${config.workspaceKey}:scan-controls`)}
    setPreferencesReady(true);
  },[config.workspaceKey]);
  useEffect(()=>{
    if(!preferencesReady)return;
    localStorage.setItem(`trading-ai:${config.workspaceKey}:scan-controls`,JSON.stringify({universe,symbols,minimumScore,top,expirationMode,minimumDte,maximumDte,maxPerExpiry,refreshMode,ingestionScope,autoRefresh,minimumCoverage,maximumFailedSymbols,continueOnDegraded,experienceMode}));
  },[preferencesReady,config.workspaceKey,universe,symbols,minimumScore,top,expirationMode,minimumDte,maximumDte,maxPerExpiry,refreshMode,ingestionScope,autoRefresh,minimumCoverage,maximumFailedSymbols,continueOnDegraded,experienceMode]);
  const selectedSymbols=()=>symbols.split(',').map(x=>x.trim().toUpperCase()).filter(Boolean);
  const dates=()=>{const today=new Date().toISOString().slice(0,10);const start=new Date(Date.now()-365*86400000).toISOString().slice(0,10);return {today,start}};
  const load=async()=>{try{const response=await import('./api').then(m=>m.scannerApi.runs());setRuns(response.data);const current=response.data.find((r:any)=>r.kind==='DAILY_SCAN');if(current){setSelected(current);if(current.status==='SUCCEEDED'){const value=await import('./api').then(m=>m.scannerApi.results(current.run_id));setResults(value.data)}}}catch(e:any){setError(e.message)}};
  useEffect(()=>{import('./api').then(m=>m.scannerApi.universes()).then(r=>{setUniverses(r.data);if(r.data.length&&!r.data.some((u:any)=>u.id===universe))setUniverse(r.data[0].id)}).catch((e:any)=>setError(e.message));load();const timer=setInterval(load,3000);return()=>clearInterval(timer)},[]);
  const ingest=async()=>{setBusy(true);setError('');try{const {today,start}=dates();await import('./api').then(m=>m.scannerApi.refresh({data_scope:ingestionScope,universe,symbols:selectedSymbols(),start,end:today,refresh_mode:refreshMode,minimum_bars:20,stale_after_days:1,minimum_coverage_pct:minimumCoverage,maximum_failed_symbols:maximumFailedSymbols,continue_on_degraded_refresh:continueOnDegraded,max_retries:3,retry_backoff_seconds:2,maximum_retry_backoff_seconds:60,retry_jitter_ratio:.20,rate_limit_cooldown_seconds:15,circuit_breaker_threshold:3,circuit_breaker_cooldown_seconds:30,batch_size:100}));await load()}catch(e:any){setError(e.message)}finally{setBusy(false)}};
  const scan=async()=>{setBusy(true);setError('');try{const {today,start}=dates();const response=await import('./api').then(m=>m.scannerApi.scan({universe,symbols:selectedSymbols(),start,end:today,minimum_score:minimumScore,top,pricing_dte:30,expiration_mode:expirationMode,minimum_dte:minimumDte,maximum_dte:maximumDte,maximum_expirations_per_symbol:4,maximum_trades_per_expiration:maxPerExpiry,option_data_mode:'live',liquidity_data_mode:'adaptive',maximum_option_spread_pct:.25,minimum_option_open_interest:100,minimum_option_volume:10,capital:100000,risk_per_trade_pct:.02,max_position_pct:.05,take_profit_pct:.30,stop_loss_pct:.15,refresh_mode:refreshMode,auto_refresh:autoRefresh,minimum_refresh_coverage_pct:minimumCoverage,maximum_failed_refresh_symbols:maximumFailedSymbols,continue_on_degraded_refresh:continueOnDegraded,refresh_max_retries:3,refresh_retry_backoff_seconds:2,refresh_maximum_retry_backoff_seconds:60,refresh_retry_jitter_ratio:.20,refresh_rate_limit_cooldown_seconds:15,refresh_circuit_breaker_threshold:3,refresh_circuit_breaker_cooldown_seconds:30}));setSelected(response.data);await load()}catch(e:any){setError(e.message)}finally{setBusy(false)}};
  const candidates=results?.recommendations?.candidates||[];const trades=results?.trades?.trades||[];const latestIngestion=runs.find((r:any)=>r.kind==='DATA_REFRESH');
  const modeHelp=refreshMode==='cache_only'?'Validate and scan persisted PostgreSQL data only. No Yahoo or Polygon calls are allowed.':refreshMode==='refresh_missing'?'Refresh only missing or stale persisted data before analysis.':'Rebuild the selected persisted dataset from providers.';
  const selectedUniverse=universes.find((u:any)=>u.id===universe);
  const isOptionWorkspace=config.workspaceKey==='option-scanner';
  return <section className={isOptionWorkspace?'option-scanner-workspace':''}>
    <div className="page-title"><div><h2>{config.title}</h2><p>{config.description}</p></div><Badge value={selected?.status||'IDLE'}/></div>
    {error&&<div className="scanner-error">{error}</div>}
    {!isOptionWorkspace&&<>
      <Card title="Market ingestion"><div className="scanner-form"><label>Ingestion scope<select value={ingestionScope} onChange={e=>setIngestionScope(e.target.value as any)}><option value="all">Full ingestion — Yahoo OHLCV + Polygon options</option><option value="underlying">Underlying only — Yahoo OHLCV</option><option value="options">Options only — Polygon</option></select></label><label>Ingestion mode<select value={refreshMode} onChange={e=>setRefreshMode(e.target.value as any)}><option value="cache_only">Validate persisted data only</option><option value="refresh_missing">Refresh missing / stale</option><option value="force_full">Force full rebuild</option></select><small>{modeHelp}</small></label><label>Minimum OHLCV coverage %<input type="number" min="0" max="100" step="0.1" value={minimumCoverage} onChange={e=>setMinimumCoverage(Number(e.target.value))}/></label><label>Maximum failed symbols<input type="number" min="0" max="1000" value={maximumFailedSymbols} onChange={e=>setMaximumFailedSymbols(Number(e.target.value))}/></label><label className="check"><input type="checkbox" checked={continueOnDegraded} onChange={e=>setContinueOnDegraded(e.target.checked)}/>Continue when degraded thresholds pass</label><div className="scanner-actions"><button disabled={busy} onClick={ingest}>Run market ingestion</button></div></div><div className="grid metrics"><Metric label="Last ingestion" value={latestIngestion?new Date(latestIngestion.created_at).toLocaleString():'—'}/><Metric label="Ingestion scope" value={latestIngestion?.request?.data_scope||'—'}/><Metric label="Ingestion status" value={<Badge value={latestIngestion?.status||'UNKNOWN'}/>}/><Metric label="Coverage" value={latestIngestion?.summary?.coverage||'—'}/></div></Card>
      <Card title="Scan controls"><div className="scanner-form"><label>Universe<select value={universe} onChange={e=>setUniverse(e.target.value)}>{universes.length?universes.map((u:any)=><option key={u.id} value={u.id}>{u.label} — {u.symbol_count}</option>):<option value="liquid-us-700">Highly Liquid U.S. Equities & ETFs</option>}</select><small>{selectedUniverse?.description||'Loaded from the governed backend registry.'}</small></label><label>Custom symbols<input value={symbols} onChange={e=>setSymbols(e.target.value)} placeholder="AAPL,MSFT,SPY"/></label><label>Minimum score<input type="number" value={minimumScore} onChange={e=>setMinimumScore(Number(e.target.value))}/></label><label>Top trades<input type="number" value={top} onChange={e=>setTop(Number(e.target.value))}/></label><label>Expiration selection<select value={expirationMode} onChange={e=>setExpirationMode(e.target.value as any)}><option value="automatic">Automatic — all eligible horizons</option><option value="short">Short — 7 to 21 DTE</option><option value="swing">Swing — 22 to 45 DTE</option><option value="medium">Medium — 46 to 75 DTE</option><option value="long">Long — 76 to 120 DTE</option><option value="custom">Custom DTE range</option><option value="fixed">Fixed — legacy 30 DTE</option></select></label><label>Minimum DTE<input type="number" min="1" max="730" value={minimumDte} onChange={e=>setMinimumDte(Number(e.target.value))}/></label><label>Maximum DTE<input type="number" min="1" max="730" value={maximumDte} onChange={e=>setMaximumDte(Number(e.target.value))}/></label><label>Max trades per expiry<input type="number" min="0" max="100" value={maxPerExpiry} onChange={e=>setMaxPerExpiry(Number(e.target.value))}/><small>Use 0 to disable expiry diversification.</small></label><label className="check"><input type="checkbox" checked={autoRefresh} onChange={e=>setAutoRefresh(e.target.checked)}/>Run governed ingestion before scanning</label><div className="scanner-actions"><button className="primary" disabled={busy} onClick={scan}>{config.actionLabel}</button></div></div></Card>
    </>}
    {isOptionWorkspace&&<>
      <div className="option-scanner-toolbar">
        <div><span className="eyebrow">Workspace depth</span><div className="mode-switch" role="group" aria-label="Option Scanner workspace depth">{(['basic','advanced','professional'] as ScannerExperienceMode[]).map(mode=><button key={mode} type="button" className={experienceMode===mode?'active':''} onClick={()=>setExperienceMode(mode)}>{mode[0].toUpperCase()+mode.slice(1)}</button>)}</div></div>
        <div className="workspace-summary"><span>Universe</span><strong>{selectedUniverse?.label||universe}</strong><small>{selectedUniverse?.symbol_count??'—'} governed symbols</small></div>
        <div className="workspace-summary"><span>Contract horizon</span><strong>{expirationMode==='automatic'?'Automatic':`${minimumDte}–${maximumDte} DTE`}</strong><small>{maxPerExpiry?`${maxPerExpiry} trades per expiry`:'No expiry cap'}</small></div>
        <div className="workspace-summary"><span>Data policy</span><strong>{autoRefresh?'Refresh before scan':'Persisted data'}</strong><small>{refreshMode.replaceAll('_',' ')}</small></div>
      </div>
      <div className="option-scanner-control-grid">
        <article className="control-section control-section-primary">
          <div className="control-section-heading"><div><span>01</span><h3>Opportunity definition</h3></div><p>Choose the governed symbol population and ranking threshold.</p></div>
          <div className="control-fields">
            <label className="field-wide">Universe<select value={universe} onChange={e=>setUniverse(e.target.value)}>{universes.length?universes.map((u:any)=><option key={u.id} value={u.id}>{u.label} — {u.symbol_count}</option>):<option value="liquid-us-700">Highly Liquid U.S. Equities & ETFs</option>}</select><small>{selectedUniverse?.description||'Loaded from the governed backend registry.'}</small></label>
            <label>Minimum score<input type="number" min="0" max="100" value={minimumScore} onChange={e=>setMinimumScore(Number(e.target.value))}/></label>
            <label>Maximum opportunities<input type="number" min="1" max="250" value={top} onChange={e=>setTop(Number(e.target.value))}/></label>
            {experienceMode!=='basic'&&<label className="field-wide">Custom symbol override<input value={symbols} onChange={e=>setSymbols(e.target.value)} placeholder="AAPL,MSFT,SPY"/><small>Optional comma-separated symbols. Canonical and data-readiness governance still applies.</small></label>}
          </div>
        </article>
        <article className="control-section">
          <div className="control-section-heading"><div><span>02</span><h3>Contract horizon</h3></div><p>Control expiration selection and diversification.</p></div>
          <div className="control-fields">
            <label className="field-wide">Expiration selection<select value={expirationMode} onChange={e=>setExpirationMode(e.target.value as any)}><option value="automatic">Automatic — all eligible horizons</option><option value="short">Short — 7 to 21 DTE</option><option value="swing">Swing — 22 to 45 DTE</option><option value="medium">Medium — 46 to 75 DTE</option><option value="long">Long — 76 to 120 DTE</option><option value="custom">Custom DTE range</option><option value="fixed">Fixed — legacy 30 DTE</option></select></label>
            {experienceMode!=='basic'&&<><label>Minimum DTE<input type="number" min="1" max="730" value={minimumDte} onChange={e=>setMinimumDte(Number(e.target.value))}/></label><label>Maximum DTE<input type="number" min="1" max="730" value={maximumDte} onChange={e=>setMaximumDte(Number(e.target.value))}/></label><label>Max trades per expiry<input type="number" min="0" max="100" value={maxPerExpiry} onChange={e=>setMaxPerExpiry(Number(e.target.value))}/><small>Use 0 to disable expiry diversification.</small></label></>}
          </div>
        </article>
        {experienceMode!=='basic'&&<article className="control-section">
          <div className="control-section-heading"><div><span>03</span><h3>Data readiness</h3></div><p>Choose whether the scan validates or refreshes governed market data.</p></div>
          <div className="control-fields">
            <label className="field-wide">Refresh policy<select value={refreshMode} onChange={e=>setRefreshMode(e.target.value as any)}><option value="cache_only">Persisted data only</option><option value="refresh_missing">Refresh missing / stale</option><option value="force_full">Force full rebuild</option></select><small>{modeHelp}</small></label>
            <label className="check field-wide"><input type="checkbox" checked={autoRefresh} onChange={e=>setAutoRefresh(e.target.checked)}/>Run governed ingestion before finding opportunities</label>
            {experienceMode==='professional'&&<><label>Minimum coverage %<input type="number" min="0" max="100" step="0.1" value={minimumCoverage} onChange={e=>setMinimumCoverage(Number(e.target.value))}/></label><label>Maximum failed symbols<input type="number" min="0" max="1000" value={maximumFailedSymbols} onChange={e=>setMaximumFailedSymbols(Number(e.target.value))}/></label><label className="check field-wide"><input type="checkbox" checked={continueOnDegraded} onChange={e=>setContinueOnDegraded(e.target.checked)}/>Continue when degraded thresholds still satisfy governance</label></>}
          </div>
        </article>}
        {experienceMode==='professional'&&<article className="control-section control-section-operations">
          <div className="control-section-heading"><div><span>04</span><h3>Ingestion operations</h3></div><p>Run market-data ingestion independently from the opportunity scan.</p></div>
          <div className="control-fields">
            <label className="field-wide">Ingestion scope<select value={ingestionScope} onChange={e=>setIngestionScope(e.target.value as any)}><option value="all">Full ingestion — Yahoo OHLCV + Polygon options</option><option value="underlying">Underlying only — Yahoo OHLCV</option><option value="options">Options only — Polygon</option></select></label>
            <div className="scanner-actions field-wide"><button disabled={busy} onClick={ingest}>Run market ingestion</button></div>
          </div>
          <div className="operation-status"><span>Last ingestion <strong>{latestIngestion?new Date(latestIngestion.created_at).toLocaleString():'—'}</strong></span><span>Status <Badge value={latestIngestion?.status||'UNKNOWN'}/></span><span>Coverage <strong>{latestIngestion?.summary?.coverage||'—'}</strong></span></div>
        </article>}
      </div>
      <div className="option-scanner-actionbar">
        <div><span>Ready to evaluate</span><strong>{selectedUniverse?.label||'Selected universe'}</strong><small>Minimum score {minimumScore} · Top {top} · {expirationMode==='automatic'?'automatic expiration selection':`${minimumDte}–${maximumDte} DTE`}</small></div>
        <button className="primary opportunity-action" disabled={busy} onClick={scan}>{busy?'Working…':config.actionLabel}</button>
      </div>
    </>}
    <div className="grid metrics"><Metric label="Symbols scanned" value={selected?.summary?.symbols_scanned||0}/><Metric label="Candidates" value={candidates.length||selected?.summary?.candidate_count||0}/><Metric label="Best trades" value={trades.length||selected?.summary?.trade_count||0}/><Metric label="Top score" value={selected?.summary?.top_score?Number(selected.summary.top_score).toFixed(2):'—'}/></div>
    <Card title="Data readiness" compact><div className="grid metrics compact-metrics readiness-metrics"><Metric label="Scanner source" value="PostgreSQL"/><Metric label="Underlying data" value={<Badge value={selected?.summary?.underlying_data_status||latestIngestion?.summary?.underlying_status||'READY'}/>}/><Metric label="Options snapshot" value={<Badge value={selected?.summary?.options_data_status||latestIngestion?.summary?.options_status||'READY'}/>}/><Metric label="Dealer analytics" value={<Badge value={trades.some((trade:any)=>trade.dealer_context_status==='FRESH')?'FRESH':trades.length?'MISSING':'UNKNOWN'}/>}/><Metric label="Last refresh" value={latestIngestion?new Date(latestIngestion.created_at).toLocaleString():'—'}/></div></Card>
    <Card title="Run history" compact><div className="run-history-scroll"><Table rows={runs} columns={[{key:'created_at',label:'Created',render:r=>new Date(r.created_at).toLocaleString()},{key:'kind',label:'Workflow'},{key:'status',label:'Status',render:r=><Badge value={r.status}/>},{key:'scope',label:'Scope',render:r=>r.request?.data_scope??(r.kind==='DAILY_SCAN'?'scan':'—')},{key:'refresh_mode',label:'Ingestion mode',render:r=>r.request?.refresh_mode==='refresh_missing'?'Refresh missing / stale':r.request?.refresh_mode==='force_full'?'Force full rebuild':r.request?.refresh_mode==='cache_only'?'Persisted data only':'—'},{key:'candidate_count',label:'Candidates',render:r=>r.summary?.candidate_count??'—'},{key:'coverage',label:'Coverage',render:r=>r.summary?.coverage??'—'},{key:'excluded_symbols',label:'Excluded',render:r=>r.summary?.excluded_symbols&&r.summary.excluded_symbols!=='NONE'?r.summary.excluded_symbols:'—'},{key:'trade_count',label:'Trades',render:r=>r.summary?.trade_count??'—'}]}/></div></Card>
    <Card title="Best trade candidates">
      <div className="candidate-table-scroll">
        <table className="candidate-table">
          <thead><tr><th aria-label="Expand ranking reason"></th><th>Symbol</th><th>Signal</th><th>Strategy</th><th>Final AI</th><th>Base AI</th><th>Dealer adj.</th><th>Dealer data</th><th>Positioning</th><th>Gamma regime</th><th>MS confidence</th><th>Contract</th><th>Expiry</th><th>DTE</th><th>Strike</th><th>Entry</th><th>Target</th><th>Stop</th><th>R/R</th></tr></thead>
          <tbody>{trades.length?trades.map((trade:any,index:number)=>{
            const tradeKey=String(trade.id||trade.trade_id||trade.contract_ticker||`${trade.symbol}-${trade.expiry}-${trade.strike}-${index}`);
            const expanded=expandedTrade===tradeKey;
            const reason=candidateRankingReason(trade);
            return <Fragment key={tradeKey}>
              <tr className={`candidate-row${expanded?' expanded':''}`} onClick={()=>setExpandedTrade(expanded?null:tradeKey)} aria-expanded={expanded}>
                <td className="expand-cell">{expanded?<ChevronDown size={16}/>:<ChevronRight size={16}/>}</td><td><strong>{trade.symbol||'—'}</strong></td><td><Badge value={trade.signal}/></td><td>{trade.strategy||'—'}</td><td>{numeric(trade.ai_score).toFixed(2)}</td><td>{numeric(trade.base_ai_score, numeric(trade.ai_score)).toFixed(2)}</td><td className={numeric(trade.dealer_score_adjustment)>=0?'positive-value':'negative-value'}>{numeric(trade.dealer_score_adjustment)>=0?'+':''}{numeric(trade.dealer_score_adjustment).toFixed(2)}</td><td><Badge value={trade.dealer_context_status||'MISSING'}/></td><td>{String(trade.positioning_label||'—').replaceAll('_',' ')}</td><td>{String(trade.gamma_regime||'—').replaceAll('_',' ')}</td><td>{numeric(trade.market_structure_confidence).toFixed(2)}</td><td>{trade.contract_ticker||trade.option_symbol||trade.contract_symbol||'—'}</td><td>{trade.expiry||'—'}</td><td>{trade.dte??'—'}</td><td>{money(trade.strike)}</td><td>{money(trade.option_entry)}</td><td>{money(trade.target_price)}</td><td>{money(trade.stop_price)}</td><td>{numeric(trade.reward_risk_ratio).toFixed(2)}</td>
              </tr>
              {expanded&&<tr className="candidate-detail-row"><td colSpan={19}>
                <div className="ranking-reason">
                  <div className="ranking-score-strip"><div><span>Base AI</span><strong>{numeric(trade.base_ai_score,numeric(trade.ai_score)).toFixed(2)}</strong></div><div><span>Dealer adjustment</span><strong className={numeric(trade.dealer_score_adjustment)>=0?'positive-value':'negative-value'}>{numeric(trade.dealer_score_adjustment)>=0?'+':''}{numeric(trade.dealer_score_adjustment).toFixed(2)}</strong></div><div><span>Final AI</span><strong>{numeric(trade.ai_score).toFixed(2)}</strong></div><div><span>Dealer snapshot</span><strong>{trade.dealer_snapshot_date||'—'}</strong></div></div>
                  <div className="ranking-reason-grid"><div><h4>Positive contributors</h4><ul>{reason.positives.map(item=><li key={item}>{item}</li>)}</ul></div><div><h4>Constraints and penalties</h4><ul>{reason.constraints.map(item=><li key={item}>{item}</li>)}</ul></div><div><h4>Contract selection</h4><ul>{reason.contractReasons.map(item=><li key={item}>{item}</li>)}</ul></div><div><h4>Data freshness</h4><ul><li>Dealer context: {trade.dealer_context_status||'MISSING'}</li><li>Dealer snapshot: {trade.dealer_snapshot_date||'—'}</li><li>Snapshot age: {trade.dealer_snapshot_age_days??'—'} day(s)</li><li>Market-structure confidence: {numeric(trade.market_structure_confidence).toFixed(2)}</li>{trade.dealer_context_warning&&<li>{trade.dealer_context_warning}</li>}</ul></div></div>
                  <TrendIntelligenceCandidateCard trade={trade}/>
                </div>
              </td></tr>}
            </Fragment>
          }):<tr><td colSpan={19} className="empty">No trade candidates available</td></tr>}</tbody>
        </table>
      </div>
    </Card>
    {selected&&(selected.stdout||selected.stderr)&&<Card title="Execution log"><pre className="run-log">{selected.stdout}{selected.stderr&&`\n${selected.stderr}`}</pre></Card>}
  </section>
}


const scoreTone=(value:number)=>value>=65?'good':value<40?'bad':'warn';
const fmt=(value:any,digits=1)=>Number(value??0).toFixed(digits);
const signed=(value:any)=>`${Number(value??0)>=0?'+':''}${fmt(value,2)}%`;
function ScoreBar({label,value}:{label:string;value:any}){const n=Math.max(0,Math.min(100,Number(value??0)));return <div className="score-bar"><div><span>{label}</span><b>{n.toFixed(1)}</b></div><div className="score-track"><i style={{width:`${n}%`}}/></div></div>}
function DistributionGroup({title,values}:{title:string;values:Record<string,any>}){const entries=Object.entries(values||{}).map(([state,count])=>({state,count:numeric(count)})).sort((a,b)=>b.count-a.count);const total=entries.reduce((sum,row)=>sum+row.count,0);return <div className="distribution-group"><div className="distribution-group-title"><h5>{title}</h5><span>{total} symbols</span></div>{entries.length?<div className="distribution-bars">{entries.map(row=>{const share=total?row.count/total*100:0;return <div className="distribution-row" key={`${title}-${row.state}`}><div><span>{row.state.replaceAll('_',' ')}</span><b>{row.count}</b></div><div className="distribution-track"><i style={{width:`${share}%`}}/></div><small>{share.toFixed(0)}%</small></div>})}</div>:<p className="empty distribution-empty">No distribution available</p>}</div>}


const DAILY_SCANNER_WORKSPACE: ScannerWorkspaceConfig = {
  workspaceKey: 'daily-scanner',
  title: 'Daily scanner',
  description: 'Ingest governed provider data when requested, then run analysis exclusively from persisted PostgreSQL data.',
  actionLabel: 'Run database-only daily scan',
};

const OPTION_SCANNER_WORKSPACE: ScannerWorkspaceConfig = {
  workspaceKey: 'option-scanner',
  title: 'Option scanner',
  description: 'A parallel options-opportunity workspace cloned from the production Daily Scanner for controlled side-by-side evaluation.',
  actionLabel: 'Find Opportunities',
};

export function DailyScannerPage(){return <ScannerWorkspacePage config={DAILY_SCANNER_WORKSPACE}/>;}
export function OptionScannerPage(){return <ScannerWorkspacePage config={OPTION_SCANNER_WORKSPACE}/>;}

function LegacyMarketOverviewPage(){
  const [data,setData]=useState<any>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState('');const [refreshing,setRefreshing]=useState(false);
  const headers=()=>{const h:Record<string,string>={'Accept':'application/json'};const key=sessionStorage.getItem('trading-ai-api-key');if(key){h['X-API-Key']=key;h['X-Actor']='workstation-user'}return h};
  const load=async()=>{setLoading(true);setError('');try{const r=await fetch('/api/v1/market-overview/latest',{headers:headers()});const p=await r.json();if(!r.ok)throw new Error(p.detail||r.statusText);setData(p.data)}catch(e:any){setError(e.message)}finally{setLoading(false)}};
  const refresh=async()=>{setRefreshing(true);setError('');try{const h=headers();h['Content-Type']='application/json';const r=await fetch('/api/v1/market-overview/refresh',{method:'POST',headers:h});const p=await r.json();if(!r.ok)throw new Error(p.detail||r.statusText);setData(p.data)}catch(e:any){setError(e.message)}finally{setRefreshing(false)}};
  useEffect(()=>{load()},[]);
  if(loading)return <State loading error={null} onRetry={load}>{null}</State>;if(error&&!data)return <State loading={false} error={new Error(error)} onRetry={load}>{null}</State>;
  const b=data?.breadth||{},tm=data?.trend_momentum||{},rs=data?.regime_sentiment||{},vol=data?.volatility_options||{},liq=data?.liquidity_participation||{};
  const opp=data?.opportunity_map||{},ti=data?.trend_intelligence||{},tib=ti?.breadth||{},tid=ti?.distributions||{},tio=ti?.operations||{};
  return <section className="market-overview-page">
    <div className="page-title"><div><h2>Market overview</h2><p>Top-down market health, regime, sector rotation, options structure, and trading opportunity context from persisted data.</p></div><div className="overview-actions"><Badge value={data?.market_bias||'UNKNOWN'}/><button disabled={refreshing} onClick={refresh}>{refreshing?'Refreshing…':'Refresh analytics'}</button></div></div>
    {error&&<div className="scanner-error">{error}</div>}
    <div className="market-status-grid">
      <Metric label="Market bias" value={<Badge value={data?.market_bias}/>} detail={`Confidence ${fmt(data?.confidence_score)}%`}/>
      <Metric label="Preferred strategy" value={String(data?.preferred_strategy||'—').replaceAll('_',' ')} detail={data?.volatility_regime}/>
      <Metric label="Market health" value={fmt(data?.market_health_score)} detail={data?.breadth_regime}/>
      <Metric label="Regime transition" value={<Badge value={data?.regime_transition_risk}/>} detail={data?.trend_regime}/>
      <Metric label="Snapshot" value={data?.as_of_date||'—'} detail={data?.snapshot_timestamp?new Date(data.snapshot_timestamp).toLocaleString():'—'}/>
    </div>
    <div className="overview-two-column">
      <Card title="Market health & breadth"><div className="score-stack"><ScoreBar label="Breadth score" value={data?.breadth_score}/><ScoreBar label="Above EMA 20" value={b.pct_above_ema20}/><ScoreBar label="Above SMA 50" value={b.pct_above_sma50}/><ScoreBar label="Above SMA 200" value={b.pct_above_sma200}/></div><div className="mini-metrics"><span>Advancers <b>{b.advancers??0}</b></span><span>Decliners <b>{b.decliners??0}</b></span><span>A/D ratio <b>{fmt(b.advance_decline_ratio,2)}</b></span><span>20D highs/lows <b>{b.new_highs_20d??0}/{b.new_lows_20d??0}</b></span><span>Up/down volume <b>{fmt(b.up_down_volume_ratio,2)}</b></span><span>Regime <Badge value={b.breadth_regime}/></span></div></Card>
      <Card title="Trend, momentum & regime"><div className="score-stack"><ScoreBar label="Trend" value={data?.trend_score}/><ScoreBar label="Momentum" value={data?.momentum_score}/><ScoreBar label="Risk-on" value={data?.risk_on_score}/><ScoreBar label="Sentiment" value={data?.sentiment_score}/></div><div className="regime-grid"><span>Trend <Badge value={data?.trend_regime}/></span><span>Volatility <Badge value={data?.volatility_regime}/></span><span>Liquidity <Badge value={data?.liquidity_regime}/></span><span>Correlation <Badge value={data?.correlation_regime}/></span></div></Card>
    </div>
    <Card title="Institutional trend breadth"><div className="detail-list institutional-breadth-list"><span>Participation breadth <b>{fmt(ti.institutional_overview?.participation_breadth_pct)}%</b></span><span>Leadership breadth <b>{fmt(ti.institutional_overview?.leadership_breadth_pct)}%</b></span><span>Deterioration watch <b>{fmt(ti.institutional_overview?.deterioration_watch_pct)}%</b></span><span>Average participation <b>{fmt(ti.institutional_overview?.average_participation_score)}</b></span><span>Average leadership <b>{fmt(ti.institutional_overview?.average_leadership_score)}</b></span><span>Average trend quality <b>{fmt(ti.institutional_overview?.average_trend_quality_score)}</b></span></div></Card>
    <Card title="Trend Intelligence">
      <div className="trend-intelligence-header"><div><Badge value={ti.status||'NOT_AVAILABLE'}/><span>{ti.symbol_count??0} governed symbols</span><span>{ti.snapshot_timestamp?new Date(ti.snapshot_timestamp).toLocaleString():'No snapshot'}</span></div><div>{(ti.warnings||[]).map((warning:string)=><small key={warning}>{warning}</small>)}</div></div>
      <div className="trend-intelligence-metrics"><Metric label="Bullish" value={tib.bullish??0} detail={`${fmt(tib.bullish_pct)}% of coverage`}/><Metric label="Neutral" value={tib.neutral??0}/><Metric label="Bearish" value={tib.bearish??0} detail={`${fmt(tib.bearish_pct)}% of coverage`}/><Metric label="Transition watch" value={tib.transition_watch_count??0}/><Metric label="Operational status" value={<Badge value={tio.status||'NOT_AVAILABLE'}/>} detail={tio.score==null?'No score':`Score ${fmt(tio.score)}`}/></div>
      <div className="distribution-section"><div className="distribution-section-heading"><div><h4>Model distributions</h4><p>State counts and percentage of governed symbol coverage.</p></div></div><div className="distribution-groups"><DistributionGroup title="Base trend" values={tid.base_trend||{}}/><DistributionGroup title="Transition state" values={tid.transition||{}}/><DistributionGroup title="Forecast direction" values={tid.forecast||{}}/><DistributionGroup title="Institutional participation" values={tid.institutional_participation||{}}/></div></div>
      <div className="trend-watch-grid">
        <div><h4>Top strengthening</h4><div className="trend-symbol-list">{(ti.top_strengthening||[]).map((row:any)=><span key={row.symbol}><b>{row.symbol}</b><em>{String(row.state||'—').replaceAll('_',' ')}</em><strong>{fmt(row.score)}</strong></span>)}</div></div>
        <div><h4>Deterioration & reversal watch</h4><div className="trend-symbol-list">{(ti.top_deteriorating||[]).slice(0,4).map((row:any)=><span key={`d-${row.symbol}`}><b>{row.symbol}</b><em>Deterioration</em><strong>{fmt(row.score)}</strong></span>)}{(ti.top_reversal_risk||[]).slice(0,4).map((row:any)=><span key={`r-${row.symbol}`}><b>{row.symbol}</b><em>Reversal risk</em><strong>{fmt(row.score)}</strong></span>)}</div></div>
      </div>
    </Card>
    <Card title="Benchmark index context"><div className="overview-table-scroll"><Table rows={data?.index_context||[]} columns={[{key:'symbol',label:'Symbol'},{key:'asset_type',label:'Type',render:r=><Badge value={r.asset_type||'UNKNOWN'}/>},{key:'name',label:'Benchmark'},{key:'close',label:'Close',render:r=>money(r.close)},{key:'return_1d',label:'1D',render:r=><span className={Number(r.return_1d)>=0?'positive-value':'negative-value'}>{signed(r.return_1d)}</span>},{key:'return_5d',label:'5D',render:r=>signed(r.return_5d)},{key:'return_20d',label:'20D',render:r=>signed(r.return_20d)},{key:'above_20',label:'EMA20',render:r=><Badge value={r.above_20?'ABOVE':'BELOW'}/>},{key:'above_50',label:'SMA50',render:r=><Badge value={r.above_50?'ABOVE':'BELOW'}/>},{key:'above_200',label:'SMA200',render:r=><Badge value={r.above_200?'ABOVE':'BELOW'}/>},{key:'realized_vol_20d',label:'RV20',render:r=>`${fmt(r.realized_vol_20d)}%`},{key:'proxy_symbol',label:'ETF proxy',render:r=>r.proxy_symbol||'—'},{key:'proxy_return_spread_20d',label:'Index−ETF 20D',render:r=>r.proxy_return_spread_20d==null?'—':signed(r.proxy_return_spread_20d)}]}/></div><p className="overview-note">SPX, NDX, and RUT are cash indices. SPY, QQQ, and IWM remain ETF proxies. Cash-index volume is intentionally excluded from breadth and participation analytics.</p></Card>
    <Card title="Sector performance & rotation"><div className="sector-heatmap">{(data?.sectors||[]).map((s:any)=><article key={s.sector_etf} className={`sector-tile ${scoreTone(Number(s.momentum_score))}`}><div><b>{s.sector_etf}</b><span>{s.sector}</span></div><Badge value={s.rotation_label}/><strong className={Number(s.return_20d)>=0?'positive-value':'negative-value'}>{signed(s.return_20d)}</strong><small>5D {signed(s.return_5d)} · RS {signed(s.relative_strength)}</small><small>Momentum {fmt(s.momentum_score)} · Dealer {s.dealer_positioning_score==null?'—':fmt(s.dealer_positioning_score)}</small></article>)}</div></Card>
    <Card title="Dealer positioning & options structure"><div className="overview-table-scroll"><Table rows={data?.dealer_positioning||[]} columns={[{key:'symbol',label:'Symbol'},{key:'positioning_label',label:'Positioning',render:r=><Badge value={r.positioning_label}/>},{key:'gamma_regime',label:'Gamma',render:r=><Badge value={r.gamma_regime}/>},{key:'institutional_positioning_score',label:'Score',render:r=>fmt(r.institutional_positioning_score)},{key:'gamma_flip',label:'Gamma flip',render:r=>r.gamma_flip==null?'No flip detected':money(r.gamma_flip)},{key:'primary_call_wall',label:'Call wall',render:r=>money(r.primary_call_wall)},{key:'primary_put_wall',label:'Put wall',render:r=>money(r.primary_put_wall)},{key:'range_probability',label:'Range',render:r=>pct(r.range_probability)},{key:'breakout_probability',label:'Breakout',render:r=>pct(r.breakout_probability)},{key:'breakdown_probability',label:'Breakdown',render:r=>pct(r.breakdown_probability)},{key:'confidence_score',label:'Confidence',render:r=>pct(r.confidence_score)}]}/></div><p className="overview-note">Dealer positioning is explicitly model-derived from open interest and Greeks; it is not observed dealer inventory.</p></Card>
    <div className="overview-three-column">
      <Card title="Volatility & options environment"><div className="detail-list"><span>Average ATM IV <b>{fmt(vol.average_atm_iv)}%</b></span><span>Realized volatility <b>{fmt(vol.average_realized_volatility_20d)}%</b></span><span>Volatility risk premium <b>{fmt(vol.volatility_risk_premium)} pts</b></span><span>Long-premium attractiveness <b>{fmt(vol.long_premium_attractiveness)}</b></span><span>Short-premium attractiveness <b>{fmt(vol.short_premium_attractiveness)}</b></span><span>Regime <Badge value={vol.volatility_regime}/></span></div></Card>
      <Card title="Liquidity & participation"><div className="detail-list"><span>Evaluated symbols <b>{liq.evaluated_symbols??0}</b></span><span>Relative volume <b>{fmt(liq.relative_volume_composite,2)}</b></span><span>A/D ratio <b>{fmt(liq.advance_decline_ratio,2)}</b></span><span>Up/down volume <b>{fmt(liq.up_down_volume_ratio,2)}</b></span><span>Liquidity regime <Badge value={liq.liquidity_regime}/></span></div></Card>
      <Card title="Opportunity map"><div className="detail-list"><span>Best bullish sector <b>{opp.best_bullish_sector?.sector||'—'} ({opp.best_bullish_sector?.sector_etf||'—'})</b></span><span>Best bearish sector <b>{opp.best_bearish_sector?.sector||'—'} ({opp.best_bearish_sector?.sector_etf||'—'})</b></span><span>Strongest cash index <b>{opp.strongest_cash_index?.symbol||'—'} {opp.strongest_cash_index?`(${signed(opp.strongest_cash_index.return_20d)})`:''}</b></span><span>Weakest cash index <b>{opp.weakest_cash_index?.symbol||'—'} {opp.weakest_cash_index?`(${signed(opp.weakest_cash_index.return_20d)})`:''}</b></span><span>Breakout market <b>{opp.best_breakout_market?.symbol||'—'}</b></span><span>Range market <b>{opp.best_range_market?.symbol||'—'}</b></span><span>Strategy fit <b>{data?.preferred_strategy?.replaceAll('_',' ')||'—'}</b></span></div></Card>
    </div>
    <Card title="Cross-asset confirmation"><div className="overview-table-scroll"><Table rows={data?.cross_asset||[]} columns={[{key:'symbol',label:'Symbol'},{key:'name',label:'Asset'},{key:'return_1d',label:'1D',render:r=>signed(r.return_1d)},{key:'return_5d',label:'5D',render:r=>signed(r.return_5d)},{key:'return_20d',label:'20D',render:r=>signed(r.return_20d)},{key:'trend',label:'Trend',render:r=><Badge value={r.trend}/>} ]}/></div></Card>
    <Card title="Risk dashboard"><div className="risk-alert-grid">{(data?.risk_alerts||[]).length?(data.risk_alerts||[]).map((a:any,i:number)=><article key={`${a.title}-${i}`} className={`risk-alert ${String(a.severity).toLowerCase()}`}><Badge value={a.severity}/><h4>{a.title}</h4><p>{a.evidence}</p><small>{a.trading_implication}</small></article>):<p className="empty">No active market-level risk alerts.</p>}</div></Card>
    <Card title="Data freshness" compact><div className="grid metrics compact-metrics"><Metric label="Source" value={data?.data_freshness?.source||'PostgreSQL'}/><Metric label="Price history" value={data?.data_freshness?.price_history_as_of||'—'}/><Metric label="Cash indices" value={data?.data_freshness?.cash_indices_as_of||'—'}/><Metric label="Dealer snapshot" value={data?.data_freshness?.dealer_snapshot_as_of||'—'}/><Metric label="Generated" value={data?.data_freshness?.generated_at?new Date(data.data_freshness.generated_at).toLocaleString():'—'}/></div></Card>
  </section>
}


function TrendWatchColumn({title,rows,kind}:{title:string;rows:any[];kind:'strengthening'|'reversal'|'deteriorating'}){
  const marker=kind==='strengthening'?'▲':kind==='reversal'?'⚠':'▼';
  return <div className={`proposed-watch-column ${kind}`}><div className="proposed-watch-title"><span>{marker}</span><h4>{title}</h4></div><div className="trend-symbol-list">{rows.length?rows.map((row:any,index:number)=><span key={`${kind}-${row.symbol}-${index}`}><b>{row.symbol}</b><em>{String(row.state||title).replaceAll('_',' ')}</em><strong>{fmt(row.score)}</strong></span>):<p className="empty">No symbols available</p>}</div></div>
}

export function MarketOverviewPage(){
  const [data,setData]=useState<any>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState('');const [refreshing,setRefreshing]=useState(false);
  const headers=()=>{const h:Record<string,string>={'Accept':'application/json'};const key=sessionStorage.getItem('trading-ai-api-key');if(key){h['X-API-Key']=key;h['X-Actor']='workstation-user'}return h};
  const load=async()=>{setLoading(true);setError('');try{const r=await fetch('/api/v1/market-overview/latest',{headers:headers()});const p=await r.json();if(!r.ok)throw new Error(p.detail||r.statusText);setData(p.data)}catch(e:any){setError(e.message)}finally{setLoading(false)}};
  const refresh=async()=>{setRefreshing(true);setError('');try{const h=headers();h['Content-Type']='application/json';const r=await fetch('/api/v1/market-overview/refresh',{method:'POST',headers:h});const p=await r.json();if(!r.ok)throw new Error(p.detail||r.statusText);setData(p.data)}catch(e:any){setError(e.message)}finally{setRefreshing(false)}};
  useEffect(()=>{load()},[]);
  if(loading)return <State loading error={null} onRetry={load}>{null}</State>;if(error&&!data)return <State loading={false} error={new Error(error)} onRetry={load}>{null}</State>;
  const b=data?.breadth||{},vol=data?.volatility_options||{},liq=data?.liquidity_participation||{},opp=data?.opportunity_map||{};
  const ti=data?.trend_intelligence||{},tib=ti?.breadth||{},tid=ti?.distributions||{},tio=ti?.operations||{};
  const forecastBullish=numeric(tid?.forecast?.BULLISH)+numeric(tid?.forecast?.STRONGLY_BULLISH);
  const forecastTotal=Object.values(tid?.forecast||{}).reduce((sum:number,value:any)=>sum+numeric(value),0);
  const forecastBullishPct=forecastTotal?forecastBullish/forecastTotal*100:0;
  const participation=ti?.institutional_overview||{};
  return <section className="market-overview-page proposed-market-overview-page">
    <div className="page-title"><div><h2>Market overview</h2><p>Decision-first market posture, institutional participation, trend change, dealer positioning, risk, and opportunity context.</p></div><div className="overview-actions"><Badge value={data?.market_bias||'UNKNOWN'}/><button disabled={refreshing} onClick={refresh}>{refreshing?'Refreshing…':'Refresh analytics'}</button></div></div>
    {error&&<div className="scanner-error">{error}</div>}
    <div className="proposed-pulse-grid">
      <Metric label="Market posture" value={<Badge value={data?.market_bias}/>} detail={`Confidence ${fmt(data?.confidence_score)}%`}/>
      <Metric label="Market health" value={fmt(data?.market_health_score)} detail={data?.breadth_regime}/>
      <Metric label="Trend regime" value={<Badge value={data?.trend_regime}/>} detail={`Trend score ${fmt(data?.trend_score)}`}/>
      <Metric label="Risk state" value={<Badge value={data?.regime_transition_risk}/>} detail={`${(data?.risk_alerts||[]).length} active alerts`}/>
      <Metric label="Strategy fit" value={String(data?.preferred_strategy||'—').replaceAll('_',' ')} detail={data?.volatility_regime}/>
    </div>

    <div className="overview-two-column proposed-foundation-grid">
      <Card title="Market health"><div className="score-stack"><ScoreBar label="Market health" value={data?.market_health_score}/><ScoreBar label="Breadth" value={data?.breadth_score}/><ScoreBar label="Trend" value={data?.trend_score}/><ScoreBar label="Momentum" value={data?.momentum_score}/></div><div className="mini-metrics"><span>Advancers <b>{b.advancers??0}</b></span><span>Decliners <b>{b.decliners??0}</b></span><span>A/D ratio <b>{fmt(b.advance_decline_ratio,2)}</b></span><span>Up/down volume <b>{fmt(b.up_down_volume_ratio,2)}</b></span></div></Card>
      <Card title="Regime & participation"><div className="proposed-regime-matrix"><span>Trend <Badge value={data?.trend_regime}/></span><span>Volatility <Badge value={data?.volatility_regime}/></span><span>Breadth <Badge value={data?.breadth_regime}/></span><span>Liquidity <Badge value={data?.liquidity_regime}/></span><span>Correlation <Badge value={data?.correlation_regime}/></span><span>Transition risk <Badge value={data?.regime_transition_risk}/></span></div><p className="decision-caption">Current posture: <b>{String(data?.market_bias||'UNKNOWN').replaceAll('_',' ')}</b>. Preferred implementation: <b>{String(data?.preferred_strategy||'—').replaceAll('_',' ')}</b>.</p></Card>
    </div>

    <Card title="Institutional trend breadth"><div className="proposed-institutional-summary"><div><span>Participation breadth</span><strong>{fmt(participation.participation_breadth_pct)}%</strong><ScoreBar label="" value={participation.participation_breadth_pct}/></div><div><span>Leadership breadth</span><strong>{fmt(participation.leadership_breadth_pct)}%</strong><ScoreBar label="" value={participation.leadership_breadth_pct}/></div><div><span>Deterioration watch</span><strong>{fmt(participation.deterioration_watch_pct)}%</strong><ScoreBar label="" value={participation.deterioration_watch_pct}/></div><div><span>Average participation</span><strong>{fmt(participation.average_participation_score)}</strong><small>Leadership {fmt(participation.average_leadership_score)} · Quality {fmt(participation.average_trend_quality_score)}</small></div></div></Card>

    <div className="overview-three-column proposed-environment-grid">
      <Card title="Volatility environment"><div className="detail-list"><span>Average ATM IV <b>{fmt(vol.average_atm_iv)}%</b></span><span>Realized volatility <b>{fmt(vol.average_realized_volatility_20d)}%</b></span><span>Volatility risk premium <b>{fmt(vol.volatility_risk_premium)} pts</b></span><span>Regime <Badge value={vol.volatility_regime}/></span><span>Long premium <b>{fmt(vol.long_premium_attractiveness)}</b></span><span>Short premium <b>{fmt(vol.short_premium_attractiveness)}</b></span></div></Card>
      <Card title="Liquidity & participation"><div className="detail-list"><span>Evaluated symbols <b>{liq.evaluated_symbols??0}</b></span><span>Relative volume <b>{fmt(liq.relative_volume_composite,2)}</b></span><span>A/D ratio <b>{fmt(liq.advance_decline_ratio,2)}</b></span><span>Up/down volume <b>{fmt(liq.up_down_volume_ratio,2)}</b></span><span>Liquidity regime <Badge value={liq.liquidity_regime}/></span></div></Card>
      <Card title="Opportunity map"><div className="detail-list"><span>Best bullish sector <b>{opp.best_bullish_sector?.sector||'—'} ({opp.best_bullish_sector?.sector_etf||'—'})</b></span><span>Best bearish sector <b>{opp.best_bearish_sector?.sector||'—'} ({opp.best_bearish_sector?.sector_etf||'—'})</b></span><span>Strongest index <b>{opp.strongest_cash_index?.symbol||'—'}</b></span><span>Weakest index <b>{opp.weakest_cash_index?.symbol||'—'}</b></span><span>Breakout market <b>{opp.best_breakout_market?.symbol||'—'}</b></span><span>Range market <b>{opp.best_range_market?.symbol||'—'}</b></span></div></Card>
    </div>

    <Card title="Risk dashboard"><div className="risk-alert-grid">{(data?.risk_alerts||[]).length?(data.risk_alerts||[]).map((a:any,i:number)=><article key={`${a.title}-${i}`} className={`risk-alert ${String(a.severity).toLowerCase()}`}><Badge value={a.severity}/><h4>{a.title}</h4><p>{a.evidence}</p><small>{a.trading_implication}</small></article>):<p className="empty">No active market-level risk alerts.</p>}</div></Card>

    <Card title="Trend Intelligence">
      <div className="trend-intelligence-header"><div><Badge value={ti.status||'NOT_AVAILABLE'}/><span>{ti.symbol_count??0} governed symbols</span><span>{ti.snapshot_timestamp?new Date(ti.snapshot_timestamp).toLocaleString():'No snapshot'}</span></div><div>{(ti.warnings||[]).map((warning:string)=><small key={warning}>{warning}</small>)}</div></div>
      <div className="proposed-trend-summary"><Metric label="Bullish breadth" value={`${fmt(tib.bullish_pct)}%`} detail={`${tib.bullish??0} symbols`}/><Metric label="Transition watch" value={tib.transition_watch_count??0} detail="Change or reversal candidates"/><Metric label="Forecast bullish" value={`${fmt(forecastBullishPct)}%`} detail={`${forecastBullish} symbols`}/><Metric label="Operational status" value={<Badge value={tio.status||'NOT_AVAILABLE'}/>} detail={tio.score==null?'No score':`Score ${fmt(tio.score)}`}/></div>
      <div className="proposed-distribution-grid"><DistributionGroup title="Transition state" values={tid.transition||{}}/><DistributionGroup title="Forecast direction" values={tid.forecast||{}}/><DistributionGroup title="Institutional participation" values={tid.institutional_participation||{}}/></div>
    </Card>

    <Card title="Trend watch list"><div className="proposed-watchlist"><div className="proposed-section-heading"><div><p>Highest-priority strengthening, reversal-risk, and deterioration names.</p></div></div><div className="proposed-watch-grid"><TrendWatchColumn title="Strengthening" kind="strengthening" rows={(ti.top_strengthening||[]).slice(0,5)}/><TrendWatchColumn title="Reversal risk" kind="reversal" rows={(ti.top_reversal_risk||[]).slice(0,5)}/><TrendWatchColumn title="Deteriorating" kind="deteriorating" rows={(ti.top_deteriorating||[]).slice(0,5)}/></div></div></Card>

    <Card title="Sector rotation"><div className="sector-heatmap proposed-sector-grid">{(data?.sectors||[]).map((s:any)=><article key={s.sector_etf} className={`sector-tile ${scoreTone(Number(s.momentum_score))}`}><div><b>{s.sector_etf}</b><span>{s.sector}</span></div><Badge value={s.rotation_label}/><strong className={Number(s.return_20d)>=0?'positive-value':'negative-value'}>{signed(s.return_20d)}</strong><small>5D {signed(s.return_5d)} · RS {signed(s.relative_strength)}</small><small>Momentum {fmt(s.momentum_score)} · Trend {fmt(s.trend_score)}</small></article>)}</div></Card>

    <Card title="Dealer positioning & options structure"><div className="overview-table-scroll"><Table rows={data?.dealer_positioning||[]} columns={[{key:'symbol',label:'Symbol'},{key:'positioning_label',label:'Positioning',render:r=><Badge value={r.positioning_label}/>},{key:'gamma_regime',label:'Gamma',render:r=><Badge value={r.gamma_regime}/>},{key:'institutional_positioning_score',label:'Score',render:r=>fmt(r.institutional_positioning_score)},{key:'gamma_flip',label:'Gamma flip',render:r=>r.gamma_flip==null?'No flip detected':money(r.gamma_flip)},{key:'primary_call_wall',label:'Call wall',render:r=>money(r.primary_call_wall)},{key:'primary_put_wall',label:'Put wall',render:r=>money(r.primary_put_wall)},{key:'range_probability',label:'Range',render:r=>pct(r.range_probability)},{key:'breakout_probability',label:'Breakout',render:r=>pct(r.breakout_probability)},{key:'breakdown_probability',label:'Breakdown',render:r=>pct(r.breakdown_probability)},{key:'confidence_score',label:'Confidence',render:r=>pct(r.confidence_score)}]}/></div><p className="overview-note">Dealer positioning is explicitly model-derived from open interest and Greeks; it is not observed dealer inventory.</p></Card>

    <div className="overview-two-column proposed-confirmation-grid"><Card title="Cross-asset confirmation"><div className="overview-table-scroll"><Table rows={data?.cross_asset||[]} columns={[{key:'symbol',label:'Symbol'},{key:'name',label:'Asset'},{key:'return_5d',label:'5D',render:r=>signed(r.return_5d)},{key:'return_20d',label:'20D',render:r=>signed(r.return_20d)},{key:'trend',label:'Trend',render:r=><Badge value={r.trend}/>} ]}/></div></Card><Card title="Data freshness"><div className="detail-list"><span>Price history <b>{data?.data_freshness?.price_history_as_of||'—'}</b></span><span>Cash indices <b>{data?.data_freshness?.cash_indices_as_of||'—'}</b></span><span>Dealer snapshot <b>{data?.data_freshness?.dealer_snapshot_as_of||'—'}</b></span><span>Source <b>{data?.data_freshness?.source||'PostgreSQL'}</b></span><span>Generated <b>{data?.data_freshness?.generated_at?new Date(data.data_freshness.generated_at).toLocaleString():'—'}</b></span></div></Card></div>
  </section>
}
