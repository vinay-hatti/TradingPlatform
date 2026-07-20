(() => {
  const API = "/api/v1/workspaces";
  const owner = "local-operator";
  let workspaces = [];
  let current = null;
  let dragPanel = null;

  const request = async (url, options={}) => {
    const response = await fetch(url, {
      cache:"no-store",
      headers:{"Content-Type":"application/json"},
      ...options
    });
    const body = response.status === 204 ? null : await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(body.detail || JSON.stringify(body));
    return body;
  };

  const emitNavigate = view => {
    const nav = document.querySelector(`[data-view="${view}"]`);
    if (nav) nav.click();
    else location.href = `/?view=${encodeURIComponent(view)}`;
  };

  const ensureShell = () => {
    if (document.querySelector("#workspaceButton")) return;
    const actions = document.querySelector(".actions") || document.querySelector("header");
    if (!actions) return;

    const workspaceButton = document.createElement("button");
    workspaceButton.id = "workspaceButton";
    workspaceButton.textContent = "Workspace";
    actions.appendChild(workspaceButton);

    const commandButton = document.createElement("button");
    commandButton.id = "commandButton";
    commandButton.textContent = "⌘K";
    commandButton.title = "Command Palette";
    actions.appendChild(commandButton);

    const noteButton = document.createElement("button");
    noteButton.id = "notificationButton";
    noteButton.innerHTML = `Notifications <span id="notificationBadge" class="notification-badge">0</span>`;
    actions.appendChild(noteButton);

    document.body.insertAdjacentHTML("beforeend", `
      <div id="commandPalette" class="command-palette">
        <div class="command-dialog">
          <input id="commandSearch" class="command-search" placeholder="Type a command…">
          <div id="commandList" class="command-list"></div>
        </div>
      </div>
      <div id="notificationDrawer" class="notification-drawer">
        <div class="notification-dialog">
          <div style="display:flex;justify-content:space-between;padding:14px">
            <strong>Notification Center</strong><button id="closeNotifications">Close</button>
          </div>
          <div id="notificationList" class="notification-list"></div>
        </div>
      </div>`);
  };

  const load = async () => {
    workspaces = await request(`${API}?owner=${encodeURIComponent(owner)}`);
    if (!workspaces.length) {
      current = await request(API, {
        method:"POST",
        body:JSON.stringify({name:"Default Trading Workspace",owner,template:"trading"})
      });
      workspaces=[current];
    } else {
      current = workspaces[0];
    }
    await refreshNotifications();
  };

  const save = async () => {
    if (!current) return;
    const panels = [...document.querySelectorAll(".workspace-panel")].map((element,index)=>({
      panel_id:element.dataset.panelId,
      title:element.dataset.title,
      view:element.dataset.view,
      zone:element.closest(".workspace-zone").dataset.zone,
      order:index,
      size:element.dataset.size || "medium",
      visible:true,
      collapsed:element.classList.contains("collapsed"),
      width:Math.round(element.getBoundingClientRect().width),
      height:Math.round(element.getBoundingClientRect().height),
      metadata:{}
    }));
    current = await request(`${API}/${current.workspace_id}`, {
      method:"PUT",
      body:JSON.stringify({
        panels,
        theme:document.documentElement.dataset.theme || "dark",
        active_view:new URLSearchParams(location.search).get("view") || "dashboard",
        expected_version:current.version
      })
    });
    toast("Workspace saved");
  };

  const panelMarkup = panel => `
    <article class="workspace-panel ${panel.collapsed?"collapsed":""}" draggable="true"
      data-panel-id="${panel.panel_id}" data-title="${panel.title}" data-view="${panel.view}"
      data-size="${panel.size}" style="${panel.width?`width:${panel.width}px;`:""}${panel.height?`height:${panel.height}px;`:""}">
      <div class="workspace-panel-header">
        <strong>${panel.title}</strong>
        <div class="workspace-panel-actions">
          <button data-action="open">Open</button>
          <button data-action="collapse">${panel.collapsed?"+":"−"}</button>
        </div>
      </div>
      <div class="workspace-panel-body">
        <p>Docked view: <strong>${panel.view}</strong></p>
        <p>This workspace container preserves panel placement and sizing. The existing workstation page opens through the governed navigation layer.</p>
      </div>
    </article>`;

  const renderWorkspace = () => {
    const title = document.querySelector("#pageTitle");
    const content = document.querySelector("#content");
    const notice = document.querySelector("#notice");
    if (!content) return;
    if (title) title.textContent = "Interactive Workspace";
    if (notice) notice.textContent = "Drag panels between zones, resize them, save layouts, or use ⌘K for commands.";
    content.innerHTML = `
      <div class="workspace-toolbar">
        <select id="workspaceSelect">${workspaces.map(w=>`<option value="${w.workspace_id}" ${w.workspace_id===current.workspace_id?"selected":""}>${w.name}</option>`).join("")}</select>
        <button id="saveWorkspace">Save Layout</button>
        <button id="newTradingWorkspace">New Trading</button>
        <button id="newResearchWorkspace">New Research</button>
        <button id="newOperationsWorkspace">New Operations</button>
      </div>
      <section class="workspace-grid">
        ${["left","center","right","bottom"].map(zone=>`
          <div class="workspace-zone" data-zone="${zone}">
            ${current.panels.filter(p=>p.zone===zone && p.visible).sort((a,b)=>a.order-b.order).map(panelMarkup).join("")}
          </div>`).join("")}
      </section>`;
    bindWorkspace();
  };

  const bindWorkspace = () => {
    document.querySelector("#saveWorkspace").onclick = save;
    document.querySelector("#workspaceSelect").onchange = event => {
      current = workspaces.find(w=>w.workspace_id===event.target.value);
      renderWorkspace();
    };
    [["newTradingWorkspace","trading"],["newResearchWorkspace","research"],["newOperationsWorkspace","operations"]].forEach(([id,template])=>{
      document.querySelector(`#${id}`).onclick = async () => {
        const name = prompt("Workspace name:");
        if (!name) return;
        current = await request(API,{method:"POST",body:JSON.stringify({name,owner,template})});
        workspaces.unshift(current);
        renderWorkspace();
      };
    });
    document.querySelectorAll(".workspace-panel").forEach(panel=>{
      panel.ondragstart=()=>{dragPanel=panel;panel.classList.add("dragging")};
      panel.ondragend=()=>panel.classList.remove("dragging");
      panel.querySelector('[data-action="open"]').onclick=()=>emitNavigate(panel.dataset.view);
      panel.querySelector('[data-action="collapse"]').onclick=()=>{
        panel.classList.toggle("collapsed");
      };
    });
    document.querySelectorAll(".workspace-zone").forEach(zone=>{
      zone.ondragover=e=>e.preventDefault();
      zone.ondrop=e=>{e.preventDefault();if(dragPanel)zone.appendChild(dragPanel)};
    });
  };

  const openWorkspace = () => {
    history.pushState({}, "", "/?view=workspace");
    renderWorkspace();
  };

  const openCommands = async () => {
    const palette=document.querySelector("#commandPalette");
    palette.classList.add("open");
    const commands=await request(`${API}/commands`);
    const search=document.querySelector("#commandSearch");
    const list=document.querySelector("#commandList");
    const render=()=>{
      const q=search.value.toLowerCase();
      list.innerHTML=commands.filter(c=>(c.title+" "+c.description+" "+c.category).toLowerCase().includes(q)).map(c=>`
        <div class="command-item" data-id="${c.command_id}">
          <div><strong>${c.title}</strong><div><small>${c.description}</small></div></div>
          <span>${c.shortcut||c.category}</span>
        </div>`).join("");
      list.querySelectorAll(".command-item").forEach(item=>item.onclick=()=>{
        const command=commands.find(c=>c.command_id===item.dataset.id);
        palette.classList.remove("open");
        if(command.action==="navigate")emitNavigate(command.target_view);
        if(command.action==="save-workspace")save();
        if(command.action==="toggle-theme")document.querySelector("#theme")?.click();
        if(command.action==="reset-workspace")renderWorkspace();
      });
    };
    search.value="";render();search.oninput=render;search.focus();
  };

  const refreshNotifications = async () => {
    const notes=await request(`${API}/notifications`);
    const unread=notes.filter(n=>!n.acknowledged).length;
    const badge=document.querySelector("#notificationBadge");
    if(badge)badge.textContent=unread;
    const list=document.querySelector("#notificationList");
    if(list)list.innerHTML=notes.length?notes.map(n=>`
      <div class="notification-item">
        <div><strong>${n.severity}: ${n.title}</strong><p>${n.message}</p><small>${n.created_at}</small></div>
        ${n.acknowledged?"<span>Acknowledged</span>":`<button data-note="${n.notification_id}">Acknowledge</button>`}
      </div>`).join(""):"<p>No notifications.</p>";
    list?.querySelectorAll("[data-note]").forEach(button=>button.onclick=async()=>{
      await request(`${API}/notifications/${button.dataset.note}/acknowledge`,{method:"POST",body:"{}"});
      await refreshNotifications();
    });
  };

  const toast = message => {
    const node=document.createElement("div");
    node.textContent=message;
    Object.assign(node.style,{position:"fixed",right:"20px",bottom:"20px",padding:"10px 14px",background:"#166534",color:"white",borderRadius:"8px",zIndex:10000});
    document.body.appendChild(node);setTimeout(()=>node.remove(),1800);
  };

  const boot = async () => {
    ensureShell();
    await load();
    document.querySelector("#workspaceButton").onclick=openWorkspace;
    document.querySelector("#commandButton").onclick=openCommands;
    document.querySelector("#notificationButton").onclick=async()=>{
      document.querySelector("#notificationDrawer").classList.add("open");
      await refreshNotifications();
    };
    document.querySelector("#closeNotifications").onclick=()=>document.querySelector("#notificationDrawer").classList.remove("open");
    document.querySelector("#commandPalette").onclick=e=>{if(e.target.id==="commandPalette")e.currentTarget.classList.remove("open")};
    document.addEventListener("keydown",e=>{
      if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();openCommands()}
      if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="s"&&new URLSearchParams(location.search).get("view")==="workspace"){e.preventDefault();save()}
      if(e.key==="Escape"){document.querySelector("#commandPalette")?.classList.remove("open");document.querySelector("#notificationDrawer")?.classList.remove("open")}
    });
    if(new URLSearchParams(location.search).get("view")==="workspace")renderWorkspace();
  };

  window.addEventListener("DOMContentLoaded",()=>boot().catch(error=>console.error("Workspace boot failed",error)));
})();
