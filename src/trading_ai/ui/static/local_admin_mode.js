(() => {
  const state={loaded:false,actor:null};
  async function loadSession(){
    if(state.loaded)return state.actor;
    const response=await fetch("/api/v1/session/current",{cache:"no-store",credentials:"same-origin"});
    if(!response.ok)throw new Error(`Unable to load workstation session: HTTP ${response.status}`);
    state.actor=await response.json(); state.loaded=true; applySessionToUi(state.actor); return state.actor;
  }
  function applySessionToUi(actor){
    document.documentElement.dataset.localAdminMode=actor.local_admin_mode?"true":"false";
    let badge=document.querySelector("#localAdminBadge");
    if(!badge){badge=document.createElement("div");badge.id="localAdminBadge";
      badge.setAttribute("role","status");badge.setAttribute("aria-live","polite");
      (document.querySelector("header")||document.querySelector("#app")||document.body).prepend(badge);}
    badge.className=actor.local_admin_mode?"local-admin-badge":"local-admin-badge read-only";
    badge.textContent=actor.local_admin_mode?`LOCAL ADMIN MODE — ${actor.display_name}`:"READ-ONLY WORKSTATION";
    document.querySelectorAll("[data-required-permission]").forEach(el=>{
      const ok=(actor.permissions||[]).includes(el.dataset.requiredPermission);
      el.hidden=!ok; if("disabled" in el)el.disabled=!ok;
    });
  }
  function actorPayload(){
    if(!state.actor||!state.actor.local_admin_mode)
      return {user_id:"read-only-workstation",session_id:"read-only-session",roles:[],permissions:[]};
    return {user_id:state.actor.user_id,session_id:state.actor.session_id,
            roles:state.actor.roles,permissions:state.actor.permissions};
  }
  window.LocalWorkstationAdmin={loadSession,actorPayload,
    hasPermission:p=>Boolean(state.actor&&(state.actor.permissions||[]).includes(p)),
    current:()=>state.actor};
  window.addEventListener("DOMContentLoaded",()=>loadSession().catch(error=>{
    console.error(error);applySessionToUi({local_admin_mode:false,display_name:"Read-Only Workstation",permissions:[]});
  }));
})();
