import { useEffect, useMemo, useRef, useState, type ComponentType } from 'react';
import { Check, Clock3, Command, LayoutGrid, Search, Settings2, Star, X } from 'lucide-react';
import type { WorkspaceKey } from './types';
import { nav } from './pages';

export type WorkspacePreference = {
  compactDensity: boolean;
  reducedMotion: boolean;
  showStatusBar: boolean;
};

export const DEFAULT_WORKSPACE_PREFERENCES: WorkspacePreference = {
  compactDensity: false,
  reducedMotion: false,
  showStatusBar: true,
};

const NAV = nav.map(([id, label, Icon]) => ({ id, label, Icon })) as Array<{
  id: WorkspaceKey;
  label: string;
  Icon: ComponentType<{ size?: number }>;
}>;

const COMMANDS = [
  { id: 'refresh', label: 'Refresh global context', keywords: 'reload update published snapshot', shortcut: 'R' },
  { id: 'toggle-navigation', label: 'Collapse or expand navigation', keywords: 'sidebar menu', shortcut: 'B' },
  { id: 'preferences', label: 'Open workstation preferences', keywords: 'settings density motion status bar', shortcut: ',' },
] as const;

export function loadWorkspacePreferences(): WorkspacePreference {
  try {
    return { ...DEFAULT_WORKSPACE_PREFERENCES, ...JSON.parse(localStorage.getItem('workstation-preferences') ?? '{}') };
  } catch {
    return DEFAULT_WORKSPACE_PREFERENCES;
  }
}

export function loadWorkspaceList(key: string): WorkspaceKey[] {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? '[]');
    return Array.isArray(value) ? value.filter(item => NAV.some(route => route.id === item)).slice(0, 6) : [];
  } catch {
    return [];
  }
}

export function persistWorkspaceList(key: string, items: WorkspaceKey[]) {
  localStorage.setItem(key, JSON.stringify(items.slice(0, 6)));
}

export function useWorkspaceShortcuts(actions: {
  openPalette: () => void;
  openPreferences: () => void;
  refresh: () => void;
  toggleNavigation: () => void;
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editing = target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA' || target?.isContentEditable;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        actions.openPalette();
        return;
      }
      if (editing || !event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === 'r') { event.preventDefault(); actions.refresh(); }
      if (key === 'b') { event.preventDefault(); actions.toggleNavigation(); }
      if (event.key === ',') { event.preventDefault(); actions.openPreferences(); }
    };
    addEventListener('keydown', handler);
    return () => removeEventListener('keydown', handler);
  }, [actions]);
}

export function CommandPalette({
  open,
  onClose,
  onNavigate,
  onRefresh,
  onToggleNavigation,
  onOpenPreferences,
  recent,
  favorites,
}:{
  open: boolean;
  onClose: () => void;
  onNavigate: (workspace: WorkspaceKey) => void;
  onRefresh: () => void;
  onToggleNavigation: () => void;
  onOpenPreferences: () => void;
  recent: WorkspaceKey[];
  favorites: WorkspaceKey[];
}) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    requestAnimationFrame(() => inputRef.current?.focus());
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    addEventListener('keydown', handler);
    return () => removeEventListener('keydown', handler);
  }, [open, onClose]);

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const routes = NAV.filter(item => !needle || `${item.label} ${item.id}`.toLowerCase().includes(needle));
    const commands = COMMANDS.filter(item => !needle || `${item.label} ${item.keywords}`.toLowerCase().includes(needle));
    return { routes, commands };
  }, [query]);

  if (!open) return null;
  const routeById = new Map(NAV.map(item => [item.id, item]));
  const featured = [...favorites, ...recent.filter(item => !favorites.includes(item))].slice(0, 6);
  const executeCommand = (id: typeof COMMANDS[number]['id']) => {
    onClose();
    if (id === 'refresh') onRefresh();
    if (id === 'toggle-navigation') onToggleNavigation();
    if (id === 'preferences') onOpenPreferences();
  };

  return <div className="productivity-overlay" role="presentation" onMouseDown={event => event.currentTarget === event.target && onClose()}>
    <section className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette">
      <header><Search size={18}/><input ref={inputRef} value={query} onChange={event => setQuery(event.target.value)} placeholder="Search workspaces and commands" aria-label="Search commands"/><kbd>Esc</kbd></header>
      {!query && featured.length > 0 && <div className="command-section"><h2><Clock3 size={13}/> Recent and favorite</h2>{featured.map(id => { const item=routeById.get(id); if(!item)return null; const Icon=item.Icon; return <button key={id} onClick={()=>{onNavigate(id);onClose();}}><Icon size={16}/><span>{item.label}</span>{favorites.includes(id)&&<Star size={13}/>}</button>})}</div>}
      <div className="command-grid">
        <div className="command-section"><h2><LayoutGrid size={13}/> Workspaces</h2>{results.routes.map(item => { const Icon=item.Icon; return <button key={item.id} onClick={()=>{onNavigate(item.id);onClose();}}><Icon size={16}/><span>{item.label}</span><small>Open</small></button>})}</div>
        <div className="command-section"><h2><Command size={13}/> Commands</h2>{results.commands.map(item => <button key={item.id} onClick={()=>executeCommand(item.id)}><Command size={15}/><span>{item.label}</span><kbd>⌥ {item.shortcut}</kbd></button>)}</div>
      </div>
      {results.routes.length===0&&results.commands.length===0&&<div className="command-empty">No matching workspace or command.</div>}
    </section>
  </div>;
}

export function PreferencesPanel({ open, value, onChange, onClose }:{
  open:boolean;
  value:WorkspacePreference;
  onChange:(value:WorkspacePreference)=>void;
  onClose:()=>void;
}) {
  useEffect(()=>{
    if(!open)return;
    const handler=(event:KeyboardEvent)=>{if(event.key==='Escape')onClose()};
    addEventListener('keydown',handler);return()=>removeEventListener('keydown',handler);
  },[open,onClose]);
  if(!open)return null;
  const choices:[keyof WorkspacePreference,string,string][]=[
    ['compactDensity','Compact density','Reduce shell spacing for data-heavy workflows.'],
    ['reducedMotion','Reduced motion','Disable nonessential transitions and animations.'],
    ['showStatusBar','Status bar','Show workspace and shortcut diagnostics.'],
  ];
  return <div className="productivity-overlay preferences-overlay" role="presentation" onMouseDown={event=>event.currentTarget===event.target&&onClose()}>
    <aside className="preferences-panel" role="dialog" aria-modal="true" aria-label="Workstation preferences">
      <header><div><span className="eyebrow">Personal workspace</span><h2>Preferences</h2></div><button className="icon-button" onClick={onClose} aria-label="Close preferences"><X size={17}/></button></header>
      <div className="preference-list">{choices.map(([key,label,description])=><button key={key} className={value[key]?'selected':''} onClick={()=>onChange({...value,[key]:!value[key]})}><span><strong>{label}</strong><small>{description}</small></span><i>{value[key]?<Check size={15}/>:null}</i></button>)}</div>
      <footer><Settings2 size={14}/> Preferences are stored locally in this browser.</footer>
    </aside>
  </div>;
}
