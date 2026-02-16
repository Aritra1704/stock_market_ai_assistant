const byId = (id) => document.getElementById(id);

async function apiCall(url, method = "GET", body = null) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) options.body = JSON.stringify(body);

  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || JSON.stringify(data));
  }
  return data;
}

function htmlList(items) {
  if (!items || !items.length) return "<span class='muted'>None</span>";
  return items.map((x) => `<span class="chip">${x}</span>`).join(" ");
}

function renderBudgets(budget) {
  const html = `
    <div class="panel">
      <h3>Intraday</h3>
      <p>Total: ${budget.intraday.total}</p>
      <p>Spent: ${budget.intraday.spent}</p>
      <p>Remaining: ${budget.intraday.remaining}</p>
    </div>
    <div class="panel">
      <h3>Swing</h3>
      <p>Total: ${budget.swing.total}</p>
      <p>Spent: ${budget.swing.spent}</p>
      <p>Remaining: ${budget.swing.remaining}</p>
    </div>`;
  byId("budgetGrid").innerHTML = html;
}

function renderPicked(picked) {
  byId("pickedGrid").innerHTML = `
    <div class="panel"><h3>Intraday Picks</h3>${htmlList(picked.intraday)}</div>
    <div class="panel"><h3>Swing Picks</h3>${htmlList(picked.swing)}</div>`;
}

function renderWatchlist(watchlist) {
  byId("watchlistGrid").innerHTML = `
    <div class="panel"><h3>Intraday Watchlist</h3>${htmlList(watchlist.intraday)}</div>
    <div class="panel"><h3>Swing Watchlist</h3>${htmlList(watchlist.swing)}</div>`;
}

function setTableRows(tableId, rowsHtml) {
  byId(tableId).querySelector("tbody").innerHTML = rowsHtml || "<tr><td colspan='12' class='muted'>No data</td></tr>";
}

function renderPlans(plans) {
  const rows = plans
    .map((p) => `
      <tr>
        <td>${p.id}</td>
        <td>${p.mode}</td>
        <td>${p.symbol}</td>
        <td>${p.side}</td>
        <td>${p.status}</td>
        <td>${p.qty}</td>
        <td>${p.price_ref ?? "-"}</td>
        <td>${p.buy_trigger ?? "-"}</td>
        <td>${p.sell_trigger ?? "-"}</td>
        <td>${p.rationale ?? "-"}</td>
        <td><pre>${JSON.stringify(p.justification || {}, null, 2)}</pre></td>
      </tr>`)
    .join("");
  setTableRows("plansTable", rows);
}

function renderGtts(gtts) {
  const rows = gtts
    .map((g) => `
      <tr>
        <td>${g.id}</td>
        <td>${g.symbol}</td>
        <td>${g.side}</td>
        <td>${g.qty}</td>
        <td>${g.trigger_price}</td>
        <td>${g.status}</td>
        <td>${g.linked_trade_plan_id}</td>
        <td>${g.executed_price ?? "-"}</td>
      </tr>`)
    .join("");
  setTableRows("gttTable", rows);
}

function renderTxs(txs) {
  const rows = txs
    .map((t) => `
      <tr>
        <td>${t.id}</td>
        <td>${t.mode}</td>
        <td>${t.symbol}</td>
        <td>${t.side}</td>
        <td>${t.qty}</td>
        <td>${t.entry_price ?? "-"}</td>
        <td>${t.exit_price ?? "-"}</td>
        <td>${t.pnl ?? "-"}</td>
        <td>${t.order_type}</td>
        <td>${t.source_portal}</td>
        <td>${t.execution_portal}</td>
        <td>${t.reason ?? "-"}</td>
      </tr>`)
    .join("");
  setTableRows("txTable", rows);
}

async function loadDashboard() {
  byId("statusText").textContent = "Loading dashboard...";
  try {
    const data = await apiCall("/api/dashboard/today");
    renderBudgets(data.budget);
    renderPicked(data.picked_stocks);
    renderWatchlist(data.watchlist);
    renderPlans(data.trade_plans);
    renderGtts(data.gtt_orders);
    renderTxs(data.transactions);
    byId("statusText").textContent = `Updated for ${data.date}`;
  } catch (err) {
    byId("statusText").textContent = `Error: ${err.message}`;
  }
}

async function runMode(mode) {
  byId("statusText").textContent = `Running ${mode}...`;
  try {
    const payload = mode === "INTRADAY"
      ? { mode: "INTRADAY", interval: "5m", period: "5d" }
      : { mode: "SWING", interval: "1d", period: "6mo" };

    const result = await apiCall("/api/run", "POST", payload);
    byId("statusText").textContent = `${mode} run complete. Trades executed: ${result.trades_executed}`;
    await loadDashboard();
  } catch (err) {
    byId("statusText").textContent = `Run failed: ${err.message}`;
  }
}

byId("refreshBtn").addEventListener("click", loadDashboard);
byId("runIntradayBtn").addEventListener("click", () => runMode("INTRADAY"));
byId("runSwingBtn").addEventListener("click", () => runMode("SWING"));

loadDashboard();
