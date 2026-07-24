import { useEffect, useState, type ReactNode } from 'react';
import { Activity, BriefcaseBusiness, ShieldCheck, Waypoints, ScanLine, LogOut, RadioTower, Search } from 'lucide-react';
import { platformApi } from './api';
import { useRemote } from './hooks';
import { asArray, firstNumber, money, pct } from './model';
import { Badge, Card, Freshness, JsonView, Metric, State, Table } from './components';

type ArtifactEnvelope = { data: any; metadata?: { stale?: boolean; age_seconds?: number | null } };
type Loader = (signal?: AbortSignal) => Promise<any>;

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
  ['scanner', 'Daily scanner', Search],
  ['portfolio', 'Portfolio', BriefcaseBusiness],
  ['risk', 'Risk', ShieldCheck],
  ['execution', 'Execution', Waypoints],
  ['positions', 'Positions', ScanLine],
  ['exits', 'Exits', LogOut],
  ['command', 'Command center', RadioTower],
] as const;

export function CommandCenter(){const [data,setData]=useState<any>(null);const [events,setEvents]=useState<any[]>([]);useEffect(()=>{fetch('/api/v1/realtime/snapshot',{headers:{'X-API-Key':sessionStorage.getItem('trading-ai-api-key')??''}}).then(r=>r.json()).then(setData);const key=sessionStorage.getItem('trading-ai-api-key')??'';const ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/realtime/stream?api_key=${encodeURIComponent(key)}`);ws.onmessage=e=>setEvents(v=>[JSON.parse(e.data),...v].slice(0,50));return()=>ws.close()},[]);return <section><h2>Operational Command Center</h2><div className="metrics"><article><b>{data?.connected_clients??0}</b><span>Live clients</span></article><article><b>{data?.open_alerts??0}</b><span>Open alerts</span></article><article><b>{data?.critical_alerts??0}</b><span>Critical alerts</span></article><article><b>{data?.events_published??0}</b><span>Events</span></article></div><div className="panel"><h3>Live event stream</h3><pre>{JSON.stringify(events,null,2)}</pre></div></section>}

export function DailyScannerPage(){
  const [runs,setRuns]=useState<any[]>([]);const [selected,setSelected]=useState<any>(null);const [results,setResults]=useState<any>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const [universe,setUniverse]=useState('liquid-us-700');const [universes,setUniverses]=useState<any[]>([]);const [symbols,setSymbols]=useState('');const [minimumScore,setMinimumScore]=useState(60);const [top,setTop]=useState(10);const [expirationMode,setExpirationMode]=useState<'automatic'|'short'|'swing'|'medium'|'long'|'custom'|'fixed'>('automatic');const [minimumDte,setMinimumDte]=useState(14);const [maximumDte,setMaximumDte]=useState(90);const [maxPerExpiry,setMaxPerExpiry]=useState(3);const [refreshMode,setRefreshMode]=useState<'cache_only'|'refresh_missing'|'force_full'>('refresh_missing');const [ingestionScope,setIngestionScope]=useState<'underlying'|'options'|'all'>('all');const [autoRefresh,setAutoRefresh]=useState(true);const [minimumCoverage,setMinimumCoverage]=useState(98);const [maximumFailedSymbols,setMaximumFailedSymbols]=useState(10);const [continueOnDegraded,setContinueOnDegraded]=useState(true);
  const selectedSymbols=()=>symbols.split(',').map(x=>x.trim().toUpperCase()).filter(Boolean);
  const dates=()=>{const today=new Date().toISOString().slice(0,10);const start=new Date(Date.now()-365*86400000).toISOString().slice(0,10);return {today,start}};
  const load=async()=>{try{const response=await import('./api').then(m=>m.scannerApi.runs());setRuns(response.data);const current=response.data.find((r:any)=>r.kind==='DAILY_SCAN');if(current){setSelected(current);if(current.status==='SUCCEEDED'){const value=await import('./api').then(m=>m.scannerApi.results(current.run_id));setResults(value.data)}}}catch(e:any){setError(e.message)}};
  useEffect(()=>{import('./api').then(m=>m.scannerApi.universes()).then(r=>{setUniverses(r.data);if(r.data.length&&!r.data.some((u:any)=>u.id===universe))setUniverse(r.data[0].id)}).catch((e:any)=>setError(e.message));load();const timer=setInterval(load,3000);return()=>clearInterval(timer)},[]);
  const ingest=async()=>{setBusy(true);setError('');try{const {today,start}=dates();await import('./api').then(m=>m.scannerApi.refresh({data_scope:ingestionScope,universe,symbols:selectedSymbols(),start,end:today,refresh_mode:refreshMode,minimum_bars:20,stale_after_days:1,minimum_coverage_pct:minimumCoverage,maximum_failed_symbols:maximumFailedSymbols,continue_on_degraded_refresh:continueOnDegraded,max_retries:3,retry_backoff_seconds:2,maximum_retry_backoff_seconds:60,retry_jitter_ratio:.20,rate_limit_cooldown_seconds:15,circuit_breaker_threshold:3,circuit_breaker_cooldown_seconds:30,batch_size:100}));await load()}catch(e:any){setError(e.message)}finally{setBusy(false)}};
  const scan=async()=>{setBusy(true);setError('');try{const {today,start}=dates();const response=await import('./api').then(m=>m.scannerApi.scan({universe,symbols:selectedSymbols(),start,end:today,minimum_score:minimumScore,top,pricing_dte:30,expiration_mode:expirationMode,minimum_dte:minimumDte,maximum_dte:maximumDte,maximum_expirations_per_symbol:4,maximum_trades_per_expiration:maxPerExpiry,option_data_mode:'live',liquidity_data_mode:'adaptive',maximum_option_spread_pct:.25,minimum_option_open_interest:100,minimum_option_volume:10,capital:100000,risk_per_trade_pct:.02,max_position_pct:.05,take_profit_pct:.30,stop_loss_pct:.15,refresh_mode:refreshMode,auto_refresh:autoRefresh,minimum_refresh_coverage_pct:minimumCoverage,maximum_failed_refresh_symbols:maximumFailedSymbols,continue_on_degraded_refresh:continueOnDegraded,refresh_max_retries:3,refresh_retry_backoff_seconds:2,refresh_maximum_retry_backoff_seconds:60,refresh_retry_jitter_ratio:.20,refresh_rate_limit_cooldown_seconds:15,refresh_circuit_breaker_threshold:3,refresh_circuit_breaker_cooldown_seconds:30}));setSelected(response.data);await load()}catch(e:any){setError(e.message)}finally{setBusy(false)}};
  const candidates=results?.recommendations?.candidates||[];const trades=results?.trades?.trades||[];const latestIngestion=runs.find((r:any)=>r.kind==='DATA_REFRESH');
  const modeHelp=refreshMode==='cache_only'?'Use persisted data only. No Yahoo or Polygon calls are allowed.':refreshMode==='refresh_missing'?'Refresh only missing or stale persisted data before analysis.':'Rebuild the selected persisted dataset from providers.';
  return <section>
    <div className="page-title"><div><h2>Daily scanner</h2><p>Ingest governed market data, then analyze only persisted PostgreSQL/cache data.</p></div><Badge value={selected?.status||'IDLE'}/></div>
    {error&&<div className="scanner-error">{error}</div>}
    <Card title="Data architecture" compact><div className="grid metrics compact-metrics"><Metric label="Underlying OHLCV" value="Yahoo → PostgreSQL"/><Metric label="Options data" value="Polygon → PostgreSQL"/><Metric label="Scanner access" value="Database / cache only"/><Metric label="Direct provider calls during scan" value="Disabled"/></div></Card>
    <Card title="Market ingestion"><div className="scanner-form"><label>Ingestion scope<select value={ingestionScope} onChange={e=>setIngestionScope(e.target.value as any)}><option value="all">Full ingestion — Yahoo OHLCV + Polygon options</option><option value="underlying">Underlying only — Yahoo OHLCV</option><option value="options">Options only — Polygon</option></select></label><label>Ingestion mode<select value={refreshMode} onChange={e=>setRefreshMode(e.target.value as any)}><option value="cache_only">Validate persisted data only</option><option value="refresh_missing">Refresh missing / stale</option><option value="force_full">Force full rebuild</option></select><small>{modeHelp}</small></label><label>Minimum OHLCV coverage %<input type="number" min="0" max="100" step="0.1" value={minimumCoverage} onChange={e=>setMinimumCoverage(Number(e.target.value))}/></label><label>Maximum failed symbols<input type="number" min="0" max="1000" value={maximumFailedSymbols} onChange={e=>setMaximumFailedSymbols(Number(e.target.value))}/></label><label className="check"><input type="checkbox" checked={continueOnDegraded} onChange={e=>setContinueOnDegraded(e.target.checked)}/>Continue when degraded thresholds pass</label><div className="scanner-actions"><button disabled={busy} onClick={ingest}>Run market ingestion</button></div></div><div className="grid metrics"><Metric label="Last ingestion" value={latestIngestion?new Date(latestIngestion.created_at).toLocaleString():'—'}/><Metric label="Ingestion scope" value={latestIngestion?.request?.data_scope||'—'}/><Metric label="Ingestion status" value={<Badge value={latestIngestion?.status||'UNKNOWN'}/>}/><Metric label="Coverage" value={latestIngestion?.summary?.coverage||'—'}/></div></Card>
    <Card title="Scan controls"><div className="scanner-form"><label>Universe<select value={universe} onChange={e=>setUniverse(e.target.value)}>{universes.length?universes.map((u:any)=><option key={u.id} value={u.id}>{u.label} — {u.symbol_count}</option>):<option value="liquid-us-700">Highly Liquid U.S. Equities & ETFs</option>}</select><small>{universes.find((u:any)=>u.id===universe)?.description||'Loaded from the governed backend registry.'}</small></label><label>Custom symbols<input value={symbols} onChange={e=>setSymbols(e.target.value)} placeholder="AAPL,MSFT,SPY"/></label><label>Minimum score<input type="number" value={minimumScore} onChange={e=>setMinimumScore(Number(e.target.value))}/></label><label>Top trades<input type="number" value={top} onChange={e=>setTop(Number(e.target.value))}/></label><label>Expiration selection<select value={expirationMode} onChange={e=>setExpirationMode(e.target.value as any)}><option value="automatic">Automatic — all eligible horizons</option><option value="short">Short — 7 to 21 DTE</option><option value="swing">Swing — 22 to 45 DTE</option><option value="medium">Medium — 46 to 75 DTE</option><option value="long">Long — 76 to 120 DTE</option><option value="custom">Custom DTE range</option><option value="fixed">Fixed — legacy 30 DTE</option></select></label><label>Minimum DTE<input type="number" min="1" max="730" value={minimumDte} onChange={e=>setMinimumDte(Number(e.target.value))}/></label><label>Maximum DTE<input type="number" min="1" max="730" value={maximumDte} onChange={e=>setMaximumDte(Number(e.target.value))}/></label><label>Max trades per expiry<input type="number" min="0" max="100" value={maxPerExpiry} onChange={e=>setMaxPerExpiry(Number(e.target.value))}/><small>Use 0 to disable expiry diversification.</small></label><label className="check"><input type="checkbox" checked={autoRefresh} onChange={e=>setAutoRefresh(e.target.checked)}/>Run governed ingestion before scanning</label><div className="scanner-actions"><button className="primary" disabled={busy} onClick={scan}>Run database-only daily scan</button></div></div></Card>
    <div className="grid metrics"><Metric label="Symbols scanned" value={selected?.summary?.symbols_scanned||0}/><Metric label="Candidates" value={candidates.length||selected?.summary?.candidate_count||0}/><Metric label="Best trades" value={trades.length||selected?.summary?.trade_count||0}/><Metric label="Top score" value={selected?.summary?.top_score?Number(selected.summary.top_score).toFixed(2):'—'}/></div>
    <Card title="Provider health and lineage" compact><div className="grid metrics compact-metrics"><Metric label="OHLCV provider" value="Yahoo"/><Metric label="Options provider" value="Polygon"/><Metric label="Scan source" value="Persisted data"/><Metric label="Provider status" value={<Badge value={selected?.summary?.provider_status||'UNKNOWN'}/>}/><Metric label="Rate limits" value={selected?.summary?.provider_rate_limits||0}/><Metric label="Retries" value={selected?.summary?.provider_retries||0}/></div></Card>
    <Card title="Run history" compact><div className="run-history-scroll"><Table rows={runs} columns={[{key:'created_at',label:'Created',render:r=>new Date(r.created_at).toLocaleString()},{key:'kind',label:'Workflow'},{key:'status',label:'Status',render:r=><Badge value={r.status}/>},{key:'scope',label:'Scope',render:r=>r.request?.data_scope??(r.kind==='DAILY_SCAN'?'scan':'—')},{key:'refresh_mode',label:'Ingestion mode',render:r=>r.request?.refresh_mode==='refresh_missing'?'Refresh missing / stale':r.request?.refresh_mode==='force_full'?'Force full rebuild':r.request?.refresh_mode==='cache_only'?'Persisted data only':'—'},{key:'candidate_count',label:'Candidates',render:r=>r.summary?.candidate_count??'—'},{key:'coverage',label:'Coverage',render:r=>r.summary?.coverage??'—'},{key:'excluded_symbols',label:'Excluded',render:r=>r.summary?.excluded_symbols&&r.summary.excluded_symbols!=='NONE'?r.summary.excluded_symbols:'—'},{key:'trade_count',label:'Trades',render:r=>r.summary?.trade_count??'—'}]}/></div></Card>
    <Card title="Best trade candidates"><Table rows={trades} columns={[{key:'symbol',label:'Symbol'},{key:'signal',label:'Signal',render:r=><Badge value={r.signal}/>},{key:'strategy',label:'Strategy'},{key:'ai_score',label:'AI score',render:r=>Number(r.ai_score||0).toFixed(2)},{key:'contract_ticker',label:'Contract',render:r=>r.contract_ticker||r.option_symbol||r.contract_symbol||'—'},{key:'expiry',label:'Expiry'},{key:'dte',label:'DTE'},{key:'strike',label:'Strike',render:r=>money(r.strike)},{key:'option_entry',label:'Entry',render:r=>money(r.option_entry)},{key:'target_price',label:'Target',render:r=>money(r.target_price)},{key:'stop_price',label:'Stop',render:r=>money(r.stop_price)},{key:'reward_risk_ratio',label:'R/R',render:r=>Number(r.reward_risk_ratio||0).toFixed(2)}]}/></Card>
    {selected&&(selected.stdout||selected.stderr)&&<Card title="Execution log"><pre className="run-log">{selected.stdout}{selected.stderr&&`\n${selected.stderr}`}</pre></Card>}
  </section>
}

