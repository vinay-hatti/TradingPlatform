import { useEffect, useMemo, useState } from 'react';
import { institutionalIntelligenceApi, opportunityApi } from './api';
import type { IntelligenceBundle, IntelligenceEvidence, IntelligenceScore, OpportunityRecord } from './types';

const pct=(value:number)=>`${Math.round(value*100)}%`;
const num=(value:number|null|undefined,digits=1)=>value==null?'—':Number(value).toFixed(digits);
const tone=(value:number)=>value>=75?'positive':value>=55?'warning':'critical';
const opportunityScore=(item:OpportunityRecord):number|null=>{
  const payload=item.source_payload??{};
  const value=payload.ai_score??payload.score??payload.opportunity_score??item.metadata?.ai_score??item.metadata?.score;
  const numeric=Number(value);
  return Number.isFinite(numeric)?numeric:null;
};

function ScoreRing({value,label}:{value:number;label:string}){
  const safe=Math.max(0,Math.min(100,value));
  return <div className="ii-score-ring" style={{'--score':safe} as React.CSSProperties} aria-label={`${label} ${safe.toFixed(0)}`}>
    <div><strong>{safe.toFixed(0)}</strong><span>{label}</span></div>
  </div>;
}

function EvidenceRow({item}:{item:IntelligenceEvidence}){
  return <article className="ii-evidence-row">
    <div className="ii-evidence-main"><strong>{item.title}</strong><span>{item.description}</span></div>
    <div className="ii-evidence-meta"><span>{item.source}</span><b>{num(item.contribution)}</b><small>{pct(item.confidence)}</small></div>
  </article>;
}

function ScoreCard({score,expanded,onToggle}:{score:IntelligenceScore;expanded:boolean;onToggle:()=>void}){
  return <section className={`ii-score-card tone-${tone(score.overall_score)}`}>
    <button className="ii-score-card-head" onClick={onToggle} aria-expanded={expanded}>
      <div><span>{score.category}</span><strong>{score.name}</strong></div>
      <div className="ii-score-card-value"><b>{score.overall_score.toFixed(1)}</b><small>{score.status}</small></div>
    </button>
    <div className="ii-meter"><span style={{width:`${Math.max(0,Math.min(100,score.overall_score))}%`}}/></div>
    <div className="ii-score-card-summary"><span>Confidence {pct(score.confidence)}</span><span>Percentile {score.percentile.toFixed(0)}</span><span>{score.trend}</span></div>
    {expanded&&<div className="ii-score-card-detail">
      {score.evidence.length?score.evidence.map((item)=><EvidenceRow key={`${item.source}-${item.title}`} item={item}/>):<p className="ii-muted">No evidence published.</p>}
      {score.risks?.length>0&&<div className="ii-risk-list"><h4>Risks</h4>{score.risks.map((risk:any,index:number)=><article key={index}><b>{risk.title||risk.description||'Risk'}</b><span>{risk.description||''}</span><small>{risk.mitigation||''}</small></article>)}</div>}
    </div>}
  </section>;
}

export function InstitutionalIntelligenceRefinedPage(){
  const [opportunities,setOpportunities]=useState<OpportunityRecord[]>([]);
  const [selectedId,setSelectedId]=useState('');
  const [bundle,setBundle]=useState<IntelligenceBundle|null>(null);
  const [history,setHistory]=useState<any[]>([]);
  const [query,setQuery]=useState('');
  const [category,setCategory]=useState('ALL');
  const [expanded,setExpanded]=useState<Record<string,boolean>>({});
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');

  useEffect(()=>{opportunityApi.list().then((response)=>{const rows=response.data||[];setOpportunities(rows);if(rows[0])setSelectedId(rows[0].opportunity_id)}).catch((reason)=>setError(reason.message||String(reason)))},[]);
  useEffect(()=>{if(!selectedId)return;const controller=new AbortController();setLoading(true);setError('');Promise.all([
    institutionalIntelligenceApi.get(selectedId,controller.signal),
    institutionalIntelligenceApi.history(selectedId,controller.signal).catch(()=>({data:[]})),
  ]).then(([current,versions])=>{setBundle(current.data);setHistory(versions.data||[])}).catch((reason)=>{if(reason.name!=='AbortError')setError(reason.message||String(reason))}).finally(()=>setLoading(false));return()=>controller.abort()},[selectedId]);

  const selected=opportunities.find((item)=>item.opportunity_id===selectedId);
  const visibleScores=useMemo(()=>bundle?.scores.filter((score)=>category==='ALL'||score.category===category)??[],[bundle,category]);
  const filteredOpportunities=useMemo(()=>{const needle=query.trim().toLowerCase();return opportunities.filter((item)=>!needle||`${item.symbol} ${item.strategy} ${item.direction} ${item.workflow_state}`.toLowerCase().includes(needle))},[opportunities,query]);
  const categories=useMemo(()=>Array.from(new Set(bundle?.scores.map((score)=>score.category)??[])),[bundle]);

  const regenerate=()=>{if(!selectedId)return;setLoading(true);setError('');institutionalIntelligenceApi.generate(selectedId).then((response)=>setBundle(response.data)).then(()=>institutionalIntelligenceApi.history(selectedId).then((response)=>setHistory(response.data||[]))).catch((reason)=>setError(reason.message||String(reason))).finally(()=>setLoading(false))};
  const navigate=(route:string)=>{window.location.hash=route};

  return <section className="ii-workspace">
    <header className="ii-command-header">
      <div><span className="ii-eyebrow">Opportunity Research</span><h1>Institutional Intelligence</h1><p>Explainability, evidence, risk, recommendations, and trade construction from one governed snapshot.</p></div>
      <div className="ii-command-actions"><button className="secondary" onClick={()=>navigate('#/opportunities')}>Opportunity Inbox</button><button onClick={regenerate} disabled={!selectedId||loading}>{loading?'Generating…':'Generate snapshot'}</button></div>
    </header>
    {error&&<div className="ii-error" role="alert"><b>Unable to load intelligence</b><span>{error}</span></div>}
    <div className="ii-layout">
      <aside className="ii-opportunity-rail">
        <div className="ii-rail-head"><label>Opportunity search<input value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="Symbol, strategy, state"/></label><span>{filteredOpportunities.length} opportunities</span></div>
        <div className="ii-opportunity-list">{filteredOpportunities.map((item)=><button key={item.opportunity_id} className={item.opportunity_id===selectedId?'active':''} onClick={()=>setSelectedId(item.opportunity_id)}>
          <div><strong>{item.symbol}</strong><span>{item.direction} · {item.strategy}</span></div><div><b>{num(opportunityScore(item))}</b><small>{item.workflow_state}</small></div>
        </button>)}</div>
      </aside>
      <main className="ii-main">
        {!bundle?<div className="ii-empty"><h2>{loading?'Loading intelligence…':'Select an opportunity'}</h2><p>Choose a canonical opportunity to inspect its institutional intelligence snapshot.</p></div>:<>
          <section className="ii-hero">
            <div className="ii-symbol-block"><span>{selected?.workflow_state}</span><h2>{selected?.symbol}</h2><p>{selected?.direction} · {selected?.strategy}</p><small>Snapshot {bundle.snapshot_id}</small></div>
            <ScoreRing value={bundle.health.score} label="Health"/>
            <ScoreRing value={bundle.explanation.confidence*100} label="Confidence"/>
            <div className="ii-hero-facts"><div><span>Risk profile</span><b>{bundle.profile.risk_profile||'—'}</b></div><div><span>Preferred strategy</span><b>{bundle.profile.preferred_strategy||bundle.playbook.preferred_strategy}</b></div><div><span>Health direction</span><b>{bundle.health.direction}</b></div><div><span>Recommended action</span><b>{bundle.health.recommended_action}</b></div></div>
          </section>
          <section className="ii-summary-grid">
            <article className="ii-panel ii-span-2"><div className="ii-panel-title"><h3>Executive thesis</h3><span>{pct(bundle.explanation.confidence)} confidence</span></div><p className="ii-thesis">{bundle.explanation.summary}</p><div className="ii-driver-columns"><div><h4>Positive drivers</h4>{bundle.explanation.positive_drivers.map((item)=><EvidenceRow key={`positive-${item.title}`} item={item}/>)}</div><div><h4>Negative drivers</h4>{bundle.explanation.negative_drivers.map((item)=><EvidenceRow key={`negative-${item.title}`} item={item}/>)}</div></div></article>
            <article className="ii-panel"><div className="ii-panel-title"><h3>Institutional checklist</h3><span>{bundle.explanation.checklist.filter((item)=>item.passed).length}/{bundle.explanation.checklist.length} passed</span></div><div className="ii-checklist">{bundle.explanation.checklist.map((item)=><div key={item.category} className={item.passed?'passed':'failed'}><span>{item.passed?'✓':'!'}</span><div><b>{item.label}</b><small>{item.category}</small></div><strong>{item.score.toFixed(1)}</strong></div>)}</div></article>
          </section>
          <nav className="ii-category-tabs"><button className={category==='ALL'?'active':''} onClick={()=>setCategory('ALL')}>All intelligence</button>{categories.map((item)=><button key={item} className={category===item?'active':''} onClick={()=>setCategory(item)}>{item}</button>)}</nav>
          <section className="ii-score-grid">{visibleScores.map((score)=><ScoreCard key={score.category} score={score} expanded={!!expanded[score.category]} onToggle={()=>setExpanded((state)=>({...state,[score.category]:!state[score.category]}))}/>)}</section>
        </>}
      </main>
      <aside className="ii-decision-rail">
        {!bundle?<div className="ii-panel"><h3>Decision workspace</h3><p className="ii-muted">Intelligence actions appear after selection.</p></div>:<>
          <section className="ii-panel"><div className="ii-panel-title"><h3>Trade playbook</h3><span>{pct(bundle.playbook.probability)} probability</span></div><dl className="ii-fact-list"><dt>Preferred</dt><dd>{bundle.playbook.preferred_strategy}</dd><dt>Alternative</dt><dd>{bundle.playbook.alternative_strategy}</dd><dt>Entry</dt><dd>{num(bundle.playbook.entry,2)}</dd><dt>Stop</dt><dd>{num(bundle.playbook.stop,2)}</dd><dt>Targets</dt><dd>{bundle.playbook.targets.map((target)=>num(target,2)).join(' / ')||'—'}</dd><dt>Expected hold</dt><dd>{bundle.playbook.expected_hold_days} days</dd><dt>Position size</dt><dd>{num(bundle.playbook.position_size_pct,2)}%</dd></dl>{bundle.playbook.risk_notes?.length>0&&<div className="ii-note-list">{bundle.playbook.risk_notes.map((note)=><p key={note}>{note}</p>)}</div>}</section>
          <section className="ii-panel"><div className="ii-panel-title"><h3>Recommendations</h3><span>{bundle.recommendations.length}</span></div><div className="ii-recommendations">{bundle.recommendations.map((item:any,index:number)=><article key={`${item.title}-${index}`}><span>{item.action}</span><b>{item.title}</b><p>{item.reason}</p><small>Confidence {pct(item.confidence||0)}</small></article>)}</div></section>
          <section className="ii-panel"><div className="ii-panel-title"><h3>Invalidation</h3><span>{bundle.explanation.invalidation_conditions.length}</span></div><ol className="ii-invalidation">{bundle.explanation.invalidation_conditions.map((item)=><li key={item}>{item}</li>)}</ol></section>
          <section className="ii-panel"><div className="ii-panel-title"><h3>Snapshot history</h3><span>{history.length}</span></div><div className="ii-history">{history.slice(0,6).map((item:any,index:number)=><div key={item.snapshot_id||index}><b>{item.snapshot_id||`Version ${index+1}`}</b><span>{item.generated_at||item.snapshot_timestamp||'—'}</span></div>)}</div></section>
          <div className="ii-handoff-actions"><button onClick={()=>navigate('#/trade-builder')}>Open Trade Builder</button><button className="secondary" onClick={()=>navigate('#/opportunity-comparison')}>Compare</button></div>
        </>}
      </aside>
    </div>
  </section>;
}
