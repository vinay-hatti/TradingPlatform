(() => {
  const nav=document.querySelector("#nav");
  if(nav && !nav.querySelector('[data-view="professional-orders"]')){
    const b=document.createElement("button");b.dataset.view="professional-orders";b.textContent="Strategy Order Entry";nav.appendChild(b);
    b.onclick=()=>{history.pushState({},"","/?view=professional-orders");render()};
  }
  const actor=(approver=false)=>({
    user_id:approver?"risk-approver":"local-operator",
    session_id:approver?"risk-session":"local-session",
    roles:approver?["RISK_APPROVER"]:["TRADER"],
    permissions:approver?["paper_orders.approve"]:["paper_orders.submit"]
  });
  const req=async(url,opt={})=>{const r=await fetch(url,{headers:{"Content-Type":"application/json"},...opt});const p=await r.json().catch(()=>({}));if(!r.ok)throw new Error(p.detail||JSON.stringify(p));return p};
  const uid=()=>`${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  async function render(){
    document.querySelector("#pageTitle").textContent="Professional Strategy Order Entry";
    document.querySelector("#notice").textContent="Preview, size, approve, and submit multi-leg PAPER strategies. Live trading remains disabled.";
    document.querySelector("#content").innerHTML=`
      <div class="card"><h2>Strategy Builder</h2>
      <p>Paste legs from Option Chain selections or enter JSON below.</p>
      <textarea id="strategyLegs" rows="10" style="width:100%">[{"leg_id":"leg-1","symbol":"AAPL","option_expiry":"2026-08-21","option_strike":200,"option_type":"CALL","side":"BUY","ratio":1,"bid":6,"ask":6.4,"delta":0.52,"gamma":0.03,"theta":-0.12,"vega":0.18}]</textarea>
      <div class="form-grid">
      <label>Strategy Name<input id="strategyName" value="Custom Strategy"></label>
      <label>Contracts<input id="contracts" type="number" value="1"></label>
      <label>Underlying Price<input id="underlying" type="number" value="200"></label>
      <label>Account Equity<input id="equity" type="number" value="100000"></label>
      <label>Max Risk %<input id="riskPct" type="number" step=".01" value=".02"></label>
      <label>Net Limit Price<input id="netPrice" type="number" step=".01" value="6.4"></label></div>
      <label>Reason<input id="reason" value="Governed paper strategy evaluation"></label>
      <button id="preview">Preview</button><button id="create">Create Approval Ticket</button>
      <pre id="result"></pre></div><div class="card"><h2>Approval Queue</h2><div id="queue">Loading…</div></div>`;
    document.querySelector("#preview").onclick=()=>submit(false);
    document.querySelector("#create").onclick=()=>submit(true);
    await queue();
  }
  const payload=()=>({
    environment:"PAPER",account_id:"paper-account",strategy_name:document.querySelector("#strategyName").value,
    order_type:"LIMIT",time_in_force:"DAY",contracts:Number(document.querySelector("#contracts").value),
    net_limit_price:Number(document.querySelector("#netPrice").value),underlying_price:Number(document.querySelector("#underlying").value),
    account_equity:Number(document.querySelector("#equity").value),max_risk_pct:Number(document.querySelector("#riskPct").value),
    commission_per_contract:.65,reason:document.querySelector("#reason").value,
    legs:JSON.parse(document.querySelector("#strategyLegs").value),actor:actor(false)
  });
  async function submit(create){
    try{const p=await req(`/api/v1/professional-orders/${create?"tickets":"preview"}`,{method:"POST",body:JSON.stringify(payload())});document.querySelector("#result").textContent=JSON.stringify(p,null,2);await queue()}catch(e){document.querySelector("#result").textContent=e.message}
  }
  async function queue(){
    const tickets=await req("/api/v1/professional-orders/tickets");
    document.querySelector("#queue").innerHTML=tickets.length?tickets.map(t=>`<div class="card"><strong>${t.request.strategy_name}</strong> — ${t.status}<br>
      Risk: ${t.preview.maximum_loss??"unbounded"} | Margin: ${t.preview.estimated_margin} | Recommended: ${t.preview.contracts_recommended}
      ${t.status==="PENDING_APPROVAL"?`<button data-approve="${t.ticket_id}">Approve</button>`:""}
      ${t.status==="APPROVED"?`<button data-submit="${t.ticket_id}">Submit Paper Legs</button>`:""}</div>`).join(""):"No tickets.";
    document.querySelectorAll("[data-approve]").forEach(b=>b.onclick=async()=>{await req(`/api/v1/professional-orders/tickets/${b.dataset.approve}/approval`,{method:"POST",body:JSON.stringify({decision:"APPROVE",reason:"Risk review completed",confirmation_token:`CONFIRM-PAPER-${uid()}`,actor:actor(true)})});await queue()});
    document.querySelectorAll("[data-submit]").forEach(b=>b.onclick=async()=>{await req(`/api/v1/professional-orders/tickets/${b.dataset.submit}/submit`,{method:"POST",body:JSON.stringify({confirmation_token:`CONFIRM-PAPER-${uid()}`,idempotency_key:`strategy-${uid()}`,actor:actor(false)})});await queue()});
  }
  document.addEventListener("click",e=>{if(e.target.closest('[data-view="professional-orders"]'))render()});
  if(new URLSearchParams(location.search).get("view")==="professional-orders")window.addEventListener("DOMContentLoaded",render);
})();
