const qs = selector => document.querySelector(selector);
const qsa = selector => [...document.querySelectorAll(selector)];

async function api(url, options={}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
      "Pragma": "no-cache",
      ...(options.headers || {})
    },
    ...options
  });
  const data = await response.json().catch(() => ({detail: "Respuesta inválida"}));
  if (!response.ok) throw new Error(data.detail || "Error");
  return data;
}

function formatMoney(value) {
  return Number(value || 0).toLocaleString("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function signedMoney(value) {
  const number = Number(value || 0);
  return `${number > 0 ? "+" : ""}${formatMoney(number)}`;
}

function signedPercent(value) {
  const number = Number(value || 0);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function pnlClass(value) {
  const number = Number(value || 0);
  if (number > 0) return "positive";
  if (number < 0) return "negative";
  return "neutral";
}

function setMetric(id, value, classValue=null) {
  const element = qs(`#${id}`);
  element.textContent = value;
  if (classValue !== null) element.className = pnlClass(classValue);
}

qs("#loginForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify({password: qs("#password").value})
    });
    location.reload();
  } catch(error) {
    qs("#loginError").textContent = error.message;
  }
});

qs("#logoutBtn")?.addEventListener("click", async () => {
  const button = qs("#logoutBtn");
  button.disabled = true;
  button.textContent = "Saliendo...";
  try {
    await api("/api/logout", {method: "POST"});
    location.reload();
  } catch(error) {
    button.disabled = false;
    button.textContent = "Cerrar sesión";
    qs("#performanceUpdated").textContent = error.message;
  }
});

function updateCustomDateVisibility() {
  const custom = qs("#periodFilter")?.value === "custom";
  qsa("[data-custom-date]").forEach(element => element.classList.toggle("hidden", !custom));
}

function setDefaultDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 29);
  qs("#startDate").value = start.toISOString().slice(0, 10);
  qs("#endDate").value = end.toISOString().slice(0, 10);
}

function selectedBooks() {
  return qsa('input[name="performanceBook"]:checked').map(input => input.value);
}

function buildPerformanceUrl() {
  const period = qs("#periodFilter").value;
  const params = new URLSearchParams({period, ts: Date.now().toString()});
  const books = selectedBooks();
  if (books.length) params.set("books", books.join(","));
  if (period === "custom") {
    params.set("start", qs("#startDate").value);
    params.set("end", qs("#endDate").value);
  }
  return `/api/performance?${params.toString()}`;
}

function renderSummary(summary) {
  setMetric("grossPnl", signedMoney(summary.gross_pnl_mxn), summary.gross_pnl_mxn);
  setMetric("performanceFees", formatMoney(summary.fees_mxn));
  setMetric("netPnl", signedMoney(summary.net_pnl_mxn), summary.net_pnl_mxn);
  setMetric("netReturn", signedPercent(summary.return_pct), summary.net_pnl_mxn);
  setMetric("closedOperations", String(summary.closed_operations));
  setMetric("winsLosses", `${summary.wins} ganadas · ${summary.losses} perdidas`);
  setMetric("winRate", `${Number(summary.win_rate_pct).toFixed(2)}%`);
  setMetric("bestTrade", signedMoney(summary.best_trade_mxn), summary.best_trade_mxn);
  setMetric("worstTrade", `Peor: ${signedMoney(summary.worst_trade_mxn)}`, summary.worst_trade_mxn);
}

function renderDailyChart(rows) {
  const container = qs("#dailyChart");
  if (!rows.length) {
    container.className = "bar-chart empty-chart";
    container.textContent = "Sin operaciones cerradas en el periodo.";
    return;
  }

  const maxAbsolute = Math.max(...rows.map(row => Math.abs(Number(row.net_pnl_mxn))), 0.01);
  container.className = "bar-chart";
  container.innerHTML = rows.map(row => {
    const value = Number(row.net_pnl_mxn);
    const height = Math.max(6, Math.round(Math.abs(value) / maxAbsolute * 110));
    const date = new Date(`${row.date}T12:00:00`).toLocaleDateString("es-MX", {day: "2-digit", month: "short"});
    return `
      <div class="bar-column" title="${row.date}: ${signedMoney(value)}">
        <div class="bar-value ${pnlClass(value)}">${signedMoney(value)}</div>
        <div class="bar-track">
          <span class="chart-bar ${value >= 0 ? "bar-positive" : "bar-negative"}" style="height:${height}px"></span>
        </div>
        <small>${date}</small>
      </div>`;
  }).join("");
}

function renderCumulativeChart(rows) {
  const container = qs("#cumulativeChart");
  if (!rows.length) {
    container.className = "line-chart empty-chart";
    container.textContent = "Sin operaciones cerradas en el periodo.";
    return;
  }

  const values = rows.map(row => Number(row.cumulative_net_pnl_mxn));
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const range = maximum - minimum || 1;
  const width = 640;
  const height = 220;
  const padding = 28;
  const drawableWidth = width - padding * 2;
  const drawableHeight = height - padding * 2;
  const points = values.map((value, index) => {
    const x = padding + (values.length === 1 ? drawableWidth / 2 : index / (values.length - 1) * drawableWidth);
    const y = padding + (maximum - value) / range * drawableHeight;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const zeroY = padding + (maximum - 0) / range * drawableHeight;
  const finalValue = values.at(-1);
  const firstDate = new Date(`${rows[0].date}T12:00:00`).toLocaleDateString("es-MX", {day: "2-digit", month: "short"});
  const lastDate = new Date(`${rows.at(-1).date}T12:00:00`).toLocaleDateString("es-MX", {day: "2-digit", month: "short"});

  container.className = `line-chart ${pnlClass(finalValue)}`;
  container.innerHTML = `
    <div class="line-chart-total ${pnlClass(finalValue)}">${signedMoney(finalValue)}</div>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Ganancia neta acumulada">
      <line class="zero-line" x1="${padding}" y1="${zeroY}" x2="${width - padding}" y2="${zeroY}"></line>
      <polyline class="cumulative-line" points="${points}"></polyline>
      ${points.split(" ").map(point => {
        const [x, y] = point.split(",");
        return `<circle class="line-point" cx="${x}" cy="${y}" r="3"></circle>`;
      }).join("")}
    </svg>
    <div class="chart-axis"><small>${firstDate}</small><small>${lastDate}</small></div>`;
}

function renderBookPerformance(rows) {
  const body = qs("#bookPerformance");
  body.innerHTML = rows.length ? rows.map(row => `
    <tr>
      <td><strong>${row.book.toUpperCase()}</strong></td>
      <td>${row.operations}</td>
      <td>${row.wins}</td>
      <td class="${pnlClass(row.gross_pnl_mxn)}">${signedMoney(row.gross_pnl_mxn)}</td>
      <td>${formatMoney(row.fees_mxn)}</td>
      <td class="${pnlClass(row.net_pnl_mxn)}"><strong>${signedMoney(row.net_pnl_mxn)}</strong></td>
      <td class="${pnlClass(row.net_pnl_mxn)}">${signedPercent(row.return_pct)}</td>
    </tr>`).join("") : '<tr><td colspan="7">Sin resultados.</td></tr>';
}

function renderOperations(rows) {
  const body = qs("#performanceOperations");
  body.innerHTML = rows.length ? rows.map(row => `
    <tr>
      <td>${new Date(row.closed_at).toLocaleString("es-MX")}</td>
      <td><strong>${row.book.toUpperCase()}</strong></td>
      <td>${row.side === "buy" ? "Compra" : "Venta corta"}</td>
      <td>${formatMoney(row.amount_mxn)}</td>
      <td class="${pnlClass(row.gross_pnl_mxn)}">${signedMoney(row.gross_pnl_mxn)}</td>
      <td>${formatMoney(row.fees_mxn)}</td>
      <td class="${pnlClass(row.net_pnl_mxn)}"><strong>${signedMoney(row.net_pnl_mxn)}</strong></td>
      <td class="${pnlClass(row.net_pnl_mxn)}">${signedPercent(row.return_pct)}</td>
    </tr>`).join("") : '<tr><td colspan="8">Sin operaciones cerradas.</td></tr>';
}

async function loadPerformance() {
  const button = qs(".apply-filters");
  const books = selectedBooks();
  if (!books.length) {
    qs("#filterMessage").textContent = "Selecciona al menos una criptomoneda.";
    return;
  }

  qs("#filterMessage").textContent = "";
  button.disabled = true;
  button.textContent = "Calculando...";
  qs("#performanceUpdated").textContent = "Consultando resultados...";
  try {
    const data = await api(buildPerformanceUrl());
    renderSummary(data.summary);
    renderDailyChart(data.daily);
    renderCumulativeChart(data.daily);
    renderBookPerformance(data.by_book);
    renderOperations(data.operations);
    qs("#performancePeriodLabel").textContent = data.period_label;
    qs("#performanceUpdated").textContent = `Actualizado ${new Date(data.updated_at).toLocaleTimeString("es-MX")}`;
  } catch(error) {
    qs("#filterMessage").textContent = error.message;
    qs("#performanceUpdated").textContent = "Error";
  } finally {
    button.disabled = false;
    button.textContent = "Aplicar filtros";
  }
}

qs("#periodFilter")?.addEventListener("change", updateCustomDateVisibility);
qs("#selectAllBooks")?.addEventListener("click", () => qsa('input[name="performanceBook"]').forEach(input => { input.checked = true; }));
qs("#clearBooks")?.addEventListener("click", () => qsa('input[name="performanceBook"]').forEach(input => { input.checked = false; }));
qs("#performanceFilters")?.addEventListener("submit", event => {
  event.preventDefault();
  loadPerformance();
});

if (!qs("#performanceContent")?.classList.contains("hidden")) {
  setDefaultDates();
  updateCustomDateVisibility();
  loadPerformance();
}
