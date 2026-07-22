import { useEffect, useState, type ReactNode } from 'react';
import { Activity, BriefcaseBusiness, ShieldCheck, Waypoints, ScanLine, LogOut, RadioTower } from 'lucide-react';
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
  ['portfolio', 'Portfolio', BriefcaseBusiness],
  ['risk', 'Risk', ShieldCheck],
  ['execution', 'Execution', Waypoints],
  ['positions', 'Positions', ScanLine],
  ['exits', 'Exits', LogOut],
  ['command', 'Command center', RadioTower],
] as const;

export function CommandCenter(){const [data,setData]=useState<any>(null);const [events,setEvents]=useState<any[]>([]);useEffect(()=>{fetch('/api/v1/realtime/snapshot',{headers:{'X-API-Key':sessionStorage.getItem('trading-ai-api-key')??''}}).then(r=>r.json()).then(setData);const key=sessionStorage.getItem('trading-ai-api-key')??'';const ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/realtime/stream?api_key=${encodeURIComponent(key)}`);ws.onmessage=e=>setEvents(v=>[JSON.parse(e.data),...v].slice(0,50));return()=>ws.close()},[]);return <section><h2>Operational Command Center</h2><div className="metrics"><article><b>{data?.connected_clients??0}</b><span>Live clients</span></article><article><b>{data?.open_alerts??0}</b><span>Open alerts</span></article><article><b>{data?.critical_alerts??0}</b><span>Critical alerts</span></article><article><b>{data?.events_published??0}</b><span>Events</span></article></div><div className="panel"><h3>Live event stream</h3><pre>{JSON.stringify(events,null,2)}</pre></div></section>}
