const byId = (id) => document.getElementById(id);

let runInProgress = false;
let latestConfig = null;

const actionButtonIds = [
  "refreshBtn",
  "planDayBtn",
  "runTickBtn",
  "exitDayBtn",
  "refreshAuditBtn",
  "saveConfigBtn",
  "saveScheduleBtn",
  "updateUniverseBtn",
  "pickIntradayBtn",
  "pickSwingBtn",
  "runIntradayBtn",
  "runSwingBtn",
];

function setStatus(message, tone = "info") {
  const el = byId("statusText");
  if (!el) return;
  el.textContent = message;
  el.className = `status status-${tone}`;
}

function setRunFeedback(message, tone = "info") {
  const el = byId("runFeedback");
  if (!el) return;

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

  if (!btn.dataset.defaultLabel) {
    btn.dataset.defaultLabel = btn.textContent;
  }

  btn.disabled = disabled;
  btn.classList.toggle("busy", busy);
  btn.textContent = label || btn.dataset.defaultLabel;
}

function startBusy(buttonId, label) {
  runInProgress = true;
  actionButtonIds.forEach((id) => {
    if (id === buttonId) {
      setButtonState(id, true, label, true);
    } else {
      setButtonState(id, true);
    }
  });
}

function stopBusy() {
  runInProgress = false;
  actionButtonIds.forEach((id) => setButtonState(id, false));
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

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function jsonBlock(obj) {
  return `<pre>${escapeHtml(JSON.stringify(obj || {}, null, 2))}</pre>`;
}

function htmlList(items) {
  if (!items || !items.length) return "<span class='muted'>None</span>";
  return items.map((x) => `<span class="chip">${escapeHtml(x)}</span>`).join(" ");
}

function setTableRows(tableId, rowsHtml) {
  const table = byId(tableId);
  if (!table) return;

  const colCount = table.querySelectorAll("thead th").length || 1;
  table.querySelector("tbody").innerHTML =
    rowsHtml || `<tr><td colspan='${colCount}' class='muted'>No data</td></tr>`;
}

function parseSymbolsInput(raw) {
  if (!raw) return [];
  const cleaned = raw
    .split(/[\s,]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
  return [...new Set(cleaned)];
}

function toDateInputValue(dateObj) {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, "0");
  const d = String(dateObj.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getInputValue(id) {
  const el = byId(id);
  if (!el) return "";
  return String(el.value || "").trim();
}

function getDateInputOrNull() {
  const value = getInputValue("mvpDateInput");
  return value || null;
}

function getNumber(id, fallback = 0) {
  const raw = getInputValue(id);
  if (!raw) return fallback;
  const out = Number(raw);
  return Number.isFinite(out) ? out : fallback;
}

function setInputValue(id, value) {
  const el = byId(id);
  if (!el || value === undefined || value === null) return;
  el.value = value;
}

function renderActiveConfig(config) {
  const panel = byId("activeConfigPanel");
  if (!panel) return;

  panel.innerHTML = `
    <h3>Config #${escapeHtml(config.id)}</h3>
    <p><strong>Mode:</strong> ${escapeHtml(config.mode)} | <strong>Version:</strong> ${escapeHtml(config.strategy_version)}</p>
    <p><strong>Sector Override:</strong> ${escapeHtml(config.sector || "(schedule driven)")}</p>
    <p><strong>Budget:</strong> ₹${escapeHtml(config.budget_daily_inr)} | <strong>Max Positions:</strong> ${escapeHtml(config.max_positions)}</p>
    <p><strong>Monitor:</strong> ${escapeHtml(config.monitor_interval_min)}m | <strong>Entries/Symbol/Day:</strong> ${escapeHtml(config.max_entries_per_symbol_per_day)}</p>
    <p><strong>SL/Target:</strong> ${escapeHtml(config.stop_pct)}% / ${escapeHtml(config.target_pct)}% | <strong>Time Exit:</strong> ${escapeHtml(config.time_exit_hhmm)}</p>
  `;
}

function fillConfigForm(config) {
  latestConfig = config;

  setInputValue("cfgSector", config.sector || "");
  setInputValue("cfgBudget", config.budget_daily_inr);
  setInputValue("cfgMaxPositions", config.max_positions);
  setInputValue("cfgInterval", config.monitor_interval_min);
  setInputValue("cfgMaxEntries", config.max_entries_per_symbol_per_day);
  setInputValue("cfgTargetPct", config.target_pct);
  setInputValue("cfgStopPct", config.stop_pct);
  setInputValue("cfgTimeExit", config.time_exit_hhmm);
  setInputValue("cfgPartialThreshold", config.rebalance_partial_threshold);
  setInputValue("cfgFullThreshold", config.rebalance_full_threshold);
  setInputValue("cfgPartialFraction", config.rebalance_partial_fraction);

  const tickIntervalInput = byId("tickIntervalInput");
  if (tickIntervalInput && !tickIntervalInput.value) {
    tickIntervalInput.value = config.monitor_interval_min;
  }
}

function buildConfigPayload() {
  const base = latestConfig || {};
  const sectorRaw = getInputValue("cfgSector");

  return {
    active: true,
    set_active: true,
    mode: "INTRADAY",
    strategy_version: String(base.strategy_version || "momentum_v1"),
    sector: sectorRaw || null,
    budget_daily_inr: getNumber("cfgBudget", Number(base.budget_daily_inr || 10000)),
    max_positions: Math.max(1, Math.min(2, getNumber("cfgMaxPositions", Number(base.max_positions || 2)))),
    monitor_interval_min: Math.max(1, Math.min(60, getNumber("cfgInterval", Number(base.monitor_interval_min || 5)))),
    warmup_minutes: Number(base.warmup_minutes || 20),
    max_entries_per_symbol_per_day: Math.max(
      1,
      Math.min(10, getNumber("cfgMaxEntries", Number(base.max_entries_per_symbol_per_day || 1))),
    ),
    target_pct: getNumber("cfgTargetPct", Number(base.target_pct || 1.5)),
    stop_pct: getNumber("cfgStopPct", Number(base.stop_pct || 1.0)),
    time_exit_hhmm: getInputValue("cfgTimeExit") || String(base.time_exit_hhmm || "15:20"),
    rebalance_partial_threshold: getNumber(
      "cfgPartialThreshold",
      Number(base.rebalance_partial_threshold || 15.0),
    ),
    rebalance_full_threshold: getNumber("cfgFullThreshold", Number(base.rebalance_full_threshold || 20.0)),
    rebalance_partial_fraction: getNumber(
      "cfgPartialFraction",
      Number(base.rebalance_partial_fraction || 0.5),
    ),
    fill_model: String(base.fill_model || "close"),
  };
}

function renderDayPlan(data) {
  const info = byId("dayPlanInfo");
  if (info) {
    info.innerHTML = `
      <p><strong>Date:</strong> ${escapeHtml(data.date)} | <strong>Sector:</strong> ${escapeHtml(data.sector_name)}</p>
      <p><strong>Day Plan ID:</strong> ${escapeHtml(data.day_plan_id)} | <strong>Selection ID:</strong> ${escapeHtml(data.day_selection_id)}</p>
    `;
  }

  const rows = (data.top5 || [])
    .map(
      (item) => `
      <tr>
        <td>${escapeHtml(item.rank)}</td>
        <td>${escapeHtml(item.symbol)}</td>
        <td>${escapeHtml(item.score)}</td>
        <td>${escapeHtml(item.summary_text || "-")}</td>
        <td>${jsonBlock(item.reasons_json || {})}</td>
      </tr>`,
    )
    .join("");
  setTableRows("top5Table", rows);
}

function renderAudit(data) {
  const panel = byId("mvpSummaryPanel");
  if (panel) {
    const budget = data.budget || {};
    panel.innerHTML = `
      <div class="panel">
        <h3>Day</h3>
        <p><strong>Date:</strong> ${escapeHtml(data.date)}</p>
        <p><strong>Sector:</strong> ${escapeHtml(data.sector_name || "-")}</p>
      </div>
      <div class="panel">
        <h3>Budget</h3>
        <p><strong>Total:</strong> ₹${escapeHtml(budget.budget_total ?? 0)}</p>
        <p><strong>Used:</strong> ₹${escapeHtml(budget.used ?? 0)}</p>
        <p><strong>Remaining:</strong> ₹${escapeHtml(budget.remaining ?? 0)}</p>
      </div>
    `;
  }

  const top5Rows = (data.top5 || [])
    .map(
      (item) => `
      <tr>
        <td>${escapeHtml(item.rank)}</td>
        <td>${escapeHtml(item.symbol)}</td>
        <td>${escapeHtml(item.score)}</td>
        <td>${escapeHtml(item.summary_text || "-")}</td>
        <td>${jsonBlock(item.reasons_json || {})}</td>
      </tr>`,
    )
    .join("");
  if (top5Rows) {
    setTableRows("top5Table", top5Rows);
    const info = byId("dayPlanInfo");
    if (info && !info.textContent.trim()) {
      info.innerHTML = `<p><strong>Date:</strong> ${escapeHtml(data.date)} | <strong>Sector:</strong> ${escapeHtml(data.sector_name || "-")}</p>`;
    }
  }

  const positionRows = (data.positions || [])
    .map(
      (pos) => `
      <tr>
        <td>${escapeHtml(pos.id)}</td>
        <td>${escapeHtml(pos.symbol)}</td>
        <td>${escapeHtml(pos.status)}</td>
        <td>${escapeHtml(pos.qty)}</td>
        <td>${escapeHtml(pos.entry_price)}</td>
        <td>${escapeHtml(pos.stop_price)}</td>
        <td>${escapeHtml(pos.target_price)}</td>
        <td>${escapeHtml(pos.exit_price ?? "-")}</td>
        <td>${escapeHtml(pos.pnl ?? "-")}</td>
        <td>${escapeHtml(pos.exit_reason ?? "-")}</td>
      </tr>`,
    )
    .join("");
  setTableRows("positionsTable", positionRows);

  const decisionRows = (data.decisions || [])
    .map(
      (item) => `
      <tr>
        <td>${escapeHtml(item.id)}</td>
        <td>${escapeHtml(item.symbol)}</td>
        <td>${escapeHtml(item.action)}</td>
        <td>${escapeHtml(item.intended_qty)}</td>
        <td>${escapeHtml(item.intended_price)}</td>
        <td>${escapeHtml(item.summary_text || "-")}</td>
        <td>${jsonBlock(item.reasons_json || {})}</td>
      </tr>`,
    )
    .join("");
  setTableRows("decisionsTable", decisionRows);

  const txRows = (data.transactions || [])
    .map(
      (item) => `
      <tr>
        <td>${escapeHtml(item.id)}</td>
        <td>${escapeHtml(item.position_id)}</td>
        <td>${escapeHtml(item.decision_id ?? "-")}</td>
        <td>${escapeHtml(item.side)}</td>
        <td>${escapeHtml(item.qty)}</td>
        <td>${escapeHtml(item.price)}</td>
        <td>${escapeHtml(item.timestamp)}</td>
      </tr>`,
    )
    .join("");
  setTableRows("paperTxTable", txRows);
}

function renderSectorResult(result) {
  const panel = byId("sectorResultPanel");
  if (!panel) return;

  if (!result) {
    panel.innerHTML = "";
    return;
  }

  if (result.active_symbols) {
    panel.innerHTML = `
      <h3>${escapeHtml(result.sector_name || "Sector")}</h3>
      <p><strong>Active Symbols:</strong> ${escapeHtml(result.count || 0)}</p>
      <div>${htmlList(result.active_symbols || [])}</div>
    `;
    return;
  }

  if (result.mappings) {
    panel.innerHTML = `
      <h3>Saved Schedule Mapping</h3>
      <div>${htmlList((result.mappings || []).map((m) => `${m.weekday}:${m.sector_name}${m.active ? "" : "(inactive)"}`))}</div>
    `;
  }
}

async function loadActiveConfig() {
  const config = await apiCall("/api/config/active");
  renderActiveConfig(config);
  fillConfigForm(config);
  return config;
}

async function loadMvpAudit() {
  const data = await apiCall("/api/audit/today");
  renderAudit(data);
  return data;
}

async function executeAction(buttonId, busyLabel, handler, onSuccess) {
  if (runInProgress) {
    setRunFeedback("An action is already in progress. Please wait.", "warn");
    return;
  }

  startBusy(buttonId, busyLabel);
  try {
    const result = await handler();
    if (onSuccess) {
      setRunFeedback(onSuccess(result), "success");
    }
    await Promise.allSettled([loadActiveConfig(), loadMvpAudit(), loadDashboard()]);
    setStatus("Data refreshed", "success");
  } catch (err) {
    setRunFeedback(err.message || String(err), "error");
    setStatus("Action failed", "error");
  } finally {
    stopBusy();
  }
}

function buildPlanPayload() {
  const payload = {
    notes: getInputValue("planNotesInput") || null,
    force_replan: Boolean(byId("forceReplanInput")?.checked),
  };
  const dateValue = getDateInputOrNull();
  if (dateValue) payload.date = dateValue;
  return payload;
}

function buildRunTickPayload() {
  const payload = {
    interval_min: Math.max(1, Math.min(60, getNumber("tickIntervalInput", Number(latestConfig?.monitor_interval_min || 5)))),
  };
  const dateValue = getDateInputOrNull();
  if (dateValue) payload.date = dateValue;
  return payload;
}

function buildExitPayload() {
  const payload = {};
  const dateValue = getDateInputOrNull();
  if (dateValue) payload.date = dateValue;
  return payload;
}

function buildSchedulePayload() {
  return {
    mappings: [
      {
        weekday: Number(byId("scheduleWeekday")?.value || 0),
        sector_name: getInputValue("scheduleSector"),
        active: Boolean(byId("scheduleActive")?.checked),
      },
    ],
  };
}

function buildUniversePayload() {
  return {
    sector_name: getInputValue("universeSector"),
    add_symbols: parseSymbolsInput(getInputValue("universeAdd")),
    remove_symbols: parseSymbolsInput(getInputValue("universeRemove")),
  };
}

function formatSignals(signals) {
  if (!signals || typeof signals !== "object") return "-";
  const parts = Object.entries(signals).map(([signal, count]) => `${signal}: ${count}`);
  return parts.length ? parts.join(", ") : "-";
}

async function refreshAll() {
  if (runInProgress) {
    setRunFeedback("An action is already in progress. Please wait.", "warn");
    return;
  }

  startBusy("refreshBtn", "Refreshing");
  setStatus("Refreshing data...", "info");
  try {
    const results = await Promise.allSettled([loadActiveConfig(), loadMvpAudit(), loadDashboard()]);
    const failed = results.filter((r) => r.status === "rejected");
    if (failed.length) {
      setStatus(`Partial refresh (${failed.length} request failed)`, "warn");
    } else {
      setStatus("All sections refreshed", "success");
    }
  } catch (err) {
    setStatus(`Refresh failed: ${err.message}`, "error");
  } finally {
    stopBusy();
  }
}

async function saveConfig() {
  await executeAction(
    "saveConfigBtn",
    "Saving Config",
    async () => {
      const payload = buildConfigPayload();
      return apiCall("/api/config", "POST", payload);
    },
    (result) => `Config saved. Active config id: ${result.id}`,
  );
}

async function saveSchedule() {
  await executeAction(
    "saveScheduleBtn",
    "Saving Schedule",
    async () => {
      const payload = buildSchedulePayload();
      if (!payload.mappings[0].sector_name) {
        throw new Error("Sector name is required for schedule mapping");
      }
      const result = await apiCall("/api/sector/schedule", "POST", payload);
      renderSectorResult(result);
      return result;
    },
    () => "Sector schedule updated",
  );
}

async function updateUniverse() {
  await executeAction(
    "updateUniverseBtn",
    "Updating Universe",
    async () => {
      const payload = buildUniversePayload();
      if (!payload.sector_name) {
        throw new Error("Sector name is required for universe update");
      }
      const result = await apiCall("/api/sector/universe", "POST", payload);
      renderSectorResult(result);
      return result;
    },
    (result) => `Universe updated for ${result.sector_name}. Active symbols: ${result.count}`,
  );
}

async function planDay() {
  await executeAction(
    "planDayBtn",
    "Planning Day",
    async () => {
      const result = await apiCall("/api/plan/day", "POST", buildPlanPayload());
      renderDayPlan(result);
      return result;
    },
    (result) => `Plan ready for ${result.date} (${result.sector_name}). Top 5 selected: ${result.top5.length}.`,
  );
}

async function runTick() {
  await executeAction(
    "runTickBtn",
    "Running Tick",
    () => apiCall("/api/run/tick", "POST", buildRunTickPayload(), 180000),
    (result) => {
      if (result.skipped_weekend) {
        return `Tick skipped for weekend date ${result.date}`;
      }
      return `Tick complete: checked=${result.symbols_checked}, buys=${result.buys}, sells=${result.sells}, holds=${result.holds}, rebalances=${result.rebalances}`;
    },
  );
}

async function exitDay() {
  await executeAction(
    "exitDayBtn",
    "Exiting Day",
    () => apiCall("/api/exit/day", "POST", buildExitPayload(), 120000),
    (result) => {
      if (result.skipped_weekend) {
        return `Exit skipped for weekend date ${result.date}`;
      }
      return `Force exit completed. Closed positions: ${result.closed_positions}`;
    },
  );
}

async function refreshAudit() {
  await executeAction(
    "refreshAuditBtn",
    "Refreshing Audit",
    () => loadMvpAudit(),
    () => "Audit refreshed",
  );
}

function renderBudgets(budget) {
  const container = byId("budgetGrid");
  if (!container) return;
  const html = `
    <div class="panel">
      <h3>Intraday</h3>
      <p>Total: ${escapeHtml(budget.intraday.total)}</p>
      <p>Spent: ${escapeHtml(budget.intraday.spent)}</p>
      <p>Remaining: ${escapeHtml(budget.intraday.remaining)}</p>
    </div>
    <div class="panel">
      <h3>Swing</h3>
      <p>Total: ${escapeHtml(budget.swing.total)}</p>
      <p>Spent: ${escapeHtml(budget.swing.spent)}</p>
      <p>Remaining: ${escapeHtml(budget.swing.remaining)}</p>
    </div>`;
  container.innerHTML = html;
}

function renderPicked(picked) {
  const el = byId("pickedGrid");
  if (!el) return;
  el.innerHTML = `
    <div class="panel"><h3>Intraday Picks</h3>${htmlList(picked.intraday)}</div>
    <div class="panel"><h3>Swing Picks</h3>${htmlList(picked.swing)}</div>`;
}

function renderWatchlist(watchlist) {
  const el = byId("watchlistGrid");
  if (!el) return;
  el.innerHTML = `
    <div class="panel"><h3>Intraday Watchlist</h3>${htmlList(watchlist.intraday)}</div>
    <div class="panel"><h3>Swing Watchlist</h3>${htmlList(watchlist.swing)}</div>`;
}

function renderPlans(plans) {
  const rows = (plans || [])
    .map(
      (p) => `
      <tr>
        <td>${escapeHtml(p.id)}</td>
        <td>${escapeHtml(p.mode)}</td>
        <td>${escapeHtml(p.symbol)}</td>
        <td>${escapeHtml(p.side)}</td>
        <td>${escapeHtml(p.status)}</td>
        <td>${escapeHtml(p.qty)}</td>
        <td>${escapeHtml(p.price_ref ?? "-")}</td>
        <td>${escapeHtml(p.buy_trigger ?? "-")}</td>
        <td>${escapeHtml(p.sell_trigger ?? "-")}</td>
        <td>${escapeHtml(p.rationale ?? "-")}</td>
        <td>${jsonBlock(p.justification || {})}</td>
      </tr>`,
    )
    .join("");
  setTableRows("plansTable", rows);
}

function renderGtts(gtts) {
  const rows = (gtts || [])
    .map(
      (g) => `
      <tr>
        <td>${escapeHtml(g.id)}</td>
        <td>${escapeHtml(g.symbol)}</td>
        <td>${escapeHtml(g.side)}</td>
        <td>${escapeHtml(g.qty)}</td>
        <td>${escapeHtml(g.trigger_price)}</td>
        <td>${escapeHtml(g.status)}</td>
        <td>${escapeHtml(g.linked_trade_plan_id)}</td>
        <td>${escapeHtml(g.executed_price ?? "-")}</td>
      </tr>`,
    )
    .join("");
  setTableRows("gttTable", rows);
}

function renderTxs(txs) {
  const rows = (txs || [])
    .map(
      (t) => `
      <tr>
        <td>${escapeHtml(t.id)}</td>
        <td>${escapeHtml(t.mode)}</td>
        <td>${escapeHtml(t.symbol)}</td>
        <td>${escapeHtml(t.side)}</td>
        <td>${escapeHtml(t.qty)}</td>
        <td>${escapeHtml(t.entry_price ?? "-")}</td>
        <td>${escapeHtml(t.exit_price ?? "-")}</td>
        <td>${escapeHtml(t.pnl ?? "-")}</td>
        <td>${escapeHtml(t.order_type)}</td>
        <td>${escapeHtml(t.source_portal)}</td>
        <td>${escapeHtml(t.execution_portal)}</td>
        <td>${escapeHtml(t.reason ?? "-")}</td>
      </tr>`,
    )
    .join("");
  setTableRows("txTable", rows);
}

async function loadDashboard() {
  try {
    const data = await apiCall("/api/dashboard/today");
    renderBudgets(data.budget);
    renderPicked(data.picked_stocks);
    renderWatchlist(data.watchlist);
    renderPlans(data.trade_plans);
    renderGtts(data.gtt_orders);
    renderTxs(data.transactions);
    return data;
  } catch (err) {
    return null;
  }
}

async function pickModeWatchlist(mode) {
  if (runInProgress) {
    setRunFeedback("An action is already in progress. Please wait.", "warn");
    return;
  }

  const promptText = `Enter ${mode} symbols (comma or space separated).`;
  const promptDefault = mode === "INTRADAY" ? "RELIANCE.NS, TCS.NS, INFY.NS" : "HDFCBANK.NS, ITC.NS, SBIN.NS";
  const input = window.prompt(promptText, promptDefault);
  if (input === null) return;

  const symbols = parseSymbolsInput(input);
  if (!symbols.length) {
    setRunFeedback(`No valid ${mode} symbols entered.`, "warn");
    return;
  }

  await executeAction(
    mode === "INTRADAY" ? "pickIntradayBtn" : "pickSwingBtn",
    mode === "INTRADAY" ? "Saving Intraday" : "Saving Swing",
    () =>
      apiCall("/api/watchlist", "POST", {
        mode,
        symbols,
        reason: "manual-ui",
        ...(mode === "SWING" ? { horizon_days: 20 } : {}),
      }),
    (result) => `Watchlist updated for ${mode}. Inserted ${result.inserted} symbol(s).`,
  );
}

async function runMode(mode) {
  await executeAction(
    mode === "INTRADAY" ? "runIntradayBtn" : "runSwingBtn",
    mode === "INTRADAY" ? "Running Intraday" : "Running Swing",
    () =>
      apiCall(
        "/api/run",
        "POST",
        mode === "INTRADAY"
          ? { mode: "INTRADAY", interval: "5m", period: "5d" }
          : { mode: "SWING", interval: "1d", period: "6mo" },
        180000,
      ),
    (result) => {
      if (!result.symbols_processed) {
        return `${mode} run completed with 0 symbols processed.`;
      }
      return `${mode} run: processed ${result.symbols_processed}, trades ${result.trades_executed}, signals ${formatSignals(result.signals)}.`;
    },
  );
}

function bindClick(id, handler) {
  const el = byId(id);
  if (el) {
    el.addEventListener("click", handler);
  }
}

function initializeDefaults() {
  const dateInput = byId("mvpDateInput");
  if (dateInput && !dateInput.value) {
    dateInput.value = toDateInputValue(new Date());
  }
}

async function initialize() {
  initializeDefaults();
  await refreshAll();
}

bindClick("refreshBtn", refreshAll);
bindClick("planDayBtn", planDay);
bindClick("runTickBtn", runTick);
bindClick("exitDayBtn", exitDay);
bindClick("refreshAuditBtn", refreshAudit);
bindClick("saveConfigBtn", saveConfig);
bindClick("saveScheduleBtn", saveSchedule);
bindClick("updateUniverseBtn", updateUniverse);

bindClick("pickIntradayBtn", () => pickModeWatchlist("INTRADAY"));
bindClick("pickSwingBtn", () => pickModeWatchlist("SWING"));
bindClick("runIntradayBtn", () => runMode("INTRADAY"));
bindClick("runSwingBtn", () => runMode("SWING"));

initialize();
