const $ = (selector) => document.querySelector(selector);
let state = { page: 1, totalPages: 1, records: [] };

function pct(value) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}
function num(value, digits = 2) {
  return value == null ? "—" : Number(value).toFixed(digits);
}
function integer(value) {
  return value == null ? "—" : Number(value).toLocaleString();
}
function queryParams() {
  const params = new URLSearchParams();
  const search = $("#searchInput").value.trim();
  const direction = $("#directionFilter").value;
  const minScore = $("#minScore").value;
  const minPop = $("#minPop").value;
  if (search) params.set("search", search);
  if (direction) params.set("direction", direction);
  if (minScore && Number(minScore) > 0) params.set("min_score", minScore);
  if (minPop && Number(minPop) > 0) params.set("min_pop", minPop);
  params.set("sort_by", $("#sortBy").value);
  params.set("sort_order", $("#sortOrder").value);
  params.set("page", state.page);
  params.set("page_size", "25");
  return params;
}
function sourceClass(stale) {
  return stale ? "status-pill warning" : "status-pill healthy";
}
function renderSummary(data) {
  $("#totalRecords").textContent = data.total_records;
  $("#filteredRecords").textContent = data.filtered_records;
  $("#topScore").textContent = data.records.length ? data.records[0].score.toFixed(1) : "—";
  const pops = data.records.map(item => item.probability_of_profit).filter(value => value != null);
  $("#averagePop").textContent = pops.length
    ? pct(pops.reduce((sum, value) => sum + value, 0) / pops.length)
    : "—";
}
function renderRows(records) {
  const body = $("#opportunityRows");
  body.innerHTML = "";
  if (!records.length) {
    body.innerHTML = `<tr><td colspan="14" class="muted">No opportunities match the current filters.</td></tr>`;
    return;
  }
  records.forEach((item, index) => {
    const row = document.createElement("tr");
    const spreadClass = item.spread_pct != null && item.spread_pct > 0.25 ? "warning" : "";
    row.innerHTML = `
      <td>${item.rank}</td>
      <td><strong>${item.symbol}</strong></td>
      <td><span class="direction">${item.direction}</span></td>
      <td>${item.strategy}</td>
      <td class="score">${item.score.toFixed(1)}</td>
      <td>${pct(item.probability_of_profit)}</td>
      <td>${num(item.expected_value)}</td>
      <td>${item.regime}</td>
      <td>${item.contract || "—"}</td>
      <td>${num(item.liquidity_score, 1)}</td>
      <td>${integer(item.open_interest)}</td>
      <td>${integer(item.volume)}</td>
      <td class="${spreadClass}">${item.spread_pct == null ? "—" : `${item.spread_pct.toFixed(2)}%`}</td>
      <td>${item.status}</td>
    `;
    row.addEventListener("click", () => showDetail(index));
    body.appendChild(row);
  });
}
function showDetail(index) {
  const item = state.records[index];
  if (!item) return;
  $("#detailTitle").textContent = `${item.symbol} · ${item.direction} · ${item.strategy}`;
  const fields = [
    ["Score", item.score.toFixed(1)],
    ["POP", pct(item.probability_of_profit)],
    ["Expected Value", num(item.expected_value)],
    ["Contract", item.contract || "—"],
    ["Expiry", item.expiry || "—"],
    ["Strike", num(item.strike)],
    ["Bid", num(item.bid)],
    ["Ask", num(item.ask)],
    ["Spread", item.spread_pct == null ? "—" : `${item.spread_pct.toFixed(2)}%`],
    ["Volume", integer(item.volume)],
    ["Open Interest", integer(item.open_interest)],
    ["IV", num(item.implied_volatility, 4)],
    ["Delta", num(item.delta, 4)],
    ["Gamma", num(item.gamma, 4)],
    ["Theta", num(item.theta, 4)],
    ["Vega", num(item.vega, 4)],
    ["Liquidity", num(item.liquidity_score, 1)],
    ["Grade", item.confidence_grade || "—"],
    ["Regime", item.regime],
    ["Source", item.source],
  ];
  $("#detailGrid").innerHTML = fields.map(([label, value]) =>
    `<div class="detail-item"><span>${label}</span><strong>${value}</strong></div>`
  ).join("");
  $("#detailNotes").innerHTML = (item.notes.length ? item.notes : ["No additional notes."])
    .map(note => `<div class="notice">${note}</div>`).join("");
  $("#detailPanel").classList.remove("hidden");
  $("#detailPanel").scrollIntoView({ behavior: "smooth" });
}
async function load() {
  $("#sourceStatus").textContent = "Loading";
  $("#sourceStatus").className = "status-pill warning";
  try {
    const response = await fetch(`/api/v1/opportunities?${queryParams()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.totalPages = data.total_pages;
    state.records = data.records;
    renderSummary(data);
    renderRows(data.records);
    $("#pageText").textContent = `Page ${data.page} of ${data.total_pages}`;
    $("#prevPage").disabled = data.page <= 1;
    $("#nextPage").disabled = data.page >= data.total_pages;
    $("#sourceStatus").textContent = data.stale ? "Source Stale" : "Source Current";
    $("#sourceStatus").className = sourceClass(data.stale);
    $("#freshnessText").textContent =
      `${data.source_detail} · age ${Math.round(data.age_seconds)} seconds`;
  } catch (error) {
    $("#sourceStatus").textContent = "Load Failed";
    $("#sourceStatus").className = "status-pill offline";
    $("#opportunityRows").innerHTML =
      `<tr><td colspan="14" class="critical">${error.message}</td></tr>`;
  }
}
$("#applyFilters").addEventListener("click", () => { state.page = 1; load(); });
$("#clearFilters").addEventListener("click", () => {
  $("#searchInput").value = "";
  $("#directionFilter").value = "";
  $("#minScore").value = "0";
  $("#minPop").value = "0";
  $("#sortBy").value = "score";
  $("#sortOrder").value = "desc";
  state.page = 1;
  load();
});
$("#refreshButton").addEventListener("click", load);
$("#prevPage").addEventListener("click", () => {
  if (state.page > 1) { state.page -= 1; load(); }
});
$("#nextPage").addEventListener("click", () => {
  if (state.page < state.totalPages) { state.page += 1; load(); }
});
$("#exportButton").addEventListener("click", () => {
  const params = queryParams();
  params.delete("page");
  params.delete("page_size");
  window.location.href = `/api/v1/opportunities/export.csv?${params}`;
});
$("#closeDetail").addEventListener("click", () => $("#detailPanel").classList.add("hidden"));
$("#themeToggle").addEventListener("click", () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("trading-ai-theme", root.dataset.theme);
});
document.documentElement.dataset.theme =
  localStorage.getItem("trading-ai-theme") || "dark";
load();
setInterval(load, 60_000);
