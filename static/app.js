(() => {
  const byId = (id) => document.getElementById(id);
  const page = document.body.dataset.page || "dashboard";
  const sortState = {};
  const cache = {
    decisions: [],
    audit: null,
    settings: null,
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmtNum(value, digits = 2) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "-";
    return n.toFixed(digits);
  }

  function fmtDateTime(value) {
    if (!value) return "-";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString();
  }

  function fmtMoney(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "-";
    return `₹${n.toFixed(2)}`;
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
      const text = await res.text();
      let payload = null;
      if (text) {
        try {
          payload = JSON.parse(text);
        } catch (_err) {
          payload = null;
        }
      }

      if (!res.ok) {
        throw new Error(parseApiError(res.status, payload, text));
      }
      if (payload !== null) return payload;
      return {};
    } catch (err) {
      if (err && err.name === "AbortError") {
        throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)} seconds`);
      }
      throw err;
    } finally {
      clearTimeout(timeout);
    }
  }

  function setStatus(id, message) {
    const el = byId(id);
    if (el) el.textContent = message;
  }

  function toast(message, tone = "info") {
    const host = byId("toastHost");
    if (!host) return;

    const el = document.createElement("div");
    el.className = `toast ${tone}`;
    el.textContent = message;
    host.appendChild(el);

    setTimeout(() => {
      el.remove();
    }, 3200);
  }

  function todayInputValue() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function getActionDate() {
    const value = (byId("globalDate")?.value || "").trim();
    return value || null;
  }

  function getActionInterval() {
    const raw = Number((byId("globalInterval")?.value || "5").trim());
    if (!Number.isFinite(raw)) return 5;
    return Math.max(1, Math.min(60, Math.round(raw)));
  }

  function setBusy(buttonId, busy, busyLabel) {
    const btn = byId(buttonId);
    if (!btn) return;
    if (!btn.dataset.defaultLabel) btn.dataset.defaultLabel = btn.textContent;
    btn.disabled = busy;
    btn.textContent = busy ? busyLabel : btn.dataset.defaultLabel;
  }

  function attachThemeControls() {
    const select = byId("themeMode");
    if (!select) return;

    const stored = localStorage.getItem("ui-theme") || "auto";
    select.value = stored;
    applyTheme(stored);

    select.addEventListener("change", () => {
      const mode = select.value;
      localStorage.setItem("ui-theme", mode);
      applyTheme(mode);
      toast(`Theme set to ${mode}`, "info");
    });
  }

  function applyTheme(mode) {
    const root = document.documentElement;
    if (mode === "light" || mode === "dark") {
      root.setAttribute("data-theme", mode);
      return;
    }
    root.removeAttribute("data-theme");
  }

  function attachSidebarToggle() {
    const btn = byId("sidebarToggle");
    if (!btn) return;
    btn.addEventListener("click", () => {
      document.body.classList.toggle("sidebar-open");
    });
  }

  function sortableValue(value) {
    if (value === null || value === undefined) return "";
    if (typeof value === "number") return value;
    const num = Number(value);
    if (Number.isFinite(num) && String(value).trim() !== "") return num;
    const ts = Date.parse(String(value));
    if (!Number.isNaN(ts)) return ts;
    return String(value).toLowerCase();
  }

  function sortRows(tableId, rows) {
    const spec = sortState[tableId];
    if (!spec || !spec.key) return [...rows];

    const out = [...rows];
    out.sort((a, b) => {
      const av = sortableValue(a[spec.key]);
      const bv = sortableValue(b[spec.key]);
      if (av < bv) return spec.dir === "asc" ? -1 : 1;
      if (av > bv) return spec.dir === "asc" ? 1 : -1;
      return 0;
    });
    return out;
  }

  function renderTable(tableId, columns, rows, emptyText = "No data") {
    const table = byId(tableId);
    if (!table) return;

    const sortedRows = sortRows(tableId, rows);
    const currentSort = sortState[tableId] || { key: null, dir: "asc" };

    const headHtml = `
      <thead>
        <tr>
          ${columns
            .map((col) => {
              const sortable = col.sortable !== false;
              const sorted = sortable && currentSort.key === col.key;
              return `<th class="${sortable ? "sortable" : ""} ${sorted ? `sorted ${currentSort.dir}` : ""}" ${
                sortable ? `data-key="${col.key}"` : ""
              }>${escapeHtml(col.label)}</th>`;
            })
            .join("")}
        </tr>
      </thead>`;

    let bodyHtml = "";
    if (!sortedRows.length) {
      bodyHtml = `<tbody><tr><td class="empty" colspan="${columns.length}">${escapeHtml(emptyText)}</td></tr></tbody>`;
    } else {
      bodyHtml = `<tbody>${sortedRows
        .map((row) => {
          const tds = columns
            .map((col) => {
              const value = col.render ? col.render(row[col.key], row) : escapeHtml(row[col.key] ?? "-");
              return `<td>${value}</td>`;
            })
            .join("");
          return `<tr>${tds}</tr>`;
        })
        .join("")}</tbody>`;
    }

    table.innerHTML = `${headHtml}${bodyHtml}`;

    table.querySelectorAll("th.sortable").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.key;
        const prev = sortState[tableId];
        const dir = prev && prev.key === key && prev.dir === "asc" ? "desc" : "asc";
        sortState[tableId] = { key, dir };
        renderTable(tableId, columns, rows, emptyText);
      });
    });
  }

  function compactReasons(reasons) {
    if (!reasons || typeof reasons !== "object") return "-";
    const list = Array.isArray(reasons.rules_triggered) ? reasons.rules_triggered : [];
    if (!list.length) return "-";
    return list.map((x) => `<span class="badge">${escapeHtml(x)}</span>`).join(" ");
  }

  function getBadgeClass(action) {
    const clean = String(action || "").toLowerCase();
    if (clean.includes("buy")) return "buy";
    if (clean.includes("sell")) return "sell";
    return "hold";
  }

  async function fetchAudit() {
    const data = await apiCall("/api/audit/today");
    cache.audit = data;
    cache.decisions = data.decisions || [];
    return data;
  }

  async function fetchSelection() {
    return apiCall("/api/selection/today");
  }

  async function fetchPositions() {
    return apiCall("/api/positions/today");
  }

  async function fetchTransactions() {
    return apiCall("/api/transactions/today");
  }

  async function fetchConfig() {
    const data = await apiCall("/api/config/active");
    cache.settings = data;
    return data;
  }

  async function loadDashboard() {
    setStatus("dashboardStatus", "Loading dashboard...");
    const [audit, positions] = await Promise.all([fetchAudit(), fetchPositions()]);

    const decisions = Array.isArray(audit.decisions) ? audit.decisions : [];
    const budget = audit.budget || {};
    const lastTickRaw = decisions
      .map((d) => d.tick_time || d.created_at)
      .filter(Boolean)
      .sort((a, b) => Date.parse(b) - Date.parse(a))[0];

    byId("dashSector").textContent = audit.sector_name || "-";
    byId("dashBudgetUsed").textContent = fmtMoney(budget.used);
    byId("dashBudgetRemaining").textContent = fmtMoney(budget.remaining);
    byId("dashOpenPositions").textContent = String(positions.count || 0);
    byId("dashLastTick").textContent = fmtDateTime(lastTickRaw);

    const openRows = (positions.positions || []).filter((x) => x.status === "OPEN");
    renderTable(
      "dashboardPositionsTable",
      [
        { key: "symbol", label: "Symbol" },
        { key: "status", label: "Status" },
        { key: "qty", label: "Qty", render: (v) => fmtNum(v, 4) },
        { key: "entry_price", label: "Entry", render: (v) => fmtNum(v, 2) },
        { key: "stop_price", label: "Stop", render: (v) => fmtNum(v, 2) },
        { key: "target_price", label: "Target", render: (v) => fmtNum(v, 2) },
        { key: "pnl", label: "PnL", render: (v) => (v === null || v === undefined ? "-" : fmtNum(v, 2)) },
      ],
      openRows,
      "No open positions",
    );

    const recent = [...decisions]
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .slice(0, 12)
      .map((d) => `[${fmtDateTime(d.tick_time || d.created_at)}] ${d.symbol} ${d.action} :: ${d.summary_text || "-"}`);

    const logEl = byId("dashboardLog");
    if (logEl) {
      logEl.textContent = recent.length ? recent.join("\n") : "No decisions yet.";
    }

    setStatus("dashboardStatus", `Updated ${fmtDateTime(new Date().toISOString())}`);
  }

  async function loadPlan() {
    setStatus("planStatus", "Loading plan...");
    const data = await fetchSelection();

    const meta = byId("planMeta");
    if (meta) {
      meta.innerHTML = `
        <div class="meta-item"><span class="k">Date</span><span class="v">${escapeHtml(data.date || "-")}</span></div>
        <div class="meta-item"><span class="k">Sector</span><span class="v">${escapeHtml(data.sector_name || "-")}</span></div>
        <div class="meta-item"><span class="k">Day Plan ID</span><span class="v">${escapeHtml(data.day_plan_id || "-")}</span></div>
        <div class="meta-item"><span class="k">Selection ID</span><span class="v">${escapeHtml(data.day_selection_id || "-")}</span></div>
      `;
    }

    renderTable(
      "planTable",
      [
        { key: "rank", label: "Rank" },
        { key: "symbol", label: "Symbol" },
        { key: "score", label: "Score", render: (v) => fmtNum(v, 2) },
        { key: "summary_text", label: "Summary" },
        { key: "reasons_json", label: "Reasons", render: (v) => compactReasons(v) },
      ],
      data.top5 || [],
      "No plan yet. Use Plan Day action.",
    );

    setStatus("planStatus", `Loaded ${data.top5?.length || 0} selections`);
  }

  async function loadPositions() {
    setStatus("positionsStatus", "Loading positions...");
    const data = await fetchPositions();

    renderTable(
      "positionsTable",
      [
        { key: "id", label: "ID" },
        { key: "symbol", label: "Symbol" },
        { key: "status", label: "Status" },
        { key: "qty", label: "Qty", render: (v) => fmtNum(v, 4) },
        { key: "entry_price", label: "Entry", render: (v) => fmtNum(v, 2) },
        { key: "stop_price", label: "Stop", render: (v) => fmtNum(v, 2) },
        { key: "target_price", label: "Target", render: (v) => fmtNum(v, 2) },
        { key: "exit_price", label: "Exit", render: (v) => (v == null ? "-" : fmtNum(v, 2)) },
        { key: "pnl", label: "PnL", render: (v) => (v == null ? "-" : fmtNum(v, 2)) },
        { key: "exit_reason", label: "Reason", render: (v) => escapeHtml(v || "-") },
      ],
      data.positions || [],
      "No positions for today",
    );

    setStatus("positionsStatus", `${data.count || 0} position rows`);
  }

  function getDecisionFilterId() {
    if (page === "audit") return "auditSymbolFilter";
    return "decisionsSymbolFilter";
  }

  function filterDecisions(source) {
    const filterEl = byId(getDecisionFilterId());
    const symbol = (filterEl?.value || "").trim().toUpperCase();
    if (!symbol) return source;
    return source.filter((row) => String(row.symbol || "").toUpperCase().includes(symbol));
  }

  function renderDecisionsTable(rows) {
    renderTable(
      "decisionsTable",
      [
        { key: "tick_time", label: "Tick Time", render: (v, r) => fmtDateTime(v || r.created_at) },
        { key: "run_tick_id", label: "Tick ID", render: (v) => escapeHtml(v ?? "-") },
        { key: "symbol", label: "Symbol" },
        {
          key: "action",
          label: "Action",
          render: (v) => `<span class="badge ${getBadgeClass(v)}">${escapeHtml(v)}</span>`,
        },
        { key: "intended_qty", label: "Qty", render: (v) => fmtNum(v, 4) },
        { key: "intended_price", label: "Price", render: (v) => fmtNum(v, 2) },
        { key: "summary_text", label: "Summary" },
        { key: "reasons_json", label: "Reasons", render: (v) => compactReasons(v) },
      ],
      rows,
      "No decisions available",
    );
  }

  async function loadDecisions() {
    setStatus("decisionsStatus", "Loading decisions...");
    const audit = await fetchAudit();
    const filtered = filterDecisions(audit.decisions || []);
    renderDecisionsTable(filtered);
    setStatus("decisionsStatus", `${filtered.length} decisions shown`);
  }

  async function loadTransactions() {
    setStatus("transactionsStatus", "Loading transactions...");
    const data = await fetchTransactions();

    renderTable(
      "transactionsTable",
      [
        { key: "timestamp", label: "Timestamp", render: (v) => fmtDateTime(v) },
        { key: "id", label: "ID" },
        { key: "position_id", label: "Position" },
        { key: "decision_id", label: "Decision", render: (v) => escapeHtml(v ?? "-") },
        { key: "side", label: "Side" },
        { key: "qty", label: "Qty", render: (v) => fmtNum(v, 4) },
        { key: "price", label: "Price", render: (v) => fmtNum(v, 2) },
        { key: "mode", label: "Mode" },
      ],
      data.transactions || [],
      "No transactions for today",
    );

    setStatus("transactionsStatus", `${data.count || 0} transactions`);
  }

  function renderAuditTimeline(decisions) {
    const host = byId("auditTimeline");
    if (!host) return;

    if (!decisions.length) {
      host.innerHTML = `<div class="result-box">No justification entries for selected filter.</div>`;
      return;
    }

    const groups = new Map();
    decisions.forEach((row) => {
      const keyRaw = row.tick_time || row.created_at || "Unknown";
      const key = fmtDateTime(keyRaw);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    });

    const entries = [...groups.entries()];
    entries.sort((a, b) => Date.parse(b[0]) - Date.parse(a[0]));

    host.innerHTML = entries
      .map(([tickLabel, rows]) => {
        const lines = rows
          .map((row) => {
            const reasons = compactReasons(row.reasons_json);
            return `
              <li>
                <div class="timeline-line">
                  <span class="badge ${getBadgeClass(row.action)}">${escapeHtml(row.action)}</span>
                  <strong>${escapeHtml(row.symbol)}</strong>
                  <span class="muted">qty ${fmtNum(row.intended_qty, 4)} @ ${fmtNum(row.intended_price, 2)}</span>
                </div>
                <div class="timeline-line">
                  <span>${escapeHtml(row.summary_text || "-")}</span>
                </div>
                <div class="timeline-line">${reasons}</div>
              </li>
            `;
          })
          .join("");

        return `
          <div class="timeline-group">
            <div class="timeline-head">${escapeHtml(tickLabel)} (${rows.length} decisions)</div>
            <ul class="timeline-list">${lines}</ul>
          </div>
        `;
      })
      .join("");
  }

  async function loadAudit() {
    setStatus("auditStatus", "Loading audit timeline...");
    const audit = await fetchAudit();
    const filtered = filterDecisions(audit.decisions || []);
    renderAuditTimeline(filtered);
    setStatus("auditStatus", `${filtered.length} decisions shown`);
  }

  async function saveSchedule(event) {
    event.preventDefault();
    const payload = {
      mappings: [
        {
          weekday: Number(byId("scheduleWeekday")?.value || 0),
          sector_name: (byId("scheduleSector")?.value || "").trim(),
          active: Boolean(byId("scheduleActive")?.checked),
        },
      ],
    };

    if (!payload.mappings[0].sector_name) {
      toast("Sector name is required", "error");
      return;
    }

    setBusy("scheduleSaveBtn", true, "Saving...");
    try {
      const result = await apiCall("/api/sector/schedule", "POST", payload);
      const names = (result.mappings || []).map((x) => `${x.weekday}:${x.sector_name}`).join(", ");
      byId("scheduleResult").textContent = names || "Saved.";
      setStatus("sectorsStatus", "Schedule updated");
      toast("Schedule saved", "success");
    } catch (err) {
      toast(err.message || String(err), "error");
    } finally {
      setBusy("scheduleSaveBtn", false, "Saving...");
    }
  }

  function parseSymbols(raw) {
    if (!raw) return [];
    return [...new Set(raw.split(/[\s,]+/).map((x) => x.trim().toUpperCase()).filter(Boolean))];
  }

  async function saveUniverse(event) {
    event.preventDefault();
    const payload = {
      sector_name: (byId("universeSector")?.value || "").trim(),
      add_symbols: parseSymbols(byId("universeAdd")?.value || ""),
      remove_symbols: parseSymbols(byId("universeRemove")?.value || ""),
    };

    if (!payload.sector_name) {
      toast("Sector name is required", "error");
      return;
    }

    setBusy("universeSaveBtn", true, "Saving...");
    try {
      const result = await apiCall("/api/sector/universe", "POST", payload);
      byId("universeResult").innerHTML = `Active symbols (${result.count}): ${escapeHtml((result.active_symbols || []).join(", "))}`;
      setStatus("sectorsStatus", "Universe updated");
      toast("Universe updated", "success");
    } catch (err) {
      toast(err.message || String(err), "error");
    } finally {
      setBusy("universeSaveBtn", false, "Saving...");
    }
  }

  async function loadSectors() {
    setStatus("sectorsStatus", "Ready. Submit schedule or universe changes.");
  }

  function configPayloadFromForm() {
    return {
      active: true,
      set_active: true,
      mode: "INTRADAY",
      strategy_version: cache.settings?.strategy_version || "momentum_v1",
      sector: ((byId("cfgSector")?.value || "").trim() || null),
      budget_daily_inr: Number(byId("cfgBudget")?.value || 10000),
      max_positions: Number(byId("cfgMaxPositions")?.value || 2),
      monitor_interval_min: Number(byId("cfgInterval")?.value || 5),
      warmup_minutes: Number(byId("cfgWarmup")?.value || 20),
      max_entries_per_symbol_per_day: Number(byId("cfgMaxEntries")?.value || 1),
      target_pct: Number(byId("cfgTargetPct")?.value || 1.5),
      stop_pct: Number(byId("cfgStopPct")?.value || 1.0),
      time_exit_hhmm: (byId("cfgTimeExit")?.value || "15:20").trim(),
      rebalance_partial_threshold: Number(byId("cfgPartialThreshold")?.value || 15.0),
      rebalance_full_threshold: Number(byId("cfgFullThreshold")?.value || 20.0),
      rebalance_partial_fraction: Number(byId("cfgPartialFraction")?.value || 0.5),
      fill_model: (byId("cfgFillModel")?.value || "close").trim() || "close",
    };
  }

  function populateConfigForm(config) {
    byId("cfgSector").value = config.sector || "";
    byId("cfgBudget").value = config.budget_daily_inr;
    byId("cfgMaxPositions").value = config.max_positions;
    byId("cfgInterval").value = config.monitor_interval_min;
    byId("cfgWarmup").value = config.warmup_minutes;
    byId("cfgMaxEntries").value = config.max_entries_per_symbol_per_day;
    byId("cfgTargetPct").value = config.target_pct;
    byId("cfgStopPct").value = config.stop_pct;
    byId("cfgTimeExit").value = config.time_exit_hhmm;
    byId("cfgPartialThreshold").value = config.rebalance_partial_threshold;
    byId("cfgFullThreshold").value = config.rebalance_full_threshold;
    byId("cfgPartialFraction").value = config.rebalance_partial_fraction;
    byId("cfgFillModel").value = config.fill_model;
  }

  function renderSettingsSummary(config) {
    const box = byId("settingsSummary");
    if (!box) return;

    box.innerHTML = `
      <strong>Config #${escapeHtml(config.id)}</strong><br/>
      Mode: ${escapeHtml(config.mode)} | Version: ${escapeHtml(config.strategy_version)}<br/>
      Sector override: ${escapeHtml(config.sector || "(schedule)")}<br/>
      Budget: ${fmtMoney(config.budget_daily_inr)} | Max positions: ${escapeHtml(config.max_positions)}<br/>
      Monitor: ${escapeHtml(config.monitor_interval_min)}m | Entries/day: ${escapeHtml(config.max_entries_per_symbol_per_day)}<br/>
      Stop/Target: ${escapeHtml(config.stop_pct)}% / ${escapeHtml(config.target_pct)}% | Exit: ${escapeHtml(config.time_exit_hhmm)}
    `;
  }

  async function saveSettings(event) {
    event.preventDefault();
    setBusy("saveConfigBtn", true, "Saving...");
    try {
      const payload = configPayloadFromForm();
      const result = await apiCall("/api/config", "POST", payload);
      cache.settings = result;
      renderSettingsSummary(result);
      populateConfigForm(result);
      setStatus("settingsStatus", "Config saved");
      toast("Config saved", "success");
    } catch (err) {
      toast(err.message || String(err), "error");
    } finally {
      setBusy("saveConfigBtn", false, "Saving...");
    }
  }

  async function loadSettings() {
    setStatus("settingsStatus", "Loading active config...");
    const config = await fetchConfig();
    renderSettingsSummary(config);
    populateConfigForm(config);
    setStatus("settingsStatus", "Loaded active config");
  }

  function bindPageEvents() {
    if (page === "decisions") {
      byId("decisionsFilterBtn")?.addEventListener("click", () => loadDecisions().catch((err) => toast(err.message, "error")));
      byId("decisionsClearBtn")?.addEventListener("click", () => {
        byId("decisionsSymbolFilter").value = "";
        loadDecisions().catch((err) => toast(err.message, "error"));
      });
    }

    if (page === "audit") {
      byId("auditFilterBtn")?.addEventListener("click", () => loadAudit().catch((err) => toast(err.message, "error")));
      byId("auditClearBtn")?.addEventListener("click", () => {
        byId("auditSymbolFilter").value = "";
        loadAudit().catch((err) => toast(err.message, "error"));
      });
    }

    if (page === "sectors") {
      byId("scheduleForm")?.addEventListener("submit", saveSchedule);
      byId("universeForm")?.addEventListener("submit", saveUniverse);
    }

    if (page === "settings") {
      byId("settingsForm")?.addEventListener("submit", saveSettings);
    }
  }

  async function refreshPage() {
    switch (page) {
      case "dashboard":
        await loadDashboard();
        break;
      case "plan":
        await loadPlan();
        break;
      case "positions":
        await loadPositions();
        break;
      case "decisions":
        await loadDecisions();
        break;
      case "transactions":
        await loadTransactions();
        break;
      case "audit":
        await loadAudit();
        break;
      case "sectors":
        await loadSectors();
        break;
      case "settings":
        await loadSettings();
        break;
      default:
        break;
    }
  }

  function actionPayload(includeInterval = false) {
    const payload = {};
    const date = getActionDate();
    if (date) payload.date = date;
    if (includeInterval) payload.interval_min = getActionInterval();
    return payload;
  }

  async function runAction(buttonId, busyText, fn, successMessage, refreshAfter = true) {
    setBusy(buttonId, true, busyText);
    try {
      const result = await fn();
      toast(typeof successMessage === "function" ? successMessage(result) : successMessage, "success");
      if (refreshAfter) {
        await refreshPage();
      }
    } catch (err) {
      toast(err.message || String(err), "error");
    } finally {
      setBusy(buttonId, false, busyText);
    }
  }

  function bindGlobalActions() {
    byId("actionRefresh")?.addEventListener("click", () => {
      runAction("actionRefresh", "Refreshing...", () => refreshPage(), "Refreshed", false);
    });

    byId("actionPlanDay")?.addEventListener("click", () => {
      runAction(
        "actionPlanDay",
        "Planning...",
        () => apiCall("/api/plan/day", "POST", { ...actionPayload(false), force_replan: false }),
        (r) => `Plan ready for ${r.date}`,
      );
    });

    byId("actionRunTick")?.addEventListener("click", () => {
      runAction(
        "actionRunTick",
        "Running...",
        () => apiCall("/api/run/tick", "POST", actionPayload(true), 180000),
        (r) => (r.skipped_weekend ? `Skipped weekend ${r.date}` : `Tick done (buys ${r.buys}, sells ${r.sells})`),
      );
    });

    byId("actionExitDay")?.addEventListener("click", () => {
      runAction(
        "actionExitDay",
        "Exiting...",
        () => apiCall("/api/exit/day", "POST", actionPayload(false), 120000),
        (r) => (r.skipped_weekend ? `Skipped weekend ${r.date}` : `Closed ${r.closed_positions} positions`),
      );
    });
  }

  function initializeActionDefaults() {
    const dateInput = byId("globalDate");
    if (dateInput && !dateInput.value) {
      dateInput.value = todayInputValue();
    }

    if (cache.settings?.monitor_interval_min && byId("globalInterval")) {
      byId("globalInterval").value = cache.settings.monitor_interval_min;
    }
  }

  async function boot() {
    attachThemeControls();
    attachSidebarToggle();
    bindGlobalActions();
    bindPageEvents();
    initializeActionDefaults();

    try {
      // Preload config for globally useful defaults.
      await fetchConfig();
      initializeActionDefaults();
    } catch (_err) {
      // Keep pages usable if config fetch fails.
    }

    await refreshPage();
  }

  boot().catch((err) => {
    toast(err.message || "UI initialization failed", "error");
  });
})();
