(() => {
  const nav = document.querySelector("#nav");
  if (!nav || document.querySelector('[data-view="deployment-recovery"]')) return;

  const button = document.createElement("button");
  button.dataset.view = "deployment-recovery";
  button.textContent = "Deployment & Recovery";
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
        item.dataset.view === "deployment-recovery"
      )
    );
    title.textContent = "Deployment & Recovery";
    notice.textContent =
      "Versioned packaging, governed promotion, runtime supervision, backup integrity, and isolated recovery.";
    status.textContent = "LOADING";

    try {
      const state = await api("/api/v1/deployment-recovery");
      status.textContent = state.summary.recovery_readiness;
      content.innerHTML = `
        <section class="cards">
          <article class="card"><span>Packages</span><strong>${state.summary.package_count}</strong><small>${state.summary.latest_package_version || "No release"}</small></article>
          <article class="card"><span>Promotions</span><strong>${state.summary.promotion_count}</strong><small>Governed history</small></article>
          <article class="card"><span>Running</span><strong>${state.summary.active_runtime_count}</strong><small>Supervised components</small></article>
          <article class="card"><span>Recovery</span><strong>${state.summary.recovery_readiness}</strong><small>${state.summary.verified_backup_count} verified backups</small></article>
        </section>

        <section class="grid">
          <article class="panel">
            <small>Release Engineering</small><h2>Create Deployment Package</h2>
            <form id="packageForm" class="stack">
              <input name="version" placeholder="Version" value="32.4.0" required>
              <select name="environment"><option>DEV</option><option>TEST</option><option>PAPER</option><option>STAGING</option><option>PRODUCTION</option></select>
              <input name="requested_by" value="local-operator" required>
              <button type="submit">Create Package</button>
            </form>
          </article>
          <article class="panel">
            <small>Resilience</small><h2>Create Backup</h2>
            <form id="backupForm" class="stack">
              <input name="actor" value="local-operator" required>
              <input name="reason" value="Operational recovery checkpoint" required>
              <button type="submit">Create Backup</button>
            </form>
          </article>
        </section>

        <section class="panel">
          <small>Deployment Artifacts</small><h2>Packages</h2>
          <div class="table-wrap"><table>
            <thead><tr><th>Package</th><th>Version</th><th>Environment</th><th>Files</th><th>Size</th><th>Checksum</th></tr></thead>
            <tbody>${state.packages.length ? state.packages.map(item => `
              <tr><td>${item.package_id}</td><td>${item.version}</td><td>${item.environment}</td><td>${item.file_count}</td><td>${item.size_bytes}</td><td>${item.checksum_sha256.slice(0,16)}…</td></tr>
            `).join("") : `<tr><td colspan="6">No deployment packages.</td></tr>`}</tbody>
          </table></div>
        </section>

        <section class="panel">
          <small>Runtime Supervision</small><h2>Components</h2>
          <div class="stack">
            ${state.runtime_components.length ? state.runtime_components.map(item => `
              <div class="item ${item.status}">
                <div class="item-head"><strong>${item.name}</strong><span>${item.status}</span></div>
                <p>PID ${item.pid || "—"} · Restarts ${item.restart_count}</p>
                <button class="runtime-action" data-name="${item.name}" data-action="start">Start</button>
                <button class="runtime-action" data-name="${item.name}" data-action="stop">Stop</button>
                <button class="runtime-action" data-name="${item.name}" data-action="restart">Restart</button>
              </div>
            `).join("") : `<div class="empty">No supervised runtime components registered.</div>`}
          </div>
        </section>

        <section class="panel">
          <small>Backup & Recovery</small><h2>Recovery Points</h2>
          <div class="table-wrap"><table>
            <thead><tr><th>Backup</th><th>Status</th><th>Created</th><th>Size</th><th>Actions</th></tr></thead>
            <tbody>${state.backups.length ? state.backups.map(item => `
              <tr>
                <td>${item.backup_id}</td><td>${item.status}</td><td>${item.created_at}</td><td>${item.size_bytes}</td>
                <td>
                  <button class="verify-backup" data-backup="${item.backup_id}">Verify</button>
                  <button class="restore-backup" data-backup="${item.backup_id}">Restore</button>
                </td>
              </tr>
            `).join("") : `<tr><td colspan="5">No recovery points.</td></tr>`}</tbody>
          </table></div>
        </section>`;

      document.querySelector("#packageForm").onsubmit = async event => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(event.currentTarget));
        await api("/api/v1/deployment-recovery/packages", {
          method: "POST",
          body: JSON.stringify(data)
        });
        await render();
      };

      document.querySelector("#backupForm").onsubmit = async event => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(event.currentTarget));
        await api("/api/v1/deployment-recovery/backups", {
          method: "POST",
          body: JSON.stringify(data)
        });
        await render();
      };

      document.querySelectorAll(".runtime-action").forEach(action => {
        action.onclick = async () => {
          const reason = prompt("Runtime action reason:");
          if (!reason) return;
          await api(
            `/api/v1/deployment-recovery/runtime/${action.dataset.name}/${action.dataset.action}`,
            {
              method: "POST",
              body: JSON.stringify({
                actor: "local-operator",
                reason,
                confirmation_token: `CONFIRM-RUNTIME-${Date.now()}`
              })
            }
          );
          await render();
        };
      });

      document.querySelectorAll(".verify-backup").forEach(action => {
        action.onclick = async () => {
          await api(
            `/api/v1/deployment-recovery/backups/${action.dataset.backup}/verify`,
            {method: "POST", body: "{}"}
          );
          await render();
        };
      });

      document.querySelectorAll(".restore-backup").forEach(action => {
        action.onclick = async () => {
          const reason = prompt("Restore reason:");
          if (!reason) return;
          await api(
            `/api/v1/deployment-recovery/backups/${action.dataset.backup}/restore`,
            {
              method: "POST",
              body: JSON.stringify({
                actor: "local-operator",
                reason,
                confirmation_token: `CONFIRM-RESTORE-${Date.now()}`
              })
            }
          );
          await render();
        };
      });
    } catch (error) {
      status.textContent = "FAILED";
      notice.textContent = `Deployment and recovery failed: ${error.message}`;
    }
  };

  button.addEventListener("click", event => {
    event.stopImmediatePropagation();
    const url = new URL(location.href);
    url.searchParams.set("view", "deployment-recovery");
    history.pushState({}, "", url);
    render();
  });

  if (
    new URLSearchParams(location.search).get("view") === "deployment-recovery"
  ) {
    render();
  }
})();
