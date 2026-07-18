(() => {
  const nav = document.querySelector("#nav");
  if (!nav || document.querySelector('[data-view="paper-commands"]')) return;

  const button = document.createElement("button");
  button.dataset.view = "paper-commands";
  button.textContent = "Paper Trading";
  nav.insertBefore(
    button,
    document.querySelector('[data-view="execution"]') || null
  );

  const content = document.querySelector("#content");
  const title = document.querySelector("#pageTitle");
  const notice = document.querySelector("#notice");
  const status = document.querySelector("#status");

  const uid = () =>
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

  const actor = () => ({
    user_id: localStorage.getItem("paper.user_id") || "local-operator",
    session_id: localStorage.getItem("paper.session_id") || "local-session",
    roles: ["TRADER"],
    permissions: [
      "paper_orders.view",
      "paper_orders.submit",
      "paper_orders.cancel",
      "paper_orders.replace"
    ]
  });

  const request = async (url, options = {}) => {
    const response = await fetch(url, {
      cache: "no-store",
      headers: {"Content-Type": "application/json"},
      ...options
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail || payload;
      throw new Error(
        typeof detail === "string"
          ? detail
          : detail.message || JSON.stringify(detail)
      );
    }
    return payload;
  };

  const money = value => {
    const number = Number(value);
    return Number.isFinite(number)
      ? number.toLocaleString(undefined, {
          style: "currency",
          currency: "USD"
        })
      : "—";
  };

  const render = async () => {
    document.querySelectorAll("#nav button").forEach(
      item => item.classList.toggle(
        "active",
        item.dataset.view === "paper-commands"
      )
    );
    title.textContent = "Governed Paper Trading";
    notice.textContent =
      "Paper-only commands. Live trading remains disabled by server policy.";
    status.textContent = "LOADING";

    try {
      const state = await request("/api/v1/paper-commands");
      const summary = state.summary;
      status.textContent = summary.mode;

      content.innerHTML = `
        <section class="cards">
          <article class="card"><span>Mode</span><strong>${summary.environment}</strong><small>Live trading disabled</small></article>
          <article class="card"><span>Total Orders</span><strong>${summary.total_orders}</strong><small>${summary.open_orders} open</small></article>
          <article class="card"><span>Cancelled</span><strong>${summary.cancelled_orders}</strong><small>${summary.rejected_orders} rejected</small></article>
          <article class="card"><span>Gross Notional</span><strong>${money(summary.gross_notional)}</strong><small>Paper exposure only</small></article>
        </section>

        <section class="grid">
          <article class="panel">
            <small>Governed Command</small>
            <h2>Submit Paper Order</h2>
            <form id="paperOrderForm" class="stack">
              <div class="toolbar">
                <input name="symbol" placeholder="Symbol" value="AAPL" required>
                <select name="side"><option>BUY</option><option>SELL</option></select>
                <select name="order_type"><option>LIMIT</option><option>MARKET</option></select>
                <input name="quantity" type="number" min="1" max="1000" value="1" required>
                <input name="limit_price" type="number" min="0.01" step="0.01" placeholder="Limit price">
              </div>
              <input name="reason" placeholder="Business reason" value="Paper strategy validation" required>
              <label><input name="confirm" type="checkbox" required> I confirm this is a PAPER order.</label>
              <button type="submit">Submit Paper Order</button>
            </form>
            <div id="paperResult" class="notice">No command submitted.</div>
          </article>

          <article class="panel">
            <small>Safety Governance</small>
            <h2>Active Controls</h2>
            <div class="stack">
              ${state.safety_notices.map(item => `<div class="item PASS"><strong>${item}</strong></div>`).join("")}
              <div class="item PASS"><strong>Maximum quantity: 1,000</strong></div>
              <div class="item PASS"><strong>Maximum notional: $100,000</strong></div>
              <div class="item PASS"><strong>Idempotency required for every command</strong></div>
            </div>
          </article>
        </section>

        <section class="panel">
          <small>Order Lifecycle</small>
          <h2>Paper Orders</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Order</th><th>Symbol</th><th>Side</th><th>Type</th><th>Qty</th><th>Price</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                ${state.orders.length ? state.orders.map(order => `
                  <tr>
                    <td>${order.order_id}</td>
                    <td><strong>${order.symbol}</strong></td>
                    <td>${order.side}</td>
                    <td>${order.order_type}</td>
                    <td>${order.quantity}</td>
                    <td>${money(order.limit_price || order.estimated_price)}</td>
                    <td>${order.status}</td>
                    <td>
                      ${["PENDING","ACCEPTED","PARTIALLY_FILLED"].includes(order.status)
                        ? `<button class="paper-cancel" data-order="${order.order_id}">Cancel</button>
                           <button class="paper-replace" data-order="${order.order_id}" data-qty="${order.quantity}" data-price="${order.limit_price || ""}">Replace</button>`
                        : "—"}
                    </td>
                  </tr>`).join("")
                : `<tr><td colspan="8">No paper orders are available.</td></tr>`}
              </tbody>
            </table>
          </div>
        </section>`;

      document.querySelector("#paperOrderForm").onsubmit = async event => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const orderType = form.get("order_type");
        const payload = {
          environment: "PAPER",
          symbol: form.get("symbol"),
          instrument_type: "EQUITY",
          side: form.get("side"),
          order_type: orderType,
          quantity: Number(form.get("quantity")),
          limit_price: orderType === "LIMIT"
            ? Number(form.get("limit_price"))
            : null,
          estimated_price: orderType === "MARKET"
            ? Number(form.get("limit_price")) || null
            : null,
          reason: form.get("reason"),
          confirmation_token: `CONFIRM-PAPER-${uid()}`,
          idempotency_key: `submit-${uid()}`,
          actor: actor()
        };
        try {
          const decision = await request(
            "/api/v1/paper-commands/orders",
            {method: "POST", body: JSON.stringify(payload)}
          );
          document.querySelector("#paperResult").textContent =
            `${decision.status}: ${decision.message}`;
          await render();
        } catch (error) {
          document.querySelector("#paperResult").textContent =
            `Rejected: ${error.message}`;
        }
      };

      document.querySelectorAll(".paper-cancel").forEach(action => {
        action.onclick = async () => {
          const reason = prompt("Cancellation reason:");
          if (!reason) return;
          await request(
            `/api/v1/paper-commands/orders/${action.dataset.order}/cancel`,
            {
              method: "POST",
              body: JSON.stringify({
                environment: "PAPER",
                reason,
                confirmation_token: `CONFIRM-PAPER-${uid()}`,
                idempotency_key: `cancel-${uid()}`,
                actor: actor()
              })
            }
          );
          await render();
        };
      });

      document.querySelectorAll(".paper-replace").forEach(action => {
        action.onclick = async () => {
          const quantity = Number(prompt(
            "Replacement quantity:",
            action.dataset.qty
          ));
          const limitPrice = Number(prompt(
            "Replacement limit price:",
            action.dataset.price
          ));
          const reason = prompt("Replacement reason:");
          if (!quantity || !limitPrice || !reason) return;
          await request(
            `/api/v1/paper-commands/orders/${action.dataset.order}/replace`,
            {
              method: "POST",
              body: JSON.stringify({
                environment: "PAPER",
                quantity,
                limit_price: limitPrice,
                reason,
                confirmation_token: `CONFIRM-PAPER-${uid()}`,
                idempotency_key: `replace-${uid()}`,
                actor: actor()
              })
            }
          );
          await render();
        };
      });
    } catch (error) {
      status.textContent = "FAILED";
      notice.textContent = `Failed to load paper trading: ${error.message}`;
    }
  };

  button.addEventListener("click", event => {
    event.stopImmediatePropagation();
    const url = new URL(location.href);
    url.searchParams.set("view", "paper-commands");
    history.pushState({}, "", url);
    render();
  });

  if (new URLSearchParams(location.search).get("view") === "paper-commands") {
    render();
  }
})();
