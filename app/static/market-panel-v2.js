(() => {
  const grid = document.querySelector("#marketGridV2");
  const filters = document.querySelector("#marketFiltersV2");
  const status = document.querySelector("#marketCatalogStatusV2");
  const orderBook = document.querySelector("#orderBook");
  if (!grid) return;

  const actionLabels = {buy: "COMPRAR", hold: "MANTENER", sell: "VENDER SI TIENES"};
  const CACHE_KEY = "paul-market-card-cache-v3";
  const REQUEST_TIMEOUT_MS = 5000;
  let typeFilter = "all";
  let signalFilter = "all";
  let loadedCount = 0;
  let failedCount = 0;

  const sellFilter = filters?.querySelector('[data-signal-filter="sell"]');
  if (sellFilter) sellFilter.textContent = "Vender si tienes";

  const sideSelect = document.querySelector("#orderSide");
  if (sideSelect) {
    sideSelect.value = "buy";
    const label = sideSelect.closest("label");
    if (label) label.hidden = true;
  }
  const orderTitle = document.querySelector("#orderForm")?.previousElementSibling;
  if (orderTitle?.tagName === "H2") orderTitle.textContent = "Abrir compra simulada";
  const orderButton = document.querySelector('#orderForm button[type="submit"]');
  if (orderButton) orderButton.textContent = "Comprar en simulación";

  const cards = [...grid.querySelectorAll("[data-book]")];
  const catalog = new Map(cards.map(card => {
    const book = card.dataset.book;
    const symbol = card.querySelector(".market-symbol")?.textContent?.trim() || book.toUpperCase();
    const name = card.querySelector(".market-card-head small")?.textContent?.trim() || symbol;
    const assetType = ["algn_mxn", "tsla_mxn", "aapl_mxn"].includes(book)
      ? "stock"
      : book === "mxn_cash" ? "cash" : "market";
    return [book, {book, symbol, name, asset_type: assetType, signal: {action: "hold"}}];
  }));

  function money(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "Sin precio";
    return Number(value).toLocaleString("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function feeLabel(item) {
    if (item.fee_included_in_quote) return "Costo incluido en cotización Bitso";
    const fee = item.effective_fee_percent;
    if (fee === null || fee === undefined) return item.asset_type === "cash" ? "Sin comisión" : "Comisión no disponible";
    if (Number(fee) === 0) return "Comisión 0%";
    return `Comisión estimada ${Number(fee).toFixed(3)}%`;
  }

  function routeLabel(item) {
    if (item.route_label) return item.route_label;
    if (!item.route?.length) return item.asset_type === "cash" ? "Efectivo disponible" : "Ruta no disponible";
    return item.route.map(value => String(value).toUpperCase()).join(" → ");
  }

  function saveCache() {
    try {
      const values = [...catalog.values()].filter(item => item.last !== undefined);
      localStorage.setItem(CACHE_KEY, JSON.stringify({savedAt: Date.now(), values}));
    } catch (_) {}
  }

  function restoreCache() {
    try {
      const parsed = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
      if (!parsed?.values || Date.now() - Number(parsed.savedAt || 0) > 24 * 60 * 60 * 1000) return;
      parsed.values.forEach(item => {
        if (catalog.has(item.book)) catalog.set(item.book, {...catalog.get(item.book), ...item});
      });
    } catch (_) {}
  }

  function updateCard(book) {
    const item = catalog.get(book);
    const card = grid.querySelector(`[data-book="${book}"]`);
    if (!item || !card) return;
    const action = item.signal?.action || "hold";
    card.classList.remove("signal-buy", "signal-hold", "signal-sell", "market-load-error");
    card.classList.add(`signal-${action}`);
    if (item.error) card.classList.add("market-load-error");
    const actionElement = card.querySelector(".market-action");
    const priceElement = card.querySelector(".market-price");
    const smalls = card.querySelectorAll(":scope > small");
    if (actionElement) actionElement.textContent = item.error ? "REINTENTAR" : (actionLabels[action] || "MANTENER");
    if (priceElement) priceElement.textContent = item.error ? "Sin respuesta" : money(item.last);
    if (smalls[0]) smalls[0].textContent = item.error ? "Toca para intentar de nuevo" : feeLabel(item);
    if (smalls[1]) smalls[1].textContent = item.error || routeLabel(item);
    card.dataset.assetType = item.asset_type === "stock" ? "stocks" : "markets";
    card.dataset.signal = action;
    applyFilters();
  }

  function applyFilters() {
    cards.forEach(card => {
      const typeMatches = typeFilter === "all" || card.dataset.assetType === typeFilter;
      const signalMatches = signalFilter === "all" || card.dataset.signal === signalFilter;
      card.hidden = !(typeMatches && signalMatches);
    });
    const visible = cards.filter(card => !card.hidden).length;
    grid.querySelector(".market-empty")?.remove();
    if (!visible) {
      const message = document.createElement("p");
      message.className = "market-empty";
      message.textContent = "No hay activos que coincidan con estos filtros.";
      grid.appendChild(message);
    }
  }

  function updateStatus() {
    const pending = Math.max(0, cards.length - loadedCount - failedCount);
    if (pending) status.textContent = `${loadedCount} listos · ${pending} cargando · filtros instantáneos`;
    else if (failedCount) status.textContent = `${loadedCount} listos · ${failedCount} sin respuesta · toca una tarjeta para reintentar`;
    else status.textContent = `${loadedCount} activos actualizados · rojo significa vender solo si ya tienes posición`;
  }

  function withTimeout(promise, ms) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ms);
    return {signal: controller.signal, done: promise(controller.signal).finally(() => clearTimeout(timer))};
  }

  async function loadBook(book, {retry = false} = {}) {
    const card = grid.querySelector(`[data-book="${book}"]`);
    if (!card || card.dataset.loading === "true") return;
    card.dataset.loading = "true";
    card.classList.add("market-loading");
    if (retry) {
      failedCount = Math.max(0, failedCount - 1);
      updateStatus();
    }

    const request = withTimeout(signal => fetch(`/api/market/${book}?ts=${Date.now()}`, {
      cache: "no-store",
      signal,
      headers: {"Cache-Control": "no-cache", "Pragma": "no-cache"}
    }), REQUEST_TIMEOUT_MS);

    try {
      const response = await request.done;
      const data = await response.json().catch(() => ({detail: "Respuesta inválida"}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      const ticker = data.ticker || {};
      catalog.set(book, {
        ...catalog.get(book),
        ...ticker,
        signal: data.signal || {action: "hold"},
        available: true,
        tradeable: book !== "mxn_cash",
        error: null
      });
      loadedCount += 1;
      updateCard(book);
      saveCache();
    } catch (error) {
      catalog.set(book, {...catalog.get(book), error: error.name === "AbortError" ? "La consulta tardó más de 5 segundos" : error.message});
      failedCount += 1;
      updateCard(book);
    } finally {
      card.dataset.loading = "false";
      card.classList.remove("market-loading");
      updateStatus();
    }
  }

  filters?.addEventListener("click", event => {
    event.preventDefault();
    const typeButton = event.target.closest("[data-type-filter]");
    const signalButton = event.target.closest("[data-signal-filter]");
    if (typeButton) {
      typeFilter = typeButton.dataset.typeFilter;
      filters.querySelectorAll("[data-type-filter]").forEach(button => button.classList.toggle("active", button === typeButton));
    }
    if (signalButton) {
      signalFilter = signalButton.dataset.signalFilter;
      filters.querySelectorAll("[data-signal-filter]").forEach(button => button.classList.toggle("active", button === signalButton));
    }
    applyFilters();
  });

  grid.addEventListener("click", event => {
    const card = event.target.closest("[data-book]");
    if (!card) return;
    const item = catalog.get(card.dataset.book);
    if (item?.error) {
      loadBook(card.dataset.book, {retry: true});
      return;
    }
    grid.querySelectorAll(".book").forEach(element => element.classList.remove("active"));
    card.classList.add("active");
    window.marketBridge?.select?.(card.dataset.book);
  });

  restoreCache();
  cards.forEach(card => updateCard(card.dataset.book));
  applyFilters();
  updateStatus();
  cards.forEach(card => loadBook(card.dataset.book));
})();
