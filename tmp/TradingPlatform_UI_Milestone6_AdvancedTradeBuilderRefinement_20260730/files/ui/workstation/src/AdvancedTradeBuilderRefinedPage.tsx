import { useEffect, useMemo, useState } from 'react';
import { opportunityApi, tradeBuilderApi } from './api';
import type { OpportunityRecord, TradePlan } from './types';
import './advanced-trade-builder-refined.css';

const numberValue=(value:unknown,fallback=0)=>Number.isFinite(Number(value))?Number(value):fallback;
const money=(value:unknown)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(numberValue(value));
const score=(opportunity?:OpportunityRecord)=>{
  const payload=opportunity?.source_payload??{};
  for(const value of [payload.ai_score,payload.score,payload.opportunity_score]) if(Number.isFinite(Number(value))) return Number(value);
  return null;
};
const greek=(plan:TradePlan|undefined,key:string)=>numberValue(plan?.net_greeks?.[key]??plan?.net_greeks?.[key.toLowerCase()]);

function PayoffPreview({longStrike,shortStrike,netDebit,direction}:{longStrike:number;shortStrike:number;netDebit:number;direction:string}){
  const low=Math.min(longStrike,shortStrike)-Math.max(5,Math.abs(shortStrike-longStrike));
  const high=Math.max(longStrike,shortStrike)+Math.max(5,Math.abs(shortStrike-longStrike));
  const points=Array.from({length:31},(_,i)=>low+(high-low)*i/30);
  const put=direction.toUpperCase().includes('PUT');
  const values=points.map(price=>{
    const longIntrinsic=put?Math.max(longStrike-price,0):Math.max(price-longStrike,0);
    const shortIntrinsic=put?Math.max(shortStrike-price,0):Math.max(price-shortStrike,0);
    return (longIntrinsic-shortIntrinsic-netDebit)*100;
  });
  const max=Math.max(...values.map(v=>Math.abs(v)),1);
  const path=values.map((v,i)=>`${i===0?'M':'L'} ${(i/(values.length-1))*100} ${50-(v/max)*43}`).join(' ');
  return <div className="tb-payoff"><svg viewBox="0 0 100 100" role="img" aria-label="Estimated expiration payoff"><line x1="0" y1="50" x2="100" y2="50"/><path d={path}/></svg><div><span>{money(low)}</span><b>Expiration payoff</b><span>{money(high)}</span></div></div>;
}

export function AdvancedTradeBuilderRefinedPage(){
  const [opportunities,setOpportunities]=useState<OpportunityRecord[]>([]);
  const [plans,setPlans]=useState<TradePlan[]>([]);
  const [opportunityId,setOpportunityId]=useState('');
  const [selectedPlanId,setSelectedPlanId]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [account,setAccount]=useState('PAPER-PRIMARY');
  const [capital,setCapital]=useState(100000);
  const [riskPct,setRiskPct]=useState(1);
  const [strategy,setStrategy]=useState('BULL_CALL_SPREAD');
  const [expiry,setExpiry]=useState('2026-09-18');
  const [longStrike,setLongStrike]=useState(100);
  const [shortStrike,setShortStrike]=useState(110);
  const [longPrice,setLongPrice]=useState(5);
  const [shortPrice,setShortPrice]=useState(2);
  const [contracts,setContracts]=useState(1);

  const selectedOpportunity=useMemo(()=>opportunities.find(item=>item.opportunity_id===opportunityId),[opportunities,opportunityId]);
  const selectedPlan=useMemo(()=>plans.find(item=>item.trade_plan_id===selectedPlanId)??plans[0],[plans,selectedPlanId]);
  const debit=Math.max(0,(longPrice-shortPrice)*100*contracts);
  const width=Math.abs(shortStrike-longStrike)*100*contracts;
  const maxProfit=Math.max(0,width-debit);
  const riskBudget=capital*riskPct/100;
  const estimatedContracts=Math.max(1,Math.floor(riskBudget/Math.max(debit,1)));
  const rewardRisk=debit>0?maxProfit/debit:null;
  const validationWarnings=[...(debit<=0?['Net debit must be positive.']:[]),...(longStrike===shortStrike?['Long and short strikes must differ.']:[]),...(debit>riskBudget?['Estimated max loss exceeds the configured risk budget.']:[]),...(contracts<1?['At least one contract is required.']:[])];

  const load=async()=>{
    const [oppResponse,planResponse]=await Promise.all([opportunityApi.list(),tradeBuilderApi.list()]);
    const available=oppResponse.data.filter(item=>['UNDER_REVIEW','APPROVED','TRADE_BUILT'].includes(item.workflow_state));
    setOpportunities(available);setPlans(planResponse.data);
    if(!opportunityId&&available[0]) setOpportunityId(available[0].opportunity_id);
    if(!selectedPlanId&&planResponse.data[0]) setSelectedPlanId(planResponse.data[0].trade_plan_id);
  };
  useEffect(()=>{load().catch(error=>setMessage(error instanceof Error?error.message:String(error)))},[]);

  const build=async()=>{
    if(!selectedOpportunity||validationWarnings.length) return;
    setBusy(true);setMessage('');
    try{
      const right=selectedOpportunity.direction.toUpperCase().includes('PUT')?'PUT':'CALL';
      const created=await tradeBuilderApi.build({opportunity_id:selectedOpportunity.opportunity_id,expected_opportunity_version:selectedOpportunity.version,account_id:account,strategy,capital,risk_budget_pct:riskPct,legs:[{side:'BUY',quantity:contracts,option_right:right,strike:longStrike,expiry,limit_price:longPrice},{side:'SELL',quantity:contracts,option_right:right,strike:shortStrike,expiry,limit_price:shortPrice}],notes:'Created in UI Milestone 6 governed trade builder'});
      setMessage('Trade plan created and validated.');setSelectedPlanId(created.data.trade_plan_id);await load();
    }catch(error){setMessage(error instanceof Error?error.message:String(error))}finally{setBusy(false)}
  };
  const transition=async(plan:TradePlan,state:string)=>{
    setBusy(true);setMessage('');
    try{await tradeBuilderApi.transition(plan.trade_plan_id,plan.version,state,`Workstation transition to ${state}`);setMessage(`Trade plan moved to ${state}.`);await load()}catch(error){setMessage(error instanceof Error?error.message:String(error))}finally{setBusy(false)}
  };

  return <section className="tb-page">
    <header className="tb-header"><div><span className="eyebrow">Execution workspace</span><h2>Advanced Trade Builder</h2><p>Translate approved opportunities into versioned, defined-risk paper execution intent.</p></div><div className="tb-governance"><b>Paper governed</b><span>No direct broker submission</span></div></header>
    {message&&<div className="tb-message">{message}</div>}
    <div className="tb-kpis"><div><span>Opportunity</span><b>{selectedOpportunity?.symbol??'—'}</b><small>{selectedOpportunity?.strategy??'Select an opportunity'}</small></div><div><span>AI score</span><b>{score(selectedOpportunity)?.toFixed(1)??'—'}</b><small>{selectedOpportunity?.workflow_state??'—'}</small></div><div><span>Risk budget</span><b>{money(riskBudget)}</b><small>{riskPct.toFixed(2)}% of capital</small></div><div><span>Est. max loss</span><b>{money(debit)}</b><small>{debit<=riskBudget?'Within budget':'Review required'}</small></div><div><span>Reward / risk</span><b>{rewardRisk?.toFixed(2)??'—'}</b><small>{money(maxProfit)} max profit</small></div></div>
    <div className="tb-workspace">
      <aside className="tb-construction">
        <div className="tb-section-title"><div><span>01</span><h3>Construction</h3></div><button onClick={()=>{setContracts(estimatedContracts);setMessage(`Position size set to ${estimatedContracts} contract(s).`)}}>Use risk budget</button></div>
        <label>Canonical opportunity<select value={opportunityId} onChange={event=>setOpportunityId(event.target.value)}><option value="">Select opportunity</option>{opportunities.map(item=><option key={item.opportunity_id} value={item.opportunity_id}>{item.symbol} · {item.direction} · v{item.version}</option>)}</select></label>
        <div className="tb-form-grid"><label>Paper account<input value={account} onChange={event=>setAccount(event.target.value)}/></label><label>Strategy<select value={strategy} onChange={event=>setStrategy(event.target.value)}><option>BULL_CALL_SPREAD</option><option>BEAR_PUT_SPREAD</option><option>LONG_CALL</option><option>LONG_PUT</option></select></label><label>Capital<input type="number" value={capital} onChange={event=>setCapital(numberValue(event.target.value))}/></label><label>Risk budget %<input type="number" step="0.1" value={riskPct} onChange={event=>setRiskPct(numberValue(event.target.value))}/></label><label>Expiration<input type="date" value={expiry} onChange={event=>setExpiry(event.target.value)}/></label><label>Contracts<input type="number" min="1" value={contracts} onChange={event=>setContracts(Math.max(1,numberValue(event.target.value,1)))}/></label></div>
        <div className="tb-leg"><header><b>Long leg</b><span>BUY</span></header><label>Strike<input type="number" value={longStrike} onChange={event=>setLongStrike(numberValue(event.target.value))}/></label><label>Limit price<input type="number" step="0.01" value={longPrice} onChange={event=>setLongPrice(numberValue(event.target.value))}/></label></div>
        <div className="tb-leg"><header><b>Short leg</b><span>SELL</span></header><label>Strike<input type="number" value={shortStrike} onChange={event=>setShortStrike(numberValue(event.target.value))}/></label><label>Limit price<input type="number" step="0.01" value={shortPrice} onChange={event=>setShortPrice(numberValue(event.target.value))}/></label></div>
        <button className="tb-primary" disabled={!selectedOpportunity||busy||validationWarnings.length>0} onClick={build}>{busy?'Working…':'Build governed plan'}</button>
      </aside>
      <main className="tb-analysis">
        <article className="tb-card"><div className="tb-section-title"><div><span>02</span><h3>Payoff & capital impact</h3></div></div><PayoffPreview longStrike={longStrike} shortStrike={shortStrike} netDebit={Math.max(0,longPrice-shortPrice)} direction={selectedOpportunity?.direction??strategy}/><div className="tb-risk-grid"><div><span>Net debit</span><b>{money(debit)}</b></div><div><span>Spread width</span><b>{money(width)}</b></div><div><span>Max profit</span><b>{money(maxProfit)}</b></div><div><span>Breakeven</span><b>{money(selectedOpportunity?.direction.toUpperCase().includes('PUT')?longStrike-(longPrice-shortPrice):longStrike+(longPrice-shortPrice))}</b></div><div><span>Budget usage</span><b>{riskBudget?`${Math.min(999,debit/riskBudget*100).toFixed(1)}%`:'—'}</b></div><div><span>Suggested size</span><b>{estimatedContracts} contract(s)</b></div></div></article>
        <article className="tb-card"><div className="tb-section-title"><div><span>03</span><h3>Validation & governance</h3></div></div>{validationWarnings.length?<ul className="tb-validation bad">{validationWarnings.map(item=><li key={item}>{item}</li>)}</ul>:<div className="tb-validation good"><b>Construction checks passed</b><span>Defined risk, positive debit, and budget constraints are satisfied.</span></div>}<p className="tb-note">Preparing a plan for paper execution creates governed execution intent only. Existing IBKR account binding, confirmation, and routing controls remain authoritative.</p></article>
      </main>
      <aside className="tb-plan-panel">
        <div className="tb-section-title"><div><span>04</span><h3>Plan intelligence</h3></div><span>{plans.length} plans</span></div>
        <select value={selectedPlan?.trade_plan_id??''} onChange={event=>setSelectedPlanId(event.target.value)}><option value="">Select plan</option>{plans.map(plan=><option key={plan.trade_plan_id} value={plan.trade_plan_id}>{plan.symbol} · {plan.strategy} · {plan.state}</option>)}</select>
        {selectedPlan?<><div className="tb-plan-state"><span>{selectedPlan.state}</span><b>v{selectedPlan.version}</b></div><div className="tb-risk-grid compact"><div><span>Max loss</span><b>{money(selectedPlan.max_loss)}</b></div><div><span>Max profit</span><b>{selectedPlan.max_profit===null?'—':money(selectedPlan.max_profit)}</b></div><div><span>R/R</span><b>{selectedPlan.reward_risk_ratio?.toFixed(2)??'—'}</b></div><div><span>Risk amount</span><b>{money(selectedPlan.risk_budget_amount)}</b></div></div><h4>Net Greeks</h4><div className="tb-greeks"><div><span>Δ</span><b>{greek(selectedPlan,'delta').toFixed(3)}</b></div><div><span>Γ</span><b>{greek(selectedPlan,'gamma').toFixed(3)}</b></div><div><span>Θ</span><b>{greek(selectedPlan,'theta').toFixed(3)}</b></div><div><span>V</span><b>{greek(selectedPlan,'vega').toFixed(3)}</b></div></div><h4>Legs</h4><div className="tb-plan-legs">{selectedPlan.legs.map((leg,index)=><div key={index}><b>{leg.side} {leg.quantity}× {leg.option_right}</b><span>{leg.expiry} · {money(leg.strike)} @ {money(leg.limit_price)}</span></div>)}</div><div className="tb-actions">{selectedPlan.state==='VALIDATED'&&<button disabled={busy} onClick={()=>transition(selectedPlan,'APPROVED')}>Approve plan</button>}{selectedPlan.state==='APPROVED'&&<button className="tb-primary" disabled={busy} onClick={()=>transition(selectedPlan,'PAPER_READY')}>Prepare paper intent</button>}</div></>:<div className="empty">No trade plans available.</div>}
      </aside>
    </div>
  </section>;
}
