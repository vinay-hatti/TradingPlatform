import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, ChevronRight, CircleDollarSign, Gauge, Layers3, RefreshCw, ShieldAlert, ShieldCheck, Target, TrendingDown, TrendingUp, WalletCards } from 'lucide-react';
import { brokerPortfolioApi, dynamicPositionManagementApi, portfolioIntelligenceApi, portfolioRiskAllocationApi } from './api';
import type { DynamicExitInstruction, ManagedPosition, PortfolioIntelligenceSnapshot } from './types';
import './portfolio-intelligence-refined.css';

const money = (value: number | null | undefined) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Number(value || 0));
const pct = (value: number | null | undefined, digits = 1) => `${Number(value || 0).toFixed(digits)}%`;
const number = (value: number | null | undefined, digits = 2) => Number(value || 0).toFixed(digits);
const tone = (value: number, high = 75, medium = 50) => value >= high ? 'positive' : value >= medium ? 'warning' : 'critical';
const signed = (value: number) => `${value > 0 ? '+' : ''}${number(value)}`;
const exposureEntries = (source?: Record<string, number>) => Object.entries(source || {}).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

const TERMINAL_EXIT_STATUSES = new Set(['CANCELLED', 'CANCELED', 'COMPLETED', 'FILLED', 'SUPERSEDED', 'REJECTED', 'FAILED']);
const CRITICAL_PROTECTION_LABELS = new Set(['EMERGENCY_OPTION_STOP', 'STRUCTURAL_STOP', 'SHORT_LEG_ASSIGNMENT_EXIT', 'THETA_EXIT', 'VOLATILITY_EXIT']);
const PROFIT_TARGET_LABELS = new Set(['TARGET_1', 'TARGET_2', 'TARGET_3']);
const ACTIVE_EXIT_STATUSES = new Set(['ARMED', 'PENDING_APPROVAL', 'READY_FOR_AUTOMATIC_SUBMISSION', 'SUBMITTED', 'ACKNOWLEDGED']);
const NON_OPERATIONAL_POSITION_STATES = new Set(['CLOSED', 'CANCELLED', 'SUPERSEDED']);
const M75_ADDITIONAL_NON_OPERATIONAL_POSITION_STATES = new Set(['EXPIRED', 'ASSIGNED', 'STOPPED', 'TERMINAL', 'ARCHIVED']);
const isNonOperationalPositionState = (value: unknown) => {
  const state = String(value || '').toUpperCase();
  return NON_OPERATIONAL_POSITION_STATES.has(state) || M75_ADDITIONAL_NON_OPERATIONAL_POSITION_STATES.has(state);
};
type ManagementVisibility = 'AUTO' | 'MANUAL' | 'DEGRADED' | 'CLOSED';
type ManagementAssessment = {
  status: ManagementVisibility;
  label: string;
  detail: string;
  activeExitCount: number;
  automationMode: string;
  managerState: string;
  canonicalLineage: boolean;
  protectionFailureCount: number;
  targetIssueCount: number;
};

function instructionLabel(item: DynamicExitInstruction) {
  return String(item.payload?.label || item.action || 'UNKNOWN').toUpperCase();
}

function currentInstructionProjection(instructions: DynamicExitInstruction[], positionId?: string) {
  const latest = new Map<string, DynamicExitInstruction>();
  for (const item of instructions) {
    if (positionId && item.position_id !== positionId) continue;
    const key = `${item.position_id}|${instructionLabel(item)}`;
    const current = latest.get(key);
    const itemTime = Date.parse(String(item.created_at || '')) || 0;
    const currentTime = current ? (Date.parse(String(current.created_at || '')) || 0) : -1;
    if (!current || itemTime > currentTime || (itemTime === currentTime && String(item.instruction_id) > String(current.instruction_id))) latest.set(key, item);
  }
  return Array.from(latest.values());
}

function managementAssessment(position: ManagedPosition, instructions: DynamicExitInstruction[]): ManagementAssessment {
  if (isNonOperationalPositionState(position.state)) {
    const finalized = String(position.metadata?.m75_lifecycle_status || position.metadata?.lifecycle_governance?.status || '').toUpperCase() === 'FINALIZED';
    const terminalReason = String(position.metadata?.lifecycle_governance?.terminal_reason || position.state || 'CLOSED').replaceAll('_',' ');
    return { status: 'CLOSED', label: finalized ? 'LIFECYCLE FINALIZED' : 'CLOSED', detail: finalized ? `Terminal lifecycle finalized · ${terminalReason}` : 'Position lifecycle is complete.', activeExitCount: 0, automationMode: String(position.metadata?.automation_mode || '—'), managerState: finalized ? 'FINALIZED' : String(position.metadata?.m73_management || position.metadata?.manager_state || '—'), canonicalLineage: true, protectionFailureCount: 0, targetIssueCount: 0 };
  }
  const currentInstructions = currentInstructionProjection(instructions, position.position_id);
  const operational = currentInstructions.filter(item => !TERMINAL_EXIT_STATUSES.has(String(item.status || '').toUpperCase()));
  const activeExitCount = operational.filter(item => ACTIVE_EXIT_STATUSES.has(String(item.status || '').toUpperCase())).length;
  const protectionFailures = operational.filter(item => CRITICAL_PROTECTION_LABELS.has(instructionLabel(item)) && String(item.status || '').toUpperCase() === 'SUBMISSION_FAILED');
  const targetIssues = operational.filter(item => PROFIT_TARGET_LABELS.has(instructionLabel(item)) && String(item.status || '').toUpperCase() === 'SUBMISSION_FAILED');
  const automationMode = String(position.metadata?.automation_mode || 'ADVISORY').toUpperCase();
  const managerState = String(position.metadata?.m73_management || position.metadata?.manager_state || position.metadata?.m73_manager_state || '').toUpperCase();
  const managerActive = managerState === 'ACTIVE' || (automationMode === 'FULLY_AUTOMATIC' && Boolean(position.metadata?.m73_manager_id));
  const canonicalLineage = Boolean(position.execution_id) && position.strategy !== 'BROKER_DISCOVERED' && !String(position.trade_plan_id || '').startsWith('BROKER-DISCOVERED:');
  const ownership = (position.metadata?.position_ownership || {}) as any;
  const platformOwned = String(ownership.origin || '').toUpperCase() === 'PLATFORM' || canonicalLineage;
  const bootstrapState = String(ownership.bootstrap_state || position.metadata?.m74_13_bootstrap_state || '').toUpperCase();
  if (automationMode === 'FULLY_AUTOMATIC' && managerActive && activeExitCount > 0 && canonicalLineage && protectionFailures.length === 0) {
    const targetDetail = targetIssues.length ? ` · ${targetIssues.length} profit-target execution issue${targetIssues.length === 1 ? '' : 's'}; critical protection remains armed` : '';
    return { status: 'AUTO', label: targetIssues.length ? 'AUTO MANAGED · TARGET ATTENTION' : 'AUTO MANAGED', detail: `${activeExitCount} current autonomous exit rule${activeExitCount === 1 ? '' : 's'} armed · platform ownership verified${targetDetail}`, activeExitCount, automationMode, managerState: managerState || 'ACTIVE', canonicalLineage, protectionFailureCount: 0, targetIssueCount: targetIssues.length };
  }
  if (platformOwned || automationMode === 'FULLY_AUTOMATIC') {
    const reasons = [bootstrapState === 'AUTO_BOOTSTRAPPING' && 'platform ownership verified; autonomous exits are being bootstrapped', !canonicalLineage && 'institutional lineage incomplete', !managerActive && 'manager not confirmed active', activeExitCount === 0 && 'no current active exit rules', protectionFailures.length > 0 && `${protectionFailures.length} critical protection rule${protectionFailures.length === 1 ? '' : 's'} failed`].filter(Boolean).join(' · ');
    return { status: 'DEGRADED', label: bootstrapState === 'AUTO_BOOTSTRAPPING' ? 'AUTO BOOTSTRAPPING' : 'AUTO MANAGEMENT DEGRADED', detail: reasons || 'Autonomous management is not fully verified. Manually supervise until recovery completes.', activeExitCount, automationMode, managerState: managerState || 'UNKNOWN', canonicalLineage, protectionFailureCount: protectionFailures.length, targetIssueCount: targetIssues.length };
  }
  return { status: 'MANUAL', label: 'MANUAL MANAGEMENT REQUIRED', detail: 'This position is not autonomously managed. You must manually manage this position through closure.', activeExitCount, automationMode, managerState: managerState || 'UNKNOWN', canonicalLineage, protectionFailureCount: protectionFailures.length, targetIssueCount: targetIssues.length };
}


function strategyLifecycle(position: ManagedPosition) {
  const stored = (position.metadata?.strategy_lifecycle || position.metadata?.m73_live_market?.strategy_lifecycle || {}) as any;
  const liveLegs = (position.metadata?.m73_live_market?.live_legs || []) as any[];
  const shortLegs = liveLegs.filter(leg => String(leg?.side || '').toUpperCase() === 'SELL');
  const multiLeg = Boolean(stored.multi_leg ?? liveLegs.length > 1);
  const shortLegCount = Number(stored.short_leg_count ?? shortLegs.length ?? 0);
  return {
    multiLeg,
    legCount: Number(stored.leg_count ?? liveLegs.length ?? 0),
    shortLegCount,
    shortLegMonitored: Boolean(stored.short_leg_monitored ?? shortLegCount > 0),
    shortLegDte: stored.short_leg_dte ?? null,
    assignmentRiskDays: stored.assignment_risk_days_to_expiry ?? null,
    assignmentRiskRule: String(stored.assignment_risk_rule || position.metadata?.dynamic_management?.assignment_risk_rule || ''),
    exitMethod: String(stored.exit_execution_method || (multiLeg ? 'ATOMIC_BAG' : 'SINGLE_LEG')),
    shortLegPolicy: String(stored.short_leg_policy || (shortLegCount ? 'CLOSE_FULL_STRATEGY_BEFORE_ASSIGNMENT_RISK' : 'NOT_APPLICABLE')),
    nextAction: String(stored.next_autonomous_action || (shortLegCount ? 'MONITOR_SHORT_LEG' : 'MONITOR_POSITION')),
    rollEnabled: Boolean(stored.short_leg_roll_enabled),
    shortLegSymbols: (stored.short_leg_symbols || shortLegs.map(leg => leg?.option_symbol || leg?.local_symbol).filter(Boolean)) as string[],
  };
}

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
  const [managementFilter, setManagementFilter] = useState('ALL');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [instructions, setInstructions] = useState<DynamicExitInstruction[]>([]);
  const [allInstructions, setAllInstructions] = useState<DynamicExitInstruction[]>([]);
  const [brokerPublication, setBrokerPublication] = useState<any>(null);
  const [brokerPositions, setBrokerPositions] = useState<any[]>([]);
  const [riskAllocation, setRiskAllocation] = useState<any>(null);
  const [optimization, setOptimization] = useState<any>(null);
  const [portfolioActions, setPortfolioActions] = useState<any[]>([]);

  const load = async () => {
    setError('');
    const [positionsResponse, snapshotResponse, brokerPublicationResponse, brokerPositionsResponse, riskAllocationResponse, optimizationResponse, actionResponse, allInstructionsResponse] = await Promise.all([
      portfolioIntelligenceApi.positions(portfolioId),
      portfolioIntelligenceApi.snapshot(portfolioId),
      brokerPortfolioApi.publication(portfolioId).catch(() => ({data:null} as any)),
      brokerPortfolioApi.positions(portfolioId).catch(() => ({data:[]} as any)),
      portfolioRiskAllocationApi.current(portfolioId).catch(() => ({data:null} as any)),
      portfolioRiskAllocationApi.optimizerCurrent(portfolioId).catch(() => ({data:null} as any)),
      portfolioRiskAllocationApi.recommendations(portfolioId).catch(() => ({data:[]} as any)),
      dynamicPositionManagementApi.instructions().catch(() => ({data:[]} as any)),
    ]);
    setPositions(positionsResponse.data || []);
    setSnapshot(snapshotResponse.data || null);
    setBrokerPublication(brokerPublicationResponse.data || null);
    setBrokerPositions(brokerPositionsResponse.data || []);
    setRiskAllocation(riskAllocationResponse.data || null);
    setOptimization(optimizationResponse.data || null);
    setPortfolioActions(actionResponse.data || []);
    setAllInstructions(allInstructionsResponse.data || []);
    setSelectedId(current => current || positionsResponse.data?.[0]?.position_id || '');
    setLastUpdated(new Date());
  };

  useEffect(() => { load().catch(reason => setError(reason instanceof Error ? reason.message : String(reason))); }, []);

  const managementByPosition = useMemo(() => new Map(positions.map(position => [position.position_id, managementAssessment(position, allInstructions)])), [positions, allInstructions]);
  const filtered = useMemo(() => positions.filter(position => {
    const management = managementByPosition.get(position.position_id) || managementAssessment(position, allInstructions);
    const matchesQuery = !query || `${position.symbol} ${position.strategy} ${position.direction} ${position.state} ${management.label}`.toLowerCase().includes(query.toLowerCase());
    const matchesState = stateFilter === 'ALL' || (stateFilter === 'ACTIVE' ? !isNonOperationalPositionState(position.state) : position.state === stateFilter);
    const matchesManagement = managementFilter === 'ALL' || management.status === managementFilter;
    return matchesQuery && matchesState && matchesManagement;
  }).sort((a, b) => {
    const rank: Record<ManagementVisibility, number> = { MANUAL: 0, DEGRADED: 1, AUTO: 2, CLOSED: 3 };
    const statusDelta = rank[(managementByPosition.get(a.position_id)?.status || 'MANUAL')] - rank[(managementByPosition.get(b.position_id)?.status || 'MANUAL')];
    return statusDelta || b.health.score - a.health.score;
  }), [positions, query, stateFilter, managementFilter, managementByPosition, allInstructions]);

  const selectedCandidate = positions.find(position => position.position_id === selectedId);
  const selected = (stateFilter === 'ACTIVE' && selectedCandidate && isNonOperationalPositionState(selectedCandidate.state) ? undefined : selectedCandidate) || filtered[0];
  useEffect(() => { if (selected?.position_id) dynamicPositionManagementApi.instructions(selected.position_id).then(response => setInstructions(response.data || [])).catch(() => setInstructions([])); else setInstructions([]); }, [selected?.position_id, selected?.version]);
  const alerts = positions.flatMap(position => position.health.alerts.map(alert => ({ position, alert })));
  const decisions = positions.filter(position => !isNonOperationalPositionState(position.state)).sort((a, b) => {
    const priority = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 } as Record<string, number>;
    return (priority[b.decision.priority] || 0) - (priority[a.decision.priority] || 0);
  });
  const activePositions = positions.filter(position => !NON_OPERATIONAL_POSITION_STATES.has(String(position.state || '').toUpperCase())).filter(position => !M75_ADDITIONAL_NON_OPERATIONAL_POSITION_STATES.has(String(position.state || '').toUpperCase()));
  const winners = activePositions.filter(position => position.mark.unrealized_pnl > 0).length;
  const deteriorating = activePositions.filter(position => position.health.direction.toUpperCase().includes('DETERIOR')).length;
  const autoManagedCount = activePositions.filter(position => managementByPosition.get(position.position_id)?.status === 'AUTO').length;
  const manualManagedCount = activePositions.filter(position => managementByPosition.get(position.position_id)?.status === 'MANUAL').length;
  const degradedManagedCount = activePositions.filter(position => managementByPosition.get(position.position_id)?.status === 'DEGRADED').length;
  const selectedManagement = selected ? (managementByPosition.get(selected.position_id) || managementAssessment(selected, allInstructions)) : null;
  const selectedCurrentInstructions = useMemo(() => currentInstructionProjection(instructions, selected?.position_id).filter(item => !TERMINAL_EXIT_STATUSES.has(String(item.status || '').toUpperCase())), [instructions, selected?.position_id]);
  const selectedCurrentIds = useMemo(() => new Set(selectedCurrentInstructions.map(item => item.instruction_id)), [selectedCurrentInstructions]);
  const selectedHistoricalInstructions = useMemo(() => instructions.filter(item => !selectedCurrentIds.has(item.instruction_id) || TERMINAL_EXIT_STATUSES.has(String(item.status || '').toUpperCase())), [instructions, selectedCurrentIds]);
  const selectedProtectionIssues = selectedCurrentInstructions.filter(item => CRITICAL_PROTECTION_LABELS.has(instructionLabel(item)) && String(item.status || '').toUpperCase() === 'SUBMISSION_FAILED');
  const selectedTargetIssues = selectedCurrentInstructions.filter(item => PROFIT_TARGET_LABELS.has(instructionLabel(item)) && String(item.status || '').toUpperCase() === 'SUBMISSION_FAILED');
  const selectedLifecycle = selected ? strategyLifecycle(selected) : null;

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
      <article className="pi-kpi-auto"><ShieldCheck /><div><span>Auto managed</span><strong>{autoManagedCount}</strong><small>Verified manager + active exits</small></div></article>
      <article className="pi-kpi-manual"><ShieldAlert /><div><span>Manual management</span><strong>{manualManagedCount}</strong><small>Must be manually managed to closure</small></div></article>
      <article className="pi-kpi-degraded"><AlertTriangle /><div><span>Automation degraded</span><strong>{degradedManagedCount}</strong><small>Manual oversight required</small></div></article>
      <article><ShieldAlert /><div><span>Open risk</span><strong>{money(snapshot?.open_risk)}</strong><small>{money(snapshot?.buying_power)} buying power</small></div></article>
      <article><Activity /><div><span>IBKR positions</span><strong>{brokerPositions.length}</strong><small>{brokerPublication?.status || 'Awaiting sync'} · {brokerPublication?.payload_json?.broker_discovered_count ?? brokerPublication?.broker_discovered_count ?? 0} discovered</small></div></article>
      <article><ShieldAlert /><div><span>Portfolio heat</span><strong>{pct(riskAllocation?.portfolio_heat_pct || 0)}</strong><small>{money(riskAllocation?.var_95 || 0)} one-day VaR</small></div></article>
    </div>

    <div className="pi-layout">
      <aside className="pi-left pi-card">
        <header><div><h3>Managed Positions</h3><span>{filtered.length} shown</span></div></header>
        <div className="pi-controls"><input aria-label="Search positions" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search symbol or strategy" /><select aria-label="Position state" value={stateFilter} onChange={event => setStateFilter(event.target.value)}><option value="ACTIVE">Active</option><option value="ALL">All</option><option value="OPEN">Open</option><option value="PARTIAL">Partial</option><option value="HEDGED">Hedged</option><option value="ROLLED">Rolled</option><option value="CLOSED">Closed</option></select><select aria-label="Management status" value={managementFilter} onChange={event => setManagementFilter(event.target.value)}><option value="ALL">All management</option><option value="AUTO">Auto managed</option><option value="MANUAL">Manual required</option><option value="DEGRADED">Automation degraded</option></select></div>
        <div className="pi-position-list">{filtered.map(position => { const management = managementByPosition.get(position.position_id) || managementAssessment(position, allInstructions); return <button key={position.position_id} className={`${selected?.position_id === position.position_id ? 'selected ' : ''}pi-management-row ${management.status.toLowerCase()}`} onClick={() => setSelectedId(position.position_id)}><div className="pi-position-row"><strong>{position.symbol}</strong><span className={`pi-management-badge ${management.status.toLowerCase()}`}>{management.label}</span></div><p>{position.strategy} · {position.direction} · {position.state}</p><div className="pi-position-stats"><span className={position.mark.unrealized_pnl >= 0 ? 'gain' : 'loss'}>{money(position.mark.unrealized_pnl)}</span><span>{management.status === 'AUTO' ? `${management.activeExitCount} exits armed` : management.status === 'CLOSED' ? 'Lifecycle complete' : 'Manual oversight required'}</span><ChevronRight size={15} /></div></button>})}{!filtered.length && <p className="pi-empty">No managed positions match the current filters.</p>}</div>
      </aside>

      <main className="pi-center">
        {selected ? <>
          {selectedManagement && <section className={`pi-management-banner ${selectedManagement.status.toLowerCase()}`}>
            <div className="pi-management-banner-icon">{selectedManagement.status === 'AUTO' ? <ShieldCheck size={24} /> : <ShieldAlert size={24} />}</div>
            <div><strong>{selectedManagement.label}</strong><p>{selectedManagement.status === 'AUTO' ? `${selectedManagement.activeExitCount} autonomous exit rule${selectedManagement.activeExitCount === 1 ? '' : 's'} are armed and the position is under verified platform management.` : selectedManagement.status === 'CLOSED' ? selectedManagement.detail : selectedManagement.status === 'MANUAL' ? 'This position is not autonomously managed. You must manually manage this position through closure.' : 'This position is not currently confirmed as autonomously managed. You must manually manage this position through closure unless automation is restored and verified.'}</p><small>Mode {selectedManagement.automationMode.replaceAll('_',' ')} · Manager {selectedManagement.managerState.replaceAll('_',' ')} · Active exits {selectedManagement.activeExitCount} · Critical protection failures {selectedManagement.protectionFailureCount} · Target issues {selectedManagement.targetIssueCount} · Lineage {selectedManagement.canonicalLineage ? 'VERIFIED' : 'INCOMPLETE'}</small></div>
          </section>}
          <section className="pi-card pi-position-hero"><div><p className="pi-eyebrow">{selected.position_id}</p><h3>{selected.symbol} · {selected.strategy}</h3><p>{selected.direction} · Opened {new Date(selected.opened_at).toLocaleDateString()} · Version {selected.version}</p></div><div className="pi-health-cluster"><ScoreRing value={selected.health.score} label="Health" /><ScoreRing value={selected.decision.confidence * 100} label="Decision" /></div></section>
          <section className="pi-position-metrics"><article><span>Market value</span><strong>{money(selected.mark.market_value)}</strong></article><article><span>Unrealized P&amp;L</span><strong className={selected.mark.unrealized_pnl >= 0 ? 'gain' : 'loss'}>{money(selected.mark.unrealized_pnl)}</strong></article><article><span>Return</span><strong className={selected.mark.unrealized_return_pct >= 0 ? 'gain' : 'loss'}>{pct(selected.mark.unrealized_return_pct)}</strong></article><article><span>Days to expiry</span><strong>{selected.mark.days_to_expiry ?? '—'}</strong></article></section>
          <section className="pi-card pi-decision"><header><div><h3>Decision Intelligence</h3><span className={`pi-priority ${selected.decision.priority.toLowerCase()}`}>{selected.decision.priority}</span></div><b>{selected.decision.action.replaceAll('_', ' ')}</b></header><p>{selected.decision.reason}</p><div className="pi-decision-grid"><div><span>Expected benefit</span><strong>{selected.decision.expected_benefit}</strong></div><div><span>Risk impact</span><strong>{selected.decision.risk_impact}</strong></div><div><span>Confidence</span><strong>{pct(selected.decision.confidence * 100, 0)}</strong></div></div>{selected.decision.alternatives?.length > 0 && <div className="pi-alternatives"><span>Alternatives</span>{selected.decision.alternatives.map(item => <i key={item}>{item.replaceAll('_', ' ')}</i>)}</div>}</section>
          <section className="pi-card"><header><div><h3>Broker Reconciliation</h3><span>{selected.metadata?.reconciliation_status || 'AWAITING SYNC'}</span></div></header><div className="pi-decision-grid"><div><span>Position origin</span><strong>{String(selected.metadata?.provenance || 'PLATFORM').replaceAll('_',' ')}</strong></div><div><span>IBKR contract</span><strong>{selected.metadata?.local_symbol || selected.metadata?.broker_contract_id || '—'}</strong></div><div><span>Broker account</span><strong>{selected.metadata?.broker_account_id ? 'Connected paper account' : 'Not linked'}</strong></div></div></section>
          <section className="pi-card"><header><div><h3>Dynamic Management Control</h3><span>{selected.metadata?.automation_mode || 'ADVISORY'}</span></div><button onClick={evaluateManagement} disabled={busy}>Evaluate now</button></header><div className="pi-decision-grid"><div><span>Current structural stop</span><strong>{selected.metadata?.dynamic_management?.current_underlying_stop ?? selected.metadata?.dynamic_management?.underlying_stop ?? '—'}</strong></div><div><span>Trailing policy</span><strong>{String(selected.metadata?.dynamic_management?.trailing_policy || '—').replaceAll('_',' ')}</strong></div><div><span>Next management status</span><strong>{selected.metadata?.last_management_status || 'Awaiting evaluation'}</strong></div></div><div className="pi-autonomous-health"><div className={selectedProtectionIssues.length ? 'critical' : 'healthy'}><strong>{selectedProtectionIssues.length ? 'CRITICAL PROTECTION ATTENTION' : 'CRITICAL PROTECTION ACTIVE'}</strong><span>{selectedProtectionIssues.length ? `${selectedProtectionIssues.length} required protection rule${selectedProtectionIssues.length === 1 ? '' : 's'} need attention` : 'No current structural/emergency/theta/volatility/assignment submission failure'}</span></div><div className={selectedTargetIssues.length ? 'warning' : 'healthy'}><strong>{selectedTargetIssues.length ? 'PROFIT TARGET ATTENTION' : 'PROFIT TARGETS HEALTHY'}</strong><span>{selectedTargetIssues.length ? `${selectedTargetIssues.length} target execution issue${selectedTargetIssues.length === 1 ? '' : 's'}; critical protection status shown separately` : 'No current profit-target submission failure'}</span></div></div><div className="pi-alternatives"><span>Automation mode</span>{['ADVISORY','SEMI_AUTOMATIC','FULLY_AUTOMATIC'].map(mode => <button key={mode} disabled={busy || selected.metadata?.automation_mode===mode} onClick={() => setAutomationMode(mode)}>{mode.replaceAll('_',' ')}</button>)}</div><div className="pi-driver-grid">{selectedCurrentInstructions.length ? selectedCurrentInstructions.map(item => { const label=instructionLabel(item); const isProtection=CRITICAL_PROTECTION_LABELS.has(label); const isTarget=PROFIT_TARGET_LABELS.has(label); return <article key={item.instruction_id} className={`pi-exit-rule ${isProtection ? 'protection' : isTarget ? 'target' : 'other'} ${String(item.status || '').toLowerCase()}`}><div><strong>{label.replaceAll('_',' ')}</strong><span>{item.status}</span></div><p>{item.payload?.trigger_type}: {String(item.payload?.trigger_value ?? 'rule based')} · Qty {item.quantity}</p>{item.payload?.submission_recovery_state && <small>{String(item.payload.submission_recovery_state).replaceAll('_',' ')}</small>}{item.status==='PENDING_APPROVAL' && <button onClick={async()=>{const reason=window.prompt('Approval reason:');if(reason){await dynamicPositionManagementApi.approve(item.instruction_id,reason,true);await evaluateManagement();}}}>Approve & submit</button>}</article>}) : <p className="pi-empty">No current governed exit instructions have been armed yet.</p>}</div>{selectedHistoricalInstructions.length > 0 && <details className="pi-exit-history"><summary>Management history · {selectedHistoricalInstructions.length} superseded / terminal instruction{selectedHistoricalInstructions.length === 1 ? '' : 's'}</summary><div>{selectedHistoricalInstructions.slice(0,20).map(item => <article key={`history-${item.instruction_id}`}><strong>{instructionLabel(item).replaceAll('_',' ')}</strong><span>{item.status} · {new Date(item.created_at).toLocaleString()}</span></article>)}</div></details>}</section>
          {selectedLifecycle?.multiLeg && <section className="pi-card pi-strategy-lifecycle"><header><div><h3>Strategy Lifecycle</h3><span>{String(selected.strategy || '').replaceAll('_',' ')}</span></div><b>{selectedLifecycle.exitMethod === 'ATOMIC_BAG' ? 'ATOMIC BAG MANAGED' : selectedLifecycle.exitMethod.replaceAll('_',' ')}</b></header><div className="pi-decision-grid"><div><span>Strategy legs</span><strong>{selectedLifecycle.legCount}</strong></div><div><span>Short / sell legs</span><strong>{selectedLifecycle.shortLegCount}</strong></div><div><span>Short-leg monitoring</span><strong className={selectedLifecycle.shortLegMonitored ? 'gain' : 'loss'}>{selectedLifecycle.shortLegMonitored ? 'ACTIVE' : 'NOT ACTIVE'}</strong></div><div><span>Nearest short expiry</span><strong>{selectedLifecycle.shortLegDte == null ? '—' : `${selectedLifecycle.shortLegDte} DTE`}</strong></div><div><span>Assignment-risk window</span><strong>{selectedLifecycle.assignmentRiskDays == null ? '—' : `${selectedLifecycle.assignmentRiskDays} DTE`}</strong></div><div><span>Exit execution</span><strong>{selectedLifecycle.exitMethod.replaceAll('_',' ')}</strong></div></div>{selectedLifecycle.shortLegSymbols.length > 0 && <div className="pi-strategy-leg-list"><span>Short legs under management</span>{selectedLifecycle.shortLegSymbols.map(symbol => <i key={symbol}>{symbol}</i>)}</div>}<div className="pi-management-explanation"><strong>Next autonomous action</strong><span>{selectedLifecycle.nextAction.replaceAll('_',' ')}</span></div><p className="pi-strategy-note">{selectedLifecycle.shortLegCount > 0 ? (selectedLifecycle.rollEnabled ? 'The platform may roll or close the short leg under the governed strategy policy.' : 'The short leg is monitored. Current policy closes the full strategy as one BAG before assignment-risk/expiry governance is breached; autonomous rolling is not enabled yet.') : 'All legs are managed together as one canonical strategy position.'}</p></section>}
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
