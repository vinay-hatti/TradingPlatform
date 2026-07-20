(() => {
  const api=async(url,opt={})=>{
    const r=await fetch(url,{headers:{"Content-Type":"application/json"},cache:"no-store",...opt});
    const b=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(b.detail||JSON.stringify(b));
    return b;
  };
  const actor={
    user_id:"security-admin",
    session_id:"security-session",
    roles:["SECURITY_ADMIN"],
    permissions:[
      "security.identity.create",
      "security.role.manage",
      "security.entitlement.request",
      "security.entitlement.approve",
      "security.entitlement.apply",
      "security.session.revoke",
      "security.secret.metadata",
      "security.access_review.create"
    ]
  };
  function ensureNav(){
    const root=document.querySelector("#nav")||document.querySelector(".nav");
    if(root&&!root.querySelector('[data-view="security-compliance-center"]')){
      const b=document.createElement("button");
      b.dataset.view="security-compliance-center";
      b.textContent="Security & Compliance";
      root.appendChild(b);
    }
  }
  async function render(){
    const content=document.querySelector("#content");
    const title=document.querySelector("#pageTitle");
    const notice=document.querySelector("#notice");
    if(title)title.textContent="Security Administration & Compliance Center";
    if(notice)notice.textContent="Identity governance, entitlements, sessions, secret metadata, access reviews, and compliance evidence. Secret values are never displayed.";
    content.innerHTML="<p>Loading security state…</p>";
    try{
      const [identities,roles,sessions,secrets,controls,changes]=await Promise.all([
        api("/api/v1/security/identities"),
        api("/api/v1/security/roles"),
        api("/api/v1/security/sessions"),
        api("/api/v1/security/secrets"),
        api("/api/v1/security/compliance-controls"),
        api("/api/v1/security/entitlement-changes")
      ]);
      content.innerHTML=`
      <div class="option-chain-summary">
        <div class="option-chain-card"><small>Identities</small><strong>${identities.length}</strong></div>
        <div class="option-chain-card"><small>Roles</small><strong>${roles.length}</strong></div>
        <div class="option-chain-card"><small>Active Sessions</small><strong>${sessions.filter(x=>x.status==="ACTIVE").length}</strong></div>
        <div class="option-chain-card"><small>Secret References</small><strong>${secrets.length}</strong></div>
      </div>
      <div class="card"><h2>Create Identity</h2>
        <label>Display Name<input id="secIdentityName"></label>
        <label>Email<input id="secIdentityEmail"></label>
        <label>Type<select id="secIdentityType"><option>HUMAN</option><option>SERVICE</option></select></label>
        <button id="secCreateIdentity">Create Identity</button><pre id="secIdentityResult"></pre>
      </div>
      <div class="card"><h2>Identity Inventory</h2>${tableIdentities(identities)}</div>
      <div class="card"><h2>Roles & Entitlements</h2>${tableRoles(roles)}<h3>Pending Changes</h3>${tableChanges(changes)}</div>
      <div class="card"><h2>Sessions</h2>${tableSessions(sessions)}</div>
      <div class="card"><h2>Secrets Visibility</h2><p>Metadata only. Values are intentionally unavailable.</p>${tableSecrets(secrets)}</div>
      <div class="card"><h2>Compliance Controls</h2>${tableControls(controls)}<button id="secReview">Create Access Review</button><pre id="secReviewResult"></pre></div>`;
      document.querySelector("#secCreateIdentity").onclick=async()=>{
        try{
          const result=await api("/api/v1/security/identities",{method:"POST",body:JSON.stringify({
            display_name:document.querySelector("#secIdentityName").value,
            email:document.querySelector("#secIdentityEmail").value||null,
            identity_type:document.querySelector("#secIdentityType").value,
            roles:[],actor
          })});
          document.querySelector("#secIdentityResult").textContent=JSON.stringify(result,null,2);
        }catch(e){document.querySelector("#secIdentityResult").textContent=e.message}
      };
      document.querySelector("#secReview").onclick=async()=>{
        try{
          const result=await api("/api/v1/security/access-reviews",{method:"POST",body:JSON.stringify(actor)});
          document.querySelector("#secReviewResult").textContent=JSON.stringify(result,null,2);
        }catch(e){document.querySelector("#secReviewResult").textContent=e.message}
      };
    }catch(e){content.innerHTML=`<div class="error">${e.message}</div>`}
  }
  const tableIdentities=rows=>rows.length?`<div style="overflow:auto"><table><thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Roles</th><th>Last Review</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.display_name}<br><small>${x.identity_id}</small></td><td>${x.identity_type}</td><td>${x.status}</td><td>${x.roles.join(", ")||"—"}</td><td>${x.last_reviewed_at||"Never"}</td></tr>`).join("")}</tbody></table></div>`:"<p>No identities.</p>";
  const tableRoles=rows=>rows.length?`<div style="overflow:auto"><table><thead><tr><th>Role</th><th>Privileged</th><th>Permissions</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.display_name}<br><small>${x.role_id}</small></td><td>${x.privileged?"Yes":"No"}</td><td>${x.permissions.join(", ")||"—"}</td></tr>`).join("")}</tbody></table></div>`:"<p>No roles.</p>";
  const tableChanges=rows=>rows.length?`<div style="overflow:auto"><table><thead><tr><th>ID</th><th>Identity</th><th>Add</th><th>Remove</th><th>Status</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.change_id}</td><td>${x.identity_id}</td><td>${x.add_roles.join(", ")}</td><td>${x.remove_roles.join(", ")}</td><td>${x.status}</td></tr>`).join("")}</tbody></table></div>`:"<p>No entitlement changes.</p>";
  const tableSessions=rows=>rows.length?`<div style="overflow:auto"><table><thead><tr><th>Session</th><th>Identity</th><th>Status</th><th>Client</th><th>IP</th><th>Expires</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.session_id}</td><td>${x.identity_id}</td><td>${x.status}</td><td>${x.client_label}</td><td>${x.ip_masked}</td><td>${x.expires_at}</td></tr>`).join("")}</tbody></table></div>`:"<p>No sessions.</p>";
  const tableSecrets=rows=>rows.length?`<div style="overflow:auto"><table><thead><tr><th>Name</th><th>Provider</th><th>Environment</th><th>Reference</th><th>Rotation</th><th>Value</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.display_name}</td><td>${x.provider}</td><td>${x.environment}</td><td>${x.reference}</td><td>${x.rotation_status}</td><td>Hidden</td></tr>`).join("")}</tbody></table></div>`:"<p>No secret metadata.</p>";
  const tableControls=rows=>`<div style="overflow:auto"><table><thead><tr><th>Control</th><th>Title</th><th>Status</th><th>Evidence</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.control_id}</td><td>${x.title}</td><td>${x.status}</td><td>${x.evidence.join("; ")}</td></tr>`).join("")}</tbody></table></div>`;
  window.addEventListener("DOMContentLoaded",()=>{ensureNav();if(new URLSearchParams(location.search).get("view")==="security-compliance-center")render()});
  document.addEventListener("click",e=>{if(e.target.closest('[data-view="security-compliance-center"]')){history.pushState({},"","/?view=security-compliance-center");render()}});
})();
