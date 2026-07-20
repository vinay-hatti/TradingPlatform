(() => {
  const api=async(url,opt={})=>{const r=await fetch(url,{headers:{"Content-Type":"application/json"},cache:"no-store",...opt});const b=await r.json().catch(()=>({}));if(!r.ok)throw new Error(b.detail||JSON.stringify(b));return b};
  const n=(v,d=2)=>Number(v||0).toFixed(d);
  const scanner=rows=>rows.length?`<div style="overflow:auto"><table><thead><tr><th>Symbol</th><th>Date</th><th>Signal</th><th>Confidence</th><th>Call</th><th>Put</th><th>Regime</th><th>RSI</th><th>ATR</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.symbol}</td><td>${x.as_of||"—"}</td><td>${x.signal}</td><td>${n(x.confidence)}</td><td>${n(x.call_score)}</td><td>${n(x.put_score)}</td><td>${x.market_regime}</td><td>${n(x.rsi14)}</td><td>${n(x.atr14)}</td></tr>`).join("")}</tbody></table></div>`:"<p>No matching scanner artifacts.</p>";
  const importance=rows=>rows.length?rows.slice(0,20).map(x=>`<div style="display:grid;grid-template-columns:180px 1fr 70px;gap:8px;align-items:center"><span>${x.rank}. ${x.feature}</span><div style="height:10px;background:rgba(100,116,139,.25)"><div style="height:10px;width:${Math.min(100,x.importance*100)}%;background:var(--accent,#3b82f6)"></div></div><span>${n(x.importance,3)}</span></div>`).join(""):"<p>No importance artifacts.</p>";
  const walk=rows=>rows.length?`<div style="overflow:auto"><table><thead><tr><th>Run</th><th>Symbol</th><th>Test End</th><th>P/L</th><th>Win Rate</th><th>Sharpe</th><th>Drawdown</th><th>Trades</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.run_id}</td><td>${x.symbol||"ALL"}</td><td>${x.test_end||"—"}</td><td>${n(x.net_pnl)}</td><td>${n(x.win_rate)}</td><td>${n(x.sharpe_ratio)}</td><td>${n(x.max_drawdown)}</td><td>${x.trades}</td></tr>`).join("")}</tbody></table></div>`:"<p>No walk-forward artifacts.</p>";
  function ensureNav(){
    const root=document.querySelector("#nav")||document.querySelector(".nav");
    if(root&&!root.querySelector('[data-view="research-workbench"]')){
      const b=document.createElement("button");b.dataset.view="research-workbench";b.textContent="Research Workbench";root.appendChild(b);
    }
  }
  async function render(){
    const title=document.querySelector("#pageTitle"),notice=document.querySelector("#notice"),content=document.querySelector("#content");
    if(title)title.textContent="Research Workbench";
    if(notice)notice.textContent="Read-only exploration of scanner, signals, feature importance, walk-forward results, and deterministic replay.";
    content.innerHTML="<p>Loading research artifacts…</p>";
    try{
      const s=await api("/api/v1/research-workbench/snapshot");
      content.innerHTML=`
      <div class="card"><h2>Interactive Scanner</h2>
        <div class="form-grid"><label>Symbols<input id="rwSymbols" placeholder="AAPL,MSFT"></label><label>Signal<select id="rwSignal"><option>ALL</option><option>CALL</option><option>PUT</option></select></label><label>Minimum score<input id="rwScore" type="number" value="0"></label></div>
        <button id="rwScan">Run Filter</button><div id="rwScanner">${scanner(s.scanner_results)}</div>
      </div>
      <div class="card"><h2>Feature Importance</h2><div>${importance(s.feature_importance)}</div></div>
      <div class="card"><h2>Walk-Forward Explorer</h2><div>${walk(s.walk_forward_runs)}</div></div>
      <div class="card"><h2>Trade Replay</h2>
        <div class="form-grid"><label>Symbol<input id="rwReplaySymbol" value="AAPL"></label><label>Start<input id="rwReplayStart" type="date"></label><label>End<input id="rwReplayEnd" type="date"></label></div>
        <button id="rwReplay">Load Replay</button><div id="rwReplayResult"></div>
      </div>
      ${s.data_warnings.length?`<div class="warning">${s.data_warnings.join("<br>")}</div>`:""}`;
      document.querySelector("#rwScan").onclick=async()=>{
        const symbols=document.querySelector("#rwSymbols").value.split(",").map(x=>x.trim()).filter(Boolean);
        const rows=await api("/api/v1/research-workbench/scanner",{method:"POST",body:JSON.stringify({symbols,signal:document.querySelector("#rwSignal").value,min_score:Number(document.querySelector("#rwScore").value),max_results:100})});
        document.querySelector("#rwScanner").innerHTML=scanner(rows);
      };
      document.querySelector("#rwReplay").onclick=async()=>{
        const start=document.querySelector("#rwReplayStart").value,end=document.querySelector("#rwReplayEnd").value;
        if(!start||!end){document.querySelector("#rwReplayResult").textContent="Select start and end dates.";return}
        const rows=await api("/api/v1/research-workbench/replay",{method:"POST",body:JSON.stringify({symbol:document.querySelector("#rwReplaySymbol").value,start,end,speed:"STEP"})});
        let index=0;
        document.querySelector("#rwReplayResult").innerHTML=`<button id="rwPrev">Previous</button><button id="rwNext">Next</button><pre id="rwFrame"></pre>`;
        const show=()=>document.querySelector("#rwFrame").textContent=rows.length?JSON.stringify(rows[index],null,2):"No replay data found.";
        document.querySelector("#rwPrev").onclick=()=>{index=Math.max(0,index-1);show()};
        document.querySelector("#rwNext").onclick=()=>{index=Math.min(rows.length-1,index+1);show()};
        show();
      };
    }catch(e){content.innerHTML=`<div class="error">${e.message}</div>`}
  }
  window.addEventListener("DOMContentLoaded",()=>{ensureNav();if(new URLSearchParams(location.search).get("view")==="research-workbench")render()});
  document.addEventListener("click",e=>{if(e.target.closest('[data-view="research-workbench"]')){history.pushState({},"","/?view=research-workbench");render()}});
})();
