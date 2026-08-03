import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, BrainCircuit, CheckCircle2, RefreshCw, ShieldCheck, SlidersHorizontal, Target, TrendingDown, TrendingUp } from 'lucide-react';
import { performanceLearningApi } from './api';
import type { LearningPolicy, LearningReport, PerformanceMetrics } from './types';
import './performance-learning-refined.css';

const PORTFOLIO_ID = 'PAPER-PRIMARY';
const pct = (v: number, digits = 1) => `${Number(v || 0).toFixed(digits)}%`;
const num = (v: number, digits = 2) => Number(v || 0).toFixed(digits);
const tone = (v: number) => v > 0 ? 'positive' : v < 0 ? 'negative' : 'neutral';
const policyTone = (state: string) => ({ ACTIVE:'positive', APPROVED:'info', REVIEW:'warning', DRAFT:'neutral', RETIRED:'muted' }[state] || 'neutral');

function MetricCard({label,value,detail,kind='neutral'}:{label:string;value:string;detail:string;kind?:string}){
  return <article className={`pl-kpi ${kind}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}
function Bar({value,max=100}:{value:number;max?:number}){
  const width=Math.max(0,Math.min(100,(Number(value||0)/max)*100));
  return <div className="pl-bar"><i style={{width:`${width}%`}} /></div>;
}
function StrategyRow({name,metrics}:{name:string;metrics:PerformanceMetrics}){
  return <tr><td><strong>{name}</strong><small>{metrics.sample_size} observations</small></td><td>{pct(metrics.win_rate)}</td><td className={tone(metrics.expectancy_pct)}>{pct(metrics.expectancy_pct)}</td><td>{num(metrics.profit_factor)}</td><td className={tone(metrics.average_return_pct)}>{pct(metrics.average_return_pct)}</td><td>{pct(metrics.max_drawdown_pct)}</td></tr>;
}

export function PerformanceLearningRefinedPage(){
  const [report,setReport]=useState<LearningReport|null>(null);
  const [policies,setPolicies]=useState<LearningPolicy[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [strategyQuery,setStrategyQuery]=useState('');
  const [activeTab,setActiveTab]=useState<'performance'|'calibration'|'governance'>('performance');
  const [selectedPolicy,setSelectedPolicy]=useState<LearningPolicy|null>(null);

  const load=async()=>{setError('');try{const [r,p]=await Promise.all([performanceLearningApi.report(PORTFOLIO_ID),performanceLearningApi.policies()]);setReport(r.data);setPolicies(p.data||[])}catch(e){setError(e instanceof Error?e.message:'Unable to load performance analytics')}};
  useEffect(()=>{void load()},[]);
  const generate=async()=>{setBusy(true);setError('');try{const r=await performanceLearningApi.generate(PORTFOLIO_ID);setReport(r.data);await load()}catch(e){setError(e instanceof Error?e.message:'Unable to generate report')}finally{setBusy(false)}};

  const strategies=useMemo(()=>Object.entries(report?.by_strategy||{}).filter(([name])=>name.toLowerCase().includes(strategyQuery.toLowerCase())).sort((a,b)=>b[1].expectancy_pct-a[1].expectancy_pct),[report,strategyQuery]);
  const best=strategies[0]; const worst=strategies.length?strategies[strategies.length-1]:undefined;
  const dq=report?.decision_quality;
  const calibrationError=report?.calibration?.length?report.calibration.reduce((a,b)=>a+(b.calibration_error||0),0)/report.calibration.length:0;

  return <section className="pl-page">
    <header className="pl-heading"><div><span className="pl-eyebrow">Portfolio learning · {PORTFOLIO_ID}</span><h2>Performance Analytics & Continuous Learning</h2><p>Measure outcomes, decision quality, calibration, and governed model-improvement recommendations without autonomous parameter activation.</p></div><div className="pl-actions"><button className="secondary" onClick={()=>void load()}><RefreshCw size={16}/>Refresh</button><button onClick={generate} disabled={busy}><BrainCircuit size={16}/>{busy?'Generating…':'Generate governed report'}</button></div></header>
    {error&&<div className="pl-error"><AlertTriangle size={18}/><span>{error}</span></div>}
    {!report?<div className="pl-empty"><BarChart3 size={34}/><h3>No performance report yet</h3><p>Generate a governed report after managed-position observations have been captured.</p></div>:<>
      <div className="pl-kpis">
        <MetricCard label="Observations" value={String(report.overall.sample_size)} detail={`${report.overall.wins} wins · ${report.overall.losses} losses`} />
        <MetricCard label="Win rate" value={pct(report.overall.win_rate)} detail={`Median return ${pct(report.overall.median_return_pct)}`} kind={report.overall.win_rate>=50?'positive':'warning'} />
        <MetricCard label="Expectancy" value={pct(report.overall.expectancy_pct)} detail={`Average ${pct(report.overall.average_return_pct)}`} kind={tone(report.overall.expectancy_pct)} />
        <MetricCard label="Profit factor" value={num(report.overall.profit_factor)} detail="Gross profit ÷ gross loss" kind={report.overall.profit_factor>=1?'positive':'negative'} />
        <MetricCard label="Max drawdown" value={pct(report.overall.max_drawdown_pct)} detail="Observed portfolio path" kind="warning" />
        <MetricCard label="Decision alignment" value={pct(dq?.alignment_rate||0)} detail={`${pct(dq?.override_rate||0)} override rate`} kind={(dq?.alignment_rate||0)>=70?'positive':'warning'} />
      </div>
      <nav className="pl-tabs"><button className={activeTab==='performance'?'active':''} onClick={()=>setActiveTab('performance')}><Activity size={16}/>Performance</button><button className={activeTab==='calibration'?'active':''} onClick={()=>setActiveTab('calibration')}><Target size={16}/>Calibration & decisions</button><button className={activeTab==='governance'?'active':''} onClick={()=>setActiveTab('governance')}><ShieldCheck size={16}/>Learning governance</button></nav>
      {activeTab==='performance'&&<div className="pl-grid">
        <section className="pl-card pl-wide"><header><div><h3>Strategy attribution</h3><p>Ranked by realized expectancy.</p></div><label className="pl-search"><SlidersHorizontal size={15}/><input value={strategyQuery} onChange={e=>setStrategyQuery(e.target.value)} placeholder="Filter strategies"/></label></header><div className="pl-table-wrap"><table><thead><tr><th>Strategy</th><th>Win rate</th><th>Expectancy</th><th>Profit factor</th><th>Avg return</th><th>Drawdown</th></tr></thead><tbody>{strategies.map(([name,m])=><StrategyRow key={name} name={name} metrics={m}/>)}</tbody></table></div></section>
        <section className="pl-card"><header><h3>Performance leaders</h3><TrendingUp size={18}/></header>{best?<div className="pl-highlight positive"><span>Highest expectancy</span><strong>{best[0]}</strong><b>{pct(best[1].expectancy_pct)}</b><small>{best[1].sample_size} observations · {pct(best[1].win_rate)} win rate</small></div>:<p className="pl-muted">No strategy samples.</p>}{worst&&worst!==best&&<div className="pl-highlight negative"><span>Needs review</span><strong>{worst[0]}</strong><b>{pct(worst[1].expectancy_pct)}</b><small>{worst[1].sample_size} observations · PF {num(worst[1].profit_factor)}</small></div>}</section>
        <section className="pl-card"><header><h3>Directional attribution</h3><Activity size={18}/></header>{Object.entries(report.by_direction||{}).map(([name,m])=><div className="pl-direction" key={name}><div><strong>{name}</strong><span>{m.sample_size} samples</span></div><b className={tone(m.expectancy_pct)}>{pct(m.expectancy_pct)}</b><Bar value={m.win_rate}/><small>{pct(m.win_rate)} win rate · PF {num(m.profit_factor)}</small></div>)}</section>
      </div>}
      {activeTab==='calibration'&&<div className="pl-grid">
        <section className="pl-card pl-wide"><header><div><h3>Probability calibration</h3><p>Predicted probability versus observed win rate.</p></div><span className={`pl-chip ${calibrationError>.1?'warning':'positive'}`}>Mean error {pct(calibrationError*100)}</span></header><div className="pl-calibration">{report.calibration.map((b,i)=>{const predicted=b.predicted*100,observed=b.observed*100;return <article key={i}><header><strong>{Math.round(b.lower*100)}–{Math.round(b.upper*100)}%</strong><span>N {b.count}</span></header><div className="pl-cal-row"><label>Predicted <b>{pct(predicted)}</b></label><Bar value={predicted}/></div><div className="pl-cal-row"><label>Observed <b>{pct(observed)}</b></label><Bar value={observed}/></div><small className={b.calibration_error>.1?'negative':'positive'}>Calibration error {pct(b.calibration_error*100)}</small></article>})}</div></section>
        <section className="pl-card"><header><h3>Decision quality</h3><CheckCircle2 size={18}/></header><div className="pl-stat-list"><div><span>Alignment rate</span><b>{pct(dq?.alignment_rate||0)}</b></div><div><span>Manual overrides</span><b>{pct(dq?.override_rate||0)}</b></div><div><span>Profitable alignment</span><b>{pct(dq?.profitable_alignment_rate||0)}</b></div><div><span>Avoidable loss rate</span><b className="negative">{pct(dq?.avoidable_loss_rate||0)}</b></div><div><span>Evaluated decisions</span><b>{dq?.sample_size||0}</b></div></div></section>
        <section className="pl-card"><header><h3>Governed recommendations</h3><BrainCircuit size={18}/></header><div className="pl-recommendations">{report.recommendations.length?report.recommendations.map((r,i)=><article key={`${r.target}-${i}`}><span className="pl-chip info">{r.category}</span><strong>{r.target}</strong><p>{r.reason}</p><div><b>{r.current_value}</b><span>→</span><b>{r.proposed_value}</b></div><small>N {r.sample_size} · confidence {pct(r.confidence*100)}</small></article>):<p className="pl-muted">No parameter changes are currently recommended.</p>}</div></section>
      </div>}
      {activeTab==='governance'&&<div className="pl-grid">
        <section className="pl-card pl-wide"><header><div><h3>Learning-policy registry</h3><p>Human-controlled lifecycle with immutable evidence and versioned activation.</p></div><span className="pl-chip positive">±15% weight boundary</span></header><div className="pl-table-wrap"><table><thead><tr><th>Policy</th><th>Version</th><th>State</th><th>Owner</th><th>Updated</th></tr></thead><tbody>{policies.map(p=><tr key={p.policy_id} onClick={()=>setSelectedPolicy(p)} className={selectedPolicy?.policy_id===p.policy_id?'selected':''}><td><strong>{p.policy_name}</strong><small>{p.reason}</small></td><td>v{p.version}</td><td><span className={`pl-chip ${policyTone(p.state)}`}>{p.state}</span></td><td>{p.approved_by||p.created_by}</td><td>{new Date(p.updated_at).toLocaleString()}</td></tr>)}</tbody></table></div></section>
        <section className="pl-card"><header><h3>Policy controls</h3><ShieldCheck size={18}/></header><ul className="pl-controls"><li>Explicit human approval before activation</li><li>Only one active version per policy</li><li>Immutable supporting evidence</li><li>Append-only audit events</li><li>No autonomous scanner or model changes</li></ul></section>
        <section className="pl-card"><header><h3>Selected policy</h3><SlidersHorizontal size={18}/></header>{selectedPolicy?<><div className="pl-policy-title"><strong>{selectedPolicy.policy_name}</strong><span className={`pl-chip ${policyTone(selectedPolicy.state)}`}>{selectedPolicy.state}</span></div><p>{selectedPolicy.reason}</p><div className="pl-json">{Object.entries(selectedPolicy.parameters||{}).map(([k,v])=><div key={k}><span>{k}</span><b>{v}</b></div>)}</div></>:<p className="pl-muted">Select a policy to inspect its governed parameters.</p>}</section>
      </div>}
    </>}
  </section>;
}
