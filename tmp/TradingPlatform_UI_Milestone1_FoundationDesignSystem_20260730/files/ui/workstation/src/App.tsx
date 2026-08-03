import { useEffect, useState, type ComponentType } from 'react';
import type { WorkspaceKey } from './types';
import { AdvancedTradeBuilderPage } from './AdvancedTradeBuilderPage';
import { InstitutionalIntelligencePage } from './InstitutionalIntelligencePage';
import { PortfolioIntelligencePage } from './PortfolioIntelligencePage';
import { PerformanceLearningPage } from './PerformanceLearningPage';
import { CommandCenter, DailyScannerPage, Execution, Exits, MarketOverviewPage, OptionScannerPage, OpportunityWorkspacePage, Overview, Positions, Risk } from './pages';
import { GlobalIntelligenceHeader, WorkspaceCanvas, WorkspaceSidebar, WorkspaceStatusBar } from './WorkspaceChrome';
import './styles.css';

const pages: Record<WorkspaceKey, ComponentType> = {
  overview: Overview, market: MarketOverviewPage, scanner: DailyScannerPage,
  'option-scanner': OptionScannerPage, opportunities: OpportunityWorkspacePage,
  intelligence: InstitutionalIntelligencePage, 'trade-builder': AdvancedTradeBuilderPage,
  portfolio: PortfolioIntelligencePage, 'performance-learning': PerformanceLearningPage,
  risk: Risk, execution: Execution, positions: Positions, exits: Exits, command: CommandCenter,
};
function route(): WorkspaceKey { const value=location.hash.replace('#/','') as WorkspaceKey; return value in pages?value:'overview'; }
export default function App(){
  const [active,setActive]=useState<WorkspaceKey>(route());
  const [open,setOpen]=useState(false);
  const [collapsed,setCollapsed]=useState(localStorage.getItem('workstation-nav-collapsed')==='true');
  const [refreshToken,setRefreshToken]=useState(0);
  useEffect(()=>{const handler=()=>setActive(route());addEventListener('hashchange',handler);return()=>removeEventListener('hashchange',handler)},[]);
  const Page=pages[active];
  const toggleCollapsed=()=>setCollapsed(value=>{localStorage.setItem('workstation-nav-collapsed',String(!value));return !value});
  return <div className={`shell workstation-shell ${collapsed?'navigation-collapsed':''}`}>
    <WorkspaceSidebar active={active} open={open} collapsed={collapsed} onNavigate={()=>setOpen(false)} onToggleCollapsed={toggleCollapsed}/>
    <main>
      <GlobalIntelligenceHeader active={active} onMenu={()=>setOpen(!open)} onRefresh={()=>setRefreshToken(v=>v+1)} refreshing={false}/>
      <WorkspaceCanvas><div className="content" key={`${active}-${refreshToken}`}><Page/></div></WorkspaceCanvas>
      <WorkspaceStatusBar active={active}/>
    </main>
  </div>;
}
