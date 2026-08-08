import { useCallback, useEffect, useState, type ComponentType } from 'react';
import type { WorkspaceKey } from './types';
import { AdvancedTradeBuilderPage } from './AdvancedTradeBuilderPage';
import { StockIntelligenceScannerPage } from './StockIntelligenceScannerPage';
import { InstitutionalOptionsPage } from './InstitutionalOptionsPage';
import { InstitutionalIntelligencePage } from './InstitutionalIntelligencePage';
import { InflectionAnalyticsPage } from './InflectionAnalyticsPage';
import { OptionsMispricingAnalyticsPage } from './OptionsMispricingAnalyticsPage';
import { OpexIntelligencePage } from './OpexIntelligencePage';
import { PortfolioIntelligencePage } from './PortfolioIntelligencePage';
import { PerformanceLearningPage } from './PerformanceLearningPage';
import { ExecutionWorkspacePage } from './ExecutionWorkspacePage';
import { ExecutionIntelligencePage } from './ExecutionIntelligencePage';
import { CommandCenter, DailyScannerPage, MarketOverviewPage, OptionScannerPage, OpportunityWorkspacePage } from './pages';
import { GlobalIntelligenceHeader, WorkspaceCanvas, WorkspaceSidebar, WorkspaceStatusBar } from './WorkspaceChrome';
import { CommandPalette, loadWorkspaceList, loadWorkspacePreferences, persistWorkspaceList, PreferencesPanel, useWorkspaceShortcuts, type WorkspacePreference } from './WorkspaceProductivity';
import './styles.css';
import { InstitutionalIntelligenceRefinedPage } from './InstitutionalIntelligenceRefinedPage';
import './institutional-intelligence-refined.css';
import './analytics-dashboard.css';
import './opex-intelligence.css';

import { WorkstationRouteBoundary } from './WorkstationRouteBoundary';
import './workstation-shell-recovery.css';
import { PortfolioIntelligenceRefinedPage } from './PortfolioIntelligenceRefinedPage';
import { MarketOverviewRefinedPage } from './MarketOverviewRefinedPage';
import { PerformanceLearningRefinedPage } from './PerformanceLearningRefinedPage';
const pages: Record<WorkspaceKey, ComponentType> = {
  market: MarketOverviewPage, 'analytics-inflection': InflectionAnalyticsPage, 'analytics-options-mispricing': OptionsMispricingAnalyticsPage, 'analytics-opex': OpexIntelligencePage, scanner: DailyScannerPage, 'stock-intelligence': StockIntelligenceScannerPage,
  'option-scanner': OptionScannerPage, 'institutional-options': InstitutionalOptionsPage, opportunities: OpportunityWorkspacePage,
  intelligence: InstitutionalIntelligenceRefinedPage, 'trade-builder': AdvancedTradeBuilderPage,
  portfolio: PortfolioIntelligenceRefinedPage, 'performance-learning': PerformanceLearningRefinedPage,
  'execution-workspace': ExecutionWorkspacePage, 'execution-intelligence': ExecutionIntelligencePage, execution: ExecutionWorkspacePage, risk: PortfolioIntelligenceRefinedPage, positions: PortfolioIntelligenceRefinedPage, exits: PortfolioIntelligenceRefinedPage, command: CommandCenter,
};

function route(): WorkspaceKey {
  const raw=location.hash.replace('#/','');
  if (raw === 'overview') {
    if (location.hash !== '#/market') history.replaceState(null, '', '#/market');
    return 'market';
  }
  if (raw === 'execution') {
    if (location.hash !== '#/execution-workspace') history.replaceState(null, '', '#/execution-workspace');
    return 'execution-workspace';
  }
  if (raw === 'risk' || raw === 'positions' || raw === 'exits') {
    if (location.hash !== '#/portfolio') history.replaceState(null, '', '#/portfolio');
    return 'portfolio';
  }
  return raw in pages ? raw as WorkspaceKey : 'market';
}

export default function App(){
  const [active,setActive]=useState<WorkspaceKey>(route());
  const [open,setOpen]=useState(false);
  const [collapsed,setCollapsed]=useState(localStorage.getItem('workstation-nav-collapsed')==='true');
  const [refreshToken,setRefreshToken]=useState(0);
  const [paletteOpen,setPaletteOpen]=useState(false);
  const [preferencesOpen,setPreferencesOpen]=useState(false);
  const [preferences,setPreferences]=useState<WorkspacePreference>(loadWorkspacePreferences);
  const [favorites,setFavorites]=useState<WorkspaceKey[]>(()=>loadWorkspaceList('workstation-favorites'));
  const [recent,setRecent]=useState<WorkspaceKey[]>(()=>loadWorkspaceList('workstation-recent'));

  useEffect(()=>{
    const handler=()=>setActive(route());
    addEventListener('hashchange',handler);
    return()=>removeEventListener('hashchange',handler);
  },[]);

  useEffect(()=>{
    setRecent(previous=>{
      const next=[active,...previous.filter(item=>item!==active)].slice(0,6);
      persistWorkspaceList('workstation-recent',next);
      return next;
    });
  },[active]);

  useEffect(()=>{
    localStorage.setItem('workstation-preferences',JSON.stringify(preferences));
  },[preferences]);

  const Page=pages[active];
  const navigate=useCallback((workspace:WorkspaceKey)=>{
    location.hash=`#/${workspace}`;
    setOpen(false);
  },[]);
  const toggleCollapsed=useCallback(()=>setCollapsed(value=>{
    localStorage.setItem('workstation-nav-collapsed',String(!value));
    return !value;
  }),[]);
  const refresh=useCallback(()=>setRefreshToken(value=>value+1),[]);
  const toggleFavorite=useCallback((workspace:WorkspaceKey)=>setFavorites(previous=>{
    const next=previous.includes(workspace)?previous.filter(item=>item!==workspace):[workspace,...previous].slice(0,6);
    persistWorkspaceList('workstation-favorites',next);
    return next;
  }),[]);
  const openPreferences=useCallback(()=>{setPaletteOpen(false);setPreferencesOpen(true)},[]);

  useWorkspaceShortcuts({
    openPalette: useCallback(()=>setPaletteOpen(true),[]),
    openPreferences,
    refresh,
    toggleNavigation: toggleCollapsed,
  });

  const shellClasses=[
    'shell workstation-shell',
    collapsed?'navigation-collapsed':'',
    preferences.compactDensity?'compact-density':'',
    preferences.reducedMotion?'reduced-motion':'',
    preferences.showStatusBar?'':'statusbar-hidden',
  ].filter(Boolean).join(' ');

  return <div className={shellClasses}>
    <WorkspaceSidebar active={active} open={open} collapsed={collapsed} onNavigate={()=>setOpen(false)} onToggleCollapsed={toggleCollapsed} favorites={favorites} onToggleFavorite={toggleFavorite}/>
    <main>
      <GlobalIntelligenceHeader active={active} onMenu={()=>setOpen(!open)} onRefresh={refresh} refreshing={false} onOpenPalette={()=>setPaletteOpen(true)} onOpenPreferences={openPreferences} favorite={favorites.includes(active)} onToggleFavorite={()=>toggleFavorite(active)}/>
      <WorkspaceCanvas><div className="content" key={`${active}-${refreshToken}`}><WorkstationRouteBoundary routeKey={active}><Page/></WorkstationRouteBoundary></div></WorkspaceCanvas>
      {preferences.showStatusBar&&<WorkspaceStatusBar active={active}/>} 
    </main>
    <CommandPalette open={paletteOpen} onClose={()=>setPaletteOpen(false)} onNavigate={navigate} onRefresh={refresh} onToggleNavigation={toggleCollapsed} onOpenPreferences={openPreferences} recent={recent} favorites={favorites}/>
    <PreferencesPanel open={preferencesOpen} value={preferences} onChange={setPreferences} onClose={()=>setPreferencesOpen(false)}/>
  </div>;
}
