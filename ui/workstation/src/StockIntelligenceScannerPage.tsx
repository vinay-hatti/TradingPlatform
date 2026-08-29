import { Fragment, useEffect, useMemo, useState } from 'react';
import { stockIntelligenceApi } from './api';
import type { StockIntelligenceCandidate } from './types';
import './volume_response_evidence.css';

const timeframeOrder = ['5m', '15m', '30m', '1h', '1d', '1w', '1mo'];
// M75.2.1 compatibility marker retained after M76 Volume column expansion: colSpan={15}
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

type TradePlanView = {
  status: 'CERTIFIED' | 'NOT_CERTIFIED' | 'NOT_EVALUATED';
  failureDomains: string[];
};

const TRADE_PLAN_FILTER_VALUES = [
  'CERTIFIED',
  'NOT_CERTIFIED',
  'NOT_EVALUATED',
  'FAILED_MARKET',
  'FAILED_GEOMETRY',
  'FAILED_STRATEGY',
  'FAILED_RISK',
  'FAILED_EXECUTION',
  'FAILED_MANAGEMENT',
  'FAILED_LIFECYCLE',
];

const tradePlanView = (record: StockIntelligenceCandidate): TradePlanView => {
  const certification: any = record.trade_plan_certification || null;
  const rawStatus = String(record.trade_plan_certification_status || certification?.status || '').trim().toUpperCase();
  const failureCodes: string[] = (certification?.failure_codes || []).map((value: unknown) => String(value || '').toUpperCase());
  const domainMap: Array<[string, string]> = [
    ['TPC-MKT-', 'MARKET'],
    ['TPC-GEO-', 'GEOMETRY'],
    ['TPC-STR-', 'STRATEGY'],
    ['TPC-RISK-', 'RISK'],
    ['TPC-EXEC-', 'EXECUTION'],
    ['TPC-MGMT-', 'MANAGEMENT'],
    ['TPC-LCY-', 'LIFECYCLE'],
    ['TPC-LIFE-', 'LIFECYCLE'],
  ];
  const failureDomains: string[] = Array.from(new Set<string>(failureCodes.flatMap((code: string) => {
    const match = domainMap.find(([prefix]) => code.startsWith(prefix));
    return match ? [match[1]] : [];
  })));
  if (!certification && !rawStatus) return { status: 'NOT_EVALUATED', failureDomains };
  if (rawStatus === 'PASS' || rawStatus === 'CERTIFIED') return { status: 'CERTIFIED', failureDomains };
  return { status: 'NOT_CERTIFIED', failureDomains };
};

const tradePlanMatchesFilter = (record: StockIntelligenceCandidate, filter: string) => {
  if (!filter) return true;
  const view = tradePlanView(record);
  if (filter === 'CERTIFIED' || filter === 'NOT_CERTIFIED' || filter === 'NOT_EVALUATED') return view.status === filter;
  if (filter.startsWith('FAILED_')) return view.status === 'NOT_CERTIFIED' && view.failureDomains.includes(filter.replace('FAILED_', ''));
  return true;
};

const tradePlanCell = (record: StockIntelligenceCandidate) => {
  const view = tradePlanView(record);
  const tone = view.status === 'CERTIFIED' ? 'positive' : view.status === 'NOT_CERTIFIED' ? 'negative' : 'neutral';
  const detail = view.status === 'NOT_CERTIFIED' && view.failureDomains.length
    ? ` · ${view.failureDomains[0]}${view.failureDomains.length > 1 ? ` +${view.failureDomains.length - 1}` : ''}`
    : '';
  return <span className={`candidate-status-pill ${tone}`}>{display(view.status)}{detail}</span>;
};

function MetricCard({ label, value, helper, tone = 'neutral' }: { label: string; value: string; helper?: string; tone?: string }) {
  return <div className={`candidate-metric-card ${tone}`}><span>{label}</span><b>{value}</b>{helper && <small>{helper}</small>}</div>;
}

function DecisionEvidenceCard({ label, score, status, primary, secondary, tone = 'neutral' }: { label: string; score?: number | null; status?: string; primary?: string; secondary?: string; tone?: string }) {
  return <div className={`decision-evidence-card ${tone}`}>
    <div className="decision-evidence-card-head"><span>{label}</span>{status && <em>{display(status)}</em>}</div>
    <div className="decision-evidence-card-value"><b>{score == null ? (primary || '—') : fmt(score, 1)}</b>{score != null && primary && <strong>{primary}</strong>}</div>
    {secondary && <small>{secondary}</small>}
  </div>;
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
  const referencePrice = record.underlying_reference_price == null ? null : Number(record.underlying_reference_price);
  const referenceTimestamp = record.underlying_reference_timestamp || record.snapshot_timestamp;
  const referenceAgeMinutes = referenceTimestamp ? Math.max(0, (Date.now() - new Date(referenceTimestamp).getTime()) / 60000) : null;
  const bullishPlan = String(record.direction || '').toUpperCase().includes('BULL');
  const bearishPlan = String(record.direction || '').toUpperCase().includes('BEAR');
  const entryStatus = (() => {
    if (referencePrice == null || record.entry_zone_low == null || record.entry_zone_high == null) return 'Reference unavailable';
    if (referencePrice >= record.entry_zone_low && referencePrice <= record.entry_zone_high) return 'Inside entry zone';
    if (referencePrice < record.entry_zone_low) return 'Below entry zone';
    if (referencePrice > record.entry_zone_high) return 'Above entry zone';
    return 'Reference unavailable';
  })();
  const certification:any = record.trade_plan_certification || detail.trade_plan?.certification || {};
  const certificationFailures:string[] = certification.failure_codes || [];
  const certificationFailureReasons:string[] = certification.failure_reasons || [];
  const idi:any = record.decision_intelligence || detail.decision_intelligence || {};
  const qualityVector:any = idi.quality_vector || {};
  const barrier:any = idi.barrier_probability || {};
  const outcomeProbability:any = record.outcome_probability || idi.outcome_probability || {};
  const outcomeAnalogs:any = outcomeProbability.analog_evidence || {};
  const outcomeContributions:any[] = outcomeProbability.feature_contributions || [];
  const evidenceRegistry:any[] = idi.evidence_registry || [];
  const idiExplain:any = idi.explainability || {};
  const tradeQualityBreakdown:any[] = idiExplain.trade_quality?.components || [];
  const readinessBreakdown:any[] = Object.entries(idiExplain.decision_readiness?.components || {}).map(([key,value]:any)=>({key,...value}));
  const capitalBreakdown:any[] = Object.entries(idiExplain.capital_priority?.components || {}).map(([key,value]:any)=>({key,...value}));
  const freshnessDetail:any = idiExplain.opportunity_freshness || {};
  const competition:any = idi.competition || {};
  const marketRank:any = record.decision_market_rank ?? competition.market_rank;
  const populationSize:any = record.decision_population_size ?? competition.population_size;
  const rankLabel = marketRank && populationSize ? `Rank #${marketRank} / ${populationSize}` : 'Rank unavailable';
  const topPercent = competition.top_percent ?? (marketRank && populationSize ? (Number(marketRank) / Number(populationSize)) * 100 : null);
  const zones = detail.structure_zones || [];
  const primarySupport = zones.find((zone: any) => zone.hierarchy === 'PRIMARY_STRUCTURE' && String(zone.zone_type).toUpperCase() === 'SUPPORT');
  const primaryResistance = zones.find((zone: any) => zone.hierarchy === 'PRIMARY_STRUCTURE' && String(zone.zone_type).toUpperCase() === 'RESISTANCE');
  const positives = [
    record.alignment_score >= 70 ? `Multi-timeframe alignment ${fmt(record.alignment_score, 0)}` : null,
    record.management_quality >= 70 ? `Management quality ${fmt(record.management_quality, 0)}` : null,
    record.relative_strength_grade && !['UNKNOWN', 'UNAVAILABLE'].includes(record.relative_strength_grade) ? `Relative strength ${display(record.relative_strength_grade)}` : null,
    record.participation_state && !['UNKNOWN', 'UNAVAILABLE', 'NEUTRAL'].includes(record.participation_state) ? display(record.participation_state) : null,
    record.institutional_volume_signal && !['UNKNOWN','UNAVAILABLE','NEUTRAL'].includes(record.institutional_volume_signal) ? `Volume ${display(record.institutional_volume_signal)} · RVOL ${fmt(record.relative_volume_1d,2)}×` : null,
    record.breakout_state && !['UNKNOWN', 'UNAVAILABLE', 'NONE'].includes(record.breakout_state) ? display(record.breakout_state) : null,
    record.market_regime && !['UNKNOWN', 'UNAVAILABLE'].includes(record.market_regime) ? `Market regime ${display(record.market_regime)}` : null,
  ].filter(Boolean) as string[];
  const volumeResponse:any = detail.volume_response_interpretation || {};
  const volumeEvidence:any = volumeResponse.evidence || {};
  const volumeReasons:string[] = volumeResponse.reason_codes || [];
  const volumeImplicationTone = ['BULLISH','BULLISH_CONFIRMATION','BULLISH_LEAN','BULLISH_REVERSAL_WATCH','CONSTRUCTIVE_AWAITING_BREAKOUT_CONFIRMATION'].includes(String(volumeResponse.directional_implication || '')) ? 'positive' : ['BEARISH','BEARISH_WARNING','BEARISH_CAUTION'].includes(String(volumeResponse.directional_implication || '')) ? 'negative' : 'neutral';
  const risks = [...record.warnings];
  if (record.confidence < 65) risks.push('Confidence is below the preferred institutional threshold');
  if (record.structural_reward_risk < 1.5) risks.push('Structural reward/risk is below 1.5');
  if (record.freshness < 70) risks.push('The published setup may be aging');
  if (primaryResistance?.distance_pct != null && primaryResistance.distance_pct > 0 && primaryResistance.distance_pct < 2) risks.push('Primary resistance is less than 2% overhead');

  return <div className="candidate-workspace">
    <section className="candidate-summary-band">
      <div className="candidate-summary-title"><div><span className="candidate-symbol">{record.symbol}</span><StatusPill value={record.primary_category}/></div><h3>{conviction(record)}</h3><p>{display(record.direction)} · {display(record.structure)} · {record.primary_timeframe || 'Primary timeframe not published'}</p></div>
      <div className="candidate-summary-metrics">
        <MetricCard label="Institutional grade" value={display(record.institutional_grade || idi.institutional_grade)} helper={`${rankLabel}${topPercent == null ? '' : ` · Top ${fmt(topPercent, 1)}%`}`} tone={(record.institutional_grade || '').startsWith('A') ? 'positive' : 'accent'}/>
        <MetricCard label="Trade quality" value={fmt(record.institutional_trade_quality ?? idi.overall_trade_quality, 1)} helper={rankLabel} tone="accent"/>
        <MetricCard label="Decision readiness" value={fmt(record.decision_readiness ?? idi.decision_readiness, 1)} helper={`${display(record.opportunity_lifecycle || idi.opportunity_lifecycle)} · ${display(record.institutional_decision || idi.decision)}`} />
        <MetricCard label="Capital priority" value={fmt(record.capital_priority ?? idi.capital_priority, 1)} helper={`${rankLabel} · Freshness ${fmt(record.opportunity_freshness ?? idi.opportunity_freshness, 1)}`} />
      </div>
    </section>

    <section className="candidate-section"><div className="candidate-section-heading"><div><h4>Market alignment</h4><p>External context supporting or challenging the setup.</p></div></div>
      <div className="candidate-context-grid">
        <MetricCard label="Market regime" value={display(record.market_regime)} tone={directionTone(record.market_regime)} />
        <MetricCard label="Relative strength" value={display(record.relative_strength_grade)} tone={directionTone(record.relative_strength_grade)} />
        <MetricCard label="Dealer positioning" value={display(record.dealer_positioning)} tone={directionTone(record.dealer_positioning)} />
        <MetricCard label="Gamma regime" value={display(record.gamma_regime)} tone={directionTone(record.gamma_regime)} />
        <MetricCard label="Participation" value={display(record.participation_state)} tone={directionTone(record.participation_state)} />
        <MetricCard label="Institutional volume" value={fmt(record.institutional_volume_score, 1)} helper={display(record.institutional_volume_signal)} tone={directionTone(record.institutional_volume_signal)} />
        <MetricCard label="Volume regime" value={display(record.institutional_volume_regime)} helper={`RVOL ${fmt(record.relative_volume_1d, 2)}×`} tone={directionTone(record.institutional_volume_signal)} />
        <MetricCard label="Volume persistence" value={fmt(record.volume_persistence_score, 1)} helper={`Dry-up ${fmt(record.volume_dry_up_score, 1)} · Absorption ${fmt(record.volume_absorption_score, 1)}`} />
        <MetricCard label="Freshness" value={fmt(record.freshness, 1)} />
      </div>
      {volumeResponse.classification && <div className="candidate-disclosure-body"><div className="candidate-context-grid">
        <MetricCard label="Volume response class" value={display(volumeResponse.classification)} helper={`Raw signal ${display(volumeResponse.raw_volume_signal)}`} tone={volumeImplicationTone} />
        <MetricCard label="Directional implication" value={display(volumeResponse.directional_implication)} helper={`Interpretation confidence ${fmt(volumeResponse.confidence, 1)}%`} tone={volumeImplicationTone} />
        <MetricCard label="Structural location" value={display(volumeResponse.location_context)} helper={volumeResponse.resistance_distance_pct != null ? `Resistance ${fmt(volumeResponse.nearest_resistance,2)} · ${fmt(volumeResponse.resistance_distance_pct,2)}% overhead` : volumeResponse.support_distance_pct != null ? `Support ${fmt(volumeResponse.nearest_support,2)} · ${fmt(volumeResponse.support_distance_pct,2)}% below` : 'No nearby published level'} />
        <MetricCard label="Price response" value={display(volumeResponse.price_response)} helper={`CLV ${fmt(volumeEvidence.close_location_value,2)} · 1d ${fmt(Number(volumeEvidence.price_change_1d || 0)*100,2)}%`} tone={volumeImplicationTone} />
      </div>
      {volumeReasons.length > 0 && <div className="candidate-risk-panel"><b>Institutional volume response evidence</b><div className="volume-response-evidence-grid">{volumeReasons.map((reason:string)=>{
        const normalized = String(reason || '').toUpperCase();
        const evidenceTone = /NEGATIVE|FAILED|REJECTED|DISTRIBUTION|WEAK|BREAKDOWN|EXHAUSTION/.test(normalized) ? 'negative' : /POSITIVE|ACCUMULATION|UPPER_RANGE|ABSORBED|CONFIRMED|STRONG_CLOSE/.test(normalized) ? 'positive' : 'neutral';
        const label = display(reason).replace(/ LE 1PCT/gi, ' · ≤1%').replace(/ 20D/gi, ' · 20D').replace(/ 1D/gi, ' · 1D');
        return <span key={reason} className={`volume-response-evidence-chip ${evidenceTone}`}>{label}</span>;
      })}</div></div>}
      <div className="candidate-risk-panel interpretation-boundary-panel"><b>Interpretation boundary</b><div><span>This response classifier is presentation-only. It does not change Stock Intelligence score, ranking, trade-plan certification, M64 allocation, or execution authority.</span></div></div>
      </div>}
    </section>

    <section className="candidate-section"><div className="candidate-section-heading"><div><h4>Multi-timeframe alignment</h4><p>Trend, market structure, and confidence across published horizons.</p></div><MetricCard label="Alignment score" value={fmt(record.alignment_score, 1)} /></div>
      <div className="candidate-timeframe-table"><div className="candidate-timeframe-header"><span>Timeframe</span><span>Trend</span><span>Structure</span><span>Confidence</span></div>
        {timeframeEntries.map(([timeframe, value]: any) => <div className="candidate-timeframe-row" key={timeframe}><b>{timeframe === '1mo' ? '1 month' : timeframe}</b><StatusPill value={value.direction}/><span>{display(value.structure)}</span><strong>{fmt(value.confidence, 0)}%</strong></div>)}
      </div>
    </section>

    <section className="candidate-section"><div className="candidate-section-heading"><div><h4>Institutional decision intelligence</h4><p>Deterministic M76.2 trade-quality, readiness, barrier-probability, and opportunity-competition evidence. Barrier probabilities are uncalibrated priors until outcome learning is promoted.</p></div><MetricCard label="Decision" value={display(record.institutional_decision || idi.decision)} helper={`Passport ${idi.passport_id || '—'}`} tone={(record.institutional_decision || idi.decision) === 'PRIORITIZE' ? 'positive' : 'accent'} /></div>
      <div className="candidate-context-grid">
        <MetricCard label="Trade quality" value={fmt(record.institutional_trade_quality ?? idi.overall_trade_quality, 1)} helper={`${display(record.institutional_grade || idi.institutional_grade)} · ${rankLabel}`} tone="accent" />
        <MetricCard label="Decision readiness" value={fmt(record.decision_readiness ?? idi.decision_readiness, 1)} helper={`${display(record.opportunity_lifecycle || idi.opportunity_lifecycle)} · ${display(record.institutional_decision || idi.decision)}`} />
        <MetricCard label="Capital priority" value={fmt(record.capital_priority ?? idi.capital_priority, 1)} helper={rankLabel} />
        <MetricCard label="Opportunity freshness" value={fmt(record.opportunity_freshness ?? idi.opportunity_freshness, 1)} helper={topPercent == null ? 'Population rank unavailable' : `Top ${fmt(topPercent, 1)}% of current population`} />
        <MetricCard label="P(Target 1 before stop)" value={`${fmt(record.barrier_target_1_probability ?? barrier.target_1_before_stop, 1)}%`} helper="Uncalibrated deterministic prior" />
        <MetricCard label="P(Target 2 before stop)" value={`${fmt(record.barrier_target_2_probability ?? barrier.target_2_before_stop, 1)}%`} helper="Uncalibrated deterministic prior" />
        <MetricCard label="P(Target 3 before stop)" value={`${fmt(record.barrier_target_3_probability ?? barrier.target_3_before_stop, 1)}%`} helper="Uncalibrated deterministic prior" />
        <MetricCard label="Expected excursion" value={`MFE ${fmt(record.expected_mfe_pct ?? barrier.expected_mfe_pct, 1)}%`} helper={`MAE ${fmt(record.expected_mae_pct ?? barrier.expected_mae_pct, 1)}% · Hold ${barrier.expected_holding_days ?? '—'}d`} />
        <MetricCard label="Learning mode" value={display(idi.learning_snapshot?.mode || 'SHADOW_CAPTURE')} helper="No adaptive ranking influence" />
      </div>
      {tradeQualityBreakdown.length > 0 && <details className="candidate-disclosure"><summary>Trade quality breakdown ({tradeQualityBreakdown.length})</summary><div className="candidate-disclosure-body"><div className="decision-evidence-grid">{tradeQualityBreakdown.map((item:any)=><DecisionEvidenceCard key={item.key} label={display(item.key)} score={item.score} primary={`Contribution ${fmt(item.contribution,1)}`} secondary={`Weight ${fmt(Number(item.weight)*100,1)}%`} tone={Number(item.score)>=80?'positive':Number(item.score)<60?'negative':'neutral'} />)}</div></div></details>}
      {readinessBreakdown.length > 0 && <details className="candidate-disclosure"><summary>Decision readiness breakdown</summary><div className="candidate-disclosure-body"><div className="decision-evidence-grid">{readinessBreakdown.map((item:any)=><DecisionEvidenceCard key={item.key} label={display(item.key)} score={item.score} primary={`Contribution ${fmt(item.contribution,1)}`} secondary={`Weight ${fmt(Number(item.weight)*100,1)}%`} tone={Number(item.score)>=80?'positive':Number(item.score)<60?'negative':'neutral'} />)}</div></div></details>}
      {capitalBreakdown.length > 0 && <details className="candidate-disclosure"><summary>Capital priority breakdown · {rankLabel}</summary><div className="candidate-disclosure-body"><div className="decision-evidence-grid">{capitalBreakdown.map((item:any)=><DecisionEvidenceCard key={item.key} label={display(item.key)} score={item.score} primary={`Contribution ${fmt(item.contribution,1)}`} secondary={`Weight ${fmt(Number(item.weight)*100,1)}%`} tone={Number(item.score)>=80?'positive':Number(item.score)<60?'negative':'neutral'} />)}</div></div></details>}
      <details className="candidate-disclosure"><summary>Freshness & barrier diagnostics</summary><div className="candidate-disclosure-body"><div className="decision-evidence-grid"><DecisionEvidenceCard label="Market rank" primary={rankLabel} secondary={topPercent == null ? undefined : `Top ${fmt(topPercent,1)}%`} tone="accent"/><DecisionEvidenceCard label="Opportunity freshness" score={record.opportunity_freshness ?? idi.opportunity_freshness} primary={`${fmt(freshnessDetail.extension_atr,2)} ATR extension`} secondary={`Aging penalty ${fmt(freshnessDetail.aging_penalty,1)}`} tone="positive"/><DecisionEvidenceCard label="Reference price" primary={freshnessDetail.reference_price == null ? '—' : `$${fmt(freshnessDetail.reference_price,2)}`} secondary={freshnessDetail.entry_zone ? `Entry ${fmt(freshnessDetail.entry_zone[0],2)}–${fmt(freshnessDetail.entry_zone[1],2)}` : undefined}/><DecisionEvidenceCard label="Target 1 before stop" score={barrier.target_1_before_stop} primary="Uncalibrated prior" secondary={display(barrier.model)}/><DecisionEvidenceCard label="Target 2 before stop" score={barrier.target_2_before_stop} primary="Uncalibrated prior" secondary={display(barrier.model)}/><DecisionEvidenceCard label="Target 3 before stop" score={barrier.target_3_before_stop} primary="Uncalibrated prior" secondary={display(barrier.model)}/><DecisionEvidenceCard label="Expected MFE" primary={barrier.expected_mfe_pct == null?'—':`${fmt(barrier.expected_mfe_pct,1)}%`} secondary={barrier.expected_mae_pct == null?undefined:`Expected MAE ${fmt(barrier.expected_mae_pct,1)}%`}/><DecisionEvidenceCard label="Expected holding" primary={barrier.expected_holding_days == null ? '—' : `${barrier.expected_holding_days} days`} secondary={`${display(barrier.calibration_status)} · ${display(barrier.model)}`} /></div></div></details>
      {evidenceRegistry.length > 0 && <details className="candidate-disclosure"><summary>Institutional evidence registry ({evidenceRegistry.length})</summary><div className="candidate-disclosure-body"><div className="decision-evidence-grid">{evidenceRegistry.map((item:any,index:number)=><DecisionEvidenceCard key={`${item.key}-${index}`} label={item.label || display(item.key)} score={item.score} status={item.status} primary={item.details?.extension_atr != null ? `Extension ${fmt(item.details.extension_atr,2)} ATR` : undefined} secondary={item.details?.note || (item.details?.extension_atr != null ? 'Opportunity aging evidence' : 'Governed deterministic evidence')} tone={String(item.status||'').includes('STRONG')?'positive':String(item.status||'').includes('WEAK')?'negative':'neutral'} />)}</div></div></details>}
    </section>

    <section className="candidate-section"><div className="candidate-section-heading"><div><h4>M77 outcome probability</h4><p>Chronologically evaluated meta-label, path, uncertainty, and analog evidence. M77 remains shadow-only and cannot change M76 ranking, M64 allocation, certification, or trade authority.</p></div><MetricCard label="Shadow disposition" value={display(outcomeProbability.recommended_disposition || 'ABSTAIN')} helper={display(outcomeProbability.status || 'SHADOW_NOT_READY')} tone={outcomeProbability.recommended_disposition === 'TRADE' ? 'positive' : outcomeProbability.recommended_disposition === 'ABSTAIN' ? 'negative' : 'accent'} /></div>
      <div className="candidate-context-grid">
        <MetricCard label="P(Target 1 before stop)" value={outcomeProbability.target_1_before_stop == null ? '—' : `${fmt(outcomeProbability.target_1_before_stop,1)}%`} helper={display(outcomeProbability.calibration_status || 'NOT_AVAILABLE')} />
        <MetricCard label="P(Target 2 before stop)" value={outcomeProbability.target_2_before_stop == null ? '—' : `${fmt(outcomeProbability.target_2_before_stop,1)}%`} helper="Out-of-sample shadow estimate" />
        <MetricCard label="P(Profitable at horizon)" value={outcomeProbability.profitable_at_horizon == null ? '—' : `${fmt(outcomeProbability.profitable_at_horizon,1)}%`} helper="30-session governed horizon" />
        <MetricCard label="P(Thesis invalidation)" value={outcomeProbability.thesis_invalidation == null ? '—' : `${fmt(outcomeProbability.thesis_invalidation,1)}%`} helper="Structural stop before Target 1" />
        <MetricCard label="Expected value" value={outcomeProbability.expected_value_r == null ? '—' : `${fmt(outcomeProbability.expected_value_r,2)}R`} helper="Structural reward/risk basis" />
        <MetricCard label="Model confidence" value={`${fmt(outcomeProbability.model_confidence,1)}%`} helper={outcomeProbability.model_version || 'No approved shadow model'} />
        <MetricCard label="Epistemic uncertainty" value={fmt(Number(outcomeProbability.epistemic_uncertainty || 0)*100,1)} helper="Lower is better" />
        <MetricCard label="Out-of-distribution" value={fmt(Number(outcomeProbability.out_of_distribution_score || 0)*100,1)} helper="Distance from training evidence" />
        <MetricCard label="Expected MFE / MAE" value={outcomeProbability.expected_mfe_pct == null ? '—' : `${fmt(outcomeProbability.expected_mfe_pct,1)}% / ${fmt(outcomeProbability.expected_mae_pct,1)}%`} helper={outcomeProbability.expected_days_to_target_1 == null ? undefined : `${fmt(outcomeProbability.expected_days_to_target_1,1)} expected sessions to Target 1`} />
        <MetricCard label="Historical analogs" value={outcomeAnalogs.sample_size ?? 0} helper={outcomeAnalogs.target_1_before_stop_rate_pct == null ? display(outcomeAnalogs.status || 'NO_ANALOGS') : `${fmt(outcomeAnalogs.target_1_before_stop_rate_pct,1)}% reached Target 1 before stop`} />
      </div>
      {outcomeContributions.length > 0 && <details className="candidate-disclosure"><summary>M77 feature contributions ({outcomeContributions.length})</summary><div className="candidate-disclosure-body"><div className="decision-evidence-grid">{outcomeContributions.map((item:any)=><DecisionEvidenceCard key={item.feature} label={display(item.feature)} primary={`Log-odds ${Number(item.log_odds_contribution)>=0?'+':''}${fmt(item.log_odds_contribution,3)}`} secondary={`Standardized ${fmt(item.standardized_value,2)} · coefficient ${fmt(item.coefficient,3)}`} tone={Number(item.log_odds_contribution)>=0?'positive':'negative'} />)}</div></div></details>}
      <div className="candidate-risk-panel"><b>Shadow governance</b><div><span>M77 recommendations are evidence only. Automatic activation and adaptive ranking influence are disabled.</span>{(outcomeProbability.warnings||[]).map((warning:string)=><span key={warning}>⚠ {display(warning)}</span>)}</div></div>
    </section>

    {detail.cyclical_seasonality && (() => { const cycles:any=detail.cyclical_seasonality; const cal:any=cycles.calendar_state||{}; const research:any=cycles.research_summary||{}; const matches:any[]=cycles.current_walk_forward_matches||[]; const alignment=String(cycles.thesis_alignment||'NO_CURRENT_WALK_FORWARD_MATCH'); const tone=alignment.startsWith('CONFIRMING')?'positive':alignment.startsWith('CONFLICTING')?'negative':'neutral'; return <section className="candidate-section"><div className="candidate-section-heading"><div><h4>Cycles &amp; seasonality intelligence</h4><p>Current calendar-position evidence mapped to frozen M77 walk-forward research. Research annotation only; zero production score, ranking, certification, allocation, execution, or trade-authority effect.</p></div><MetricCard label="Governance" value="RESEARCH ONLY" helper="Not shadow certified" tone="accent" /></div><div className="candidate-context-grid"><MetricCard label="Thesis alignment" value={display(alignment)} helper={`${cycles.confirming_match_count||0} confirming · ${cycles.conflicting_match_count||0} conflicting`} tone={tone}/><MetricCard label="Week of month" value={cal.week_of_month||'—'} helper={`As of ${cycles.as_of||'—'}`}/><MetricCard label="Month" value={cal.month||'—'} helper="Calendar seasonality"/><MetricCard label="Quarter" value={cal.quarter||'—'} helper="Calendar seasonality"/><MetricCard label="Current WF matches" value={String(cycles.current_match_count||0)} helper="20d / 60d research histories"/><MetricCard label="Walk-forward universe" value={String(research.walk_forward_supported??0)} helper={`${research.supported_20d??0} at 20d · ${research.supported_60d??0} at 60d`}/><MetricCard label="Shadow Tier 1" value={String(research.shadow_certified_tier_1??0)} helper="Strict fold-native gate"/><MetricCard label="Shadow Tier 2" value={String(research.shadow_certified_tier_2??0)} helper={`${research.not_shadow_certified??0} not certified`}/></div>{matches.length>0?<details className="candidate-disclosure"><summary>Current walk-forward-supported calendar evidence ({matches.length})</summary><div className="candidate-disclosure-body"><div className="decision-evidence-grid">{matches.map((item:any,index:number)=><DecisionEvidenceCard key={`${item.factor}-${item.state}-${item.direction}-${item.horizon}-${index}`} label={`${display(item.factor)} · ${item.state}`} status={item.alignment} primary={`${item.horizon}d · ${display(item.direction)}`} secondary={`Min N ${item.minimum_passed_holdout_n??'—'} · return ${item.minimum_passed_holdout_thesis_return_pct==null?'—':`${fmt(item.minimum_passed_holdout_thesis_return_pct,2)}%`} · hit ${item.minimum_passed_holdout_hit_rate_pct==null?'—':`${fmt(item.minimum_passed_holdout_hit_rate_pct,1)}%`} · ${item.full_year_passed??0}/${item.full_year_holdouts??0} full-year`} tone={item.alignment==='CONFIRMING'?'positive':item.alignment==='CONFLICTING'?'negative':'neutral'}/>)}</div></div></details>:<div className="candidate-risk-panel"><b>No current walk-forward calendar match</b><div><span>Absence of a current match is not bearish evidence.</span></div></div>}<div className="candidate-risk-panel"><b>Cycles &amp; seasonality governance</b><div><span>188 histories passed walk-forward research, but zero survived strict fold-native shadow certification.</span><span>Next gate: {display(cycles.governance?.next_required_gate)}</span></div></div></section>; })()}

    <section className="candidate-section"><div className="candidate-section-heading"><div><h4>Dynamic trade plan</h4><p>Underlying-based execution and management levels with latest-ingestion reference context.</p></div><MetricCard label="Structural R/R" value={fmt(record.structural_reward_risk, 2)} /></div>
      <div className="candidate-context-grid">
        <MetricCard label="Underlying reference" value={referencePrice == null ? '—' : `$${fmt(referencePrice)}`} helper="Latest underlying ingestion" tone={referencePrice == null ? 'negative' : 'accent'} />
        <MetricCard label="Reference as of" value={referenceTimestamp ? new Date(referenceTimestamp).toLocaleString() : '—'} helper={referenceAgeMinutes == null ? 'Freshness unavailable' : `Age ${referenceAgeMinutes < 60 ? `${fmt(referenceAgeMinutes, 0)} min` : `${fmt(referenceAgeMinutes / 60, 1)} hr`}`} />
        <MetricCard label="Entry status" value={entryStatus} tone={entryStatus === 'Inside entry zone' ? 'positive' : 'neutral'} />
        <MetricCard label="Trade plan certification" value={String(record.trade_plan_certification_status || certification.status || 'NOT CERTIFIED').replaceAll('_',' ')} helper={`M75.2 quality ${record.trade_plan_quality_score == null ? '—' : fmt(record.trade_plan_quality_score, 0)}`} tone={(record.trade_plan_certification_status || certification.status) === 'PASS' ? 'positive' : 'negative'} />
      </div>
      {certificationFailures.length > 0 && <div className="candidate-risk-panel"><b>Certification failures</b><div>{certificationFailures.map((code:string,index:number)=><span key={`${code}-${index}`}><b>{code}:</b> {certificationFailureReasons[index] || 'Certification rule failed.'}</span>)}</div></div>}
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
  const options = useMemo(() => ({ symbol: unique(records.map(record => record.symbol)), category: unique(records.map(record => record.primary_category)), direction: unique(records.map(record => record.direction)), structure: unique(records.map(record => record.structure)), participation: unique(records.map(record => record.participation_state)), volume: unique(records.map(record => record.institutional_volume_signal)), breakout: unique(records.map(record => record.breakout_state)), grade: unique(records.map(record => record.institutional_grade || '')) }), [records]);
  const visible = useMemo(() => records.filter(record => {
    if (search && !record.symbol.toUpperCase().includes(search.trim().toUpperCase())) return false;
    if (record.score < minScore || record.confidence < minConfidence) return false;
    const pairs: Record<string, string> = { symbol: record.symbol, category: record.primary_category, direction: record.direction, structure: record.structure, participation: record.participation_state, volume: record.institutional_volume_signal, breakout: record.breakout_state, grade: record.institutional_grade || '' };
    if (Object.entries(filters).some(([key, value]) => value && key !== 'trade_plan' && key in pairs && pairs[key] !== value)) return false;
    if (!tradePlanMatchesFilter(record, filters.trade_plan || '')) return false;
    if (filters.trade_quality && Number(record.institutional_trade_quality || 0) < Number(filters.trade_quality)) return false; if (filters.readiness && Number(record.decision_readiness || 0) < Number(filters.readiness)) return false; if (filters.score && record.score < Number(filters.score)) return false; if (filters.confidence && record.confidence < Number(filters.confidence)) return false; if (filters.alignment && record.alignment_score < Number(filters.alignment)) return false; if (filters.rr && record.structural_reward_risk < Number(filters.rr)) return false;
    return true;
  }), [records, search, minScore, minConfidence, filters]);
  const setFilter = (key: string, value: string) => setFilters(current => ({ ...current, [key]: value }));
  const toggle = async (record: StockIntelligenceCandidate) => { const next = expandedId === record.candidate_id ? null : record.candidate_id; setExpandedId(next); if (next && !details[next]) { try { const response = await stockIntelligenceApi.candidate(next); setDetails(current => ({ ...current, [next]: response.data })); } catch (caught: any) { setError(caught.message); } } };
  const headerSelect = (key: string, values: string[], label = 'All') => <select aria-label={`${key} filter`} value={filters[key] || ''} onChange={event => setFilter(key, event.target.value)} onClick={event => event.stopPropagation()}><option value="">{label}</option>{values.map(value => <option key={value} value={value}>{display(value)}</option>)}</select>;

  return <section className="stock-intelligence-page"><div className="page-title"><div><h2>Stock Intelligence Scanner</h2><p>Published equities, ETFs, and indexes with explainable multi-timeframe intelligence and underlying-driven trade management.</p></div><button className="primary" onClick={load} disabled={busy}>{busy ? 'Loading…' : 'Refresh publication'}</button></div>
    {error && <div className="handoff-message">{error}</div>}
    <article className="panel stock-publication-info"><h3>Publication details</h3><div className="stock-publication-grid"><div><span>Name</span><b>{publication?.publication_name || 'current_stock_intelligence'}</b></div><div><span>Status</span><b>{display(publication?.status)}</b></div><div><span>Published snapshot</span><b>{publication?.snapshot_timestamp ? new Date(publication.snapshot_timestamp).toLocaleString() : 'Not published'}</b></div><div><span>Scanner run</span><b>{publication?.scanner_run_id || 'Not published'}</b></div><div><span>Published rows</span><b>{records.length}</b></div></div></article>
    <article className="panel"><div className="scanner-form stock-intelligence-controls"><label>Search<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Symbol"/></label><label>Min score<input type="number" value={minScore} onChange={event => setMinScore(Number(event.target.value))}/></label><label>Min confidence<input type="number" value={minConfidence} onChange={event => setMinConfidence(Number(event.target.value))}/></label><button onClick={() => { setSearch(''); setMinScore(0); setMinConfidence(0); setFilters({}); }}>Clear all filters</button></div></article>
    <article className="panel stock-intelligence-table"><h3>Published candidates <small>{visible.length} of {records.length}</small></h3><div className="table-wrap"><table><thead><tr><th>Rank</th><th>Symbol</th><th>Category</th><th>Trade plan</th><th>Grade</th><th>Trade quality</th><th>Readiness</th><th>Score</th><th>Confidence</th><th>Direction</th><th>Structure</th><th>Alignment</th><th>Participation</th><th>Volume</th><th>Breakout</th><th>Entry</th><th>Stop</th><th>Targets</th><th>R/R</th></tr><tr className="stock-filter-row"><th></th><th>{headerSelect('symbol', options.symbol)}</th><th>{headerSelect('category', options.category)}</th><th>{headerSelect('trade_plan', TRADE_PLAN_FILTER_VALUES)}</th><th>{headerSelect('grade', options.grade)}</th><th>{headerSelect('trade_quality', ['90', '85', '80', '75', '70'], 'Any')}</th><th>{headerSelect('readiness', ['90', '85', '80', '75', '70'], 'Any')}</th><th>{headerSelect('score', ['90', '80', '70', '60'], 'Any')}</th><th>{headerSelect('confidence', ['90', '80', '70', '60'], 'Any')}</th><th>{headerSelect('direction', options.direction)}</th><th>{headerSelect('structure', options.structure)}</th><th>{headerSelect('alignment', ['90', '80', '70', '60'], 'Any')}</th><th>{headerSelect('participation', options.participation)}</th><th>{headerSelect('volume', options.volume)}</th><th>{headerSelect('breakout', options.breakout)}</th><th></th><th></th><th></th><th>{headerSelect('rr', ['3', '2', '1.5', '1'], 'Any')}</th></tr></thead><tbody>{visible.map(record => { const expanded = expandedId === record.candidate_id; return <Fragment key={record.candidate_id}><tr className={expanded ? 'selected-row' : ''} onClick={() => toggle(record)}><td>{record.rank ?? '—'}</td><td><b>{record.symbol}</b></td><td>{display(record.primary_category)}</td><td>{tradePlanCell(record)}</td><td><span className={`candidate-status-pill ${(record.institutional_grade || '').startsWith('A') ? 'positive' : 'neutral'}`}>{display(record.institutional_grade)}</span></td><td>{fmt(record.institutional_trade_quality, 1)}</td><td>{fmt(record.decision_readiness, 1)}</td><td>{fmt(record.score, 1)}</td><td>{fmt(record.confidence, 1)}</td><td>{display(record.direction)}</td><td>{display(record.structure)}</td><td>{fmt(record.alignment_score, 1)}</td><td>{display(record.participation_state)}</td><td><span className={`candidate-status-pill ${directionTone(record.institutional_volume_signal)}`}>{display(record.institutional_volume_signal)} · {fmt(record.relative_volume_1d,2)}×</span></td><td>{display(record.breakout_state)}</td><td>{fmt(record.entry_zone_low)}–{fmt(record.entry_zone_high)}</td><td>{fmt(record.recommended_stop)}</td><td>{record.targets.filter(value => value != null).map(value => fmt(value)).join(' / ') || '—'}</td><td>{fmt(record.structural_reward_risk, 2)}</td></tr>{expanded && <tr className="stock-expanded-row"><td colSpan={19}><CandidateWorkspace record={record} detail={details[record.candidate_id] || {}}/></td></tr>}</Fragment>; })}</tbody></table></div></article>
  </section>;
}
