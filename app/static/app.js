const qs = selector => document.querySelector(selector);
const HISTORY_PAGE_SIZE = 5;
const POSITION_REFRESH_MS = 5000;

let selectedBook = document.querySelector(".book.active")?.dataset.book || "btc_mxn";
let marketRequestId = 0;
let historyOffset = 0;
let historyLoading = false;
let positionsLoading = false;
let positionRefreshTimer = null;
let pendingCloseId = null;
const currentPositions = new Map();

async function api(url, options={}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      "Content-Type":"application/json",
      "Cache-Control":"no-cache",
      "Pragma":"no-cache",
      ...(options.headers||{})
    },
    ...options
  });
  const data = await response.json().catch(()=>({detail:"Respuesta inválida"}));
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

function formatPrice(value) {
  return Number(value || 0).toLocaleString("es-MX", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function signedMoney(value) {
  const number = Number(value || 0);
  const prefix = number > 0 ? "+" : "";
  return `${prefix}${formatMoney(number)}`;
}

function signedPercent(value) {
  const number = Number(value || 0);
  const prefix = number > 0 ? "+" : "";
  return `${prefix}${number.toFixed(2)}%`;
}

function pnlClass(value) {
  const number = Number(value || 0);
  if (number > 0) return "positive";
  if (number < 0) return "negative";
  return "neutral";
}

function assetSymbol(book, provided=null) {
  if (provided) return provided;
  if (typeof window.displayMarketSymbol === "function") return window.displayMarketSymbol(book);
  return String(book || "").replace(/_mxn$|_cash$/i, "").toUpperCase();
}

function assetName(book, provided=null) {
  if (provided) return provided;
  if (typeof window.displayMarketName === "function") return window.displayMarketName(book);
  return assetSymbol(book);
}

function setText(element, text, {pulse=false, className=null}={}) {
  if (!element) return;
  const changed = element.textContent !== text;
  if (changed) element.textContent = text;
  if (className !== null) element.className = className;
  if (changed && pulse) {
    element.classList.remove("value-refresh");
    void element.offsetWidth;
    element.classList.add("value-refresh");
  }
}

document.querySelectorAll(".book").forEach(btn => btn.addEventListener("click", async () => {
  document.querySelectorAll(".book").forEach(x=>x.classList.remove("active"));
  btn.classList.add("active");
  selectedBook = btn.dataset.book;
  const option = qs(`#orderBook option[value="${selectedBook}"]`);
  if (option) qs("#orderBook").value = selectedBook;
  await refreshMarket();
}));

qs("#loginForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await api("/api/login", {method:"POST", body:JSON.stringify({password:qs("#password").value})});
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
    await api("/api/logout", {method:"POST"});
    location.reload();
  } catch(error) {
    button.disabled = false;
    button.textContent = "Cerrar sesión";
    qs("#statusText").textContent = error.message;
  }
});

async function refreshMarket() {
  const requestId = ++marketRequestId;
  const requestedBook = selectedBook;
  const symbol = assetSymbol(requestedBook);
  qs("#statusText").textContent = "Consultando...";
  qs("#marketResult").innerHTML = `<p>Actualizando ${symbol}...</p>`;
  try {
    const data = await api(`/api/market/${requestedBook}?ts=${Date.now()}`);
    if (requestId !== marketRequestId) return;
    const signal = data.signal;
    const ticker = data.ticker || {};
    const actionLabel = {buy:"COMPRAR", hold:"MANTENER", sell:"VENDER"}[signal.action] || signal.action.toUpperCase();
    const fee = ticker.effective_fee_percent == null
      ? "No disponible"
      : `${Number(ticker.effective_fee_percent).toFixed(3)}%`;
    const route = ticker.route?.length ? ticker.route.map(value => value.toUpperCase()).join(" → ") : "Sin conversión";
    qs("#marketResult").innerHTML = `
      <div class="signal ${signal.action}">${actionLabel}</div>
      <p><strong>${ticker.name || assetName(requestedBook)}:</strong> ${formatMoney(signal.reference_price)}</p>
      <p><strong>Confianza:</strong> ${signal.confidence}%</p>
      <p><strong>Comisión estimada de entrada:</strong> ${fee}</p>
      <p><strong>Ruta:</strong> ${route}</p>
      <p>${signal.reason}</p>`;
    qs("#statusText").textContent = ticker.delayed ? "Referencia retrasada" : "Actualizado";
  } catch(error) {
    if (requestId !== marketRequestId) return;
    qs("#marketResult").innerHTML = `<p class="error">${error.message}</p>`;
    qs("#statusText").textContent = "Error";
  }
}

qs("#refreshBtn")?.addEventListener("click", refreshMarket);

function createPositionElement(position) {
  const article = document.createElement("article");
  article.className = "position-row";
  article.dataset.positionId = position.id;
  article.innerHTML = `
    <button type="button" class="position-summary" data-toggle-position="${position.id}" aria-expanded="false">
      <div class="position-identity">
        <strong data-field="book"></strong>
        <small data-field="meta"></small>
      </div>
      <div class="compact-value">
        <span>Invertido</span><strong data-field="amount"></strong>
      </div>
      <div class="compact-value">
        <span>Valor neto</span><strong data-field="currentValue"></strong>
      </div>
      <div class="compact-result">
        <strong data-field="pnl"></strong><small data-field="returnPct"></small>
      </div>
      <span class="position-chevron" aria-hidden="true">⌄</span>
    </button>
    <div class="position-details hidden">
      <div class="position-values">
        <div><span>Precio entrada</span><strong data-field="entryPrice"></strong></div>
        <div><span>Precio actual</span><strong data-field="currentPrice"></strong></div>
        <div><span>Cantidad virtual</span><strong data-field="quantity"></strong></div>
        <div><span>Comisión entrada</span><strong data-field="entryFee"></strong><small data-field="entryFeePct"></small></div>
        <div><span>Salida estimada</span><strong data-field="exitFee"></strong><small data-field="exitFeePct"></small></div>
        <div><span>Precio de equilibrio</span><strong data-field="breakEven"></strong><small data-field="breakEvenPct"></small></div>
      </div>
      <button type="button" class="secondary close-position" data-close-id="${position.id}">Cerrar posición</button>
    </div>`;
  return article;
}

function updatePositionElement(article, position) {
  const pnl = Number(position.unrealized_pnl_mxn || 0);
  const sideLabel = position.side === "buy" ? "COMPRA" : "VENTA CORTA";
  const symbol = assetSymbol(position.book, position.symbol);
  const name = assetName(position.book, position.name);
  setText(article.querySelector('[data-field="book"]'), `${symbol} · ${name}`);
  setText(article.querySelector('[data-field="meta"]'), `${sideLabel} · ${new Date(position.created_at).toLocaleString("es-MX")}`);
  setText(article.querySelector('[data-field="amount"]'), formatMoney(position.amount_mxn));
  setText(article.querySelector('[data-field="currentValue"]'), formatMoney(position.current_value_mxn), {pulse:true});
  setText(article.querySelector('[data-field="pnl"]'), signedMoney(pnl), {pulse:true, className:pnlClass(pnl)});
  setText(article.querySelector('[data-field="returnPct"]'), signedPercent(position.return_pct), {pulse:true, className:pnlClass(pnl)});
  setText(article.querySelector('[data-field="entryPrice"]'), formatMoney(position.entry_price));
  setText(article.querySelector('[data-field="currentPrice"]'), formatMoney(position.current_price), {pulse:true});
  setText(article.querySelector('[data-field="quantity"]'), Number(position.asset_quantity || 0).toLocaleString("es-MX", {maximumFractionDigits:12}));
  setText(article.querySelector('[data-field="entryFee"]'), formatMoney(position.entry_fee_mxn));
  setText(article.querySelector('[data-field="entryFeePct"]'), `${Number(position.entry_fee_percent).toFixed(3)}%`);
  setText(article.querySelector('[data-field="exitFee"]'), formatMoney(position.estimated_exit_fee_mxn), {pulse:true});
  setText(article.querySelector('[data-field="exitFeePct"]'), `${Number(position.exit_fee_percent).toFixed(3)}%`);
  setText(article.querySelector('[data-field="breakEven"]'), formatMoney(position.break_even_price));
  setText(article.querySelector('[data-field="breakEvenPct"]'), signedPercent(position.break_even_change_pct));
}

function syncPositions(items) {
  const container = qs("#openPositions");
  const incomingIds = new Set(items.map(item => item.id));

  container.querySelectorAll("[data-position-id]").forEach(element => {
    if (!incomingIds.has(element.dataset.positionId)) element.remove();
  });

  if (!items.length) {
    currentPositions.clear();
    container.innerHTML = "<p>No hay posiciones abiertas.</p>";
    return;
  }

  container.querySelector("p")?.remove();
  items.forEach(position => {
    currentPositions.set(position.id, position);
    let article = container.querySelector(`[data-position-id="${position.id}"]`);
    if (!article) article = createPositionElement(position);
    updatePositionElement(article, position);
    container.appendChild(article);
  });

  [...currentPositions.keys()].forEach(id => {
    if (!incomingIds.has(id)) currentPositions.delete(id);
  });
}

function updatePortfolioSummary(summary) {
  setText(qs("#openPositionCount"), String(summary.open_positions));
  setText(qs("#totalInvested"), formatMoney(summary.invested_mxn));
  setText(qs("#totalCurrentValue"), formatMoney(summary.current_value_mxn), {pulse:true});
  setText(qs("#totalPnl"), signedMoney(summary.unrealized_pnl_mxn), {pulse:true, className:pnlClass(summary.unrealized_pnl_mxn)});
  setText(qs("#totalReturn"), signedPercent(summary.return_pct), {pulse:true, className:pnlClass(summary.unrealized_pnl_mxn)});
  setText(qs("#totalFees"), formatMoney(summary.estimated_fees_mxn), {pulse:true});
}

async function loadPositions() {
  if (positionsLoading || document.hidden) return;
  positionsLoading = true;
  try {
    const data = await api(`/api/positions?ts=${Date.now()}`);
    updatePortfolioSummary(data.summary);
    syncPositions(data.items);
    const sourceLabels = {
      bitso_account: "comisiones de tu cuenta",
      public_fallback: "comisiones públicas de respaldo",
      bitso_stock_zero_fee: "acciones 0% de comisión",
      mixed: "comisiones según cada activo",
      none: "sin comisiones"
    };
    const source = sourceLabels[data.fee_source] || "comisiones según cada activo";
    qs("#positionsUpdated").textContent = `Actualizado ${new Date(data.updated_at).toLocaleTimeString("es-MX")} · ${source}`;
  } catch(error) {
    qs("#positionsUpdated").textContent = `Error: ${error.message}`;
  } finally {
    positionsLoading = false;
  }
}

async function runPositionRefreshLoop() {
  window.clearTimeout(positionRefreshTimer);
  await loadPositions();
  positionRefreshTimer = window.setTimeout(runPositionRefreshLoop, POSITION_REFRESH_MS);
}

function togglePosition(id) {
  const article = qs(`[data-position-id="${id}"]`);
  if (!article) return;
  const summary = article.querySelector(".position-summary");
  const details = article.querySelector(".position-details");
  const expanded = summary.getAttribute("aria-expanded") === "true";
  summary.setAttribute("aria-expanded", String(!expanded));
  details.classList.toggle("hidden", expanded);
  article.classList.toggle("expanded", !expanded);
}

function openCloseDialog(id) {
  const position = currentPositions.get(id);
  if (!position) return;
  pendingCloseId = id;
  const pnl = Number(position.unrealized_pnl_mxn || 0);
  setText(qs("#closeDialogBook"), `Cerrar ${assetSymbol(position.book, position.symbol)}`);
  setText(qs("#closeDialogValue"), formatMoney(position.current_value_mxn));
  setText(qs("#closeDialogPnl"), signedMoney(pnl), {className:pnlClass(pnl)});
  setText(qs("#closeDialogReturn"), signedPercent(position.return_pct), {className:pnlClass(pnl)});
  setText(qs("#closeDialogFee"), formatMoney(position.estimated_exit_fee_mxn));
  setText(qs("#closeDialogPrice"), formatMoney(position.current_price));
  qs("#closePositionDialog").showModal();
}

qs("#openPositions")?.addEventListener("click", event => {
  const closeButton = event.target.closest("[data-close-id]");
  if (closeButton) {
    openCloseDialog(closeButton.dataset.closeId);
    return;
  }
  const toggleButton = event.target.closest("[data-toggle-position]");
  if (toggleButton) togglePosition(toggleButton.dataset.togglePosition);
});

qs("#closePositionDialog")?.addEventListener("close", () => {
  if (qs("#closePositionDialog").returnValue === "cancel") pendingCloseId = null;
});

qs("#confirmClosePosition")?.addEventListener("click", async () => {
  if (!pendingCloseId) return;
  const button = qs("#confirmClosePosition");
  button.disabled = true;
  button.textContent = "Cerrando...";
  try {
    const closed = await api(`/api/simulations/${pendingCloseId}/close`, {method:"POST"});
    qs("#closePositionDialog").close();
    qs("#orderMessage").textContent = `Posición cerrada: ${signedMoney(closed.realized_pnl_mxn)} (${signedPercent(closed.return_pct)}), comisiones ${formatMoney(closed.total_estimated_fees_mxn)}.`;
    pendingCloseId = null;
    await Promise.all([loadPositions(), loadHistory({reset:true})]);
  } catch(error) {
    qs("#orderMessage").textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Cerrar posición";
  }
});

qs("#orderForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  submitButton.textContent = "Abriendo...";
  try {
    const data = await api("/api/orders", {
      method:"POST",
      body:JSON.stringify({
        book:qs("#orderBook").value,
        side:qs("#orderSide").value,
        amount_mxn:Number(qs("#orderAmount").value),
        daily_pnl_mxn:0,
        open_orders:0
      })
    });
    qs("#orderMessage").textContent = `Posición abierta en ${assetSymbol(data.book, data.symbol)} a ${formatMoney(data.reference_price)}. Comisión de entrada: ${formatMoney(data.entry_fee_mxn)}.`;
    await Promise.all([loadPositions(), loadHistory({reset:true})]);
  } catch(error) {
    qs("#orderMessage").textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Abrir simulación";
  }
});

function renderHistoryItems(items) {
  return items.map(item => {
    const statusLabel = item.status === "open" ? "ABIERTA" : item.status === "closed" ? "CERRADA" : "REGISTRO";
    const result = item.realized_pnl_mxn == null
      ? ""
      : `<br><small class="${pnlClass(item.realized_pnl_mxn)}">Resultado neto: ${signedMoney(item.realized_pnl_mxn)}</small>`;
    return `
      <div class="history-item">
        <div><strong>${assetSymbol(item.book)}</strong><br><small>${item.side.toUpperCase()} · ${statusLabel}</small></div>
        <div><strong>${formatMoney(item.amount_mxn)}</strong><br><small>${new Date(item.created_at).toLocaleString("es-MX")}</small>${result}</div>
      </div>`;
  }).join("");
}

async function loadHistory({reset=false}={}) {
  if (historyLoading) return;

  const offset = reset ? 0 : historyOffset;
  const button = qs("#loadMoreBtn");
  historyLoading = true;
  button.disabled = true;
  button.textContent = "Cargando...";

  try {
    const data = await api(`/api/simulations?limit=${HISTORY_PAGE_SIZE}&offset=${offset}&ts=${Date.now()}`);
    const markup = renderHistoryItems(data.items);

    if (reset) {
      qs("#history").innerHTML = markup || "<p>Sin operaciones todavía.</p>";
    } else if (markup) {
      qs("#history").insertAdjacentHTML("beforeend", markup);
    }

    const shown = offset + data.items.length;
    historyOffset = data.next_offset ?? shown;
    qs("#historyMeta").textContent = data.total ? `Mostrando ${shown} de ${data.total}` : "";
    button.classList.toggle("hidden", !data.has_more);
  } catch(error) {
    if (reset) qs("#history").innerHTML = `<p class="error">${error.message}</p>`;
    else qs("#historyMeta").textContent = error.message;
  } finally {
    historyLoading = false;
    button.disabled = false;
    button.textContent = "Cargar más";
  }
}

qs("#loadMoreBtn")?.addEventListener("click", () => loadHistory());

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) runPositionRefreshLoop();
});

if (!qs("#appContent")?.classList.contains("hidden")) {
  loadHistory({reset:true});
  refreshMarket();
  runPositionRefreshLoop();
}
