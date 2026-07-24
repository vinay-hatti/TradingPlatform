import { useEffect, useState, type ChangeEvent, type ComponentType } from 'react';
import { KeyRound, Menu, RefreshCw } from 'lucide-react';
import type { WorkspaceKey } from './types';
import { CommandCenter, DailyScannerPage, Execution, Exits, nav, Overview, Portfolio, Positions, Risk } from './pages';
import './styles.css';

const pages: Record<WorkspaceKey, ComponentType> = {
  overview: Overview,
  scanner: DailyScannerPage,
  portfolio: Portfolio,
  risk: Risk,
  execution: Execution,
  positions: Positions,
  exits: Exits,
  command: CommandCenter,
};

function route(): WorkspaceKey {
  const value = location.hash.replace('#/', '') as WorkspaceKey;
  return value in pages ? value : 'overview';
}

export default function App() {
  const [active, setActive] = useState<WorkspaceKey>(route());
  const [open, setOpen] = useState(false);
  const [apiKey, setApiKey] = useState(sessionStorage.getItem('trading-ai-api-key') ?? '');

  useEffect(() => {
    const handleHashChange = () => setActive(route());
    addEventListener('hashchange', handleHashChange);
    return () => removeEventListener('hashchange', handleHashChange);
  }, []);

  const Page = pages[active];
  const saveApiKey = () => {
    if (apiKey) sessionStorage.setItem('trading-ai-api-key', apiKey);
    else sessionStorage.removeItem('trading-ai-api-key');
    location.reload();
  };

  const handleApiKeyChange = (event: ChangeEvent<HTMLInputElement>) => {
    setApiKey(event.target.value);
  };

  return (
    <div className="shell">
      <aside className={open ? 'open' : ''}>
        <div className="brand">
          <div className="brandmark">TA</div>
          <div><b>Trading AI</b><span>Institutional Workstation</span></div>
        </div>
        <nav>
          {nav.map(([id, label, Icon]) => (
            <a key={id} href={`#/${id}`} className={active === id ? 'active' : ''} onClick={() => setOpen(false)}>
              <Icon size={18} />{label}
            </a>
          ))}
        </nav>
        <div className="api-key">
          <label><KeyRound size={15} />API key</label>
          <input type="password" value={apiKey} onChange={handleApiKeyChange} placeholder="Session only" />
          <button onClick={saveApiKey}>Apply</button>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <button className="menu" onClick={() => setOpen(!open)}><Menu /></button>
          <div><span className="eyebrow">MILESTONE 43</span><h1>Trading Operations Workstation</h1></div>
          <button className="refresh" onClick={() => location.reload()}><RefreshCw size={16} />Refresh</button>
        </header>
        <div className="content"><Page /></div>
      </main>
    </div>
  );
}
