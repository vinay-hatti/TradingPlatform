(() => {
  const api=async(url,opt={})=>{const r=await fetch(url,{headers:{"Content-Type":"application/json"},cache:"no-store",...opt});const b=await r.json().catch(()=>({}));if(!r.ok)throw new Error(b.detail||JSON.stringify(b));return b};
  const n=(v,d=2)=>Number(v||0).toFixed(d);
  function nav(){
    const root=document.querySelector("#nav")||document.querySelector(".nav");
    if(root&&!root.querySelector('[data-view="interactive-portfolio"]')){
      const b=document.createElement("button");b.dataset.view="interactive-portfolio";b.textContent="Portfolio Manager";root.appendChild(b);
    }
  }
  async function render(){
    const title=document.querySelector("#pageTitle"),notice=document.querySelector("#notice"),content=document.querySelector("#content");
    if(!content)return;
    if(title)title.textContent="Interactive Portfolio Management";
    if(notice)notice.textContent="Analytics are read-only. Rebalancing creates a governed proposal for Phase 3 review and approval.";
    content.innerHTML="<p>Loading portfolio…</p>";
    try{
      const [s,m]=await Promise.all([api("/api/v1/interactive-portfolio/summary"),api("/api/v1/interactive-portfolio/exposure-matrix")]);
      content.innerHTML=`
      <div class="option-chain-summary">
        <div class="option-chain-card"><small>Market Value</small><strong>$${n(s.total_market_value)}</strong></div>
        <div class="option-chain-card"><small>Unrealized P/L</small><strong>$${n(s.total_unrealized_pnl)}</strong></div>
        <div class="option-chain-card"><small>Net Delta</small><strong>${n(s.net_delta)}</strong></div>
        <div class="option-chain-card"><small>Net Vega</small><strong>${n(s.net_vega)}</strong></div>
      </div>
      <div class="card"><h2>Positions</h2><div style="overflow:auto"><table><thead><tr><th>Symbol</th><th>Contract</th><th>Qty</th><th>Mark</th><th>Value</th><th>P/L</th><th>Δ</th><th>Γ</th><th>Θ</th><th>Vega</th></tr></thead><tbody>
      ${s.positions.map(p=>`<tr><td>${p.symbol}</td><td>${p.option_expiry||"Equity"} ${p.option_strike||""} ${p.option_type||""}</td><td>${p.quantity}</td><td>${n(p.mark_price)}</td><td>${n(p.market_value)}</td><td>${n(p.unrealized_pnl)}</td><td>${n(p.delta,3)}</td><td>${n(p.gamma,3)}</td><td>${n(p.theta,3)}</td><td>${n(p.vega,3)}</td></tr>`).join("")}
      </tbody></table></div></div>
      <div class="card"><h2>Exposure Heatmap</h2><div id="heatmap" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px">
      ${m.map(x=>`<div class="option-chain-card" style="opacity:${Math.min(1,.3+Math.abs(x.delta)/Math.max(1,...m.map(y=>Math.abs(y.delta))))}"><strong>${x.symbol}</strong><br><small>${x.expiration}</small><br>Δ ${n(x.delta)} · Vega ${n(x.vega)}<br>P/L $${n(x.unrealized_pnl)}</div>`).join("")}</div></div>
      <div class="card"><h2>Scenario Analysis</h2><button id="runScenarios">Run Standard Grid</button><div id="scenarioResult"></div></div>
      <div class="card"><h2>Governed Rebalancing</h2><label>Maximum absolute delta <input id="maxDelta" type="number" value="100"></label><button id="proposeRebalance">Create Proposal</button><pre id="rebalanceResult"></pre></div>`;
      document.querySelector("#runScenarios").onclick=async()=>{
        const rows=await api("/api/v1/interactive-portfolio/scenarios",{method:"POST",body:JSON.stringify({account_id:"paper-account",underlying_shocks_pct:[-.1,-.05,0,.05,.1],volatility_shocks_points:[-.05,0,.05],days_forward:[0,1,5]})});
        const worst=[...rows].sort((a,b)=>a.estimated_pnl-b.estimated_pnl)[0],best=[...rows].sort((a,b)=>b.estimated_pnl-a.estimated_pnl)[0];
        document.querySelector("#scenarioResult").innerHTML=`<p>Worst: $${n(worst.estimated_pnl)} at ${(worst.underlying_shock_pct*100).toFixed(0)}% / vol ${(worst.volatility_shock_points*100).toFixed(0)} pts / ${worst.days_forward}d</p><p>Best: $${n(best.estimated_pnl)}</p>`;
      };
      document.querySelector("#proposeRebalance").onclick=async()=>{
        const max=Number(document.querySelector("#maxDelta").value);
        const p=await api(`/api/v1/interactive-portfolio/rebalance-proposal?account_id=paper-account`,{method:"POST",body:JSON.stringify({max_abs_delta:max,max_abs_vega:1000,max_symbol_exposure_pct:.3,account_equity:100000})});
        document.querySelector("#rebalanceResult").textContent=JSON.stringify(p,null,2);
        sessionStorage.setItem("portfolioRebalanceProposal",JSON.stringify(p.phase3_handoff));
      };
    }catch(e){content.innerHTML=`<div class="error">${e.message}</div>`}
  }
  window.addEventListener("DOMContentLoaded",()=>{nav();if(new URLSearchParams(location.search).get("view")==="interactive-portfolio")render()});
  document.addEventListener("click",e=>{if(e.target.closest('[data-view="interactive-portfolio"]')){history.pushState({},"","/?view=interactive-portfolio");render()}});
})();
