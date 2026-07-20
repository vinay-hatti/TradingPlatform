(() => {
  const api=async(url,opt={})=>{
    const r=await fetch(url,{headers:{"Content-Type":"application/json"},cache:"no-store",...opt});
    const b=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(b.detail||JSON.stringify(b));
    return b;
  };
  const n=(v,d=2)=>Number(v||0).toFixed(d);
  function ensureNav(){
    const root=document.querySelector("#nav")||document.querySelector(".nav");
    if(root&&!root.querySelector('[data-view="executive-reporting"]')){
      const b=document.createElement("button");
      b.dataset.view="executive-reporting";
      b.textContent="Executive Dashboard";
      root.appendChild(b);
    }
  }
  async function render(){
    const content=document.querySelector("#content");
    if(document.querySelector("#pageTitle"))document.querySelector("#pageTitle").textContent="Executive Dashboard & Institutional Reporting";
    if(document.querySelector("#notice"))document.querySelector("#notice").textContent="Read-only KPI scorecards, board analytics, institutional summaries, and export-ready compliance evidence.";
    content.innerHTML="<p>Loading executive reporting artifacts…</p>";
    try{
      const [score,board]=await Promise.all([
        api("/api/v1/executive/scorecard"),
        api("/api/v1/executive/board-report")
      ]);
      content.innerHTML=`
      <div class="option-chain-summary">
        <div class="option-chain-card"><small>Net P/L</small><strong>${n(score.total_net_pnl)}</strong></div>
        <div class="option-chain-card"><small>Win Rate</small><strong>${n(score.win_rate*100)}%</strong></div>
        <div class="option-chain-card"><small>Sharpe</small><strong>${n(score.sharpe_ratio)}</strong></div>
        <div class="option-chain-card"><small>Max Drawdown</small><strong>${n(score.max_drawdown*100)}%</strong></div>
        <div class="option-chain-card"><small>Active Incidents</small><strong>${score.active_incidents}</strong></div>
        <div class="option-chain-card"><small>Critical Alerts</small><strong>${score.critical_alerts}</strong></div>
      </div>
      <div class="card"><h2>KPI Scorecard</h2>${kpis(score.kpis)}</div>
      <div class="card"><h2>Board-Level Analytics</h2><p>${board.executive_summary}</p>${sections(board.sections)}</div>
      <div class="card"><h2>Regulatory Export</h2>
        <label>Export Type<select id="execExportType">
          <option>RISK_SUMMARY</option><option>EXECUTION_ACTIVITY</option><option>GOVERNANCE_AUDIT</option><option>ACCESS_REVIEW</option><option>FULL_EVIDENCE_PACKAGE</option>
        </select></label>
        <button id="execExport">Generate Export</button><pre id="execExportResult"></pre>
      </div>
      ${score.warnings.length?`<div class="warning">${score.warnings.join("<br>")}</div>`:""}`;
      document.querySelector("#execExport").onclick=async()=>{
        try{
          const result=await api("/api/v1/executive/regulatory-exports",{method:"POST",body:JSON.stringify({
            export_type:document.querySelector("#execExportType").value,
            start_date:null,end_date:null,include_source_paths:true
          })});
          document.querySelector("#execExportResult").textContent=JSON.stringify(result,null,2);
        }catch(e){document.querySelector("#execExportResult").textContent=e.message}
      };
    }catch(e){content.innerHTML=`<div class="error">${e.message}</div>`}
  }
  const kpis=rows=>`<div style="overflow:auto"><table><thead><tr><th>KPI</th><th>Value</th><th>Unit</th><th>Status</th><th>Source</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.label}</td><td>${n(x.value,4)}</td><td>${x.unit}</td><td>${x.status}</td><td>${x.source}</td></tr>`).join("")}</tbody></table></div>`;
  const sections=rows=>rows.map(x=>`<div class="option-chain-card"><h3>${x.title}</h3><p>${x.summary}</p>${x.highlights.length?`<strong>Highlights</strong><ul>${x.highlights.map(v=>`<li>${v}</li>`).join("")}</ul>`:""}${x.risks.length?`<strong>Risks</strong><ul>${x.risks.map(v=>`<li>${v}</li>`).join("")}</ul>`:""}</div>`).join("");
  window.addEventListener("DOMContentLoaded",()=>{ensureNav();if(new URLSearchParams(location.search).get("view")==="executive-reporting")render()});
  document.addEventListener("click",e=>{if(e.target.closest('[data-view="executive-reporting"]')){history.pushState({},"","/?view=executive-reporting");render()}});
})();
