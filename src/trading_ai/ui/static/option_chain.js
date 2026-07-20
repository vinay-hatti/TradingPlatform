(() => {
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const num = (value,d=2) => value == null ? "—" : Number(value).toFixed(d);
  let snapshot = null;

  const api = async url => {
    const response = await fetch(url,{cache:"no-store"});
    const body = await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(body.detail || JSON.stringify(body));
    return body;
  };

  const ensureNav = () => {
    const nav = document.querySelector(".nav");
    if(!nav || nav.querySelector('[data-view="option-chain"]')) return;
    const button=document.createElement("button");
    button.className="nav-item";
    button.dataset.view="option-chain";
    button.textContent="Option Chain";
    button.onclick=()=>{history.pushState({},"","/?view=option-chain");render()};
    nav.appendChild(button);
  };

  const controls = () => `
    <div class="option-chain-controls">
      <label>Symbol<input id="chainSymbol" value="${esc(snapshot?.symbol || "AAPL")}"></label>
      <label>Expiration<select id="chainExpiration">${(snapshot?.expirations||[]).map(x=>`<option ${x===snapshot.expiration?"selected":""}>${x}</option>`).join("")}</select></label>
      <label>Type<select id="chainType"><option>ALL</option><option>CALL</option><option>PUT</option></select></label>
      <label>Min Volume<input id="chainVolume" type="number" min="0" value="0"></label>
      <label>Min OI<input id="chainOi" type="number" min="0" value="0"></label>
      <label>Max Spread %<input id="chainSpread" type="number" min="0" step=".05" value="1"></label>
      <button id="loadChain">Load Chain</button>
    </div>`;

  const table = () => {
    const calls=new Map(snapshot.contracts.filter(x=>x.option_type==="CALL").map(x=>[x.strike,x]));
    const puts=new Map(snapshot.contracts.filter(x=>x.option_type==="PUT").map(x=>[x.strike,x]));
    const strikes=[...new Set(snapshot.contracts.map(x=>x.strike))].sort((a,b)=>a-b);
    return `<div class="option-chain-table-wrap"><table class="option-chain-table">
      <thead><tr>
        <th>Call Δ</th><th>IV</th><th>Bid</th><th>Ask</th><th>Vol</th><th>OI</th><th>Quality</th><th>Trade</th>
        <th class="strike">Strike</th>
        <th>Trade</th><th>Quality</th><th>OI</th><th>Vol</th><th>Bid</th><th>Ask</th><th>IV</th><th>Put Δ</th>
      </tr></thead><tbody>${strikes.map(strike=>{
        const c=calls.get(strike),p=puts.get(strike);
        const quality=x=>x?`contract-${x.quote_quality.toLowerCase()}`:"";
        return `<tr>
          <td>${c?num(c.delta,3):"—"}</td><td>${c?num(c.implied_volatility*100,1)+"%":"—"}</td><td>${c?num(c.bid):"—"}</td><td>${c?num(c.ask):"—"}</td><td>${c?.volume??"—"}</td><td>${c?.open_interest??"—"}</td><td class="${quality(c)}">${c?.quote_quality??"—"}</td><td>${c?`<button class="chain-action" data-contract="${esc(c.contract_key)}">Select</button>`:""}</td>
          <td class="strike">${num(strike)}</td>
          <td>${p?`<button class="chain-action" data-contract="${esc(p.contract_key)}">Select</button>`:""}</td><td class="${quality(p)}">${p?.quote_quality??"—"}</td><td>${p?.open_interest??"—"}</td><td>${p?.volume??"—"}</td><td>${p?num(p.bid):"—"}</td><td>${p?num(p.ask):"—"}</td><td>${p?num(p.implied_volatility*100,1)+"%":"—"}</td><td>${p?num(p.delta,3):"—"}</td>
        </tr>`}).join("")}</tbody></table></div>`;
  };

  const drawSmile = () => {
    const canvas=document.querySelector("#ivSmile");
    if(!canvas || !snapshot) return;
    const ctx=canvas.getContext("2d"), ratio=devicePixelRatio||1;
    canvas.width=canvas.clientWidth*ratio;canvas.height=230*ratio;ctx.scale(ratio,ratio);
    const w=canvas.clientWidth,h=230,p=30,points=snapshot.volatility_smile;
    const values=points.flatMap(x=>[x.call_iv,x.put_iv]).filter(x=>x!=null);
    if(!values.length)return;
    const minX=Math.min(...points.map(x=>x.strike)),maxX=Math.max(...points.map(x=>x.strike));
    const minY=Math.min(...values),maxY=Math.max(...values);
    const px=x=>p+(x-minX)/(maxX-minX||1)*(w-2*p),py=y=>h-p-(y-minY)/(maxY-minY||1)*(h-2*p);
    ctx.strokeStyle="#64748b";ctx.beginPath();ctx.moveTo(p,p);ctx.lineTo(p,h-p);ctx.lineTo(w-p,h-p);ctx.stroke();
    [["call_iv","#22c55e"],["put_iv","#ef4444"]].forEach(([key,color])=>{
      ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();let started=false;
      points.forEach(pt=>{if(pt[key]==null)return;const x=px(pt.strike),y=py(pt[key]);if(!started){ctx.moveTo(x,y);started=true}else ctx.lineTo(x,y)});
      ctx.stroke();
    });
  };

  const drawLiquidity = () => {
    const canvas=document.querySelector("#liquidityChart");
    if(!canvas||!snapshot)return;
    const ctx=canvas.getContext("2d"),ratio=devicePixelRatio||1;
    canvas.width=canvas.clientWidth*ratio;canvas.height=230*ratio;ctx.scale(ratio,ratio);
    const w=canvas.clientWidth,h=230,p=30,rows=snapshot.liquidity_ladder;
    const max=Math.max(1,...rows.map(x=>x.call_open_interest+x.put_open_interest));
    const bar=(w-2*p)/Math.max(1,rows.length);
    rows.forEach((row,i)=>{
      const total=row.call_open_interest+row.put_open_interest;
      ctx.fillStyle="#3b82f6";
      ctx.fillRect(p+i*bar,h-p-(total/max)*(h-2*p),Math.max(1,bar-1),(total/max)*(h-2*p));
    });
  };

  const render = async () => {
    const content=document.querySelector("#content"),title=document.querySelector("#pageTitle"),notice=document.querySelector("#notice");
    if(!content)return;
    if(title)title.textContent="Institutional Option Chain";
    if(notice)notice.textContent="Stored/delayed option quotes with provider or calculated Greeks. Select a contract to continue into governed paper order entry.";
    content.innerHTML=controls()+`<div id="chainBody"><p>Loading option chain…</p></div>`;
    document.querySelector("#loadChain").onclick=loadFromControls;
    await loadFromControls();
  };

  const loadFromControls = async () => {
    const symbol=document.querySelector("#chainSymbol")?.value.trim().toUpperCase()||"AAPL";
    const expiration=document.querySelector("#chainExpiration")?.value||"";
    const type=document.querySelector("#chainType")?.value||"ALL";
    const volume=document.querySelector("#chainVolume")?.value||0;
    const oi=document.querySelector("#chainOi")?.value||0;
    const spread=document.querySelector("#chainSpread")?.value||1;
    const params=new URLSearchParams({option_type:type,min_volume:volume,min_open_interest:oi,max_spread_pct:spread});
    if(expiration)params.set("expiration",expiration);
    const body=document.querySelector("#chainBody");
    try{
      snapshot=await api(`/api/v1/option-chain/${encodeURIComponent(symbol)}?${params}`);
      document.querySelector("#content").innerHTML=controls()+`
        <div class="option-chain-summary">
          <div class="option-chain-card"><small>Underlying</small><strong>$${num(snapshot.underlying_price)}</strong></div>
          <div class="option-chain-card"><small>Quote Date</small><strong>${snapshot.quote_date}</strong></div>
          <div class="option-chain-card"><small>Expiration</small><strong>${snapshot.expiration}</strong></div>
          <div class="option-chain-card"><small>Put/Call Volume</small><strong>${num(snapshot.put_call_volume_ratio)}</strong></div>
          <div class="option-chain-card"><small>Put/Call OI</small><strong>${num(snapshot.put_call_open_interest_ratio)}</strong></div>
        </div>
        <div class="option-chain-layout">
          ${table()}
          <aside class="option-chain-side">
            <div class="option-chain-chart"><strong>Volatility Smile</strong><canvas id="ivSmile"></canvas><small>Calls green · Puts red</small></div>
            <div class="option-chain-chart"><strong>Open Interest by Strike</strong><canvas id="liquidityChart"></canvas></div>
          </aside>
        </div>`;
      document.querySelector("#loadChain").onclick=loadFromControls;
      document.querySelector("#chainExpiration").onchange=loadFromControls;
      document.querySelectorAll("[data-contract]").forEach(button=>button.onclick=()=>{
        const contract=snapshot.contracts.find(x=>x.contract_key===button.dataset.contract);
        sessionStorage.setItem("selectedOptionContract",JSON.stringify(contract));
        location.href="/?view=paper-commands";
      });
      drawSmile();drawLiquidity();
    }catch(error){body.innerHTML=`<div class="error">${esc(error.message)}</div>`}
  };

  const boot=()=>{
    ensureNav();
    const original=window.renderView;
    if(typeof original==="function"){
      window.renderView=async view=>view==="option-chain"?render():original(view);
    }
    document.addEventListener("click",event=>{
      const item=event.target.closest('[data-view="option-chain"]');
      if(item){event.preventDefault();history.pushState({},"","/?view=option-chain");render()}
    });
    if(new URLSearchParams(location.search).get("view")==="option-chain")render();
  };
  window.addEventListener("DOMContentLoaded",boot);
})();
