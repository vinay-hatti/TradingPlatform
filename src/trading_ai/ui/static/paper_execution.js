(() => {
  const nav = document.querySelector("#nav");
  if (!nav || document.querySelector('[data-view="paper-execution"]')) return;

  const button = document.createElement("button");
  button.dataset.view = "paper-execution";
  button.textContent = "Paper Execution";
  nav.insertBefore(
    button,
    document.querySelector('[data-view="execution"]') || null
  );

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
    const payload = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(payload));
    return payload;
  };

  const money = value => Number(value || 0).toLocaleString(undefined, {
    style: "currency",
    currency: "USD"
  });

  const render = async () => {
    document.querySelectorAll("#nav button").forEach(
      item => item.classList.toggle(
        "active",
        item.dataset.view === "paper-execution"
      )
    );
    title.textContent = "Broker-Backed Paper Execution";
    notice.textContent =
      "Local paper broker, deterministic fill simulation, position sync, and reconciliation.";
    status.textContent = "LOADING";

    try {
      const state = await api("/api/v1/paper-execution");
      status.textContent = state.summary.reconciliation_status;
      content.innerHTML = `
        <section class="cards">
          <article class="card"><span>Broker</span><strong>${state.summary.broker_adapter}</strong><small>Paper only</small></article>
          <article class="card"><span>Orders</span><strong>${state.summary.total_orders}</strong><small>${state.summary.open_orders} open</small></article>
          <article class="card"><span>Fills</span><strong>${state.summary.total_fills}</strong><small>${state.summary.total_positions} positions</small></article>
          <article class="card"><span>Unrealized P&L</span><strong>${money(state.summary.total_unrealized_pnl)}</strong><small>${state.summary.reconciliation_status}</small></article>
        </section>

        <section class="grid">
          <article class="panel">
            <small>Broker Synchronization</small>
            <h2>Submit Accepted Paper Commands</h2>
            <form id="syncForm" class="stack">
              <input id="syncPrices" value='{"AAPL":200.00}' aria-label="Market price JSON">
              <button type="submit">Synchronize Orders</button>
            </form>
          </article>
          <article class="panel">
            <small>Fill Simulation</small>
            <h2>Simulate Market Fills</h2>
            <form id="fillForm" class="stack">
              <input id="fillPrices" value='{"AAPL":199.50}' aria-label="Fill price JSON">
              <input id="maxFill" type="number" min="1" placeholder="Max fill quantity">
              <button type="submit">Simulate Fills</button>
            </form>
          </article>
        </section>

        <section class="panel">
          <small>Paper Broker</small><h2>Orders</h2>
          <div class="table-wrap"><table>
            <thead><tr><th>Broker Order</th><th>Client Order</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Filled</th><th>Remaining</th><th>Status</th></tr></thead>
            <tbody>${state.orders.length ? state.orders.map(order => `
              <tr><td>${order.broker_order_id}</td><td>${order.client_order_id}</td><td>${order.symbol}</td><td>${order.side}</td><td>${order.quantity}</td><td>${order.filled_quantity}</td><td>${order.remaining_quantity}</td><td>${order.status}</td></tr>
            `).join("") : `<tr><td colspan="8">No broker paper orders.</td></tr>`}</tbody>
          </table></div>
        </section>

        <section class="panel">
          <small>Position Synchronization</small><h2>Positions</h2>
          <div class="table-wrap"><table>
            <thead><tr><th>Symbol</th><th>Quantity</th><th>Average Price</th><th>Market Price</th><th>Market Value</th><th>Unrealized P&L</th></tr></thead>
            <tbody>${state.positions.length ? state.positions.map(position => `
              <tr><td>${position.symbol}</td><td>${position.quantity}</td><td>${money(position.average_price)}</td><td>${money(position.market_price)}</td><td>${money(position.market_value)}</td><td>${money(position.unrealized_pnl)}</td></tr>
            `).join("") : `<tr><td colspan="6">No synchronized positions.</td></tr>`}</tbody>
          </table></div>
        </section>

        <section class="panel">
          <small>Operational Control</small><h2>Reconciliation</h2>
          <div class="stack">
            <div class="item ${state.reconciliation.issue_count ? "WARNING" : "PASS"}">
              <strong>${state.reconciliation.issue_count} issues</strong>
              <p>${state.reconciliation.matched_orders} matched orders · ${state.reconciliation.matched_positions} matched positions</p>
            </div>
            ${state.reconciliation.issues.map(issue => `
              <div class="item ${issue.severity}">
                <strong>${issue.issue_type}: ${issue.resource_id}</strong>
                <p>${issue.detail}</p>
              </div>
            `).join("")}
          </div>
        </section>`;

      document.querySelector("#syncForm").onsubmit = async event => {
        event.preventDefault();
        await api("/api/v1/paper-execution/synchronize", {
          method: "POST",
          body: JSON.stringify({
            market_prices: JSON.parse(
              document.querySelector("#syncPrices").value
            )
          })
        });
        await render();
      };

      document.querySelector("#fillForm").onsubmit = async event => {
        event.preventDefault();
        const maxFill = Number(
          document.querySelector("#maxFill").value
        ) || null;
        await api("/api/v1/paper-execution/simulate-fills", {
          method: "POST",
          body: JSON.stringify({
            market_prices: JSON.parse(
              document.querySelector("#fillPrices").value
            ),
            max_fill_quantity: maxFill
          })
        });
        await render();
      };
    } catch (error) {
      status.textContent = "FAILED";
      notice.textContent = `Paper execution failed: ${error.message}`;
    }
  };

  button.addEventListener("click", event => {
    event.stopImmediatePropagation();
    const url = new URL(location.href);
    url.searchParams.set("view", "paper-execution");
    history.pushState({}, "", url);
    render();
  });

  if (
    new URLSearchParams(location.search).get("view") === "paper-execution"
  ) {
    render();
  }
})();
