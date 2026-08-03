import { useEffect, useMemo, useState, type ComponentType, type ReactNode } from 'react';
import { Activity, Bell, ChevronDown, CircleDot, Command, PanelLeftClose, PanelLeftOpen, Search, Wifi, WifiOff } from 'lucide-react';
import type { WorkspaceKey } from './types';
import { platformApi } from './api';
import { nav } from './pages';

export type NavigationGroup = { label: string; items: WorkspaceKey[] };

export const navigationGroups: NavigationGroup[] = [
  { label: 'Market intelligence', items: ['overview', 'market'] },
  { label: 'Scanning', items: ['scanner', 'option-scanner'] },
  { label: 'Opportunities', items: ['opportunities', 'intelligence', 'trade-builder'] },
  { label: 'Portfolio', items: ['portfolio', 'performance-learning', 'risk', 'positions', 'exits'] },
  { label: 'Operations', items: ['execution', 'command'] },
];

const NAV_LOOKUP = new Map(nav.map(([id, label, Icon]) => [id, { label, Icon }]));

function normalizeStatus(value: unknown, fallback = 'Unknown') {
  const text = String(value ?? '').trim();
  return text ? text.replaceAll('_', ' ') : fallback;
}

function tone(value: unknown) {
  const text = String(value ?? '').toUpperCase();
  if (/(READY|HEALTHY|CONNECTED|ACTIVE|BULL|GOOD)/.test(text)) return 'positive';
  if (/(DEGRADED|WARNING|REVIEW|STALE|NEUTRAL)/.test(text)) return 'warning';
  if (/(FAILED|CRITICAL|DISCONNECTED|ERROR|BEAR)/.test(text)) return 'negative';
  return 'neutral';
}

export function WorkspaceSidebar({ active, open, collapsed, onNavigate, onToggleCollapsed }:{
  active: WorkspaceKey;
  open: boolean;
  collapsed: boolean;
  onNavigate: () => void;
  onToggleCollapsed: () => void;
}) {
  return <aside className={`workstation-sidebar ${open ? 'open' : ''} ${collapsed ? 'collapsed' : ''}`}>
    <div className="brand workstation-brand">
      <div className="brandmark">TA</div>
      {!collapsed && <div><b>Trading AI</b><span>Institutional Workstation</span></div>}
    </div>
    <div className="navigation-scroll">
      {navigationGroups.map(group => <section className="navigation-group" key={group.label}>
        {!collapsed && <h2>{group.label}</h2>}
        <nav aria-label={group.label}>
          {group.items.map(id => {
            const item = NAV_LOOKUP.get(id);
            if (!item) return null;
            const Icon = item.Icon as ComponentType<{size?: number}>;
            return <a key={id} href={`#/${id}`} title={collapsed ? item.label : undefined} className={active === id ? 'active' : ''} onClick={onNavigate}>
              <Icon size={18}/>{!collapsed && <span>{item.label}</span>}
            </a>;
          })}
        </nav>
      </section>)}
    </div>
    <button className="sidebar-collapse" onClick={onToggleCollapsed} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}>
      {collapsed ? <PanelLeftOpen size={17}/> : <PanelLeftClose size={17}/>} {!collapsed && 'Collapse'}
    </button>
  </aside>;
}

export function GlobalIntelligenceHeader({ active, onMenu, onRefresh, refreshing }:{
  active: WorkspaceKey;
  onMenu: () => void;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const [context, setContext] = useState<any>(null);
  const [connected, setConnected] = useState(true);
  const activeLabel = NAV_LOOKUP.get(active)?.label ?? 'Workstation';

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([platformApi.overview(controller.signal), platformApi.readiness(controller.signal)])
      .then(([overview, readiness]) => {
        const overviewValue = overview.status === 'fulfilled' ? overview.value?.data : null;
        const readinessValue = readiness.status === 'fulfilled' ? readiness.value?.data : null;
        setContext({ overview: overviewValue, readiness: readinessValue });
        setConnected(overview.status === 'fulfilled' || readiness.status === 'fulfilled');
      });
    return () => controller.abort();
  }, [refreshing]);

  const chips = useMemo(() => {
    const overview = context?.overview ?? {};
    const readiness = context?.readiness ?? {};
    return [
      ['Market', normalizeStatus(overview.market_regime ?? overview.regime, 'Awaiting snapshot')],
      ['Health', normalizeStatus(overview.market_health_score ?? readiness.status, 'Unknown')],
      ['Readiness', normalizeStatus(readiness.status ?? readiness.overall_status, connected ? 'Connected' : 'Offline')],
      ['Mode', 'Paper governed'],
    ];
  }, [context, connected]);

  return <header className="global-header">
    <div className="global-header-primary">
      <button className="menu icon-button" onClick={onMenu} aria-label="Open navigation"><PanelLeftOpen size={19}/></button>
      <div className="workspace-heading"><span className="eyebrow">Institutional workspace</span><h1>{activeLabel}</h1></div>
      <label className="global-search"><Search size={16}/><input aria-label="Global search" placeholder="Search symbols, opportunities, positions…"/><kbd>⌘ K</kbd></label>
      <button className="icon-button" aria-label="Notifications"><Bell size={18}/><i/></button>
      <button className={`connection-state ${connected ? 'online' : 'offline'}`} title={connected ? 'Platform API reachable' : 'Platform API unavailable'}>
        {connected ? <Wifi size={15}/> : <WifiOff size={15}/>}<span>{connected ? 'Live' : 'Offline'}</span>
      </button>
      <button className="user-menu"><span>VH</span><ChevronDown size={14}/></button>
    </div>
    <div className="intelligence-ribbon" aria-label="Global intelligence context">
      <div className="snapshot-context"><CircleDot size={14}/><span>Published context</span><strong>{new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</strong></div>
      {chips.map(([label, value]) => <div className="context-chip" key={label}><span>{label}</span><strong className={tone(value)}>{value}</strong></div>)}
      <button className="header-refresh" onClick={onRefresh} disabled={refreshing}><Activity size={15}/>{refreshing ? 'Refreshing…' : 'Refresh context'}</button>
    </div>
  </header>;
}

export function WorkspaceStatusBar({ active }:{active:WorkspaceKey}) {
  return <footer className="workspace-statusbar">
    <span><CircleDot size={12}/> Workspace: <b>{NAV_LOOKUP.get(active)?.label}</b></span>
    <span><Wifi size={12}/> API session active</span>
    <span><Command size={12}/> Command palette foundation ready</span>
  </footer>;
}

export function WorkspaceCanvas({children}:{children:ReactNode}) { return <div className="workspace-canvas">{children}</div>; }
