const $ = selector => document.querySelector(selector);
let currentView = new URLSearchParams(location.search).get("view") || "release";
let selectedSymbol = new URLSearchParams(location.search).get("symbol") || "AAPL";
let lastPayload = null;

const views = {
  release: {title:"Workstation Release Overview", api:"/api/v1/workstation-release"},
  dashboard: {title:"Institutional Dashboard", api:"/api/v1/dashboard"},
  opportunities: {title:"Opportunity Discovery", api:"/api/v1/opportunities"},
  symbols: {
    title:"Symbol Intelligence",
    apiCandidates: symbol => [
      `/api/v1/symbols/${encodeURIComponent(symbol)}`,
      `/api/v1/symbols?symbol=${encodeURIComponent(symbol)}`,
      `/api/v1/symbol-intelligence/${encodeURIComponent(symbol)}`,
      `/api/v1/symbol-intelligence?symbol=${encodeURIComponent(symbol)}`
    ]
  },
  "portfolio-risk": {title:"Portfolio & Risk Cockpit", api:"/api/v1/portfolio-risk"},
  execution: {title:"Execution & Order Management", api:"/api/v1/execution"},
  "reporting-audit": {title:"Institutional Reports & Audit", api:"/api/v1/reporting-audit"},
  "admin-runtime": {title:"Administration & Runtime Control", api:"/api/v1/admin-runtime"},
  "auth-session": {title:"Identity & Session Governance", api:"/api/v1/auth-session"}
};

const arrayOf = (obj, ...keys) => {
  for (const key of keys) if (Array.isArray(obj?.[key])) return obj[key];
  return [];
};
const first = (obj, ...keys) => {
  for (const key of keys) if (obj?.[key] !== undefined && obj?.[key] !== null) return obj[key];
  return null;
};
const text = value => value === null || value === undefined || value === "" ? "—" : String(value);
const number = (value, digits=2) => {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString(undefined,{maximumFractionDigits:digits}) : "—";
};
const money = value => {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString(undefined,{style:"currency",currency:"USD",maximumFractionDigits:2}) : "—";
};
const percent = value => {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const normalized = Math.abs(n) <= 1 ? n * 100 : n;
  return `${normalized.toFixed(2)}%`;
};
const dateText = value => value ? String(value).replace("T"," ").replace("Z","").slice(0,19) : "—";
const statusClass = value => {
  const s = String(value || "").toUpperCase();
  if (["PASS","READY","ACTIVE","HEALTHY","UP","SUCCESS","FILLED","VERIFIED","ALLOWED","APPROVED"].includes(s)) return "status-positive";
  if (["WARNING","WARN","DEGRADED","PARTIAL","PENDING","STALE","READY_WITH_WARNINGS"].includes(s)) return "status-warning";
  if (["FAIL","FAILED","ERROR","CRITICAL","DOWN","DENIED","REJECTED","EXPIRED","NOT_READY"].includes(s)) return "status-critical";
  return "status-info";
};
const itemClass = value => String(value || "INFO").toUpperCase();

function card(label, value, detail=""){
  return `<article class="card"><span>${label}</span><strong>${text(value)}</strong><small>${text(detail)}</small></article>`;
}
function empty(message){ return `<div class="empty">${message}</div>`; }
function table(headers, rows){
  if (!rows.length) return empty("No records are currently available.");
  return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}
function objectRows(obj, omit=[]){
  if (!obj || typeof obj !== "object") return [];
  return Object.entries(obj).filter(([key])=>!omit.includes(key));
}

async function fetchJson(url) {
  const response = await fetch(url, {cache:"no-store"});
  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`);
    error.status = response.status;
    error.url = url;
    throw error;
  }
  return response.json();
}

async function fetchSymbolPayload(symbol) {
  const candidates = views.symbols.apiCandidates(symbol);
  const failures = [];

  for (const url of candidates) {
    try {
      const payload = await fetchJson(url);
      return {payload, url};
    } catch (error) {
      failures.push(`${url} -> ${error.message}`);
      if (error.status !== 404 && error.status !== 405 && error.status !== 422) {
        throw error;
      }
    }
  }

  const error = new Error(
    `No supported Symbol Intelligence endpoint was found for ${symbol}. ` +
    failures.join(" · ")
  );
  error.status = 404;
  throw error;
}

function renderRelease(d){
  const s=d.summary||{};
  $("#content").innerHTML=`
    <section class="cards">
      ${card("Release",s.release_version,s.release_name)}
      ${card("Modules Available",s.available_modules,`${text(s.unavailable_modules)} unavailable`)}
      ${card("Passing Checks",s.passing_checks,`${text(s.warning_checks)} warning · ${text(s.failing_checks)} fail`)}
      ${card("Overall Status",s.overall_status,`Milestone ${text(s.milestone)}`)}
    </section>
    <section class="grid">
      <article class="panel"><small>Integrated Modules</small><h2>Workstation</h2><div class="stack">${
        arrayOf(d,"modules").map(x=>`<div class="item ${itemClass(x.status)}"><div class="item-head"><strong>${text(x.name)}</strong><span class="${statusClass(x.status)}">${text(x.status)}</span></div><p>${text(x.detail)}</p><small>${text(x.api_path)}</small></div>`).join("") || empty("No modules registered.")
      }</div></article>
      <article class="panel"><small>Release Governance</small><h2>Readiness</h2><div class="stack">${
        arrayOf(d,"readiness").map(x=>`<div class="item ${itemClass(x.status)}"><div class="item-head"><strong>${text(x.name)}</strong><span class="${statusClass(x.status)}">${text(x.status)}</span></div><p>${text(x.detail)}</p><small>${x.required?"Required":"Optional"}</small></div>`).join("") || empty("No readiness checks.")
      }</div></article>
    </section>`;
}

function renderDashboard(d){
  const s=d.summary||d.metrics||d.dashboard||{};
  const alerts=arrayOf(d,"alerts","notices","warnings");
  const activity=arrayOf(d,"recent_activity","activities","events");
  const market=first(d,"market","market_summary","market_context")||{};
  $("#content").innerHTML=`
    <section class="cards">
      ${card("Portfolio Value",money(first(s,"portfolio_value","total_equity","equity")),`Cash ${money(first(s,"cash","available_cash"))}`)}
      ${card("Daily P&L",money(first(s,"daily_pnl","day_pnl","pnl")),percent(first(s,"daily_return","return_pct")))}
      ${card("Open Positions",first(s,"open_positions","position_count","positions"),`Orders ${text(first(s,"open_orders","order_count"))}`)}
      ${card("Risk Status",first(s,"risk_status","status","readiness"),text(first(s,"market_regime","regime")))}
    </section>
    <section class="grid">
      <article class="panel"><small>Market Context</small><h2>Current Conditions</h2><div class="kv">${
        objectRows(market).slice(0,12).map(([k,v])=>`<div>${k.replaceAll("_"," ")}</div><div>${typeof v==="object"?JSON.stringify(v):text(v)}</div>`).join("") || `<div>Market data</div><div>Not available</div>`
      }</div></article>
      <article class="panel"><small>Attention Required</small><h2>Alerts</h2><div class="stack">${
        alerts.map((x,i)=>{const o=typeof x==="object"?x:{message:x}; const st=first(o,"status","severity","level")||"INFO"; return `<div class="item ${itemClass(st)}"><div class="item-head"><strong>${text(first(o,"title","name")||`Alert ${i+1}`)}</strong><span class="${statusClass(st)}">${text(st)}</span></div><p>${text(first(o,"message","detail","description"))}</p></div>`}).join("") || empty("No active alerts.")
      }</div></article>
    </section>
    <section class="panel"><small>Operational Timeline</small><h2>Recent Activity</h2><div class="timeline">${
      activity.slice(0,25).map((x,i)=>{const o=typeof x==="object"?x:{detail:x}; const st=first(o,"status","outcome","severity")||"INFO"; return `<div class="event ${itemClass(st)}"><div class="event-head"><strong>${text(first(o,"title","event_type","type")||`Activity ${i+1}`)}</strong><span class="${statusClass(st)}">${text(st)}</span></div><p>${text(first(o,"detail","message","description"))}</p><small>${dateText(first(o,"timestamp","occurred_at","created_at"))}</small></div>`}).join("") || empty("No recent activity.")
    }</div></section>`;
}

function renderOpportunities(d){
  const opportunities=arrayOf(d,"opportunities","items","ranked_opportunities","results");
  const s=d.summary||{};
  const rows=opportunities.map((x,i)=>`<tr>
    <td>${i+1}</td><td><strong>${text(first(x,"symbol","underlying_symbol","ticker"))}</strong></td>
    <td>${text(first(x,"strategy","signal","direction","option_type"))}</td>
    <td>${percent(first(x,"probability","probability_of_profit","win_probability","pop"))}</td>
    <td>${number(first(x,"score","ranking_score","composite_score"))}</td>
    <td>${text(first(x,"regime","market_regime"))}</td>
    <td class="${statusClass(first(x,"status","decision"))}">${text(first(x,"status","decision","recommendation"))}</td>
  </tr>`);
  $("#content").innerHTML=`
    <section class="cards">
      ${card("Candidates",first(s,"total","total_opportunities","count")??opportunities.length,"ranked opportunities")}
      ${card("Accepted",first(s,"accepted","approved","selected"),"decision-engine accepted")}
      ${card("Rejected",first(s,"rejected","declined"),"governance rejected")}
      ${card("Top Score",number(first(s,"top_score","max_score")??first(opportunities[0]||{},"score","ranking_score")),"current ranking")}
    </section>
    <section class="panel"><div class="panel-head"><div><small>Decision Intelligence</small><h2>Ranked Opportunities</h2></div><span class="muted">${text(d.source_detail||d.generated_at)}</span></div>
      ${table(["Rank","Symbol","Strategy / Signal","Probability","Score","Regime","Decision"],rows)}
    </section>`;
}

function renderSymbols(d){
  const symbol=first(d,"symbol","underlying_symbol","ticker")||first(d.summary||{},"symbol")||selectedSymbol;
  const quote=first(d,"quote","market_data","price")||{};
  const technical=first(d,"technical","technicals","indicators")||{};
  const options=arrayOf(d,"options","contracts","option_chain","ranked_contracts");
  const rows=options.slice(0,100).map(x=>`<tr>
    <td>${text(first(x,"expiry","expiration","expiration_date"))}</td><td>${text(first(x,"option_type","type","right"))}</td>
    <td>${number(first(x,"strike"))}</td><td>${money(first(x,"bid"))}</td><td>${money(first(x,"ask"))}</td>
    <td>${number(first(x,"delta"),3)}</td><td>${number(first(x,"implied_volatility","iv"),3)}</td>
    <td>${number(first(x,"volume"),0)}</td><td>${number(first(x,"open_interest"),0)}</td>
  </tr>`);
  $("#content").innerHTML=`
    <section class="panel">
      <div class="panel-head">
        <div><small>Research Target</small><h2>Symbol Lookup</h2></div>
        <form id="symbolSearch" class="toolbar">
          <input id="symbolInput" value="${text(symbol)}" maxlength="12" autocomplete="off" aria-label="Symbol">
          <button type="submit">Load Symbol</button>
        </form>
      </div>
    </section>
    <section class="cards">
      ${card("Symbol",symbol,text(first(d,"company_name","name")))}
      ${card("Last Price",money(first(quote,"last","price","close")??first(d,"last_price","price")),`Change ${percent(first(quote,"change_pct","percent_change"))}`)}
      ${card("Signal",first(d,"signal","recommendation","decision"),`Score ${number(first(d,"score","composite_score"))}`)}
      ${card("Market Regime",first(d,"market_regime","regime"),`Expected move ${percent(first(d,"expected_move","expected_move_pct"))}`)}
    </section>
    <section class="grid">
      <article class="panel"><small>Market Snapshot</small><h2>Quote</h2><div class="kv">${
        objectRows(quote).slice(0,16).map(([k,v])=>`<div>${k.replaceAll("_"," ")}</div><div>${text(v)}</div>`).join("") || `<div>Quote</div><div>Not available</div>`
      }</div></article>
      <article class="panel"><small>Technical Research</small><h2>Indicators</h2><div class="kv">${
        objectRows(technical).slice(0,16).map(([k,v])=>`<div>${k.replaceAll("_"," ")}</div><div>${typeof v==="number"?number(v,4):text(v)}</div>`).join("") || `<div>Indicators</div><div>Not available</div>`
      }</div></article>
    </section>
    <section class="panel"><small>Options Intelligence</small><h2>Ranked Contracts</h2>
      ${table(["Expiry","Type","Strike","Bid","Ask","Delta","IV","Volume","Open Interest"],rows)}
    </section>`;

  $("#symbolSearch").onsubmit = event => {
    event.preventDefault();
    const value = $("#symbolInput").value.trim().toUpperCase();
    if (!value) return;
    selectedSymbol = value;
    const url = new URL(location.href);
    url.searchParams.set("view", "symbols");
    url.searchParams.set("symbol", selectedSymbol);
    history.pushState({}, "", url);
    load();
  };
}

function renderPortfolioRisk(d){
  const s=d.summary||d.portfolio||{};
  const positions=arrayOf(d,"positions","holdings","exposures");
  const risks=arrayOf(d,"risk_limits","limits","breaches","risk_events");
  const rows=positions.map(x=>`<tr>
    <td><strong>${text(first(x,"symbol","underlying_symbol"))}</strong></td><td>${text(first(x,"strategy","instrument_type","option_type"))}</td>
    <td>${number(first(x,"quantity","qty"),0)}</td><td>${money(first(x,"market_value","value"))}</td>
    <td>${money(first(x,"unrealized_pnl","pnl"))}</td><td>${number(first(x,"delta"),3)}</td>
    <td>${number(first(x,"gamma"),4)}</td><td>${number(first(x,"theta"),3)}</td><td>${number(first(x,"vega"),3)}</td>
  </tr>`);
  $("#content").innerHTML=`
    <section class="cards">
      ${card("Net Liquidation",money(first(s,"net_liquidation","portfolio_value","equity")),`Cash ${money(first(s,"cash","available_cash"))}`)}
      ${card("Total P&L",money(first(s,"total_pnl","unrealized_pnl","pnl")),percent(first(s,"return_pct","total_return")))}
      ${card("Buying Power",money(first(s,"buying_power","available_buying_power")),`Margin ${money(first(s,"margin_used","margin"))}`)}
      ${card("Risk State",first(s,"risk_status","status"),`Utilization ${percent(first(s,"risk_utilization","utilization"))}`)}
    </section>
    <section class="panel"><small>Position-Level Risk</small><h2>Positions & Greeks</h2>
      ${table(["Symbol","Strategy","Qty","Market Value","Unrealized P&L","Delta","Gamma","Theta","Vega"],rows)}
    </section>
    <section class="panel"><small>Governance</small><h2>Limits & Breaches</h2><div class="stack">${
      risks.map((x,i)=>{const st=first(x,"status","severity","result")||"INFO";return `<div class="item ${itemClass(st)}"><div class="item-head"><strong>${text(first(x,"name","limit","risk_type")||`Risk Check ${i+1}`)}</strong><span class="${statusClass(st)}">${text(st)}</span></div><p>${text(first(x,"detail","message","description"))}</p><small>Current ${text(first(x,"actual","current","value"))} · Limit ${text(first(x,"limit_value","threshold","maximum"))}</small></div>`}).join("") || empty("No active risk-limit events.")
    }</div></section>`;
}

function renderExecution(d){
  const s=d.summary||{};
  const orders=arrayOf(d,"orders","open_orders","items");
  const fills=arrayOf(d,"fills","executions","fill_events");
  const orderRows=orders.map(x=>`<tr>
    <td>${text(first(x,"order_id","id","client_order_id"))}</td><td>${text(first(x,"symbol","underlying_symbol"))}</td>
    <td>${text(first(x,"side","action"))}</td><td>${text(first(x,"order_type","type"))}</td>
    <td>${number(first(x,"quantity","qty"),0)}</td><td>${money(first(x,"limit_price","price"))}</td>
    <td class="${statusClass(first(x,"status","state"))}">${text(first(x,"status","state"))}</td><td>${dateText(first(x,"submitted_at","created_at","timestamp"))}</td>
  </tr>`);
  const fillRows=fills.map(x=>`<tr>
    <td>${text(first(x,"fill_id","execution_id","id"))}</td><td>${text(first(x,"order_id"))}</td>
    <td>${text(first(x,"symbol","underlying_symbol"))}</td><td>${number(first(x,"quantity","qty"),0)}</td>
    <td>${money(first(x,"price","fill_price"))}</td><td>${money(first(x,"fees","commission"))}</td>
    <td>${dateText(first(x,"filled_at","timestamp","created_at"))}</td>
  </tr>`);
  $("#content").innerHTML=`
    <section class="cards">
      ${card("Open Orders",first(s,"open_orders","open_count")??orders.filter(x=>!["FILLED","CANCELLED","REJECTED"].includes(String(first(x,"status","state")).toUpperCase())).length,"currently working")}
      ${card("Filled Orders",first(s,"filled_orders","filled_count"),"completed")}
      ${card("Rejected Orders",first(s,"rejected_orders","rejected_count"),"governance or broker rejected")}
      ${card("Execution Quality",first(s,"execution_quality","quality_status"),`Slippage ${text(first(s,"average_slippage_bps","slippage_bps"))} bps`)}
    </section>
    <section class="panel"><small>Order Lifecycle</small><h2>Orders</h2>${table(["Order ID","Symbol","Side","Type","Qty","Limit","Status","Submitted"],orderRows)}</section>
    <section class="panel"><small>Broker Evidence</small><h2>Fills</h2>${table(["Fill ID","Order ID","Symbol","Qty","Price","Fees","Time"],fillRows)}</section>`;
}

function renderReportingAudit(d){
  const s=d.summary||{};
  const reports=arrayOf(d,"reports","artifacts","report_artifacts");
  const events=arrayOf(d,"audit_events","events","timeline");
  const reportRows=reports.map(x=>`<tr>
    <td><strong>${text(first(x,"name","title","filename"))}</strong></td><td>${text(first(x,"category","report_type","type"))}</td>
    <td>${dateText(first(x,"generated_at","modified_at","created_at"))}</td><td class="${statusClass(first(x,"freshness","status"))}">${text(first(x,"freshness","status"))}</td>
    <td class="${statusClass(first(x,"integrity_status","verification_status"))}">${text(first(x,"integrity_status","verification_status"))}</td>
    <td>${text(first(x,"path","source"))}</td>
  </tr>`);
  $("#content").innerHTML=`
    <section class="cards">
      ${card("Reports",first(s,"report_count","total_reports")??reports.length,"discovered artifacts")}
      ${card("Verified",first(s,"verified_count","integrity_verified"),"checksum verified")}
      ${card("Stale",first(s,"stale_count","stale_reports"),"freshness review")}
      ${card("Audit Events",first(s,"audit_event_count","event_count")??events.length,"governance evidence")}
    </section>
    <section class="panel"><small>Institutional Reporting</small><h2>Report Inventory</h2>${table(["Report","Category","Generated","Freshness","Integrity","Source"],reportRows)}</section>
    <section class="panel"><small>Audit Trail</small><h2>Governance Events</h2><div class="timeline">${
      events.slice(0,100).map((x,i)=>{const st=first(x,"outcome","status","severity")||"INFO";return `<div class="event ${itemClass(st)}"><div class="event-head"><strong>${text(first(x,"event_type","type","action")||`Event ${i+1}`)}</strong><span class="${statusClass(st)}">${text(st)}</span></div><p>${text(first(x,"detail","message","reason"))}</p><small>${dateText(first(x,"occurred_at","timestamp","created_at"))} · ${text(first(x,"actor","source"))}</small></div>`}).join("") || empty("No audit events.")
    }</div></section>`;
}

function renderAdminRuntime(d){
  const s=d.summary||{};
  const profiles=arrayOf(d,"profiles");
  const readiness=arrayOf(d,"readiness");
  const components=arrayOf(d,"components");
  const flags=arrayOf(d,"feature_flags","flags");
  const drift=arrayOf(d,"drift","configuration_drift");
  $("#content").innerHTML=`
    <section class="cards">
      ${card("Environment",first(s,"environment"),first(s,"profile_name"))}
      ${card("Startup Readiness",first(s,"readiness_status"),`${text(first(s,"healthy_components"))} healthy · ${text(first(s,"failed_components"))} failed`)}
      ${card("Feature Flags",first(s,"enabled_feature_flags"),`${text(first(s,"disabled_feature_flags"))} disabled`)}
      ${card("Configuration Drift",first(s,"configuration_drift_count"),first(s,"control_mode"))}
    </section>
    <section class="grid">
      <article class="panel"><small>Environment Governance</small><h2>Profiles</h2><div class="stack">${
        profiles.map(x=>`<div class="item ${x.active?"ACTIVE":"INFO"}"><div class="item-head"><strong>${text(x.environment)} · ${text(x.profile_name)}</strong><span>${x.active?"ACTIVE":"INACTIVE"}</span></div><small>${text(x.version)} · ${text(x.source)}</small></div>`).join("") || empty("No profiles.")
      }</div></article>
      <article class="panel"><small>Startup Safety</small><h2>Readiness Checks</h2><div class="stack">${
        readiness.map(x=>`<div class="item ${itemClass(x.status)}"><div class="item-head"><strong>${text(x.name)}</strong><span class="${statusClass(x.status)}">${text(x.status)}</span></div><p>${text(x.detail)}</p><small>${x.required?"Required":"Optional"}</small></div>`).join("") || empty("No readiness checks.")
      }</div></article>
    </section>
    <section class="panel"><small>Runtime Operations</small><h2>Component Health</h2><div class="grid-3">${
      components.map(x=>`<div class="item ${itemClass(x.status)}"><div class="item-head"><strong>${text(x.name)}</strong><span class="${statusClass(x.status)}">${text(x.status)}</span></div><p>${text(x.detail)}</p><small>${x.latency_ms==null?"No latency":`${number(x.latency_ms,1)} ms`} · ${dateText(x.last_checked_at)}</small></div>`).join("") || empty("No runtime components.")
    }</div></section>
    <section class="grid">
      <article class="panel"><small>Runtime Configuration</small><h2>Feature Flags</h2><div class="stack">${
        flags.map(x=>`<div class="item ${x.enabled?"ACTIVE":"INFO"}"><div class="item-head"><strong>${text(x.name)}</strong><span class="${x.enabled?"status-positive":"muted"}">${x.enabled?"ENABLED":"DISABLED"}</span></div><p>${text(x.description)}</p><small>${text(x.scope)}</small></div>`).join("") || empty("No feature flags.")
      }</div></article>
      <article class="panel"><small>Drift Governance</small><h2>Configuration Drift</h2><div class="stack">${
        drift.map(x=>`<div class="item ${itemClass(x.status)}"><div class="item-head"><strong>${text(x.key)}</strong><span class="${statusClass(x.status)}">${text(x.status)}</span></div><p>Expected: ${text(x.expected)}<br>Actual: ${text(x.actual)}</p><small>${text(x.source)}</small></div>`).join("") || empty("No configuration drift.")
      }</div></article>
    </section>`;
}

function renderAuthSession(d){
  const g=d.governance||{};
  const identity=d.identity;
  const roles=arrayOf(d,"roles");
  const permissions=arrayOf(d,"permissions");
  const events=arrayOf(d,"events");
  $("#content").innerHTML=`
    <section class="cards">
      ${card("Session Status",first(g,"session_status"),`Idle ${number(first(g,"idle_seconds"),0)} sec`)}
      ${card("Identity",identity?.display_name||"Unauthenticated",identity?.user_id||"No principal")}
      ${card("Active Roles",first(g,"active_role_count"),first(g,"enforcement_mode"))}
      ${card("Permission Denials",first(g,"denied_permission_count"),g.privileged?"Privileged access active":"No privileged access")}
    </section>
    <section class="grid">
      <article class="panel"><small>Identity Context</small><h2>Current Session</h2>${
        identity?`<div class="kv"><div>User</div><div>${text(identity.display_name)} (${text(identity.user_id)})</div><div>Session ID</div><div>${text(identity.session_id)}</div><div>Authentication</div><div>${text(identity.authentication_method)}</div><div>Authenticated</div><div>${dateText(identity.authenticated_at)}</div><div>Last Activity</div><div>${dateText(identity.last_activity_at)}</div><div>Expires</div><div>${dateText(identity.expires_at)}</div></div>`:empty("No authenticated session.")
      }</article>
      <article class="panel"><small>Role Governance</small><h2>Assignments</h2><div class="stack">${
        roles.map(x=>`<div class="item ${x.active?"ACTIVE":"INFO"}"><div class="item-head"><strong>${text(x.role)}</strong><span>${x.active?"ACTIVE":"INACTIVE"}</span></div><small>${text(x.scope)} · ${text(x.source)}</small></div>`).join("") || empty("No role assignments.")
      }</div></article>
    </section>
    <section class="panel"><small>Authorization Policy</small><h2>Permissions</h2><div class="grid-3">${
      permissions.map(x=>`<div class="permission ${x.allowed?"ALLOWED":"DENIED"}"><div class="permission-head"><strong>${text(x.permission)}</strong><span class="${x.allowed?"status-positive":"status-critical"}">${x.allowed?"ALLOWED":"DENIED"}</span></div><p>${text(x.reason)}</p><small>${text(x.scope)} · ${text(x.source)}</small></div>`).join("") || empty("No permission grants. Deny by default.")
    }</div></section>
    <section class="panel"><small>Security Evidence</small><h2>Authentication Events</h2><div class="timeline">${
      events.map((x,i)=>`<div class="event ${itemClass(x.outcome)}"><div class="event-head"><strong>${text(x.event_type||`Event ${i+1}`)}</strong><span class="${statusClass(x.outcome)}">${text(x.outcome)}</span></div><p>${text(x.detail)}</p><small>${dateText(x.occurred_at)} · ${text(x.actor)}${x.ip_address?` · ${x.ip_address}`:""}</small></div>`).join("") || empty("No authentication events.")
    }</div></section>`;
}

const renderers = {
  release: renderRelease,
  dashboard: renderDashboard,
  opportunities: renderOpportunities,
  symbols: renderSymbols,
  "portfolio-risk": renderPortfolioRisk,
  execution: renderExecution,
  "reporting-audit": renderReportingAudit,
  "admin-runtime": renderAdminRuntime,
  "auth-session": renderAuthSession
};

async function load(){
  const view=views[currentView]||views.release;
  $("#pageTitle").textContent=view.title;
  document.querySelectorAll("#nav button").forEach(
    button=>button.classList.toggle("active",button.dataset.view===currentView)
  );
  $("#status").textContent="Loading";

  try{
    let payload;
    let sourceUrl;

    if (currentView === "symbols") {
      const result = await fetchSymbolPayload(selectedSymbol);
      payload = result.payload;
      sourceUrl = result.url;
    } else {
      sourceUrl = view.api;
      payload = await fetchJson(view.api);
    }

    lastPayload=payload;
    const summaryStatus=first(payload.summary||{},"overall_status","status","readiness_status")
      || first(payload.governance||{},"session_status")
      || (payload.available===false?"NO DATA":"AVAILABLE");
    $("#status").textContent=text(summaryStatus);
    $("#status").className=`pill ${statusClass(summaryStatus)}`;
    $("#notice").textContent=arrayOf(payload,"notices").join(" · ")
      || payload.source_detail
      || `${view.title} loaded from ${sourceUrl}.`;
    renderers[currentView](payload);
  }catch(error){
    $("#status").textContent="FAILED";
    $("#status").className="pill status-critical";
    $("#notice").textContent=`Failed to load ${view.title}: ${error.message}`;
    $("#content").innerHTML=currentView === "symbols"
      ? `<section class="panel"><div class="panel-head"><div><small>Research Target</small><h2>Symbol Lookup</h2></div>
          <form id="symbolSearch" class="toolbar"><input id="symbolInput" value="${text(selectedSymbol)}" maxlength="12" autocomplete="off"><button type="submit">Retry</button></form></div>
          ${empty("No compatible Symbol Intelligence API route responded. Review the router path if this persists.")}</section>`
      : empty("The module API could not be loaded.");

    if (currentView === "symbols" && $("#symbolSearch")) {
      $("#symbolSearch").onsubmit = event => {
        event.preventDefault();
        const value = $("#symbolInput").value.trim().toUpperCase();
        if (!value) return;
        selectedSymbol = value;
        const url = new URL(location.href);
        url.searchParams.set("view", "symbols");
        url.searchParams.set("symbol", selectedSymbol);
        history.pushState({}, "", url);
        load();
      };
    }
  }
}

document.querySelectorAll("#nav button").forEach(button=>{
  button.onclick=()=>{
    currentView=button.dataset.view;
    const url=new URL(location.href);
    currentView==="release"
      ?url.searchParams.delete("view")
      :url.searchParams.set("view",currentView);
    if (currentView !== "symbols") url.searchParams.delete("symbol");
    history.pushState({}, "", url);
    load();
  };
});
window.onpopstate=()=>{
  const params = new URLSearchParams(location.search);
  currentView=params.get("view")||"release";
  selectedSymbol=params.get("symbol")||selectedSymbol||"AAPL";
  load();
};
$("#refresh").onclick=load;
$("#theme").onclick=()=>{
  const root=document.documentElement;
  root.dataset.theme=root.dataset.theme==="dark"?"light":"dark";
};
load();
