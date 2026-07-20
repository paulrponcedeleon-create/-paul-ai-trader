const qs = selector => document.querySelector(selector);
const HISTORY_PAGE_SIZE = 20;
const POSITION_REFRESH_MS = 1000;

let selectedBook = document.querySelector(".book.active")?.dataset.book || "btc_mxn";
let marketRequestId = 0;
let historyOffset = 0;
let historyLoading = false;
let positionsLoading = false;

async function api(url, options={}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: {"Content-Type":"application/json", ...(options.headers||{})},
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

document.querySelectorAll(".book").forEach(btn => btn.addEventListener("click", async () => {
  document.querySelectorAll(".book").forEach(x=>x.classList.remove("active"));
  btn.classList.add("active");
  selectedBook = btn.dataset.book;
  qs("#orderBook").value = selectedBook;
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
  qs("#statusText").textContent = "Consultando...";
  qs("#marketResult").innerHTML = `<p>Actualizando ${requestedBook.toUpperCase()}...</p>`;
  try {
    const data = await api(`/api/market/${requestedBook}`);
    if (requestId !== marketRequestId) return;
    const signal = data.signal;
    qs("#marketResult").innerHTML = `
      <div class="signal ${signal.action}">${signal.action.toUpperCase()}</div>
      <p><strong>Precio:</strong> $${Number(signal.reference_price).toLocaleString("es-MX")}</p>
      <p><strong>Confianza:</strong> ${signal.confidence}%</p>
      <p>${signal.reason}</p>`;
    qs("#statusText").textContent = "Actualizado";
  } catch(error) {
    if (requestId !== marketRequestId) return;
    qs("#marketResult").innerHTML = `<p class="error">${error.message}</p>`;
    qs("#statusText").textContent = "Error";
  }
}

qs("#refreshBtn")?.addEventListener("click", refreshMarket);

function renderPosition(position) {
  const pnl = Number(position.unrealized_pnl_mxn || 0);
  const sideLabel = position.side === "buy" ? "COMPRA" : "VENTA CORTA";
  return `
    <article class="position-item">
      <div class="position-head">
        <div>
          <span class="position-book">${position.book.toUpperCase()}</span>
          <small>${sideLabel} · ${new Date(position.created_at).toLocaleString("es-MX")}</small>
        </div>
        <span class="position-status">ABIERTA</span>
      </div>
      <div class="position-values">
        <div><span>Invertido</span><strong>${formatMoney(position.amount_mxn)}</strong></div>
        <div><span>Valor actual</span><strong>${formatMoney(position.current_value_mxn)}</strong></div>
        <div><span>Precio entrada</span><strong>$${formatPrice(position.entry_price)}</strong></div>
        <div><span>Precio actual</span><strong>$${formatPrice(position.current_price)}</strong></div>
      </div>
      <div class="position-result ${pnlClass(pnl)}">
        <span>Ganancia / pérdida</span>
        <strong>${signedMoney(pnl)}</strong>
        <small>${signedPercent(position.return_pct)}</small>
      </div>
      <button type="button" class="secondary close-position" data-close-id="${position.id}">Cerrar simulación</button>
    </article>`;
}

function updatePortfolioSummary(summary) {
  qs("#totalInvested").textContent = formatMoney(summary.invested_mxn);
  qs("#totalCurrentValue").textContent = formatMoney(summary.current_value_mxn);
  qs("#totalPnl").textContent = signedMoney(summary.unrealized_pnl_mxn);
  qs("#totalReturn").textContent = signedPercent(summary.return_pct);
  qs("#totalPnl").className = pnlClass(summary.unrealized_pnl_mxn);
  qs("#totalReturn").className = pnlClass(summary.unrealized_pnl_mxn);
}

async function loadPositions() {
  if (positionsLoading || document.hidden) return;
  positionsLoading = true;
  try {
    const data = await api("/api/positions");
    updatePortfolioSummary(data.summary);
    qs("#openPositions").innerHTML = data.items.length
      ? data.items.map(renderPosition).join("")
      : "<p>No hay posiciones abiertas.</p>";
    qs("#positionsUpdated").textContent = `Actualizado ${new Date(data.updated_at).toLocaleTimeString("es-MX")}`;
  } catch(error) {
    qs("#positionsUpdated").textContent = `Error: ${error.message}`;
  } finally {
    positionsLoading = false;
  }
}

qs("#openPositions")?.addEventListener("click", async event => {
  const button = event.target.closest("[data-close-id]");
  if (!button) return;
  if (!window.confirm("¿Cerrar esta simulación con el precio actual de Bitso?")) return;

  button.disabled = true;
  button.textContent = "Cerrando...";
  try {
    const closed = await api(`/api/simulations/${button.dataset.closeId}/close`, {method:"POST"});
    qs("#orderMessage").textContent = `Simulación cerrada: ${signedMoney(closed.realized_pnl_mxn)} (${signedPercent(closed.return_pct)})`;
    await Promise.all([loadPositions(), loadHistory({reset:true})]);
  } catch(error) {
    button.disabled = false;
    button.textContent = "Cerrar simulación";
    qs("#orderMessage").textContent = error.message;
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
    qs("#orderMessage").textContent = `Posición abierta en ${data.book.toUpperCase()} a $${formatPrice(data.reference_price)}.`;
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
      : `<br><small class="${pnlClass(item.realized_pnl_mxn)}">Resultado: ${signedMoney(item.realized_pnl_mxn)}</small>`;
    return `
      <div class="history-item">
        <div><strong>${item.book.toUpperCase()}</strong><br><small>${item.side.toUpperCase()} · ${statusLabel}</small></div>
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
    const data = await api(`/api/simulations?limit=${HISTORY_PAGE_SIZE}&offset=${offset}`);
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
  if (!document.hidden) loadPositions();
});

if (!qs("#appContent")?.classList.contains("hidden")) {
  loadHistory({reset:true});
  loadPositions();
  refreshMarket();
  window.setInterval(loadPositions, POSITION_REFRESH_MS);
}
