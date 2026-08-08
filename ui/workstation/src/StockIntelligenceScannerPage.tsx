import { Fragment, useEffect, useMemo, useState } from 'react';
import { stockIntelligenceApi } from './api';
import type { StockIntelligenceCandidate } from './types';

const timeframeOrder = ['5m', '15m', '30m', '1h', '1d', '1w', '1mo'];
const fmt = (value: number | null | undefined, digits = 2) => value == null ? '—' : Number(value).toFixed(digits);
const display = (value: string | null | undefined) => {
  const text = String(value || '').trim().toUpperCase();
  return !text || text === 'UNKNOWN' || text === 'UNAVAILABLE' ? 'Not published' : text.replaceAll('_', ' ');
};
const unique = (values: (string | null | undefined)[]) => Array.from(new Set(values.map(value => String(value || '').trim()).filter(Boolean))).sort();
const directionTone = (value: string | null | undefined) => {
  const text = String(value || '').toUpperCase();
  if (text.includes('BULL') || text.includes('UP') || text.includes('ACCUM')) return 'positive';
  if (text.includes('BEAR') || text.includes('DOWN') || text.includes('DISTRIB')) return 'negative';
  return 'neutral';
};
const conviction = (record: StockIntelligenceCandidate) => {
  const blended = record.score * 0.55 + record.confidence * 0.3 + record.management_quality * 0.15;
  if (blended >= 90) return 'Exceptional conviction';
  if (blended >= 80) return 'High conviction';
  if (blended >= 70) return 'Strong candidate';
  if (blended >= 60) return 'Moderate candidate';
  return 'Watch only';
};
const suggestedExpression = (record: StockIntelligenceCandidate) => {
  const bearish = String(record.direction || '').toUpperCase().includes('BEAR');
  const trending = ['TRENDING', 'EARLY_TREND', 'MATURE_TREND', 'EXPANSION'].includes(String(record.structure || '').toUpperCase());
  if (bearish) return trending ? 'Put or bear put spread' : 'Defined-risk bearish structure';
  return trending ? 'Call or bull call spread' : 'Defined-risk bullish structure';
};
const zoneSectionTitle = (value: string) => ({
  PRIMARY_STRUCTURE: 'Primary structure',
  SECONDARY_STRUCTURE: 'Secondary structure',
  MAJOR_STRUCTURE: 'Major structural levels',
  DEALER_STRUCTURE: 'Dealer structure',
  HISTORICAL_STRUCTURE: 'Historical structure',
} as Record<string, string>)[value] || display(value);
const componentLabel = (value: string) => ({
  PRICE_LEVEL: 'Price structure', DEMAND_ZONE: 'Demand zone', SUPPLY_ZONE: 'Supply zone',
  PUT_WALL: 'Primary put wall', CALL_WALL: 'Primary call wall', GAMMA_FLIP: 'Gamma flip',
} as Record<string, string>)[value] || display(value);
type HeaderFilters = Record<string, string>;

function MetricCard({ label, value, helper, tone = 'neutral' }: { label: string; value: string; helper?: string; tone?: string }) {
  return <div className={`candidate-metric-card ${tone}`}><span>{label}</span><b>{value}</b>{helper && <small>{helper}</small>}</div>;
}

function StatusPill({ value }: { value: string | null | undefined }) {
  return <span className={`candidate-status-pill ${directionTone(value)}`}>{display(value)}</span>;
}

function StructureZoneCard({ zone, index }: { zone: any; index: number }) {
  return <div className={`structure-zone-card ${String(zone.zone_type || '').toLowerCase()}`} key={`${zone.zone_type}-${zone.representative_price}-${index}`}>
    <div className="structure-zone-heading"><span>{display(zone.zone_type)} · {zone.primary_timeframe || 'Dealer'}</span><em>{display(zone.status)}</em></div>
    <b>{fmt(zone.lower_bound)}–{fmt(zone.upper_bound)}</b>
    <div className="structure-zone-metrics">
      <small>Strength <strong>{fmt(zone.strength, 0)}</strong></small><small>Confluence <strong>{fmt(zone.confluence_score, 0)}</strong></small>
      <small>Hold <strong>{fmt((zone.holding_probability || 0) * 100, 0)}%</strong></small><small>Break <strong>{fmt((zone.break_probability || 0) * 100, 0)}%</strong></small>
      <small>Distance <strong>{zone.distance_pct == null ? '—' : `${zone.distance_pct > 0 ? '+' : ''}${fmt(zone.distance_pct, 2)}%`}</strong></small><small>Relevance <strong>{fmt(zone.relevance_score, 0)}</strong></small>
    </div>
    <small>Timeframes: {(zone.contributing_timeframes || []).join(', ') || 'Dealer-derived'}</small>
    <div className="structure-zone-components">{(zone.components || []).map((item: string) => <span key={item}>✓ {componentLabel(item)}</span>)}</div>
    {zone.dealer_context && Object.keys(zone.dealer_context).length > 0 && <div className="dealer-zone-context"><small>Dealer positioning: {display(zone.dealer_context.positioning)}</small><small>Gamma regime: {display(zone.dealer_context.gamma_regime)}</small><small>Dealer confidence: {fmt(zone.dealer_context.confidence_score, 0)}</small></div>}
  </div>;
}

function CandidateWorkspace({ record, detail }: { record: StockIntelligenceCandidate; detail: any }) {
  const timeframeEntries = Object.entries(record.timeframes || {}).sort(([left], [right]) => {
    const leftIndex = timeframeOrder.indexOf(left); const rightIndex = timeframeOrder.indexOf(right);
    return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex);
  });
  const entryWidth = record.entry_zone_low != null && record.entry_zone_high != null ? record.entry_zone_high - record.entry_zone_low : null;
  const entryMid = record.entry_zone_low != null && record.entry_zone_high != null ? (record.entry_zone_low + record.entry_zone_high) / 2 : null;
  const entryWidthPct = entryWidth != null && entryMid ? entryWidth / entryMid * 100 : null;
  const zones = detail.structure_zones || [];
  const primarySupport = zones.find((zone: any) => zone.hierarchy === 'PRIMARY_STRUCTURE' && String(zone.zone_type).toUpperCase() === 'SUPPORT');
  const primaryResistance = zones.find((zone: any) => zone.hierarchy === 'PRIMARY_STRUCTURE' && String(zone.zone_type).toUpperCase() === 'RESISTANCE');
  const positives = [
    record.alignment_score >= 70 ? `Multi-timeframe alignment ${fmt(record.alignment_score, 0)}` : null,
    record.management_quality >= 70 ? `Management quality ${fmt(record.management_quality, 0)}` : null,
    record.relative_strength_grade && !['UNKNOWN', 'UNAVAILABLE'].includes(record.relative_strength_grade) ? `Relative strength ${display(record.relative_strength_grade)}` : null,
    record.participation_state && !['UNKNOWN', 'UNAVAILABLE', 'NEUTRAL'].includes(record.participation_state) ? display(record.participation_state) : null,
    record.breakout_state && !['UNKNOWN', 'UNAVAILABLE', 'NONE'].includes(record.breakout_state) ? display(record.breakout_state) : null,
    record.market_regime && !['UNKNOWN', 'UNAVAILABLE'].includes(record.market_regime) ? `Market regime ${display(record.market_regime)}` : null,
  ].filter(Boolean) as string[];
  const risks = [...record.warnings];
  if (record.confidence < 65) risks.push('Confidence is below the preferred institutional threshold');
  if (record.structural_reward_risk < 1.5) risks.push('Structural reward/risk is below 1.5');
  if (record.freshness < 70) risks.push('The published setup may be aging');
  if (primaryResistance?.distance_pct != null && primaryResistance.distance_pct > 0 && primaryResistance.distance_pct < 2) risks.push('Primary resistance is less than 2% overhead');

  return <div className="candidate-workspace">
    <section className="candidate-summary-band">
      <div className="candidate-summary-title"><div><span className="candidate-symbol">{record.symbol}</span><StatusPill value={record.primary_category}/></div><h3>{conviction(record)}</h3><p>{display(record.direction)} · {display(record.structure)} · {record.primary_timeframe || 'Primary timeframe not published'}</p></div>
      <div className="candidate-summary-metrics">
        <MetricCard label="Overall score" value={fmt(record.score, 1)} tone="accent"/>
        <MetricCard label="Confidence" value={fmt(record.confidence, 1)} />
        <MetricCard label="Management quality" value={fmt(record.management_quality, 1)} />
        <MetricCard label="Suggested expression" value={suggestedExpression(record)} helper="Heuristic guidance" />
      </div>
    </section>

    <section className="candidate-section"><div className="candidate-section-heading"><div><h4>Market alignment</h4><p>External context supporting or challenging the setup.</p></div></div>
      <div className="candidate-context-grid">
        <MetricCard label="Market regime" value={display(record.market_regime)} tone={directionTone(record.market_regime)} />
        <MetricCard label="Relative strength" value={display(record.relative_strength_grade)} tone={directionTone(record.relative_strength_grade)} />
        <MetricCard label="Dealer positioning" value={display(record.dealer_positioning)} tone={directionTone(record.dealer_positioning)} />
        <MetricCard label="Gamma regime" value={display(record.gamma_regime)} tone={directionTone(record.gamma_regime)} />
        <MetricCard label="Participation" value={display(record.participation_state)} tone={directionTone(record.participation_state)} />
        <MetricCard label="Freshness" value={fmt(record.freshness, 1)} />
      </div>
    </section>

    <section className="candidate-section"><div className="candidate-section-heading"><div><h4>Multi-timeframe alignment</h4><p>Trend, market structure, and confidence across published horizons.</p></div><MetricCard label="Alignment score" value={fmt(record.alignment_score, 1)} /></div>
      <div className="candidate-timeframe-table"><div className="candidate-timeframe-header"><span>Timeframe</span><span>Trend</span><span>Structure</span><span>Confidence</span></div>
        {timeframeEntries.map(([timeframe, value]: any) => <div className="candidate-timeframe-row" key={timeframe}><b>{timeframe === '1mo' ? '1 month' : timeframe}</b><StatusPill value={value.direction}/><span>{display(value.structure)}</span><strong>{fmt(value.confidence, 0)}%</strong></div>)}
      </div>
    </section>

    <section className="candidate-section"><div className="candidate-section-heading"><div><h4>Dynamic trade plan</h4><p>Underlying-based execution and management levels.</p></div><MetricCard label="Structural R/R" value={fmt(record.structural_reward_risk, 2)} /></div>
      <div className="candidate-plan-flow">
        <div className="candidate-plan-step entry"><span>Entry zone</span><b>{fmt(record.entry_zone_low)}–{fmt(record.entry_zone_high)}</b><small>Width {fmt(entryWidth)} ({fmt(entryWidthPct, 2)}%)</small></div><i>→</i>
        <div className="candidate-plan-step stop"><span>Structural stop</span><b>{fmt(record.recommended_stop)}</b><small>Thesis invalidation</small></div><i>→</i>
        {(record.targets || []).filter(value => value != null).map((target, index) => { const meta = detail.trade_plan?.targets?.targets?.[index]; return <Fragment key={`${target}-${index}`}><div className="candidate-plan-step target"><span>Target {index + 1}</span><b>{fmt(target)}</b><small>{meta?.rationale?.[0] || 'Governed primary objective'}</small></div>{index < record.targets.filter(value => value != null).length - 1 && <i>→</i>}</Fragment>; })}
      </div>
      {(record.additional_targets || []).length > 0 && <details className="candidate-additional-targets"><summary>Additional targets ({record.additional_targets.length})</summary><p>Valid extended objectives not selected in the governed primary three. These are informational and do not automatically change trade management.</p><div className="candidate-additional-target-table"><div className="candidate-additional-target-head"><span>Price</span><span>Source</span><span>TF</span><span>Score</span><span>Strength</span><span>Confluence</span><span>Hold</span><span>R/R</span></div>{record.additional_targets.map((target: any, index: number) => <div className="candidate-additional-target-row" key={`${target.price}-${target.source_type}-${index}`}><b>{fmt(target.price)}</b><span>{display(target.source_type)}{target.source_components?.length ? <small>{target.source_components.map((value: string) => componentLabel(value)).join(' · ')}</small> : null}</span><span>{target.timeframe || '—'}</span><span>{fmt(target.target_score, 1)}</span><span>{fmt(target.strength, 0)}</span><span>{fmt(target.confluence_score, 0)}</span><span>{target.holding_probability == null ? '—' : `${fmt(target.holding_probability * 100, 0)}%`}</span><span>{fmt(target.reward_risk, 2)}</span></div>)}</div></details>}
      {detail.trade_plan?.entry?.rationale?.length > 0 && <div className="candidate-rationale"><b>Entry rationale</b><ul>{detail.trade_plan.entry.rationale.map((item: string, index: number) => <li key={index}>{item}</li>)}</ul></div>}
    </section>

    <section className="candidate-section candidate-two-column">
      <div><div className="candidate-section-heading"><div><h4>Primary institutional structure</h4><p>Nearest actionable support and resistance.</p></div></div><div className="candidate-primary-zones">{primarySupport ? <StructureZoneCard zone={primarySupport} index={0}/> : <p className="candidate-empty">Primary support not published.</p>}{primaryResistance ? <StructureZoneCard zone={primaryResistance} index={1}/> : <p className="candidate-empty">Primary resistance not published.</p>}</div></div>
      <div><div className="candidate-section-heading"><div><h4>Why this candidate?</h4><p>Explainable evidence behind the ranking.</p></div></div><ul className="candidate-evidence-list">{positives.length ? positives.map((item, index) => <li key={index}>✓ {item}</li>) : <li>No positive evidence was published.</li>}</ul>
        <div className="candidate-risk-panel"><h4>Risk factors</h4>{risks.length ? <ul>{Array.from(new Set(risks)).map((item, index) => <li key={index}>⚠ {item}</li>)}</ul> : <p>No explicit warnings were published.</p>}</div>
      </div>
    </section>

    <details className="candidate-disclosure" open><summary>Institutional structure hierarchy</summary><div className="candidate-disclosure-body"><p className="structure-zone-helper">Primary and secondary structures are actionable. Monthly and dealer structures provide broader context; historical zones remain collapsed.</p>{['PRIMARY_STRUCTURE', 'SECONDARY_STRUCTURE', 'MAJOR_STRUCTURE', 'DEALER_STRUCTURE'].map(group => { const groupZones = zones.filter((zone: any) => zone.hierarchy === group); return groupZones.length ? <section className="structure-zone-section" key={group}><h5>{zoneSectionTitle(group)}</h5><div className="stock-level-grid">{groupZones.map((zone: any, index: number) => <StructureZoneCard key={`${group}-${index}`} zone={zone} index={index}/>)}</div></section> : null; })}{zones.some((zone: any) => zone.hierarchy === 'HISTORICAL_STRUCTURE') && <details className="historical-structure-zones"><summary>Historical structure ({zones.filter((zone: any) => zone.hierarchy === 'HISTORICAL_STRUCTURE').length})</summary><div className="stock-level-grid">{zones.filter((zone: any) => zone.hierarchy === 'HISTORICAL_STRUCTURE').map((zone: any, index: number) => <StructureZoneCard key={`historical-${index}`} zone={zone} index={index}/>)}</div></details>}</div></details>

    <details className="candidate-disclosure"><summary>Advanced intelligence and raw publication data</summary><div className="candidate-disclosure-body"><div className="candidate-context-grid"><MetricCard label="Candidate ID" value={record.candidate_id}/><MetricCard label="State hash" value={record.state_hash}/><MetricCard label="Published snapshot" value={record.snapshot_timestamp ? new Date(record.snapshot_timestamp).toLocaleString() : 'Not published'}/><MetricCard label="Breakout state" value={display(record.breakout_state)}/></div></div></details>
  </div>;
}

export function StockIntelligenceScannerPage() {
  const [records, setRecords] = useState<StockIntelligenceCandidate[]>([]); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [publication, setPublication] = useState<any>(null);
  const [search, setSearch] = useState(''); const [minScore, setMinScore] = useState(0); const [minConfidence, setMinConfidence] = useState(0); const [filters, setFilters] = useState<HeaderFilters>({});
  const [expandedId, setExpandedId] = useState<string | null>(null); const [details, setDetails] = useState<Record<string, any>>({});
  const load = async () => { setBusy(true); setError(''); try { const response = await stockIntelligenceApi.candidates({ min_score: 0, min_confidence: 0, limit: 5000 }); setRecords(response.data); setPublication(response.metadata?.publication || null); } catch (caught: any) { setError(caught.message); } finally { setBusy(false); } };
  useEffect(() => { load(); }, []);
  const options = useMemo(() => ({ symbol: unique(records.map(record => record.symbol)), category: unique(records.map(record => record.primary_category)), direction: unique(records.map(record => record.direction)), structure: unique(records.map(record => record.structure)), participation: unique(records.map(record => record.participation_state)), breakout: unique(records.map(record => record.breakout_state)) }), [records]);
  const visible = useMemo(() => records.filter(record => {
    if (search && !record.symbol.toUpperCase().includes(search.trim().toUpperCase())) return false;
    if (record.score < minScore || record.confidence < minConfidence) return false;
    const pairs: Record<string, string> = { symbol: record.symbol, category: record.primary_category, direction: record.direction, structure: record.structure, participation: record.participation_state, breakout: record.breakout_state };
    if (Object.entries(filters).some(([key, value]) => value && pairs[key] !== value)) return false;
    if (filters.score && record.score < Number(filters.score)) return false; if (filters.confidence && record.confidence < Number(filters.confidence)) return false; if (filters.alignment && record.alignment_score < Number(filters.alignment)) return false; if (filters.rr && record.structural_reward_risk < Number(filters.rr)) return false;
    return true;
  }), [records, search, minScore, minConfidence, filters]);
  const setFilter = (key: string, value: string) => setFilters(current => ({ ...current, [key]: value }));
  const toggle = async (record: StockIntelligenceCandidate) => { const next = expandedId === record.candidate_id ? null : record.candidate_id; setExpandedId(next); if (next && !details[next]) { try { const response = await stockIntelligenceApi.candidate(next); setDetails(current => ({ ...current, [next]: response.data })); } catch (caught: any) { setError(caught.message); } } };
  const headerSelect = (key: string, values: string[], label = 'All') => <select aria-label={`${key} filter`} value={filters[key] || ''} onChange={event => setFilter(key, event.target.value)} onClick={event => event.stopPropagation()}><option value="">{label}</option>{values.map(value => <option key={value} value={value}>{display(value)}</option>)}</select>;

  return <section className="stock-intelligence-page"><div className="page-title"><div><h2>Stock Intelligence Scanner</h2><p>Published equities, ETFs, and indexes with explainable multi-timeframe intelligence and underlying-driven trade management.</p></div><button className="primary" onClick={load} disabled={busy}>{busy ? 'Loading…' : 'Refresh publication'}</button></div>
    {error && <div className="handoff-message">{error}</div>}
    <article className="panel stock-publication-info"><h3>Publication details</h3><div className="stock-publication-grid"><div><span>Name</span><b>{publication?.publication_name || 'current_stock_intelligence'}</b></div><div><span>Status</span><b>{display(publication?.status)}</b></div><div><span>Published snapshot</span><b>{publication?.snapshot_timestamp ? new Date(publication.snapshot_timestamp).toLocaleString() : 'Not published'}</b></div><div><span>Scanner run</span><b>{publication?.scanner_run_id || 'Not published'}</b></div><div><span>Published rows</span><b>{records.length}</b></div></div></article>
    <article className="panel"><div className="scanner-form stock-intelligence-controls"><label>Search<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Symbol"/></label><label>Min score<input type="number" value={minScore} onChange={event => setMinScore(Number(event.target.value))}/></label><label>Min confidence<input type="number" value={minConfidence} onChange={event => setMinConfidence(Number(event.target.value))}/></label><button onClick={() => { setSearch(''); setMinScore(0); setMinConfidence(0); setFilters({}); }}>Clear all filters</button></div></article>
    <article className="panel stock-intelligence-table"><h3>Published candidates <small>{visible.length} of {records.length}</small></h3><div className="table-wrap"><table><thead><tr><th>Rank</th><th>Symbol</th><th>Category</th><th>Score</th><th>Confidence</th><th>Direction</th><th>Structure</th><th>Alignment</th><th>Participation</th><th>Breakout</th><th>Entry</th><th>Stop</th><th>Targets</th><th>R/R</th></tr><tr className="stock-filter-row"><th></th><th>{headerSelect('symbol', options.symbol)}</th><th>{headerSelect('category', options.category)}</th><th>{headerSelect('score', ['90', '80', '70', '60'], 'Any')}</th><th>{headerSelect('confidence', ['90', '80', '70', '60'], 'Any')}</th><th>{headerSelect('direction', options.direction)}</th><th>{headerSelect('structure', options.structure)}</th><th>{headerSelect('alignment', ['90', '80', '70', '60'], 'Any')}</th><th>{headerSelect('participation', options.participation)}</th><th>{headerSelect('breakout', options.breakout)}</th><th></th><th></th><th></th><th>{headerSelect('rr', ['3', '2', '1.5', '1'], 'Any')}</th></tr></thead><tbody>{visible.map(record => { const expanded = expandedId === record.candidate_id; return <Fragment key={record.candidate_id}><tr className={expanded ? 'selected-row' : ''} onClick={() => toggle(record)}><td>{record.rank ?? '—'}</td><td><b>{record.symbol}</b></td><td>{display(record.primary_category)}</td><td>{fmt(record.score, 1)}</td><td>{fmt(record.confidence, 1)}</td><td>{display(record.direction)}</td><td>{display(record.structure)}</td><td>{fmt(record.alignment_score, 1)}</td><td>{display(record.participation_state)}</td><td>{display(record.breakout_state)}</td><td>{fmt(record.entry_zone_low)}–{fmt(record.entry_zone_high)}</td><td>{fmt(record.recommended_stop)}</td><td>{record.targets.filter(value => value != null).map(value => fmt(value)).join(' / ') || '—'}</td><td>{fmt(record.structural_reward_risk, 2)}</td></tr>{expanded && <tr className="stock-expanded-row"><td colSpan={14}><CandidateWorkspace record={record} detail={details[record.candidate_id] || {}}/></td></tr>}</Fragment>; })}</tbody></table></div></article>
  </section>;
}
