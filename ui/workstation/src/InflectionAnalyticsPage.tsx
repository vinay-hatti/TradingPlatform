import { Fragment, useEffect, useMemo, useState } from 'react';
import { analyticsDashboardApi } from './api';
import {
  AnalyticsMetric,
  DistributionBars,
  Histogram,
  fmt,
} from './AnalyticsShared';

type ScoreBand = { label: string; minimum: number; maximum: number } | null;
type CategoricalFilters = Record<string, string>;

const toggle = (current: string | null, next: string) =>
  current === next ? null : next;

const headerFilterStyle = {
  width: '100%',
  minHeight: 24,
  marginTop: 5,
  padding: '2px 4px',
  border: '1px solid var(--border)',
  borderRadius: 5,
  background: 'var(--panel-2)',
  color: 'var(--text)',
  fontSize: 10,
};

const cellStyle = {
  padding: '10px 9px',
  borderBottom: '1px solid var(--border)',
  textAlign: 'left' as const,
  verticalAlign: 'top' as const,
  whiteSpace: 'nowrap' as const,
};

const HEADER_FILTER_FIELDS = [
  ['symbol', 'Symbol'],
  ['company_name', 'Company'],
  ['direction', 'Direction'],
  ['transition_state', 'Transition'],
  ['disposition', 'Disposition'],
  ['sector', 'Sector'],
  ['opportunity_state', 'Opportunity state'],
  ['coverage_status', 'Coverage'],
  ['source_as_of_date', 'Source as of'],
] as const;

const thresholdOptions = [0, 40, 50, 60, 70, 80, 90];

const distinctValues = (rows: any[], key: string) =>
  Array.from(new Set(
    rows
      .map(row => String(row?.[key] ?? '').trim())
      .filter(Boolean),
  )).sort((left, right) => left.localeCompare(right));

const visibleValue = (value: any) => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'YES' : 'NO';
  return String(value);
};

const directionalBandMatches = (value: any, band: string) => {
  if (!band) return true;
  const score = Number(value);
  if (!Number.isFinite(score)) return false;
  if (band === 'STRONG_BEARISH') return score <= -70;
  if (band === 'BEARISH') return score > -70 && score < -30;
  if (band === 'NEUTRAL') return score >= -30 && score <= 30;
  if (band === 'BULLISH') return score > 30 && score < 70;
  if (band === 'STRONG_BULLISH') return score >= 70;
  return true;
};

const minimumMatches = (value: any, minimum: string) => {
  const threshold = Number(minimum);
  if (!Number.isFinite(threshold) || threshold <= 0) return true;
  const numericValue = Number(value);
  return Number.isFinite(numericValue) && numericValue >= threshold;
};

function CandidateHeaderFilter({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return <th style={{
    ...cellStyle,
    padding: '7px 6px',
    verticalAlign: 'bottom',
    background: 'var(--panel-2)',
  }}>
    <span style={{
      display: 'block',
      color: 'var(--text-muted)',
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '.04em',
      textTransform: 'uppercase',
    }}>{label}</span>
    <select
      aria-label={`Filter ${label}`}
      value={value}
      onChange={event => onChange(event.target.value)}
      style={headerFilterStyle}
    >
      {options.map(option =>
        <option key={option.value || 'ALL'} value={option.value}>
          {option.label}
        </option>,
      )}
    </select>
  </th>;
}

function InlineCandidateDetail({ row }: { row: any }) {
  const sections = [
    {
      title: 'Inflection authority',
      fields: [
        ['Snapshot Id', row.snapshot_id],
        ['Symbol', row.symbol],
        ['Company', row.company_name],
        ['Direction', row.direction],
        ['Signed score', row.directional_score],
        ['Signal strength', row.signal_strength],
        ['Confidence', row.confidence],
        ['Input quality', row.input_quality],
        ['Disposition', row.disposition],
        ['Transition', row.transition_state],
        ['Coverage', row.coverage_status],
        ['Threshold gap', row.threshold_gap],
        ['Near high conviction', row.near_high_conviction],
      ],
    },
    {
      title: 'Institutional opportunity',
      fields: [
        ['Opportunity Id', row.opportunity_id],
        ['Opportunity state', row.opportunity_state],
        ['Opportunity category', row.opportunity_category],
        ['Opportunity score', row.opportunity_score],
        ['Conviction', row.conviction],
        ['Strategy', row.strategy],
        ['Market regime', row.market_regime],
        ['Primary timeframe', row.primary_timeframe],
        ['Invalidation level', row.invalidation_level],
        ['Entry zone low', row.entry_zone_low],
        ['Entry zone high', row.entry_zone_high],
      ],
    },
    {
      title: 'Exact lineage',
      fields: [
        ['Timeframe', row.timeframe],
        ['Sector', row.sector],
        ['Industry', row.industry],
        ['Asset class', row.asset_class],
        ['Source run Id', row.source_run_id],
        ['Source as of', row.source_as_of_date],
        ['Dealer as of', row.dealer_as_of_date],
        ['Option snapshot Id', row.option_snapshot_id],
        ['Inflection option snapshot Id', row.inflection_option_snapshot_id],
        ['Snapshot timestamp', row.snapshot_timestamp],
      ],
    },
  ];
  const evidence = Array.isArray(row.evidence) ? row.evidence : [];
  const conflicts = Array.isArray(row.conflicting_evidence)
    ? row.conflicting_evidence
    : [];

  return <div style={{
    padding: '10px 12px 12px',
    background: 'var(--panel-2)',
    borderLeft: '2px solid var(--accent)',
  }}>
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(3, minmax(250px, 1fr))',
      gap: '8px 22px',
      alignItems: 'start',
    }}>
      {sections.map(section => <section key={section.title}>
        <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>{section.title}</h4>
        <dl style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(105px, auto) 1fr',
          gap: '3px 10px',
          margin: 0,
          fontSize: 12,
          lineHeight: 1.35,
        }}>
          {section.fields.map(([label, value]) => <Fragment key={String(label)}>
            <dt style={{ color: 'var(--text-muted)' }}>{label}</dt>
            <dd style={{ margin: 0, overflowWrap: 'anywhere' }}>{visibleValue(value)}</dd>
          </Fragment>)}
        </dl>
      </section>)}
    </div>

    <section style={{ marginTop: 9, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
      <h4 style={{ margin: '0 0 5px', fontSize: 13 }}>Signed components</h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(95px, 1fr))', gap: 6 }}>
        {Object.entries(row.components ?? {}).map(([name, value]) =>
          <div key={name} style={{ padding: '4px 7px', background: 'var(--panel)', borderRadius: 5, fontSize: 11 }}>
            <span style={{ color: 'var(--text-muted)', marginRight: 6 }}>{name}</span>
            <strong style={{ fontSize: 12 }}>{fmt(value, 2)}</strong>
          </div>,
        )}
        {Object.keys(row.components ?? {}).length === 0 && <span>Unavailable</span>}
      </div>
    </section>

    <div style={{
      display: 'grid',
      gridTemplateColumns: conflicts.length > 0 ? '1fr 1fr' : '1fr',
      gap: 18,
      marginTop: 8,
      paddingTop: 7,
      borderTop: '1px solid var(--border)',
      fontSize: 12,
    }}>
      <section>
        <h4 style={{ margin: '0 0 4px', fontSize: 13 }}>Supporting evidence</h4>
        {evidence.length > 0
          ? <ul style={{ margin: 0, paddingLeft: 18, columns: evidence.length > 4 ? 2 : 1 }}>
            {evidence.map((item: any, index: number) =>
              <li key={`${index}-${String(item)}`}>{String(item)}</li>,
            )}
          </ul>
          : <span style={{ color: 'var(--text-muted)' }}>No supporting evidence recorded.</span>}
      </section>
      {conflicts.length > 0 && <section>
        <h4 style={{ margin: '0 0 4px', fontSize: 13 }}>Conflicting evidence</h4>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {conflicts.map((item: any, index: number) =>
            <li key={`${index}-${String(item)}`}>{String(item)}</li>,
          )}
        </ul>
      </section>}
    </div>
  </div>;
}

export function InflectionAnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [transition, setTransition] = useState<string | null>(null);
  const [direction, setDirection] = useState<string | null>(null);
  const [disposition, setDisposition] = useState<string | null>(null);
  const [sector, setSector] = useState<string | null>(null);
  const [strategy, setStrategy] = useState<string | null>(null);
  const [regime, setRegime] = useState<string | null>(null);
  const [scoreBand, setScoreBand] = useState<ScoreBand>(null);
  const [sortComponent, setSortComponent] = useState<string | null>(null);
  const [categoricalFilters, setCategoricalFilters] = useState<CategoricalFilters>({});
  const [directionalScoreBand, setDirectionalScoreBand] = useState('');
  const [minimumStrength, setMinimumStrength] = useState('0');
  const [minimumConfidence, setMinimumConfidence] = useState('0');
  const [minimumInputQuality, setMinimumInputQuality] = useState('0');
  const [minimumOpportunityScore, setMinimumOpportunityScore] = useState('0');
  const [expandedSnapshotId, setExpandedSnapshotId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    analyticsDashboardApi.inflection(5000, controller.signal)
      .then(response => {
        if (!controller.signal.aborted) {
          setData(response.data);
          setError('');
        }
      })
      .catch(reason => {
        if (
          controller.signal.aborted ||
          (reason instanceof DOMException && reason.name === 'AbortError')
        ) return;
        setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => controller.abort();
  }, []);

  const candidates = data?.candidates ?? [];
  const filterOptions = useMemo(() => Object.fromEntries(
    HEADER_FILTER_FIELDS.map(([key]) => [key, distinctValues(candidates, key)]),
  ), [candidates]);

  const chartFilterValue = (key: string) => {
    if (key === 'direction') return direction ?? '';
    if (key === 'transition_state') return transition ?? '';
    if (key === 'disposition') return disposition ?? '';
    if (key === 'sector') return sector ?? '';
    if (key === 'strategy') return strategy ?? '';
    if (key === 'market_regime') return regime ?? '';
    return categoricalFilters[key] ?? '';
  };

  const setFilterValue = (key: string, value: string) => {
    if (key === 'direction') setDirection(value || null);
    else if (key === 'transition_state') setTransition(value || null);
    else if (key === 'disposition') setDisposition(value || null);
    else if (key === 'sector') setSector(value || null);
    else if (key === 'strategy') setStrategy(value || null);
    else if (key === 'market_regime') setRegime(value || null);
    else setCategoricalFilters(current => ({ ...current, [key]: value }));
  };

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const rows = candidates.filter((row: any) =>
      (!normalizedQuery || String(row.symbol ?? '').toLowerCase().includes(normalizedQuery) ||
        String(row.company_name ?? '').toLowerCase().includes(normalizedQuery)) &&
      (!transition || row.transition_state === transition) &&
      (!direction || row.direction === direction) &&
      (!disposition || row.disposition === disposition) &&
      (!sector || row.sector === sector) &&
      (!strategy || row.strategy === strategy) &&
      (!regime || row.market_regime === regime) &&
      Object.entries(categoricalFilters).every(([key, value]) =>
        !value || String(row?.[key] ?? '') === value,
      ) &&
      directionalBandMatches(row.directional_score, directionalScoreBand) &&
      minimumMatches(row.signal_strength, minimumStrength) &&
      minimumMatches(row.confidence, minimumConfidence) &&
      minimumMatches(row.input_quality, minimumInputQuality) &&
      minimumMatches(row.opportunity_score, minimumOpportunityScore) &&
      (!scoreBand ||
        (Number(row.signal_strength) >= scoreBand.minimum &&
          Number(row.signal_strength) < scoreBand.maximum) ||
        (scoreBand?.maximum === 100 && Number(row.signal_strength) === 100))
    );
    if (!sortComponent) return rows;
    return [...rows].sort(
      (a, b) => Number(b.components?.[sortComponent] ?? -Infinity) -
        Number(a.components?.[sortComponent] ?? -Infinity),
    );
  }, [
    candidates, query, transition, direction, disposition, sector, strategy,
    regime, categoricalFilters, directionalScoreBand, minimumStrength,
    minimumConfidence, minimumInputQuality, minimumOpportunityScore, scoreBand,
    sortComponent,
  ]);

  const clear = () => {
    setQuery('');
    setTransition(null);
    setDirection(null);
    setDisposition(null);
    setSector(null);
    setStrategy(null);
    setRegime(null);
    setScoreBand(null);
    setSortComponent(null);
    setCategoricalFilters({});
    setDirectionalScoreBand('');
    setMinimumStrength('0');
    setMinimumConfidence('0');
    setMinimumInputQuality('0');
    setMinimumOpportunityScore('0');
    setExpandedSnapshotId(null);
  };
  const active = [
    query && `Search ${query}`,
    scoreBand && `Strength ${scoreBand.label}`,
    transition && `Transition ${transition}`,
    direction && `Direction ${direction}`,
    disposition && `Disposition ${disposition}`,
    sector && `Sector ${sector}`,
    strategy && `Strategy ${strategy}`,
    regime && `Regime ${regime}`,
    ...Object.entries(categoricalFilters)
      .filter(([, value]) => Boolean(value))
      .map(([key, value]) => `${HEADER_FILTER_FIELDS.find(([field]) => field === key)?.[1] ?? key} ${value}`),
    directionalScoreBand && `Signed score ${directionalScoreBand}`,
    Number(minimumStrength) > 0 && `Strength ≥ ${minimumStrength}`,
    Number(minimumConfidence) > 0 && `Confidence ≥ ${minimumConfidence}`,
    Number(minimumInputQuality) > 0 && `Input quality ≥ ${minimumInputQuality}`,
    Number(minimumOpportunityScore) > 0 && `Opportunity score ≥ ${minimumOpportunityScore}`,
    sortComponent && `Sorted by ${sortComponent}`,
  ].filter(Boolean) as string[];

  if (error) return <section className="analytics-page"><p className="provider-warning">{error}</p></section>;
  if (!data) return <section className="analytics-page"><p>Loading governed inflection analytics…</p></section>;

  const summary = data.summary ?? {};
  const governance = data.governance ?? {};
  const incomplete = governance.coverage_status !== 'COMPLETE';
  const shownRows = filtered.slice(0, 1000);
  const categoricalOptions = (key: string) => [
    { value: '', label: 'All' },
    ...(filterOptions[key] ?? []).map((value: string) => ({
      value,
      label: value,
    })),
  ];
  const minimumOptions = thresholdOptions.map(threshold => ({
    value: String(threshold),
    label: threshold === 0 ? 'Any' : `≥ ${threshold}`,
  }));
  return <section className="analytics-page">
    <div className="analytics-page-title">
      <div>
        <span className="eyebrow">Analytics</span>
        <h2>Inflection Analytics</h2>
        <p>Signed directional evidence, signal strength, input quality, semantic transitions, and exact authority lineage.</p>
      </div>
      <div className="publication-chip">
        <span>{summary.status}</span>
        <strong>{summary.source_run_id}</strong>
        <small>{summary.published_at}</small>
      </div>
    </div>

    <section className={incomplete ? 'provider-warning' : 'analytics-panel'}>
      <strong>Authority coverage: {governance.coverage_status ?? 'UNKNOWN'}</strong>
      <p>
        Source as of {governance.source_as_of_date ?? 'unavailable'} · option snapshot{' '}
        {governance.option_snapshot_id ?? 'unavailable'} · downstream attachment{' '}
        {governance.opportunity_attachment_policy ?? 'UNKNOWN'}
      </p>
      {incomplete && <p>Missing point-in-time breadth or options inputs are governed as ABSTAIN and do not influence downstream valuation, Trade Builder readiness, or autonomous management.</p>}
    </section>

    <div className="analytics-metric-grid">
      <AnalyticsMetric label="Symbols analyzed" value={fmt(summary.symbols_analyzed, 0)} />
      <AnalyticsMetric label="Average strength" value={fmt(summary.average_signal_strength, 2)} />
      <AnalyticsMetric label="Average direction" value={fmt(summary.average_directional_score, 2)} />
      <AnalyticsMetric label="High conviction" value={fmt(summary.high_conviction, 0)} />
      <AnalyticsMetric label="Actionable" value={fmt(summary.actionable, 0)} />
      <AnalyticsMetric label="Exact opportunity links" value={fmt(summary.exact_opportunity_attachments, 0)} />
    </div>

    <div className="analytics-grid analytics-grid-wide">
      <Histogram
        title="Signal-strength histogram"
        rows={data.histogram ?? []}
        markers={[
          { label: 'Watch', value: 60 },
          { label: 'Actionable', value: 70 },
          { label: 'High conviction', value: 80 },
        ]}
        selected={scoreBand?.label ?? null}
        onSelect={(row: any) => setScoreBand(
          scoreBand?.label === row.label ? null : {
            label: String(row.label),
            minimum: Number(row.minimum),
            maximum: Number(row.maximum),
          },
        )}
      />
      <section className="analytics-panel">
        <header><h3>Strength percentiles</h3></header>
        <div className="percentile-grid">
          {Object.entries(data.percentiles ?? {}).map(([name, value]) =>
            <div key={name}><span>{name.toUpperCase()}</span><strong>{fmt(value, 2)}</strong></div>,
          )}
        </div>
        <h4>Near high-conviction threshold</h4>
        <div className="threshold-list">
          {(data.near_threshold ?? []).map((row: any) =>
            <div key={row.name} role="button" tabIndex={0}
              onClick={() => setScoreBand({
                label: row.name,
                minimum: Number(row.minimum),
                maximum: Number(row.maximum),
              })}>
              <span>{row.name}</span><strong>{row.count}</strong>
            </div>,
          )}
        </div>
      </section>
    </div>

    <div className="analytics-grid">
      <DistributionBars title="Direction" rows={data.by_direction ?? []} selected={direction}
        onSelect={(row: any) => setDirection(toggle(direction, String(row.name)))} />
      <DistributionBars title="Disposition" rows={data.by_disposition ?? []} selected={disposition}
        onSelect={(row: any) => setDisposition(toggle(disposition, String(row.name)))} />
      <DistributionBars title="Semantic transition" rows={data.by_transition_state ?? []} selected={transition}
        onSelect={(row: any) => setTransition(toggle(transition, String(row.name)))} />
      <DistributionBars title="Sector" rows={data.by_sector ?? []} selected={sector}
        onSelect={(row: any) => setSector(toggle(sector, String(row.name)))} />
      <DistributionBars title="Strategy" rows={data.by_strategy ?? []} selected={strategy}
        onSelect={(row: any) => setStrategy(toggle(strategy, String(row.name)))} />
      <DistributionBars title="Market regime" rows={data.by_market_regime ?? []} selected={regime}
        onSelect={(row: any) => setRegime(toggle(regime, String(row.name)))} />
      <DistributionBars title="Signed component averages" rows={data.component_averages ?? []}
        valueLabel="average" selected={sortComponent}
        onSelect={(row: any) => setSortComponent(toggle(sortComponent, String(row.name)))} />
    </div>

    <section className="analytics-panel">
      <header className="table-header">
        <div>
          <h3>Candidate explorer</h3>
          <p>{filtered.length} governed candidates · select a row to expand its full evidence and lineage</p>
        </div>
        <div className="analytics-filters">
          <input value={query} onChange={event => setQuery(event.target.value)}
            placeholder="Search symbol or company" />
        </div>
      </header>

      {active.length > 0 && <div className="analytics-active-filters">
        {active.map(label => <span className="analytics-filter-chip" key={label}>{label}</span>)}
        <button className="analytics-clear-filters" onClick={clear}>Clear all filters</button>
      </div>}

      <div style={{ overflowX: 'auto', marginTop: active.length > 0 ? 8 : 12 }}>
        <table style={{ width: '100%', minWidth: 1500, borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ ...cellStyle, width: 22, padding: 5 }} aria-label="Expand row" />
              <CandidateHeaderFilter label="Symbol"
                value={chartFilterValue('symbol')}
                options={categoricalOptions('symbol')}
                onChange={value => setFilterValue('symbol', value)} />
              <CandidateHeaderFilter label="Company"
                value={chartFilterValue('company_name')}
                options={categoricalOptions('company_name')}
                onChange={value => setFilterValue('company_name', value)} />
              <CandidateHeaderFilter label="Direction"
                value={chartFilterValue('direction')}
                options={categoricalOptions('direction')}
                onChange={value => setFilterValue('direction', value)} />
              <CandidateHeaderFilter label="Signed score"
                value={directionalScoreBand}
                options={[
                  { value: '', label: 'All' },
                  { value: 'STRONG_BEARISH', label: '≤ -70' },
                  { value: 'BEARISH', label: '-70 to -30' },
                  { value: 'NEUTRAL', label: '-30 to 30' },
                  { value: 'BULLISH', label: '30 to 70' },
                  { value: 'STRONG_BULLISH', label: '≥ 70' },
                ]}
                onChange={setDirectionalScoreBand} />
              <CandidateHeaderFilter label="Strength"
                value={minimumStrength}
                options={minimumOptions}
                onChange={setMinimumStrength} />
              <CandidateHeaderFilter label="Confidence"
                value={minimumConfidence}
                options={minimumOptions}
                onChange={setMinimumConfidence} />
              <CandidateHeaderFilter label="Input quality"
                value={minimumInputQuality}
                options={minimumOptions}
                onChange={setMinimumInputQuality} />
              <CandidateHeaderFilter label="Disposition"
                value={chartFilterValue('disposition')}
                options={categoricalOptions('disposition')}
                onChange={value => setFilterValue('disposition', value)} />
              <CandidateHeaderFilter label="Transition"
                value={chartFilterValue('transition_state')}
                options={categoricalOptions('transition_state')}
                onChange={value => setFilterValue('transition_state', value)} />
              <CandidateHeaderFilter label="Sector"
                value={chartFilterValue('sector')}
                options={categoricalOptions('sector')}
                onChange={value => setFilterValue('sector', value)} />
              <CandidateHeaderFilter label="Opportunity score"
                value={minimumOpportunityScore}
                options={minimumOptions}
                onChange={setMinimumOpportunityScore} />
              <CandidateHeaderFilter label="Opportunity state"
                value={chartFilterValue('opportunity_state')}
                options={categoricalOptions('opportunity_state')}
                onChange={value => setFilterValue('opportunity_state', value)} />
              <CandidateHeaderFilter label="Coverage"
                value={chartFilterValue('coverage_status')}
                options={categoricalOptions('coverage_status')}
                onChange={value => setFilterValue('coverage_status', value)} />
              <CandidateHeaderFilter label="Source as of"
                value={chartFilterValue('source_as_of_date')}
                options={categoricalOptions('source_as_of_date')}
                onChange={value => setFilterValue('source_as_of_date', value)} />
            </tr>
          </thead>
          <tbody>
            {shownRows.map((row: any, index: number) => {
              const rowId = String(row.snapshot_id ?? `${row.symbol}-${index}`);
              const expanded = expandedSnapshotId === rowId;
              const toggleExpanded = () => setExpandedSnapshotId(expanded ? null : rowId);
              return <Fragment key={rowId}>
                <tr
                  role="button"
                  tabIndex={0}
                  aria-expanded={expanded}
                  onClick={toggleExpanded}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      toggleExpanded();
                    }
                  }}
                  style={{ cursor: 'pointer', background: expanded ? 'var(--panel-2)' : undefined }}
                >
                  <td style={cellStyle}>
                    <button
                      type="button"
                      aria-label={`${expanded ? 'Collapse' : 'Expand'} ${row.symbol}`}
                      aria-expanded={expanded}
                      onClick={event => {
                        event.stopPropagation();
                        toggleExpanded();
                      }}
                      style={{ border: 0, background: 'transparent', color: 'var(--text)', cursor: 'pointer' }}
                    >{expanded ? '▾' : '›'}</button>
                  </td>
                  <td style={cellStyle}><strong>{visibleValue(row.symbol)}</strong></td>
                  <td style={cellStyle}>{visibleValue(row.company_name)}</td>
                  <td style={cellStyle}>{visibleValue(row.direction)}</td>
                  <td style={cellStyle}>{fmt(row.directional_score, 2)}</td>
                  <td style={cellStyle}><strong>{fmt(row.signal_strength, 2)}</strong></td>
                  <td style={cellStyle}>{fmt(row.confidence, 1)}</td>
                  <td style={cellStyle}>{fmt(row.input_quality, 1)}</td>
                  <td style={cellStyle}>{visibleValue(row.disposition)}</td>
                  <td style={cellStyle}>{visibleValue(row.transition_state)}</td>
                  <td style={cellStyle}>{visibleValue(row.sector)}</td>
                  <td style={cellStyle}>{fmt(row.opportunity_score, 2)}</td>
                  <td style={cellStyle}>{visibleValue(row.opportunity_state)}</td>
                  <td style={cellStyle}>{visibleValue(row.coverage_status)}</td>
                  <td style={cellStyle}>{visibleValue(row.source_as_of_date)}</td>
                </tr>
                {expanded && <tr>
                  <td colSpan={15} style={{ padding: 0, borderBottom: '1px solid var(--border)' }}>
                    <InlineCandidateDetail row={row} />
                  </td>
                </tr>}
              </Fragment>;
            })}
            {shownRows.length === 0 && <tr>
              <td colSpan={15} style={{ ...cellStyle, textAlign: 'center' }}>No candidates match the active filters.</td>
            </tr>}
          </tbody>
        </table>
      </div>
      {filtered.length > shownRows.length && <p>Showing the first {shownRows.length} of {filtered.length} matching candidates.</p>}
    </section>
  </section>;
}
