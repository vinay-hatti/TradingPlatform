(() => {
  const api=async(url,opt={})=>{const r=await fetch(url,{headers:{"Content-Type":"application/json"},cache:"no-store",...opt});const b=await r.json().catch(()=>({}));if(!r.ok)throw new Error(b.detail||JSON.stringify(b));return b};
  const actor={user_id:"strategy-admin",session_id:"strategy-session",roles:["STRATEGY_ADMIN"],permissions:["strategy.shadow.deploy","strategy.experiment.create","strategy.promote"]};
  function ensureNav(){const root=document.querySelector("#nav")||document.querySelector(".nav");if(root&&!root.querySelector('[data-view="strategy-studio"]')){const b=document.createElement("button");b.dataset.view="strategy-studio";b.textContent="Strategy Studio";root.appendChild(b)}}
  async function render(){
    const content=document.querySelector("#content");if(document.querySelector("#pageTitle"))document.querySelector("#pageTitle").textContent="Strategy Studio";
    if(document.querySelector("#notice"))document.querySelector("#notice").textContent="Versioned strategy editing with shadow-only deployment, governed experiments, and controlled promotion.";
    content.innerHTML=`<div class="card"><h2>Create Version</h2>
      <label>Strategy ID<input id="ssId" value="options_momentum"></label>
      <label>Display Name<input id="ssName" value="Options Momentum"></label>
      <label>Description<input id="ssDesc" value="Governed parameter revision"></label>
      <label>Parameters JSON<textarea id="ssParams" rows="10">[{"name":"rsi_period","value":14,"value_type":"int","minimum":2,"maximum":100,"description":"RSI lookback"},{"name":"min_confidence","value":0.65,"value_type":"float","minimum":0,"maximum":1,"description":"Minimum score"}]</textarea></label>
      <button id="ssCreate">Create Immutable Version</button><pre id="ssResult"></pre></div>
      <div class="card"><h2>Versions</h2><div id="ssVersions">Loading…</div></div>
      <div class="card"><h2>Experiments</h2><div id="ssExperiments">Loading…</div></div>`;
    document.querySelector("#ssCreate").onclick=async()=>{
      try{
        const body={strategy_id:document.querySelector("#ssId").value,display_name:document.querySelector("#ssName").value,description:document.querySelector("#ssDesc").value,parameters:JSON.parse(document.querySelector("#ssParams").value),tags:["studio"],actor};
        const result=await api("/api/v1/strategy-studio/versions",{method:"POST",body:JSON.stringify(body)});
        document.querySelector("#ssResult").textContent=JSON.stringify(result,null,2);await refresh();
      }catch(e){document.querySelector("#ssResult").textContent=e.message}
    };
    await refresh();
  }
  async function refresh(){
    const [versions,experiments]=await Promise.all([api("/api/v1/strategy-studio/versions"),api("/api/v1/strategy-studio/experiments")]);
    document.querySelector("#ssVersions").innerHTML=versions.length?versions.map(v=>`<div class="option-chain-card"><strong>${v.display_name}</strong> v${v.version_number} — ${v.status}<br><small>${v.version_id}<br>${v.checksum}</small></div>`).join(""):"No versions.";
    document.querySelector("#ssExperiments").innerHTML=experiments.length?experiments.map(e=>`<div class="option-chain-card"><strong>${e.experiment_name}</strong> — ${e.status}<br>${e.metric} · minimum observations ${e.minimum_observations}</div>`).join(""):"No experiments.";
  }
  window.addEventListener("DOMContentLoaded",()=>{ensureNav();if(new URLSearchParams(location.search).get("view")==="strategy-studio")render()});
  document.addEventListener("click",e=>{if(e.target.closest('[data-view="strategy-studio"]')){history.pushState({},"","/?view=strategy-studio");render()}});
})();
