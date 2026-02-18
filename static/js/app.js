const byId = (id) => document.getElementById(id);

let runInProgress = false;

function setStatus(message, tone = "info") {
  const el = byId("statusText");
  el.textContent = message;
  el.className = `status status-${tone}`;
}

function setRunFeedback(message, tone = "info") {
  const el = byId("runFeedback");
  if (!message) {
    el.textContent = "";
    el.className = "feedback feedback-hidden";
    return;
  }
  el.textContent = message;
  el.className = `feedback feedback-${tone}`;
}

function setButtonState(id, disabled, label = null, busy = false) {
  const btn = byId(id);
  if (!btn) return;
  if (!btn.dataset.defaultLabel) btn.dataset.defaultLabel = btn.textContent;
  btn.disabled = disabled;
  btn.classList.toggle("busy", busy);
  if (label) {
    btn.textContent = label;
    return;
  }
  btn.textContent = btn.dataset.defaultLabel;
}

function setRunUiState(mode, busy) {
  runInProgress = busy;
  if (busy) {
    const intradayBusy = mode === "INTRADAY";
    const swingBusy = mode === "SWING";
    setButtonState("refreshBtn", true);
    setButtonState("runIntradayBtn", true, intradayBusy ? "Running Intraday" : null, intradayBusy);
    setButtonState("runSwingBtn", true, swingBusy ? "Running Swing" : null, swingBusy);
    setStatus(`Running ${mode} strategy...`, "info");
    return;
  }

  setButtonState("refreshBtn", false);
  setButtonState("runIntradayBtn", false);
  setButtonState("runSwingBtn", false);
}

function parseApiError(status, payload, textPayload) {
  if (payload && typeof payload === "object") {
    if (payload.detail) return String(payload.detail);
    if (payload.message) return String(payload.message);
    return `HTTP ${status}: ${JSON.stringify(payload)}`;
  }
  if (textPayload) return `HTTP ${status}: ${textPayload}`;
  return `HTTP ${status}`;
}

async function apiCall(url, method = "GET", body = null, timeoutMs = 90000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  const options = {
    method,
    headers: { "Content-Type": "application/json" },
    signal: controller.signal,
  };
  if (body) options.body = JSON.stringify(body);

  try {
    const res = await fetch(url, options);
    const rawText = await res.text();
    let payload = null;

    if (rawText) {
      try {
        payload = JSON.parse(rawText);
      } catch (_err) {
        payload = null;
      }
    }

    if (!res.ok) {
      throw new Error(parseApiError(res.status, payload, rawText));
    }

    if (payload !== null) return payload;
    if (!rawText) return {};
    return { message: rawText };
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)} seconds`);
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
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
  const table = byId(tableId);
  const colCount = table.querySelectorAll("thead th").length || 1;
  table.querySelector("tbody").innerHTML =
    rowsHtml || `<tr><td colspan='${colCount}' class='muted'>No data</td></tr>`;
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
  if (!runInProgress) setStatus("Loading dashboard...", "info");
  try {
    const data = await apiCall("/api/dashboard/today");
    renderBudgets(data.budget);
    renderPicked(data.picked_stocks);
    renderWatchlist(data.watchlist);
    renderPlans(data.trade_plans);
    renderGtts(data.gtt_orders);
    renderTxs(data.transactions);
    setStatus(`Updated for ${data.date}`, "success");
  } catch (err) {
    setStatus(`Dashboard error: ${err.message}`, "error");
  }
}

function formatSignals(signals) {
  if (!signals || typeof signals !== "object") return "-";
  const parts = Object.entries(signals).map(([signal, count]) => `${signal}: ${count}`);
  return parts.length ? parts.join(", ") : "-";
}

async function runMode(mode) {
  if (runInProgress) {
    setRunFeedback("Another run is already in progress. Please wait for it to finish.", "warn");
    return;
  }

  setRunUiState(mode, true);
  setRunFeedback(`Started ${mode} run. Please wait while analysis is in progress.`, "info");

  try {
    const payload = mode === "INTRADAY"
      ? { mode: "INTRADAY", interval: "5m", period: "5d" }
      : { mode: "SWING", interval: "1d", period: "6mo" };

    const result = await apiCall("/api/run", "POST", payload, 180000);

    if (!result.symbols_processed) {
      setRunFeedback(
        `${mode} run finished but processed 0 symbols. Add symbols to today's ${mode} watchlist, then run again.`,
        "warn",
      );
    } else {
      setRunFeedback(
        `${mode} run completed. Processed: ${result.symbols_processed}. Trades executed: ${result.trades_executed}. Signals: ${formatSignals(result.signals)}.`,
        "success",
      );
    }

    await loadDashboard();
  } catch (err) {
    setRunFeedback(`${mode} run failed: ${err.message}`, "error");
    setStatus("Run failed. See error details above.", "error");
  } finally {
    setRunUiState(mode, false);
  }
}

byId("refreshBtn").addEventListener("click", loadDashboard);
byId("runIntradayBtn").addEventListener("click", () => runMode("INTRADAY"));
byId("runSwingBtn").addEventListener("click", () => runMode("SWING"));

loadDashboard();
