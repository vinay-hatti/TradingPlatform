import { Fragment, useEffect, useMemo, useState } from 'react';
import { analyticsDashboardApi } from './api';
import {
  AnalyticsMetric,
  DistributionBars,
  Histogram,
  fmt,
  tone,
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
  padding: '9px 8px',
  borderBottom: '1px solid var(--border)',
  textAlign: 'left' as const,
  verticalAlign: 'top' as const,
  whiteSpace: 'nowrap' as const,
};

const HEADER_FILTER_FIELDS = [
  ['symbol', 'Symbol'],
  ['company_name', 'Company'],
  ['classification', 'Classification'],
  ['strategy', 'Strategy'],
  ['sector', 'Sector'],
  ['market_regime', 'Regime'],
  ['moneyness_bucket', 'Moneyness'],
  ['executable', 'Executable'],
] as const;

const minimumScoreOptions = [0, 40, 50, 60, 70, 80, 90];
const probabilityOptions = [0, 0.5, 0.6, 0.7, 0.8, 0.9];
const returnOptions = [0, 0.25, 0.5, 1, 2];

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

const minimumMatches = (value: any, minimum: string) => {
  const threshold = Number(minimum);
  if (!Number.isFinite(threshold) || threshold <= 0) return true;
  const numericValue = Number(value);
  return Number.isFinite(numericValue) && numericValue >= threshold;
};

const valueBandMatches = (value: any, band: string) => {
  if (!band) return true;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return false;
  if (band === 'UNDER_1') return numericValue < 1;
  if (band === '1_5') return numericValue >= 1 && numericValue < 5;
  if (band === '5_10') return numericValue >= 5 && numericValue < 10;
  if (band === '10_25') return numericValue >= 10 && numericValue < 25;
  if (band === '25_PLUS') return numericValue >= 25;
  return true;
};

const mispricingBandMatches = (value: any, band: string) => {
  if (!band) return true;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return false;
  if (band === 'BELOW_NEGATIVE_10') return numericValue < -10;
  if (band === 'NEGATIVE_10_TO_5') return numericValue >= -10 && numericValue < -5;
  if (band === 'FAIR_BAND') return numericValue >= -5 && numericValue <= 5;
  if (band === 'POSITIVE_5_TO_10') return numericValue > 5 && numericValue <= 10;
  if (band === 'ABOVE_POSITIVE_10') return numericValue > 10;
  return true;
};

const expectedValueMatches = (value: any, band: string) => {
  if (!band) return true;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return false;
  if (band === 'NEGATIVE') return numericValue < 0;
  if (band === 'ZERO') return numericValue === 0;
  if (band === 'POSITIVE') return numericValue > 0;
  return true;
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

function CompactObject({
  title,
  value,
}: {
  title: string;
  value: Record<string, any> | null | undefined;
}) {
  const entries = Object.entries(value ?? {});
  if (entries.length === 0) return null;
  return <section>
    <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>{title}</h4>
    <dl style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(110px, auto) 1fr',
      gap: '3px 10px',
      margin: 0,
      fontSize: 12,
      lineHeight: 1.35,
    }}>
      {entries.map(([label, value]) => <Fragment key={label}>
        <dt style={{ color: 'var(--text-muted)' }}>
          {label.replaceAll('_', ' ')}
        </dt>
        <dd style={{ margin: 0, overflowWrap: 'anywhere' }}>
          {typeof value === 'object'
            ? JSON.stringify(value)
            : visibleValue(value)}
        </dd>
      </Fragment>)}
    </dl>
  </section>;
}

function InlineValuationDetail({ row }: { row: any }) {
  const sections = [
    {
      title: 'Valuation authority',
      fields: [
        ['Snapshot Id', row.snapshot_id],
        ['Symbol', row.symbol],
        ['Company', row.company_name],
        ['Classification', row.classification],
        ['Market mid', row.market_mid],
        ['Fair value', row.fair_value],
        ['Mispricing %', row.mispricing_pct],
        ['Edge score', row.edge_score],
        ['Confidence', row.confidence],
        ['Stability index', row.stability_index],
        ['Executable', row.executable],
        ['Trade execution authority', row.trade_execution_authority],
      ],
    },
    {
      title: 'Institutional opportunity',
      fields: [
        ['Opportunity Id', row.opportunity_id],
        ['Opportunity state', row.opportunity_state],
        ['Direction', row.direction],
        ['Category', row.category],
        ['Conviction', row.conviction],
        ['Underlying score', row.underlying_score],
        ['Strategy', row.strategy],
        ['Strategy selected', row.strategy_selected],
        ['Strategy score', row.strategy_score],
        ['Market regime', row.market_regime],
        ['Primary timeframe', row.primary_timeframe],
        ['Invalidation level', row.invalidation_level],
        ['Entry zone low', row.entry_zone_low],
        ['Entry zone high', row.entry_zone_high],
      ],
    },
    {
      title: 'Exact market lineage',
      fields: [
        ['Contract recommendation Id', row.contract_recommendation_id],
        ['Option snapshot Id', row.option_snapshot_id],
        ['Quote input snapshot Id', row.quote_input_snapshot_id],
        ['Market input as of', row.market_input_as_of],
        ['Market input status', row.market_input_status],
        ['Snapshot timestamp', row.snapshot_timestamp],
        ['DTE', row.dte],
        ['DTE bucket', row.dte_bucket],
        ['Moneyness', row.moneyness_bucket],
        ['Sector', row.sector],
        ['Industry', row.industry],
        ['Liquidity score', row.liquidity_score],
        ['Probability', row.calibrated_probability],
        ['Expected value', row.expected_value],
        ['Expected return on risk', row.expected_return_on_risk],
      ],
    },
  ];
  const evidence = Array.isArray(row.evidence) ? row.evidence : [];
  const conflicts = Array.isArray(row.conflicting_evidence)
    ? row.conflicting_evidence
    : [];
  const legs = Array.isArray(row.legs) ? row.legs : [];

  return <div style={{
    padding: '10px 12px 12px',
    background: 'var(--panel-2)',
    borderLeft: '2px solid var(--accent)',
  }}>
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(3, minmax(270px, 1fr))',
      gap: '8px 22px',
      alignItems: 'start',
    }}>
      {sections.map(section => <section key={section.title}>
        <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>{section.title}</h4>
        <dl style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(125px, auto) 1fr',
          gap: '3px 10px',
          margin: 0,
          fontSize: 12,
          lineHeight: 1.35,
        }}>
          {section.fields.map(([label, value]) => <Fragment key={String(label)}>
            <dt style={{ color: 'var(--text-muted)' }}>{label}</dt>
            <dd style={{ margin: 0, overflowWrap: 'anywhere' }}>
              {visibleValue(value)}
            </dd>
          </Fragment>)}
        </dl>
      </section>)}
    </div>

    <section style={{ marginTop: 9, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
      <h4 style={{ margin: '0 0 5px', fontSize: 13 }}>Edge components</h4>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(155px, 1fr))',
        gap: 6,
      }}>
        {Object.entries(row.components ?? {}).map(([name, value]) =>
          <div key={name} style={{
            padding: '4px 7px',
            background: 'var(--panel)',
            borderRadius: 5,
            fontSize: 11,
          }}>
            <span style={{ color: 'var(--text-muted)', marginRight: 6 }}>
              {name.replaceAll('_', ' ')}
            </span>
            <strong style={{ fontSize: 12 }}>{fmt(value, 3)}</strong>
          </div>,
        )}
        {Object.keys(row.components ?? {}).length === 0 && <span>Unavailable</span>}
      </div>
    </section>

    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, minmax(210px, 1fr))',
      gap: '8px 22px',
      marginTop: 8,
      paddingTop: 8,
      borderTop: '1px solid var(--border)',
      alignItems: 'start',
    }}>
      <CompactObject title="Relative value" value={row.relative_value} />
      <CompactObject title="Event pricing" value={row.event_pricing} />
      <CompactObject title="Segmentation" value={row.segmentation} />
      <CompactObject title="Coverage" value={row.coverage} />
    </div>

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
          : <span style={{ color: 'var(--text-muted)' }}>
            No supporting evidence recorded.
          </span>}
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

    {legs.length > 0 && <section style={{
      marginTop: 8,
      paddingTop: 8,
      borderTop: '1px solid var(--border)',
    }}>
      <h4 style={{ margin: '0 0 5px', fontSize: 13 }}>Option legs</h4>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead><tr>
            {['Side', 'Option symbol', 'Type', 'Strike', 'Expiry', 'Qty', 'Bid', 'Ask', 'Last', 'IV', 'Delta', 'Gamma', 'Theta', 'Vega', 'Volume', 'Open interest'].map(label =>
              <th key={label} style={{ ...cellStyle, padding: '5px 7px' }}>{label}</th>,
            )}
          </tr></thead>
          <tbody>{legs.map((leg: any, index: number) => <tr key={leg.leg_id ?? `${leg.option_symbol}-${index}`}>
            <td style={cellStyle}>{visibleValue(leg.side)}</td>
            <td style={cellStyle}>{visibleValue(leg.option_symbol)}</td>
            <td style={cellStyle}>{visibleValue(leg.option_type)}</td>
            <td style={cellStyle}>{fmt(leg.strike, 3)}</td>
            <td style={cellStyle}>{visibleValue(leg.expiry)}</td>
            <td style={cellStyle}>{visibleValue(leg.quantity_ratio)}</td>
            <td style={cellStyle}>{fmt(leg.bid, 3)}</td>
            <td style={cellStyle}>{fmt(leg.ask, 3)}</td>
            <td style={cellStyle}>{fmt(leg.last, 3)}</td>
            <td style={cellStyle}>{fmt(leg.implied_volatility, 4)}</td>
            <td style={cellStyle}>{fmt(leg.delta, 4)}</td>
            <td style={cellStyle}>{fmt(leg.gamma, 4)}</td>
            <td style={cellStyle}>{fmt(leg.theta, 4)}</td>
            <td style={cellStyle}>{fmt(leg.vega, 4)}</td>
            <td style={cellStyle}>{fmt(leg.volume, 0)}</td>
            <td style={cellStyle}>{fmt(leg.open_interest, 0)}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>}
  </div>;
}

export function OptionsMispricingAnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [classification, setClassification] = useState<string | null>(null);
  const [strategy, setStrategy] = useState<string | null>(null);
  const [sector, setSector] = useState<string | null>(null);
  const [dte, setDte] = useState<string | null>(null);
  const [moneyness, setMoneyness] = useState<string | null>(null);
  const [regime, setRegime] = useState<string | null>(null);
  const [edgeBand, setEdgeBand] = useState<ScoreBand>(null);
  const [sortDriver, setSortDriver] = useState<string | null>(null);
  const [categoricalFilters, setCategoricalFilters] = useState<CategoricalFilters>({});
  const [marketBand, setMarketBand] = useState('');
  const [fairValueBand, setFairValueBand] = useState('');
  const [mispricingBand, setMispricingBand] = useState('');
  const [minimumEdge, setMinimumEdge] = useState('0');
  const [minimumProbability, setMinimumProbability] = useState('0');
  const [expectedValueBand, setExpectedValueBand] = useState('');
  const [minimumReturn, setMinimumReturn] = useState('0');
  const [minimumLiquidity, setMinimumLiquidity] = useState('0');
  const [minimumStability, setMinimumStability] = useState('0');
  const [expandedSnapshotId, setExpandedSnapshotId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    analyticsDashboardApi.optionsMispricing(10000, controller.signal)
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

  const filterValue = (key: string) => {
    if (key === 'classification') return classification ?? '';
    if (key === 'strategy') return strategy ?? '';
    if (key === 'sector') return sector ?? '';
    if (key === 'market_regime') return regime ?? '';
    if (key === 'moneyness_bucket') return moneyness ?? '';
    return categoricalFilters[key] ?? '';
  };

  const setFilterValue = (key: string, value: string) => {
    if (key === 'classification') setClassification(value || null);
    else if (key === 'strategy') setStrategy(value || null);
    else if (key === 'sector') setSector(value || null);
    else if (key === 'market_regime') setRegime(value || null);
    else if (key === 'moneyness_bucket') setMoneyness(value || null);
    else setCategoricalFilters(current => ({ ...current, [key]: value }));
  };

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const rows = candidates.filter((row: any) =>
      (!normalizedQuery ||
        String(row.symbol ?? '').toLowerCase().includes(normalizedQuery) ||
        String(row.company_name ?? '').toLowerCase().includes(normalizedQuery)) &&
      Object.entries(categoricalFilters).every(([key, value]) =>
        !value || String(row?.[key] ?? '') === value,
      ) &&
      (!classification || row.classification === classification) &&
      (!strategy || row.strategy === strategy) &&
      (!sector || row.sector === sector) &&
      (!dte || row.dte_bucket === dte) &&
      (!moneyness || row.moneyness_bucket === moneyness) &&
      (!regime || row.market_regime === regime) &&
      (!edgeBand ||
        (Number(row.edge_score) >= edgeBand.minimum &&
          Number(row.edge_score) < edgeBand.maximum) ||
        (edgeBand.maximum === 100 && Number(row.edge_score) === 100)) &&
      valueBandMatches(row.market_mid, marketBand) &&
      valueBandMatches(row.fair_value, fairValueBand) &&
      mispricingBandMatches(row.mispricing_pct, mispricingBand) &&
      minimumMatches(row.edge_score, minimumEdge) &&
      minimumMatches(row.calibrated_probability, minimumProbability) &&
      expectedValueMatches(row.expected_value, expectedValueBand) &&
      minimumMatches(row.expected_return_on_risk, minimumReturn) &&
      minimumMatches(row.liquidity_score, minimumLiquidity) &&
      minimumMatches(row.stability_index, minimumStability),
    );
    if (!sortDriver) return rows;
    return [...rows].sort((left, right) =>
      Number(right.components?.[sortDriver] ?? -Infinity) -
      Number(left.components?.[sortDriver] ?? -Infinity),
    );
  }, [
    candidates,
    query,
    categoricalFilters,
    classification,
    strategy,
    sector,
    dte,
    moneyness,
    regime,
    edgeBand,
    sortDriver,
    marketBand,
    fairValueBand,
    mispricingBand,
    minimumEdge,
    minimumProbability,
    expectedValueBand,
    minimumReturn,
    minimumLiquidity,
    minimumStability,
  ]);

  const clear = () => {
    setClassification(null);
    setStrategy(null);
    setSector(null);
    setDte(null);
    setMoneyness(null);
    setRegime(null);
    setEdgeBand(null);
    setSortDriver(null);
    setCategoricalFilters({});
    setMarketBand('');
    setFairValueBand('');
    setMispricingBand('');
    setMinimumEdge('0');
    setMinimumProbability('0');
    setExpectedValueBand('');
    setMinimumReturn('0');
    setMinimumLiquidity('0');
    setMinimumStability('0');
  };

  const active = [
    edgeBand && `Edge ${edgeBand.label}`,
    classification && `Class ${classification}`,
    strategy && `Strategy ${strategy}`,
    sector && `Sector ${sector}`,
    dte && `DTE ${dte}`,
    moneyness && `Moneyness ${moneyness}`,
    regime && `Regime ${regime}`,
    sortDriver && `Sorted by ${sortDriver}`,
    ...Object.entries(categoricalFilters)
      .filter(([, value]) => Boolean(value))
      .map(([key, value]) =>
        `${HEADER_FILTER_FIELDS.find(([field]) => field === key)?.[1] ?? key} ${value}`,
      ),
    marketBand && `Market ${marketBand}`,
    fairValueBand && `Fair value ${fairValueBand}`,
    mispricingBand && `Mispricing ${mispricingBand}`,
    minimumEdge !== '0' && `Edge ≥ ${minimumEdge}`,
    minimumProbability !== '0' && `Probability ≥ ${minimumProbability}`,
    expectedValueBand && `EV ${expectedValueBand}`,
    minimumReturn !== '0' && `Exp ROR ≥ ${minimumReturn}`,
    minimumLiquidity !== '0' && `Liquidity ≥ ${minimumLiquidity}`,
    minimumStability !== '0' && `Stability ≥ ${minimumStability}`,
  ].filter(Boolean) as string[];

  if (error) {
    return <section className="analytics-page"><p className="provider-warning">{error}</p></section>;
  }
  if (!data) {
    return <section className="analytics-page"><p>Loading governed option-mispricing analytics…</p></section>;
  }

  const summary = data.summary ?? {};
  const categoricalOptions = (key: string) => [
    { value: '', label: 'All' },
    ...(filterOptions[key] ?? []).map((value: string) => ({
      value,
      label: key === 'executable'
        ? value === 'true' ? 'YES' : 'NO'
        : value,
    })),
  ];
  const valueBandOptions = [
    { value: '', label: 'Any' },
    { value: 'UNDER_1', label: '< 1' },
    { value: '1_5', label: '1 – <5' },
    { value: '5_10', label: '5 – <10' },
    { value: '10_25', label: '10 – <25' },
    { value: '25_PLUS', label: '≥ 25' },
  ];

  return <section className="analytics-page">
    <div className="analytics-page-title">
      <div>
        <span className="eyebrow">Analytics</span>
        <h2>Options Mispricing</h2>
        <p>Independent fair value, edge attribution, strategy concentration, execution quality, and candidate-level lineage.</p>
      </div>
      <div className="publication-chip">
        <span>{summary.status}</span>
        <strong>{summary.publication_id}</strong>
        <small>{summary.published_at}</small>
      </div>
    </div>

    <div className="analytics-metric-grid">
      <AnalyticsMetric label="Contracts valued" value={fmt(summary.contracts_valued, 0)} />
      <AnalyticsMetric label="Underpriced" value={fmt(summary.underpriced, 0)} />
      <AnalyticsMetric label="Overpriced" value={fmt(summary.overpriced, 0)} />
      <AnalyticsMetric label="Fair value" value={fmt(summary.fair_value, 0)} />
      <AnalyticsMetric label="Average edge score" value={fmt(summary.average_edge_score, 2)} />
      <AnalyticsMetric label="Positive EV" value={fmt(summary.positive_ev, 0)} />
      <AnalyticsMetric label="Executable" value={fmt(summary.executable, 0)} />
    </div>

    <div className="analytics-grid analytics-grid-wide">
      <Histogram
        title="Edge score distribution"
        rows={data.edge_histogram ?? []}
        selected={edgeBand?.label ?? null}
        onSelect={(row: any) => setEdgeBand(
          edgeBand?.label === row.label
            ? null
            : {
              label: String(row.label),
              minimum: Number(row.minimum),
              maximum: Number(row.maximum),
            },
        )}
      />
      <DistributionBars
        title="Mispricing classification"
        rows={data.classification_distribution ?? []}
        selected={classification}
        onSelect={(row: any) => setClassification(
          toggle(classification, String(row.name)),
        )}
      />
    </div>

    <div className="analytics-grid">
      <DistributionBars title="By strategy" rows={data.by_strategy ?? []} selected={strategy} onSelect={(row: any) => setStrategy(toggle(strategy, String(row.name)))} />
      <DistributionBars title="By sector" rows={data.by_sector ?? []} selected={sector} onSelect={(row: any) => setSector(toggle(sector, String(row.name)))} />
      <DistributionBars title="By DTE" rows={data.by_dte ?? []} selected={dte} onSelect={(row: any) => setDte(toggle(dte, String(row.name)))} />
      <DistributionBars title="By moneyness" rows={data.by_moneyness ?? []} selected={moneyness} onSelect={(row: any) => setMoneyness(toggle(moneyness, String(row.name)))} />
      <DistributionBars title="By market regime" rows={data.by_market_regime ?? []} selected={regime} onSelect={(row: any) => setRegime(toggle(regime, String(row.name)))} />
      <DistributionBars title="Average edge attribution" rows={data.driver_averages ?? []} valueLabel="average" selected={sortDriver} onSelect={(row: any) => setSortDriver(toggle(sortDriver, String(row.name)))} />
    </div>

    <section className="analytics-panel">
      <header className="table-header">
        <div>
          <h3>Mispricing candidates</h3>
          <p>{filtered.length} valuation snapshots · select a row to expand its full valuation and exact lineage</p>
        </div>
        <div className="analytics-filters">
          <input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search symbol or company"
          />
        </div>
      </header>
      {active.length > 0 && <div className="analytics-active-filters">
        {active.map(label => <span className="analytics-filter-chip" key={label}>{label}</span>)}
        <button className="analytics-clear-filters" onClick={clear}>Clear all filters</button>
      </div>}

      <div className="analytics-table-wrap">
        <table className="analytics-table">
          <thead><tr>
            <CandidateHeaderFilter label="Symbol" value={filterValue('symbol')} options={categoricalOptions('symbol')} onChange={value => setFilterValue('symbol', value)} />
            <CandidateHeaderFilter label="Company" value={filterValue('company_name')} options={categoricalOptions('company_name')} onChange={value => setFilterValue('company_name', value)} />
            <CandidateHeaderFilter label="Classification" value={filterValue('classification')} options={categoricalOptions('classification')} onChange={value => setFilterValue('classification', value)} />
            <CandidateHeaderFilter label="Strategy" value={filterValue('strategy')} options={categoricalOptions('strategy')} onChange={value => setFilterValue('strategy', value)} />
            <CandidateHeaderFilter label="Sector" value={filterValue('sector')} options={categoricalOptions('sector')} onChange={value => setFilterValue('sector', value)} />
            <CandidateHeaderFilter label="Regime" value={filterValue('market_regime')} options={categoricalOptions('market_regime')} onChange={value => setFilterValue('market_regime', value)} />
            <CandidateHeaderFilter label="Moneyness" value={filterValue('moneyness_bucket')} options={categoricalOptions('moneyness_bucket')} onChange={value => setFilterValue('moneyness_bucket', value)} />
            <CandidateHeaderFilter label="DTE" value={dte ?? ''} options={[{ value: '', label: 'All' }, ...(data.by_dte ?? []).map((row: any) => ({ value: String(row.name), label: String(row.name) }))]} onChange={value => setDte(value || null)} />
            <CandidateHeaderFilter label="Market" value={marketBand} options={valueBandOptions} onChange={setMarketBand} />
            <CandidateHeaderFilter label="Fair value" value={fairValueBand} options={valueBandOptions} onChange={setFairValueBand} />
            <CandidateHeaderFilter label="Mispricing %" value={mispricingBand} options={[
              { value: '', label: 'Any' },
              { value: 'BELOW_NEGATIVE_10', label: '< -10%' },
              { value: 'NEGATIVE_10_TO_5', label: '-10% – < -5%' },
              { value: 'FAIR_BAND', label: '-5% – 5%' },
              { value: 'POSITIVE_5_TO_10', label: '> 5% – 10%' },
              { value: 'ABOVE_POSITIVE_10', label: '> 10%' },
            ]} onChange={setMispricingBand} />
            <CandidateHeaderFilter label="Edge" value={minimumEdge} options={minimumScoreOptions.map(value => ({ value: String(value), label: value === 0 ? 'Any' : `≥ ${value}` }))} onChange={setMinimumEdge} />
            <CandidateHeaderFilter label="Probability" value={minimumProbability} options={probabilityOptions.map(value => ({ value: String(value), label: value === 0 ? 'Any' : `≥ ${Math.round(value * 100)}%` }))} onChange={setMinimumProbability} />
            <CandidateHeaderFilter label="EV" value={expectedValueBand} options={[
              { value: '', label: 'Any' },
              { value: 'POSITIVE', label: 'Positive' },
              { value: 'ZERO', label: 'Zero' },
              { value: 'NEGATIVE', label: 'Negative' },
            ]} onChange={setExpectedValueBand} />
            <CandidateHeaderFilter label="Exp ROR" value={minimumReturn} options={returnOptions.map(value => ({ value: String(value), label: value === 0 ? 'Any' : `≥ ${value}` }))} onChange={setMinimumReturn} />
            <CandidateHeaderFilter label="Liquidity" value={minimumLiquidity} options={minimumScoreOptions.map(value => ({ value: String(value), label: value === 0 ? 'Any' : `≥ ${value}` }))} onChange={setMinimumLiquidity} />
            <CandidateHeaderFilter label="Stability" value={minimumStability} options={minimumScoreOptions.map(value => ({ value: String(value), label: value === 0 ? 'Any' : `≥ ${value}` }))} onChange={setMinimumStability} />
            <CandidateHeaderFilter label="Executable" value={filterValue('executable')} options={categoricalOptions('executable')} onChange={value => setFilterValue('executable', value)} />
          </tr></thead>
          <tbody>
            {filtered.slice(0, 1500).map((row: any, index: number) => {
              const rowId = String(row.snapshot_id ?? `${row.symbol}-${index}`);
              const expanded = expandedSnapshotId === rowId;
              return <Fragment key={rowId}>
                <tr
                  className="selectable"
                  aria-expanded={expanded}
                  tabIndex={0}
                  onClick={() => setExpandedSnapshotId(expanded ? null : rowId)}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setExpandedSnapshotId(expanded ? null : rowId);
                    }
                  }}
                >
                  <td style={cellStyle}>
                    <span aria-hidden="true" style={{ display: 'inline-block', width: 16 }}>
                      {expanded ? '▾' : '›'}
                    </span>
                    <strong>{visibleValue(row.symbol)}</strong>
                  </td>
                  <td style={cellStyle}>{visibleValue(row.company_name)}</td>
                  <td style={cellStyle}><span className={`analytics-badge ${tone(row.classification)}`}>{visibleValue(row.classification)}</span></td>
                  <td style={cellStyle}>{visibleValue(row.strategy)}</td>
                  <td style={cellStyle}>{visibleValue(row.sector)}</td>
                  <td style={cellStyle}>{visibleValue(row.market_regime)}</td>
                  <td style={cellStyle}>{visibleValue(row.moneyness_bucket)}</td>
                  <td style={cellStyle}>{fmt(row.dte, 0)}</td>
                  <td style={cellStyle}>{fmt(row.market_mid, 3)}</td>
                  <td style={cellStyle}>{fmt(row.fair_value, 3)}</td>
                  <td style={cellStyle}><strong>{fmt(row.mispricing_pct, 2)}</strong></td>
                  <td style={cellStyle}>{fmt(row.edge_score, 2)}</td>
                  <td style={cellStyle}>{row.calibrated_probability == null ? '—' : fmt(row.calibrated_probability, 2)}</td>
                  <td style={cellStyle}>{row.expected_value == null ? '—' : fmt(row.expected_value, 3)}</td>
                  <td style={cellStyle}>{row.expected_return_on_risk == null ? '—' : fmt(row.expected_return_on_risk, 3)}</td>
                  <td style={cellStyle}>{fmt(row.liquidity_score, 1)}</td>
                  <td style={cellStyle}>{fmt(row.stability_index, 1)}</td>
                  <td style={cellStyle}>{row.executable ? 'YES' : 'NO'}</td>
                </tr>
                {expanded && <tr>
                  <td colSpan={18} style={{ padding: 0, borderBottom: '1px solid var(--border)' }}>
                    <InlineValuationDetail row={row} />
                  </td>
                </tr>}
              </Fragment>;
            })}
          </tbody>
        </table>
      </div>
    </section>
  </section>;
}
