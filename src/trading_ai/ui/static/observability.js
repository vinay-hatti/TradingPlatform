(() => {
  const nav = document.querySelector("#nav");
  if (!nav || document.querySelector('[data-view="observability"]')) return;

  const button = document.createElement("button");
  button.dataset.view = "observability";
  button.textContent = "Observability";
  nav.appendChild(button);

  const content = document.querySelector("#content");
  const title = document.querySelector("#pageTitle");
  const notice = document.querySelector("#notice");
  const status = document.querySelector("#status");

  const api = async (url, options = {}) => {
    const response = await fetch(url, {
      cache: "no-store",
      headers: {"Content-Type": "application/json"},
      ...options
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(JSON.stringify(payload));
    return payload;
  };

  const render = async () => {
    document.querySelectorAll("#nav button").forEach(
      item => item.classList.toggle(
        "active",
        item.dataset.view === "observability"
      )
    );
    title.textContent = "Operational Observability";
    notice.textContent =
      "Metrics, structured logging, health probes, alerting, and operational status.";
    status.textContent = "LOADING";

    try {
      const state = await api("/api/v1/observability");
      status.textContent = state.summary.service_status;

      content.innerHTML = `
        <section class="cards">
          <article class="card"><span>Service</span><strong>${state.summary.service_status}</strong><small>Aggregate health</small></article>
          <article class="card"><span>Readiness</span><strong>${state.summary.readiness_status}</strong><small>Required dependencies</small></article>
          <article class="card"><span>Liveness</span><strong>${state.summary.liveness_status}</strong><small>Process health</small></article>
          <article class="card"><span>Active Alerts</span><strong>${state.summary.active_alert_count}</strong><small>${state.summary.critical_alert_count} critical · ${state.summary.warning_alert_count} warning</small></article>
        </section>

        <section class="panel">
          <small>Health Probes</small><h2>Component Checks</h2>
          <div class="grid-3">
            ${state.health_checks.map(check => `
              <div class="item ${check.status}">
                <div class="item-head"><strong>${check.name}</strong><span>${check.status}</span></div>
                <p>${check.detail}</p>
                <small>${check.required ? "Required" : "Optional"} · ${check.latency_ms ?? "—"} ms</small>
              </div>
            `).join("")}
          </div>
        </section>

        <section class="grid">
          <article class="panel">
            <small>Alerting</small><h2>Incidents</h2>
            <div class="stack">
              ${state.alerts.length ? state.alerts.map(alert => `
                <div class="item ${alert.severity}">
                  <div class="item-head"><strong>${alert.rule_name}</strong><span>${alert.status}</span></div>
                  <p>${alert.message}</p>
                  <small>${alert.severity} · ${alert.source}</small>
                  ${alert.status === "ACTIVE" && !alert.acknowledged
                    ? `<button class="ack-alert" data-alert="${alert.alert_id}">Acknowledge</button>`
                    : ""}
                </div>
              `).join("") : `<div class="empty">No alerts.</div>`}
            </div>
          </article>

          <article class="panel">
            <small>Operational Metrics</small><h2>Current Snapshot</h2>
            <div class="table-wrap"><table>
              <thead><tr><th>Metric</th><th>Value</th><th>Unit</th><th>Labels</th></tr></thead>
              <tbody>${state.metrics.length ? state.metrics.map(metric => `
                <tr><td>${metric.name}</td><td>${metric.value}</td><td>${metric.unit}</td><td>${JSON.stringify(metric.labels)}</td></tr>
              `).join("") : `<tr><td colspan="4">No metrics collected yet.</td></tr>`}</tbody>
            </table></div>
          </article>
        </section>

        <section class="panel">
          <small>Structured Logging</small><h2>Log Destination</h2>
          <div class="kv"><div>Path</div><div>${state.summary.structured_log_path}</div><div>Format</div><div>JSON Lines</div><div>Metrics Endpoint</div><div>/api/v1/observability/metrics</div><div>Liveness</div><div>/api/v1/observability/health/live</div><div>Readiness</div><div>/api/v1/observability/health/ready</div></div>
        </section>`;

      document.querySelectorAll(".ack-alert").forEach(action => {
        action.onclick = async () => {
          const reason = prompt("Acknowledgement reason:");
          if (!reason) return;
          await api(
            `/api/v1/observability/alerts/${action.dataset.alert}/acknowledge`,
            {
              method: "POST",
              body: JSON.stringify({
                actor: "local-operator",
                reason
              })
            }
          );
          await render();
        };
      });
    } catch (error) {
      status.textContent = "FAILED";
      notice.textContent = `Observability failed: ${error.message}`;
    }
  };

  button.addEventListener("click", event => {
    event.stopImmediatePropagation();
    const url = new URL(location.href);
    url.searchParams.set("view", "observability");
    history.pushState({}, "", url);
    render();
  });

  if (
    new URLSearchParams(location.search).get("view") === "observability"
  ) {
    render();
  }
})();
