import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, ChevronRight, CircleDollarSign, Gauge, Layers3, RefreshCw, ShieldAlert, Target, TrendingDown, TrendingUp, WalletCards } from 'lucide-react';
import { brokerPortfolioApi, dynamicPositionManagementApi, portfolioIntelligenceApi, portfolioRiskAllocationApi } from './api';
import type { DynamicExitInstruction, ManagedPosition, PortfolioIntelligenceSnapshot } from './types';
import './portfolio-intelligence-refined.css';

const money = (value: number | null | undefined) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Number(value || 0));
const pct = (value: number | null | undefined, digits = 1) => `${Number(value || 0).toFixed(digits)}%`;
const number = (value: number | null | undefined, digits = 2) => Number(value || 0).toFixed(digits);
const tone = (value: number, high = 75, medium = 50) => value >= high ? 'positive' : value >= medium ? 'warning' : 'critical';
const signed = (value: number) => `${value > 0 ? '+' : ''}${number(value)}`;
const exposureEntries = (source?: Record<string, number>) => Object.entries(source || {}).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

function ScoreRing({ value, label }: { value: number; label: string }) {
  const score = Math.max(0, Math.min(100, Number(value || 0)));
  return <div className={`pi-score-ring ${tone(score)}`} style={{ '--score': `${score * 3.6}deg` } as React.CSSProperties}><div><strong>{Math.round(score)}</strong><span>{label}</span></div></div>;
}

function ExposureBars({ title, values }: { title: string; values?: Record<string, number> }) {
  const entries = exposureEntries(values);
  const max = Math.max(1, ...entries.map(([, value]) => Math.abs(value)));
  return <section className="pi-card pi-exposure"><header><h3>{title}</h3><span>{entries.length} groups</span></header>{entries.length ? entries.slice(0, 8).map(([name, value]) => <div className="pi-bar-row" key={name}><div><span>{name}</span><b>{money(value)}</b></div><div className="pi-bar-track"><i style={{ width: `${Math.max(3, Math.abs(value) / max * 100)}%` }} /></div></div>) : <p className="pi-empty">No exposure data in the latest snapshot.</p>}</section>;
}

function MiniGreeks({ snapshot, risk }: { snapshot: PortfolioIntelligenceSnapshot | null; risk?: any }) {
  const greeks = risk?.payload_json?.greeks || snapshot?.greeks || {};
  return <section className="pi-card"><header><h3>Aggregate Greeks</h3><Activity size={17} /></header><div className="pi-greeks">{['delta', 'gamma', 'theta', 'vega'].map(key => <div key={key}><span>{key}</span><strong>{signed(Number(greeks[key] || 0))}</strong></div>)}</div></section>;
}

export function PortfolioIntelligenceRefinedPage() {
  const portfolioId = 'PAPER-PRIMARY';
  const [positions, setPositions] = useState<ManagedPosition[]>([]);
  const [snapshot, setSnapshot] = useState<PortfolioIntelligenceSnapshot | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [query, setQuery] = useState('');
  const [stateFilter, setStateFilter] = useState('ACTIVE');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [instructions, setInstructions] = useState<DynamicExitInstruction[]>([]);
  const [brokerPublication, setBrokerPublication] = useState<any>(null);
  const [brokerPositions, setBrokerPositions] = useState<any[]>([]);
  const [riskAllocation, setRiskAllocation] = useState<any>(null);
  const [optimization, setOptimization] = useState<any>(null);
  const [portfolioActions, setPortfolioActions] = useState<any[]>([]);

  const load = async () => {
    setError('');
    const [positionsResponse, snapshotResponse, brokerPublicationResponse, brokerPositionsResponse, riskAllocationResponse, optimizationResponse, actionResponse] = await Promise.all([
      portfolioIntelligenceApi.positions(portfolioId),
      portfolioIntelligenceApi.snapshot(portfolioId),
      brokerPortfolioApi.publication(portfolioId).catch(() => ({data:null} as any)),
      brokerPortfolioApi.positions(portfolioId).catch(() => ({data:[]} as any)),
      portfolioRiskAllocationApi.current(portfolioId).catch(() => ({data:null} as any)),
      portfolioRiskAllocationApi.optimizerCurrent(portfolioId).catch(() => ({data:null} as any)),
      portfolioRiskAllocationApi.recommendations(portfolioId).catch(() => ({data:[]} as any)),
    ]);
    setPositions(positionsResponse.data || []);
    setSnapshot(snapshotResponse.data || null);
    setBrokerPublication(brokerPublicationResponse.data || null);
    setBrokerPositions(brokerPositionsResponse.data || []);
    setRiskAllocation(riskAllocationResponse.data || null);
    setOptimization(optimizationResponse.data || null);
    setPortfolioActions(actionResponse.data || []);
    setSelectedId(current => current || positionsResponse.data?.[0]?.position_id || '');
    setLastUpdated(new Date());
  };

  useEffect(() => { load().catch(reason => setError(reason instanceof Error ? reason.message : String(reason))); }, []);

  const filtered = useMemo(() => positions.filter(position => {
    const matchesQuery = !query || `${position.symbol} ${position.strategy} ${position.direction} ${position.state}`.toLowerCase().includes(query.toLowerCase());
    const matchesState = stateFilter === 'ALL' || (stateFilter === 'ACTIVE' ? !['CLOSED', 'CANCELLED'].includes(position.state) : position.state === stateFilter);
    return matchesQuery && matchesState;
  }).sort((a, b) => b.health.score - a.health.score), [positions, query, stateFilter]);

  const selected = positions.find(position => position.position_id === selectedId) || filtered[0];
  useEffect(() => { if (selected?.position_id) dynamicPositionManagementApi.instructions(selected.position_id).then(response => setInstructions(response.data || [])).catch(() => setInstructions([])); else setInstructions([]); }, [selected?.position_id, selected?.version]);
  const alerts = positions.flatMap(position => position.health.alerts.map(alert => ({ position, alert })));
  const decisions = positions.filter(position => !['CLOSED', 'CANCELLED'].includes(position.state)).sort((a, b) => {
    const priority = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 } as Record<string, number>;
    return (priority[b.decision.priority] || 0) - (priority[a.decision.priority] || 0);
  });
  const activePositions = positions.filter(position => !['CLOSED', 'CANCELLED'].includes(position.state));
  const winners = activePositions.filter(position => position.mark.unrealized_pnl > 0).length;
  const deteriorating = activePositions.filter(position => position.health.direction.toUpperCase().includes('DETERIOR')).length;

  const synchronizeBroker = async () => {
    setBusy(true); setError('');
    try { await brokerPortfolioApi.synchronize(portfolioId); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };

  const generateSnapshot = async () => {
    setBusy(true); setError('');
    try { await portfolioIntelligenceApi.generateSnapshot(portfolioId, snapshot?.cash || 0, snapshot?.buying_power || 0); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };


  const runPortfolioIntelligence = async () => {
    setBusy(true); setError('');
    try { await portfolioRiskAllocationApi.continuousRun(portfolioId); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };

  const applyAction = async (action: string) => {
    if (!selected) return;
    const reason = window.prompt(`Reason for ${action.replaceAll('_', ' ')} action:`);
    if (!reason?.trim()) return;
    setBusy(true); setError('');
    try { await portfolioIntelligenceApi.action(selected.position_id, selected.version, action, reason.trim()); await load(); }
    catch (reasonValue) { setError(reasonValue instanceof Error ? reasonValue.message : String(reasonValue)); }
    finally { setBusy(false); }
  };

  const setAutomationMode = async (mode: string) => {
    if (!selected) return;
    setBusy(true); setError('');
    try { await dynamicPositionManagementApi.setMode(selected.position_id, mode, `Set ${mode} management from Portfolio Command Center`); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };

  const evaluateManagement = async () => {
    if (!selected) return;
    setBusy(true); setError('');
    try { await dynamicPositionManagementApi.evaluate(selected.position_id, true); await load(); const response = await dynamicPositionManagementApi.instructions(selected.position_id); setInstructions(response.data || []); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };

  return <section className="pi-workspace">
    <header className="pi-command-header"><div><p className="pi-eyebrow">Portfolio Intelligence · Paper governed</p><h2>Portfolio Command Center</h2><p>Position health, portfolio risk, exposure, explainable decisions, and governed lifecycle actions.</p></div><div className="pi-header-actions"><span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Not refreshed'}</span><button onClick={() => load().catch(reason => setError(String(reason)))} disabled={busy}><RefreshCw size={16} />Refresh</button><button onClick={synchronizeBroker} disabled={busy}><Activity size={16} />Sync IBKR</button><button onClick={runPortfolioIntelligence} disabled={busy}><Target size={16} />Optimize portfolio</button><button className="primary" onClick={generateSnapshot} disabled={busy}><Layers3 size={16} />Generate snapshot</button></div></header>

    {error && <div className="pi-error"><AlertTriangle size={18} /><div><strong>Portfolio data could not be loaded</strong><span>{error}</span></div></div>}

    <div className="pi-kpis">
      <article><WalletCards /><div><span>Net liquidation</span><strong>{money(snapshot?.net_liquidation)}</strong><small>{money(snapshot?.cash)} cash</small></div></article>
      <article><CircleDollarSign /><div><span>Unrealized P&amp;L</span><strong className={(snapshot?.unrealized_pnl || 0) >= 0 ? 'gain' : 'loss'}>{money(snapshot?.unrealized_pnl)}</strong><small>{money(snapshot?.realized_pnl)} realized</small></div></article>
      <article><Gauge /><div><span>Portfolio health</span><strong>{Math.round(snapshot?.health_score || 0)}</strong><small>{deteriorating} deteriorating</small></div></article>
      <article><Target /><div><span>Active positions</span><strong>{activePositions.length}</strong><small>{winners} currently profitable</small></div></article>
      <article><ShieldAlert /><div><span>Open risk</span><strong>{money(snapshot?.open_risk)}</strong><small>{money(snapshot?.buying_power)} buying power</small></div></article>
      <article><Activity /><div><span>IBKR positions</span><strong>{brokerPositions.length}</strong><small>{brokerPublication?.status || 'Awaiting sync'} · {brokerPublication?.payload_json?.broker_discovered_count ?? brokerPublication?.broker_discovered_count ?? 0} discovered</small></div></article>
      <article><ShieldAlert /><div><span>Portfolio heat</span><strong>{pct(riskAllocation?.portfolio_heat_pct || 0)}</strong><small>{money(riskAllocation?.var_95 || 0)} one-day VaR</small></div></article>
    </div>

    <div className="pi-layout">
      <aside className="pi-left pi-card">
        <header><div><h3>Managed Positions</h3><span>{filtered.length} shown</span></div></header>
        <div className="pi-controls"><input aria-label="Search positions" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search symbol or strategy" /><select aria-label="Position state" value={stateFilter} onChange={event => setStateFilter(event.target.value)}><option value="ACTIVE">Active</option><option value="ALL">All</option><option value="OPEN">Open</option><option value="PARTIAL">Partial</option><option value="HEDGED">Hedged</option><option value="ROLLED">Rolled</option><option value="CLOSED">Closed</option></select></div>
        <div className="pi-position-list">{filtered.map(position => <button key={position.position_id} className={selected?.position_id === position.position_id ? 'selected' : ''} onClick={() => setSelectedId(position.position_id)}><div className="pi-position-row"><strong>{position.symbol}</strong><span className={`pi-state ${position.state.toLowerCase()}`}>{position.state}</span></div><p>{position.strategy} · {position.direction}</p><div className="pi-position-stats"><span className={position.mark.unrealized_pnl >= 0 ? 'gain' : 'loss'}>{money(position.mark.unrealized_pnl)}</span><span>Health {Math.round(position.health.score)}</span><ChevronRight size={15} /></div></button>)}{!filtered.length && <p className="pi-empty">No managed positions match the current filters.</p>}</div>
      </aside>

      <main className="pi-center">
        {selected ? <>
          <section className="pi-card pi-position-hero"><div><p className="pi-eyebrow">{selected.position_id}</p><h3>{selected.symbol} · {selected.strategy}</h3><p>{selected.direction} · Opened {new Date(selected.opened_at).toLocaleDateString()} · Version {selected.version}</p></div><div className="pi-health-cluster"><ScoreRing value={selected.health.score} label="Health" /><ScoreRing value={selected.decision.confidence * 100} label="Decision" /></div></section>
          <section className="pi-position-metrics"><article><span>Market value</span><strong>{money(selected.mark.market_value)}</strong></article><article><span>Unrealized P&amp;L</span><strong className={selected.mark.unrealized_pnl >= 0 ? 'gain' : 'loss'}>{money(selected.mark.unrealized_pnl)}</strong></article><article><span>Return</span><strong className={selected.mark.unrealized_return_pct >= 0 ? 'gain' : 'loss'}>{pct(selected.mark.unrealized_return_pct)}</strong></article><article><span>Days to expiry</span><strong>{selected.mark.days_to_expiry ?? '—'}</strong></article></section>
          <section className="pi-card pi-decision"><header><div><h3>Decision Intelligence</h3><span className={`pi-priority ${selected.decision.priority.toLowerCase()}`}>{selected.decision.priority}</span></div><b>{selected.decision.action.replaceAll('_', ' ')}</b></header><p>{selected.decision.reason}</p><div className="pi-decision-grid"><div><span>Expected benefit</span><strong>{selected.decision.expected_benefit}</strong></div><div><span>Risk impact</span><strong>{selected.decision.risk_impact}</strong></div><div><span>Confidence</span><strong>{pct(selected.decision.confidence * 100, 0)}</strong></div></div>{selected.decision.alternatives?.length > 0 && <div className="pi-alternatives"><span>Alternatives</span>{selected.decision.alternatives.map(item => <i key={item}>{item.replaceAll('_', ' ')}</i>)}</div>}</section>
          <section className="pi-card"><header><div><h3>Broker Reconciliation</h3><span>{selected.metadata?.reconciliation_status || 'AWAITING SYNC'}</span></div></header><div className="pi-decision-grid"><div><span>Position origin</span><strong>{String(selected.metadata?.provenance || 'PLATFORM').replaceAll('_',' ')}</strong></div><div><span>IBKR contract</span><strong>{selected.metadata?.local_symbol || selected.metadata?.broker_contract_id || '—'}</strong></div><div><span>Broker account</span><strong>{selected.metadata?.broker_account_id ? 'Connected paper account' : 'Not linked'}</strong></div></div></section>
          <section className="pi-card"><header><div><h3>Dynamic Management Control</h3><span>{selected.metadata?.automation_mode || 'ADVISORY'}</span></div><button onClick={evaluateManagement} disabled={busy}>Evaluate now</button></header><div className="pi-decision-grid"><div><span>Current structural stop</span><strong>{selected.metadata?.dynamic_management?.current_underlying_stop ?? selected.metadata?.dynamic_management?.underlying_stop ?? '—'}</strong></div><div><span>Trailing policy</span><strong>{String(selected.metadata?.dynamic_management?.trailing_policy || '—').replaceAll('_',' ')}</strong></div><div><span>Next management status</span><strong>{selected.metadata?.last_management_status || 'Awaiting evaluation'}</strong></div></div><div className="pi-alternatives"><span>Automation mode</span>{['ADVISORY','SEMI_AUTOMATIC','FULLY_AUTOMATIC'].map(mode => <button key={mode} disabled={busy || selected.metadata?.automation_mode===mode} onClick={() => setAutomationMode(mode)}>{mode.replaceAll('_',' ')}</button>)}</div><div className="pi-driver-grid">{instructions.length ? instructions.map(item => <article key={item.instruction_id}><div><strong>{String(item.payload?.label || item.action).replaceAll('_',' ')}</strong><span>{item.status}</span></div><p>{item.payload?.trigger_type}: {String(item.payload?.trigger_value ?? 'rule based')} · Qty {item.quantity}</p>{item.status==='PENDING_APPROVAL' && <button onClick={async()=>{const reason=window.prompt('Approval reason:');if(reason){await dynamicPositionManagementApi.approve(item.instruction_id,reason,true);await evaluateManagement();}}}>Approve & submit</button>}</article>) : <p className="pi-empty">No governed exit instructions have been armed yet.</p>}</div></section>
          <section className="pi-card"><header><h3>Position Health Drivers</h3><span>{selected.health.direction}</span></header><div className="pi-driver-grid">{selected.health.drivers.map(driver => <article key={driver.category}><div><strong>{driver.category}</strong><span>{Math.round(driver.score)}</span></div><div className="pi-driver-track"><i style={{ width: `${Math.max(2, Math.min(100, driver.score))}%` }} /></div><p>{driver.reason}</p></article>)}</div></section>
          <section className="pi-card"><header><h3>Position Greeks</h3><BarChart3 size={17} /></header><div className="pi-greeks position">{[['Delta', selected.mark.delta], ['Gamma', selected.mark.gamma], ['Theta', selected.mark.theta], ['Vega', selected.mark.vega]].map(([label, value]) => <div key={String(label)}><span>{label}</span><strong>{signed(Number(value))}</strong></div>)}</div></section>
          <section className="pi-action-bar"><span>Governed position actions require a reason and expected version.</span>{['HOLD', 'SCALE_OUT', 'ROLL', 'HEDGE', 'CLOSE'].map(action => <button key={action} disabled={busy || ['CLOSED', 'CANCELLED'].includes(selected.state)} onClick={() => applyAction(action)}>{action.replaceAll('_', ' ')}</button>)}</section>
        </> : <section className="pi-card pi-empty-state"><Target size={32} /><h3>No managed position selected</h3><p>Create a managed position from a PAPER_READY trade plan or choose a position from the queue.</p></section>}
      </main>

      <aside className="pi-right">
        <section className="pi-card"><header><h3>Portfolio Risk & Allocation</h3><span>{riskAllocation?.status || 'AWAITING BUILD'}</span></header><div className="pi-decision-grid"><div><span>Risk health</span><strong>{Math.round(riskAllocation?.health_score || 0)}</strong></div><div><span>Diversification</span><strong>{number(riskAllocation?.diversification_score || 0, 1)}</strong></div><div><span>Expected shortfall</span><strong>{money(riskAllocation?.expected_shortfall_95 || 0)}</strong></div><div><span>Option quote coverage</span><strong>{pct(riskAllocation?.payload_json?.data_quality?.exact_option_quote_coverage_pct || 0)}</strong></div><div><span>Beta-weighted delta</span><strong>{signed(Number(riskAllocation?.payload_json?.greeks?.beta_weighted_delta || 0))}</strong></div><div><span>Risk methodology</span><strong>{String(riskAllocation?.payload_json?.risk?.methodology || '—').replaceAll('_',' ')}</strong></div></div>{riskAllocation?.payload_json?.data_quality?.warnings?.length > 0 && <p className="pi-empty">{riskAllocation.payload_json.data_quality.warnings.length} position enrichment warning(s) require review.</p>}<button onClick={async()=>{setBusy(true);try{await portfolioRiskAllocationApi.build(portfolioId);await load();}finally{setBusy(false)}}} disabled={busy}>Rebuild portfolio risk</button></section>

        <section className="pi-card"><header><h3>Portfolio Optimizer</h3><span>{optimization?.status || 'AWAITING BUILD'}</span></header><div className="pi-decision-grid"><div><span>Objective score</span><strong>{number(optimization?.objective?.score || optimization?.objective_score || 0,1)}</strong></div><div><span>Selected trades</span><strong>{optimization?.selected_candidates?.length || 0}</strong></div><div><span>Recommended capital</span><strong>{money(optimization?.target_portfolio?.recommended_new_capital || optimization?.recommended_capital || 0)}</strong></div><div><span>Risk budget</span><strong>{String(optimization?.risk_budgets?.status || '—').replaceAll('_',' ')}</strong></div><div><span>Hedge ideas</span><strong>{optimization?.hedge_recommendations?.length || 0}</strong></div><div><span>Portfolio actions</span><strong>{portfolioActions.length}</strong></div></div><div className="pi-queue">{(optimization?.best_next_trades || []).slice(0,5).map((item:any)=><button key={item.opportunity_id}><div><strong>{item.symbol}</strong><span>{item.strategy} · Qty {item.recommended_quantity}</span></div><b>{number(item.final_portfolio_score,1)}</b></button>)}</div>{!(optimization?.best_next_trades || []).length && <p className="pi-empty">Run portfolio optimization to rank the best combination of new trades.</p>}<button onClick={runPortfolioIntelligence} disabled={busy}>Run cumulative portfolio intelligence</button></section>
        <section className="pi-card"><header><h3>Recommended Portfolio Actions</h3><span>{portfolioActions.length}</span></header><div className="pi-alerts">{portfolioActions.length ? portfolioActions.slice(0,8).map((item:any)=><div key={item.recommendation_id}><AlertTriangle size={15}/><div><strong>{item.symbol || item.action_type}</strong><span>{String(item.payload_json?.recommended_action || item.action_type).replaceAll('_',' ')} · {item.priority}</span></div></div>) : <p className="pi-empty">No optimizer actions have been published.</p>}</div></section>
        <MiniGreeks snapshot={snapshot} risk={riskAllocation} />
        <ExposureBars title="Sector Exposure" values={snapshot?.sector_exposure} />
        <ExposureBars title="Strategy Exposure" values={snapshot?.strategy_exposure} />
        <section className="pi-card"><header><h3>Decision Queue</h3><span>{decisions.length}</span></header><div className="pi-queue">{decisions.slice(0, 6).map(position => <button key={position.position_id} onClick={() => setSelectedId(position.position_id)}><div><strong>{position.symbol}</strong><span>{position.decision.action.replaceAll('_', ' ')}</span></div>{position.decision.action === 'CLOSE' || position.decision.action === 'SCALE_OUT' ? <TrendingDown size={16} /> : <TrendingUp size={16} />}</button>)}</div></section>
        <section className="pi-card"><header><h3>Active Alerts</h3><span>{alerts.length}</span></header><div className="pi-alerts">{alerts.length ? alerts.slice(0, 8).map(({ position, alert }, index) => <button key={`${position.position_id}-${index}`} onClick={() => setSelectedId(position.position_id)}><AlertTriangle size={15} /><div><strong>{position.symbol}</strong><span>{alert}</span></div></button>) : <p className="pi-empty">No active position-health alerts.</p>}</div></section>
      </aside>
    </div>
  </section>;
}
