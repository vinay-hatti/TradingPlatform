import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, MouseEvent as ReactMouseEvent } from 'react';
import { AlertTriangle, ArrowRight, Check, ChevronDown, ChevronRight, Circle, RefreshCw, Sparkles, Waypoints, X } from 'lucide-react';
import { institutionalOptionsApi } from './api';
import { Badge } from './components';
import type { InstitutionalOptionOpportunitySummary, InstitutionalOptionWorkspace } from './types';

const fmt=(v:any,d=1)=>{const n=Number(v);return Number.isFinite(n)?n.toFixed(d):'—'};
const money=(v:any)=>{const n=Number(v);return Number.isFinite(n)?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n):'—'};
const pct=(v:any)=>{const n=Number(v);if(!Number.isFinite(n))return '—';return `${(Math.abs(n)<=1?n*100:n).toFixed(1)}%`};
const words=(v:any)=>String(v??'—').replaceAll('_',' ');

const WORKFLOW_STATES=['DISCOVERED','VALIDATED','STRATEGIES_GENERATED','CONTRACTS_OPTIMIZED','READY_FOR_EXECUTION','EXECUTED','ACTIVE','CLOSED','ATTRIBUTED'] as const;
const FILTER_STATES=[...WORKFLOW_STATES,'REJECTED','CANCELLED'];

const IO_COLUMN_STORAGE_KEY='tradingplatform.institutional-options.column-widths.v1';
const IO_COLUMN_DEFAULTS={symbol:70,setup:90,direction:90,score:65,confidence:85,strategy:220,pop:90,returnOnRisk:100,state:260} as const;
type IoColumnKey=keyof typeof IO_COLUMN_DEFAULTS;
function loadIoColumnWidths(){
  try{
    const parsed=JSON.parse(localStorage.getItem(IO_COLUMN_STORAGE_KEY)||'{}');
    return Object.fromEntries(Object.entries(IO_COLUMN_DEFAULTS).map(([key,value])=>[key,Number.isFinite(Number(parsed?.[key]))?Number(parsed[key]):value])) as Record<IoColumnKey,number>;
  }catch{return {...IO_COLUMN_DEFAULTS} as Record<IoColumnKey,number>}
}
function summaryStateText(state:any){
  const compact:Record<string,string>={DISCOVERED:'Awaiting validation.',VALIDATED:'Thesis validated.',STRATEGIES_GENERATED:'Strategies ranked.',CONTRACTS_OPTIMIZED:'Contracts selected.',READY_FOR_EXECUTION:'Decision complete.',EXECUTED:'Order executed.',ACTIVE:'Position active.',CLOSED:'Position closed.',ATTRIBUTED:'Learning complete.',REJECTED:'Governed rejection.',CANCELLED:'Workflow cancelled.'};
  return compact[String(state)]||'Lifecycle state recorded.';
}

const STATE_INFO:Record<string,{label:string;short:string;meaning:string;next:string}>={
  DISCOVERED:{label:'Discovered',short:'Underlying opportunity identified.',meaning:'Stock Intelligence identified a potential underlying opportunity. Institutional eligibility checks and options analysis have not yet been completed.',next:'Validate the underlying thesis and institutional eligibility.'},
  VALIDATED:{label:'Validated',short:'Underlying thesis passed governance.',meaning:'The underlying opportunity passed market, trend, structure, participation, forecast, freshness, and quality governance and is eligible for options strategy analysis.',next:'Generate and rank compatible option strategies.'},
  STRATEGIES_GENERATED:{label:'Strategies generated',short:'Option strategies evaluated and ranked.',meaning:'The platform evaluated compatible option structures, retained eligible strategies, and preserved rejected alternatives with explicit reasons.',next:'Optimize exact Polygon expirations, strikes, and contract legs.'},
  CONTRACTS_OPTIMIZED:{label:'Contracts optimized',short:'Exact Polygon contract sets are available.',meaning:'Eligible strategies have executable Polygon option contracts with governed expirations, strikes, liquidity, Greeks, spreads, and multi-leg consistency.',next:'Value the alternatives, select the winner, and build the management plan.'},
  READY_FOR_EXECUTION:{label:'Ready for execution',short:'Decision and management plan are complete.',meaning:'One strategy and exact contract recommendation have been selected, valued, risk-managed, frozen into a decision snapshot, and approved for Trade Builder handoff.',next:'Review the decision and open it in Trade Builder.'},
  EXECUTED:{label:'Executed',short:'The approved order was submitted or filled.',meaning:'The selected recommendation has entered broker execution. The immutable decision snapshot remains the authoritative pre-trade record.',next:'Monitor fills and activate position management.'},
  ACTIVE:{label:'Active',short:'The live position is under dynamic management.',meaning:'The trade is open and the platform is monitoring the underlying thesis, structural stop, targets, volatility, liquidity, assignment risk, and time decay.',next:'Follow the governed hold, trail, reduce, roll, or exit action.'},
  CLOSED:{label:'Closed',short:'The position has completed.',meaning:'The trade is no longer active. Realized P&L, execution quality, MFE, MAE, and exit reasons can now be captured.',next:'Complete outcome attribution and learning analysis.'},
  ATTRIBUTED:{label:'Attributed',short:'Outcome learning is complete.',meaning:'The closed trade has been attributed to its setup, strategy, contract selection, regime, execution, and management policy for calibration and learning.',next:'No operational action is required.'},
  REJECTED:{label:'Rejected',short:'Governance declined the opportunity.',meaning:'The opportunity or every available implementation failed one or more institutional governance checks. No options trade is recommended from this record.',next:'Review the rejection reasons; wait for a materially new Stock Intelligence publication before reconsidering.'},
  CANCELLED:{label:'Cancelled',short:'Workflow was intentionally stopped.',meaning:'The opportunity was withdrawn from the institutional workflow by policy, operator action, or a superseding condition before completion.',next:'Review the cancellation audit reason. Restart only from a new governed opportunity.'},
};

function stateInfo(state:any){return STATE_INFO[String(state)]||{label:words(state),short:'Lifecycle status recorded by the platform.',meaning:'This record is in a platform-defined lifecycle state.',next:'Review its audit history for the next governed action.'}}
function uniqueStrings(values:any[]){return [...new Set(values.flatMap(v=>Array.isArray(v)?v:[v]).filter(v=>typeof v==='string'&&v.trim()).map(v=>v.trim()))]}
function rejectionReasons(workspace:InstitutionalOptionWorkspace){
  const o:any=workspace.opportunity||{};
  const audit=(workspace.audit||[]).filter((a:any)=>a.new_state==='REJECTED').map((a:any)=>a.reason);
  const warnings=o.metadata?.eligibility_warnings||o.metadata?.rejection_reasons||[];
  const strategyReasons=(workspace.strategies||[]).flatMap((s:any)=>s.disposition==='REJECTED'?(s.rejection_reasons||[]):[]);
  const decisionRisks=(workspace.decision_snapshot as any)?.explainability?.risks||[];
  return uniqueStrings([warnings,audit,strategyReasons,decisionRisks]);
}
function MiniMetric({label,value,detail}:{label:string;value:any;detail?:string}){return <div className="io-metric"><span>{label}</span><strong>{value}</strong>{detail&&<small>{detail}</small>}</div>}
function Section({title,children,action}:{title:string;children:any;action?:any}){return <section className="io-section"><header><h3>{title}</h3>{action}</header>{children}</section>}

function WorkflowProgress({state}:{state:string}){
  const rejected=state==='REJECTED'||state==='CANCELLED';
  const currentIndex=WORKFLOW_STATES.indexOf(state as any);
  return <div className={`io-workflow-progress ${rejected?'terminal':''}`}>
    <div className="io-progress-track">
      {WORKFLOW_STATES.map((stage,index)=>{
        const complete=!rejected&&currentIndex>index;
        const current=!rejected&&currentIndex===index;
        return <div className={`io-progress-stage ${complete?'complete':''} ${current?'current':''}`} key={stage} title={stateInfo(stage).meaning}>
          <span className="io-progress-icon">{complete?<Check size={13}/>:current?<Circle size={12}/>:<Circle size={10}/>}</span>
          <span>{stateInfo(stage).label}</span>
        </div>
      })}
    </div>
    {rejected&&<div className="io-terminal-branch"><X size={15}/><b>{stateInfo(state).label}</b><span>{stateInfo(state).short}</span></div>}
  </div>
}

function StateCard({workspace,onHandoff}:{workspace:InstitutionalOptionWorkspace;onHandoff:()=>void}){
  const o:any=workspace.opportunity||{};const d:any=workspace.decision_snapshot||{};const info=stateInfo(o.state);const reasons=rejectionReasons(workspace);
  const rejected=o.state==='REJECTED';const cancelled=o.state==='CANCELLED';
  const strategies=workspace.strategies||[];const contracts=workspace.contracts||[];
  const eligibleStrategies=strategies.filter((s:any)=>s.disposition!=='REJECTED').length;
  const executableContracts=contracts.filter((c:any)=>c.executable).length;
  const completedIndex=WORKFLOW_STATES.indexOf(o.state as any);
  const completedCount=completedIndex<0?0:completedIndex+1;
  return <section className={`io-state-card state-${String(o.state).toLowerCase()}`}>
    <div className="io-state-card-main">
      <div className="io-state-heading"><Badge value={o.state}/><div><h3>{info.label}</h3><p>{info.meaning}</p></div></div>
      <div className="io-state-next"><span>Next governed action</span><strong>{info.next}</strong>{o.state==='READY_FOR_EXECUTION'&&<button onClick={onHandoff}><Waypoints size={15}/>Open Trade Builder</button>}</div>
    </div>
    <WorkflowProgress state={o.state}/>
    <div className="io-pipeline-summary">
      <MiniMetric label="Pipeline progress" value={rejected||cancelled?'Terminal':`${completedCount}/${WORKFLOW_STATES.length}`}/>
      <MiniMetric label="Institutional score" value={fmt(d.scorecard?.institutional_score??o.overall_score)}/>
      <MiniMetric label="Probability" value={pct(d.valuation?.probability?.calibrated_probability??o.calibrated_probability)}/>
      <MiniMetric label="Eligible strategies" value={fmt(eligibleStrategies,0)}/>
      <MiniMetric label="Executable contracts" value={fmt(executableContracts,0)}/>
      <MiniMetric label="Selected strategy" value={words(d.selection?.strategy||o.best_strategy||'PENDING')}/>
    </div>
    {(rejected||cancelled)&&<div className="io-rejection-panel"><div className="io-rejection-title"><AlertTriangle size={17}/><div><b>{rejected?'Why this opportunity was rejected':'Why this opportunity was cancelled'}</b><span>{reasons.length?'Persisted reasons from governance and audit history.':'No detailed reason was persisted; review the advanced audit record.'}</span></div></div>{reasons.length?<ul>{reasons.map(reason=><li key={reason}>{words(reason)}</li>)}</ul>:<p>No explicit rejection reason is available on this record.</p>}</div>}
  </section>
}

function StrategyTable({workspace}:{workspace:InstitutionalOptionWorkspace}){
  const contractsByStrategy=useMemo(()=>new Map(workspace.contracts.map(c=>[c.strategy_candidate_id,c])),[workspace.contracts]);
  return <div className="io-table-wrap"><table className="io-table"><thead><tr><th>Rank</th><th>Strategy</th><th>Status</th><th>Score</th><th>POP</th><th>EV</th><th>Return on risk</th><th>Capital</th><th>Liquidity</th><th>Complexity</th></tr></thead><tbody>
    {workspace.strategies.map((s:any)=>{const c:any=contractsByStrategy.get(s.strategy_candidate_id);return <tr key={s.strategy_candidate_id} className={s.selected?'selected':''}><td>{s.rank??'—'}</td><td><b>{words(s.strategy)}</b>{s.selected&&<span className="io-selected">Recommended</span>}</td><td><Badge value={s.disposition}/></td><td>{fmt(s.strategy_score??s.eligibility_score)}</td><td>{pct(s.probability?.calibrated_probability)}</td><td>{money(s.expected_value)}</td><td>{pct(s.expected_return_on_risk)}</td><td>{money(s.capital_required)}</td><td>{fmt(c?.liquidity_score)}</td><td>{words(s.complexity)}</td></tr>})}
  </tbody></table></div>
}

function ContractCards({workspace}:{workspace:InstitutionalOptionWorkspace}){
  const selected=workspace.strategies.find((s:any)=>s.selected)||workspace.strategies[0];
  const contract=workspace.contracts.find((c:any)=>c.strategy_candidate_id===selected?.strategy_candidate_id)||workspace.contracts.find((c:any)=>c.executable);
  if(!contract)return <p className="io-empty">No executable contract recommendation has been persisted yet.</p>;
  return <div className="io-contracts">{(contract.legs||[]).map((leg:any)=><article key={leg.leg_id||leg.option_symbol}><div><Badge value={leg.side}/><b>{leg.quantity_ratio||1} × {leg.option_type}</b></div><strong>{leg.option_symbol}</strong><span>{leg.expiry} · Strike {fmt(leg.strike,2)}</span><small>Bid {money(leg.bid)} · Ask {money(leg.ask)} · Δ {fmt(leg.delta,2)} · IV {pct(leg.implied_volatility)} · OI {fmt(leg.open_interest,0)} · Vol {fmt(leg.volume,0)}</small></article>)}</div>
}

function ProbabilityPanel({workspace}:{workspace:InstitutionalOptionWorkspace}){
  const selected:any=workspace.strategies.find((s:any)=>s.selected)||workspace.strategies[0];
  const p=selected?.probability||{};
  const rows=[['Underlying',p.underlying_probability],['Option payoff',p.option_payoff_probability],['Regime adjustment',p.regime_adjustment],['Structure adjustment',p.structure_adjustment],['Dealer adjustment',p.dealer_adjustment],['Liquidity adjustment',p.liquidity_adjustment],['Final calibrated',p.calibrated_probability]];
  return <div className="io-probability">{rows.map(([label,value])=><div key={String(label)}><span>{label}</span><b>{String(label).includes('adjustment')?`${Number(value||0)>=0?'+':''}${pct(value)}`:pct(value)}</b></div>)}</div>
}

function Detail({workspace,busy,onAction,onHandoff}:{workspace:InstitutionalOptionWorkspace;busy:string;onAction:(action:string)=>void;onHandoff:()=>void}){
  const o:any=workspace.opportunity;const t:any=workspace.thesis||{};const e:any=workspace.execution_recommendation||{};const m:any=workspace.management_snapshots?.[0]||{};const pd:any=(workspace.decision_snapshot as any)?.portfolio_decision||{};const inf:any=(workspace.decision_snapshot as any)?.inflection_intelligence||o.inflection_intelligence||o.metadata?.inflection_intelligence||{};const val:any=(workspace.decision_snapshot as any)?.option_valuation_intelligence||{};
  const selected:any=workspace.strategies.find((s:any)=>s.selected)||workspace.strategies[0];const d:any=workspace.decision_snapshot||{};
  return <div className="io-workspace">
    <StateCard workspace={workspace} onHandoff={onHandoff}/>
    <section className="io-hero"><div><span className="io-kicker">Underlying-first institutional options</span><h2>{o.symbol} · {words(o.category)}</h2><p>{words(o.direction)} thesis on {t.primary_timeframe||'—'} with {words(o.conviction)} conviction.</p></div><div className="io-hero-badges"><Badge value={o.state}/><Badge value={o.direction}/><Badge value={o.conviction}/></div></section>
    <div className="io-summary-grid"><MiniMetric label="Underlying score" value={fmt(o.overall_score)}/><MiniMetric label="Confidence" value={fmt(o.confidence)}/><MiniMetric label="Best strategy" value={words(o.best_strategy||selected?.strategy)}/><MiniMetric label="Calibrated POP" value={pct(o.calibrated_probability||selected?.probability?.calibrated_probability)}/><MiniMetric label="Expected value" value={money(o.expected_value||selected?.expected_value)}/><MiniMetric label="Return on risk" value={pct(o.expected_return_on_risk||selected?.expected_return_on_risk)}/></div>
    <Section title="Underlying thesis"><div className="io-thesis-grid"><MiniMetric label="Market regime" value={words(t.market_regime)}/><MiniMetric label="Sector" value={words(t.sector_context)}/><MiniMetric label="Trend" value={words(t.trend_state)}/><MiniMetric label="Structure" value={words(t.structure_state)}/><MiniMetric label="Participation" value={words(t.participation_state)}/><MiniMetric label="Dealer" value={words(t.dealer_context)}/><MiniMetric label="Forecast" value={words(t.forecast_context)}/><MiniMetric label="Holding horizon" value={t.expected_holding_days_min?`${t.expected_holding_days_min}–${t.expected_holding_days_max||t.expected_holding_days_min} days`:'—'}/></div><div className="io-evidence-grid"><div><h4>Why this opportunity</h4><ul>{(t.evidence||[]).map((x:string)=><li key={x}>{x}</li>)}</ul></div><div className="risk"><h4>Risks and invalidation</h4><ul>{(t.risks||[]).map((x:string)=><li key={x}>{words(x)}</li>)}<li>Invalid below/above {money(t.invalidation_level)}</li></ul></div></div></Section>
    <Section title="Dynamic underlying plan"><div className="io-plan"><div><span>Entry zone</span><strong>{money(t.entry_zone_low)}–{money(t.entry_zone_high)}</strong></div><ArrowRight/><div className="stop"><span>Structural stop</span><strong>{money(t.invalidation_level||e.underlying_stop)}</strong></div><ArrowRight/>{(t.targets||e.underlying_targets||[]).slice(0,3).map((x:number,i:number)=><div key={i}><span>Target {i+1}</span><strong>{money(x)}</strong></div>)}</div><div className="io-management"><MiniMetric label="Trailing policy" value={words(e.trailing_policy||m.trailing_policy)}/><MiniMetric label="Thesis integrity" value={pct(m.thesis_integrity)}/><MiniMetric label="Position health" value={pct(m.position_health)}/><MiniMetric label="Management action" value={words(m.action||'NOT GENERATED')}/><MiniMetric label="Theta exit" value={e.theta_exit_days_to_expiry?`${e.theta_exit_days_to_expiry} DTE`:'—'}/><MiniMetric label="Trade Builder ready" value={e.ready_for_trade_builder?'YES':'NO'}/></div></Section>
    {inf.inflection_score!==undefined&&<Section title="Institutional inflection intelligence"><div className="io-summary-grid"><MiniMetric label="Inflection score" value={fmt(inf.inflection_score)}/><MiniMetric label="Confidence" value={fmt(inf.confidence)}/><MiniMetric label="Transition" value={words(inf.transition_state)}/><MiniMetric label="Direction" value={words(inf.direction)}/><MiniMetric label="Expected horizon" value={inf.horizon_min_sessions?`${inf.horizon_min_sessions}–${inf.horizon_max_sessions} sessions`:'—'}/><MiniMetric label="Velocity" value={fmt(inf.velocity)}/><MiniMetric label="Acceleration" value={fmt(inf.acceleration)}/></div><div className="io-thesis-grid">{Object.entries(inf.components||{}).map(([k,v])=><MiniMetric key={k} label={words(k)} value={fmt(v)}/>)}</div>{inf.evidence?.length?<div className="io-warning-list">{inf.evidence.map((x:string)=><span key={x}>✓ {x}</span>)}</div>:null}{inf.conflicting_evidence?.length?<div className="io-warning-list">{inf.conflicting_evidence.map((x:string)=><span key={x}>⚠ {x}</span>)}</div>:null}</Section>}
    {val.classification&&<Section title="Institutional option valuation & mispricing"><div className="io-summary-grid"><MiniMetric label="Classification" value={words(val.classification)}/><MiniMetric label="Model fair value" value={money(val.model_fair_value)}/><MiniMetric label="Executable fair value" value={money(val.fair_value)}/><MiniMetric label="Market package mid" value={money(val.market_mid)}/><MiniMetric label="Executable mispricing" value={`${fmt(val.mispricing_pct)}%`}/><MiniMetric label="Edge score" value={fmt(val.edge_score)}/><MiniMetric label="Stability" value={fmt(val.stability_index)}/><MiniMetric label="Confidence" value={fmt(val.confidence)}/></div><div className="io-thesis-grid"><MiniMetric label="Volatility edge" value={`${fmt(val.components?.volatility_edge_pct)}%`}/><MiniMetric label="Surface edge" value={`${fmt(val.components?.surface_edge_pct)}%`}/><MiniMetric label="Relative-value edge" value={`${fmt(val.components?.relative_value_edge_pct)}%`} detail={val.relative_value?.relationship_regime?words(val.relative_value.relationship_regime):undefined}/><MiniMetric label="Event edge" value={`${fmt(val.components?.event_edge_pct)}%`} detail={val.event_pricing?.event_type?`${words(val.event_pricing.event_type)} · ${val.event_pricing.days_to_event}d`:words(val.event_pricing?.status)}/><MiniMetric label="Dealer-flow edge" value={`${fmt(val.components?.dealer_flow_edge_pct)}%`}/><MiniMetric label="Execution edge" value={`${fmt(val.components?.execution_edge_pct)}%`}/></div>{val.evidence?.length?<div className="io-warning-list">{val.evidence.map((x:string)=><span key={x}>✓ {x}</span>)}</div>:null}{val.conflicting_evidence?.length?<div className="io-warning-list">{val.conflicting_evidence.map((x:string)=><span key={x}>⚠ {x}</span>)}</div>:null}</Section>}
    <Section title="Institutional decision"><div className="io-summary-grid"><MiniMetric label="Institutional score" value={fmt(d.scorecard?.institutional_score)}/><MiniMetric label="Selected strategy" value={words(d.selection?.strategy||selected?.strategy)}/><MiniMetric label="Calibrated POP" value={pct(d.valuation?.probability?.calibrated_probability)}/><MiniMetric label="Expected value" value={money(d.valuation?.expected_value)}/><MiniMetric label="Capital required" value={money(d.valuation?.capital_required)}/><MiniMetric label="Contract quality" value={fmt(d.scorecard?.contract_quality)}/><MiniMetric label="Portfolio fit" value={d.portfolio_context?.available?fmt(d.scorecard?.portfolio_fit):'N/A'}/><MiniMetric label="Execution quality" value={fmt(d.scorecard?.execution_quality)}/><MiniMetric label="Decision version" value={d.policy_version||'—'}/><MiniMetric label="Portfolio fit" value={fmt(pd.scores?.portfolio_fit_score)}/><MiniMetric label="Portfolio rank" value={pd.ranking?.rank?`${pd.ranking.rank} / ${pd.ranking.candidate_count}`:'—'}/><MiniMetric label="Final portfolio score" value={fmt(pd.scores?.final_portfolio_score)}/><MiniMetric label="Recommended size" value={pd.capital_allocation?.recommended_quantity??'—'}/><MiniMetric label="Opportunity cost" value={fmt(pd.scores?.opportunity_cost_score)}/><MiniMetric label="Portfolio decision" value={words(pd.decision||'PENDING')}/></div>{pd.explainability?.positive_reasons?.length?<div className="io-warning-list">{pd.explainability.positive_reasons.map((x:string)=><span key={x}>✓ {x}</span>)}</div>:null}{d.portfolio_context?.warnings?.length?<div className="io-warning-list">{d.portfolio_context.warnings.map((x:string)=><span key={x}>{words(x)}</span>)}</div>:null}</Section>
    <Section title="Ranked strategy implementations"><StrategyTable workspace={workspace}/></Section>
    <div className="io-two-column"><Section title="Exact Polygon contract legs"><ContractCards workspace={workspace}/></Section><Section title="Probability decomposition"><ProbabilityPanel workspace={workspace}/></Section></div>
    <Section title="Workflow actions"><div className="io-actions"><button disabled={!!busy} onClick={()=>onAction('strategies')}><Sparkles size={15}/>Generate strategies</button><button disabled={!!busy} onClick={()=>onAction('contracts')}>Optimize contracts</button><button disabled={!!busy} onClick={()=>onAction('value')}>Value & rank</button><button disabled={!!busy} onClick={()=>onAction('management')}>Generate management</button><button disabled={!!busy} onClick={()=>onAction('decision')}>Build decision snapshot</button><button disabled={!e.ready_for_trade_builder||!!busy} onClick={onHandoff}><Waypoints size={15}/>Create Trade Plan / Open Trade Builder</button>{busy&&<span>Running {busy}…</span>}</div></Section>
    <details className="io-advanced"><summary>Advanced lineage and audit</summary><div className="io-lineage"><pre>{JSON.stringify(o.lineage||{},null,2)}</pre><ol>{workspace.audit.map((a:any,i:number)=><li key={i}><b>{a.new_state}</b> · {a.reason} <small>{a.event_timestamp}</small></li>)}</ol></div></details>
  </div>
}

export function InstitutionalOptionsPage(){
  const [items,setItems]=useState<InstitutionalOptionOpportunitySummary[]>([]);const [expanded,setExpanded]=useState<string|null>(null);const [details,setDetails]=useState<Record<string,InstitutionalOptionWorkspace>>({});const [loading,setLoading]=useState(true);const [error,setError]=useState('');const [busy,setBusy]=useState('');
  const [search,setSearch]=useState('');const [direction,setDirection]=useState('');const [state,setState]=useState('');const [minimumScore,setMinimumScore]=useState(0);const [view,setView]=useState<'current'|'history'|'all'>('current');
  const [columnWidths,setColumnWidths]=useState<Record<IoColumnKey,number>>(()=>loadIoColumnWidths());
  const resizeRef=useRef<{key:IoColumnKey;startX:number;startWidth:number}|null>(null);
  const columnStyle=useMemo(()=>({
    '--io-symbol':`${columnWidths.symbol}px`,'--io-setup':`${columnWidths.setup}px`,'--io-direction':`${columnWidths.direction}px`,'--io-score':`${columnWidths.score}px`,'--io-confidence':`${columnWidths.confidence}px`,'--io-strategy':`${columnWidths.strategy}px`,'--io-pop':`${columnWidths.pop}px`,'--io-return':`${columnWidths.returnOnRisk}px`,'--io-state':`${columnWidths.state}px`,
  } as CSSProperties),[columnWidths]);
  const startResize=(key:IoColumnKey,e:ReactMouseEvent)=>{e.preventDefault();e.stopPropagation();resizeRef.current={key,startX:e.clientX,startWidth:columnWidths[key]};document.body.classList.add('io-resizing');};
  useEffect(()=>{
    const move=(e:MouseEvent)=>{const r=resizeRef.current;if(!r)return;const min={symbol:55,setup:70,direction:80,score:55,confidence:75,strategy:130,pop:70,returnOnRisk:85,state:150}[r.key];const max={symbol:140,setup:180,direction:150,score:110,confidence:140,strategy:420,pop:130,returnOnRisk:170,state:440}[r.key];const width=Math.max(min,Math.min(max,r.startWidth+(e.clientX-r.startX)));setColumnWidths(v=>({...v,[r.key]:width}));};
    const up=()=>{if(!resizeRef.current)return;resizeRef.current=null;document.body.classList.remove('io-resizing');};
    window.addEventListener('mousemove',move);window.addEventListener('mouseup',up);return()=>{window.removeEventListener('mousemove',move);window.removeEventListener('mouseup',up);document.body.classList.remove('io-resizing')};
  },[]);
  useEffect(()=>{try{localStorage.setItem(IO_COLUMN_STORAGE_KEY,JSON.stringify(columnWidths))}catch{}},[columnWidths]);
  const load=async(preserveSelection=false)=>{setLoading(true);setError('');try{const r=await institutionalOptionsApi.workspaceList({limit:2000,view});setItems(r.data as any[]);if(!preserveSelection){setExpanded(null);setDetails({})}}catch(e:any){setError(e.message)}finally{setLoading(false)}};
  useEffect(()=>{load()},[view]);
  const filtered=useMemo(()=>items.filter(x=>(!search||x.symbol.toUpperCase().includes(search.toUpperCase()))&&(!direction||x.direction===direction)&&(!state||x.state===state)&&Number(x.overall_score)>=minimumScore),[items,search,direction,state,minimumScore]);
  const toggle=async(id:string)=>{if(expanded===id){setExpanded(null);return}setExpanded(id);if(!details[id]){try{const r=await institutionalOptionsApi.workspace(id);setDetails(v=>({...v,[id]:r.data as InstitutionalOptionWorkspace}))}catch(e:any){setError(e.message)}}};
  const action=async(id:string,kind:string)=>{setBusy(kind);try{if(kind==='strategies')await institutionalOptionsApi.generateStrategies(id);if(kind==='contracts')await institutionalOptionsApi.optimizeContracts(id);if(kind==='value')await institutionalOptionsApi.valueStrategies(id);if(kind==='management')await institutionalOptionsApi.generateManagement(id);if(kind==='decision')await institutionalOptionsApi.buildDecision(id);const r=await institutionalOptionsApi.workspace(id);setDetails(v=>({...v,[id]:r.data as InstitutionalOptionWorkspace}));await load(true)}catch(e:any){setError(e.message)}finally{setBusy('')}};
  const handoff=async(id:string)=>{setBusy('handoff');try{const config=await institutionalOptionsApi.tradeBuilderConfig();const riskConfig=config.data as any;const r=await institutionalOptionsApi.handoffTradeBuilder(id,{account_id:'PAPER-PRIMARY',capital:riskConfig.capital,risk_budget_pct:riskConfig.risk_budget_pct,overrides:{}});const planId=(r.data as any).trade_plan_id;if(planId){sessionStorage.setItem('m62_trade_plan_id',planId);location.hash='#/trade-builder'}}catch(e:any){setError(e.message)}finally{setBusy('')}};
  return <section className="institutional-options-page"><div className="page-title"><div><h2>Institutional options</h2><p>Underlying-first opportunities, ranked strategy implementations, exact Polygon contracts, and dynamic management.</p></div><button onClick={()=>load()} disabled={loading}><RefreshCw size={15}/>{loading?'Loading…':'Refresh'}</button></div>
    {error&&<div className="scanner-error">{error}</div>}
    <div className="io-state-guide"><b>State guide</b><span>Expand any opportunity to see its current stage, plain-language meaning, completed workflow, next action, and persisted rejection reasons.</span></div>
    <div className="io-filter-bar"><label>View<select value={view} onChange={e=>setView(e.target.value as any)}><option value="current">Current run</option><option value="history">Historical</option><option value="all">All runs</option></select></label><label>Symbol<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search"/></label><label>Direction<select value={direction} onChange={e=>setDirection(e.target.value)}><option value="">All</option><option>BULLISH</option><option>BEARISH</option></select></label><label>State<select value={state} onChange={e=>setState(e.target.value)}><option value="">All</option>{FILTER_STATES.map(x=><option key={x}>{x}</option>)}</select></label><label>Minimum score<input type="number" min="0" max="100" value={minimumScore} onChange={e=>setMinimumScore(Number(e.target.value)||0)}/></label><span>{filtered.length} opportunities · {view==='current'?'latest Stock Intelligence run':view==='history'?'historical runs':'all runs'}</span></div>
    <div className="io-list" style={columnStyle}><div className="io-list-head"><span></span><span className="io-resizable-head">Symbol<i className="io-column-resizer" onMouseDown={e=>startResize('symbol',e)}/></span><span className="io-resizable-head">Setup<i className="io-column-resizer" onMouseDown={e=>startResize('setup',e)}/></span><span className="io-resizable-head">Direction<i className="io-column-resizer" onMouseDown={e=>startResize('direction',e)}/></span><span className="io-resizable-head">Score<i className="io-column-resizer" onMouseDown={e=>startResize('score',e)}/></span><span className="io-resizable-head">Confidence<i className="io-column-resizer" onMouseDown={e=>startResize('confidence',e)}/></span><span className="io-resizable-head">Best strategy<i className="io-column-resizer" onMouseDown={e=>startResize('strategy',e)}/></span><span className="io-resizable-head">POP<i className="io-column-resizer" onMouseDown={e=>startResize('pop',e)}/></span><span className="io-resizable-head">Return on risk<i className="io-column-resizer" onMouseDown={e=>startResize('returnOnRisk',e)}/></span><span className="io-resizable-head">State<i className="io-column-resizer" onMouseDown={e=>startResize('state',e)}/></span></div>{filtered.map(item=>{return <div className="io-list-item" key={item.opportunity_id}><button className="io-list-row" onClick={()=>toggle(item.opportunity_id)}><span>{expanded===item.opportunity_id?<ChevronDown/>:<ChevronRight/>}</span><b>{item.symbol}</b><span>{words(item.category)}</span><Badge value={item.direction}/><strong>{fmt(item.overall_score)}</strong><span>{fmt(item.confidence)}</span><span className="io-strategy-cell" title={words(item.best_strategy||'PENDING')}>{words(item.best_strategy||'PENDING')}</span><span>{pct(item.calibrated_probability)}</span><span>{pct(item.expected_return_on_risk)}</span><span className="io-state-cell"><Badge value={item.state}/><small>{summaryStateText(item.state)}</small></span></button>{expanded===item.opportunity_id&&<div className="io-expanded">{details[item.opportunity_id]?<Detail workspace={details[item.opportunity_id]} busy={busy} onAction={(kind)=>action(item.opportunity_id,kind)} onHandoff={()=>handoff(item.opportunity_id)}/>:<p className="io-empty">Loading decision workspace…</p>}</div>}</div>})}</div>
    {!loading&&!filtered.length&&<p className="io-empty">No Institutional Options opportunities match the selected filters. Ingest Stock Intelligence opportunities through the API first.</p>}
  </section>
}
