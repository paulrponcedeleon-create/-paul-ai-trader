(() => {
  const dashboardBooks = document.querySelector(".books");
  const orderBook = document.querySelector("#orderBook");
  const performanceChecks = document.querySelector(".book-checks");
  if (!dashboardBooks && !performanceChecks) return;

  let catalog = [];
  const actionLabels = {buy: "COMPRAR", hold: "MANTENER", sell: "VENDER"};

  function money(value) {
    if (value === null || value === undefined) return "Sin precio";
    return Number(value).toLocaleString("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function feeLabel(item) {
    if (item.effective_fee_percent === null || item.effective_fee_percent === undefined) {
      return item.asset_type === "cash" ? "Sin comisión" : "Comisión no disponible";
    }
    if (Number(item.effective_fee_percent) === 0) return "Comisión 0%";
    return `Comisión estimada ${Number(item.effective_fee_percent).toFixed(3)}%`;
  }

  function routeLabel(item) {
    if (!item.route?.length) return item.asset_type === "cash" ? "Efectivo" : "Ruta no disponible";
    return item.route.map(value => value.toUpperCase()).join(" → ");
  }

  function renderDashboard() {
    if (!dashboardBooks || !orderBook || !catalog.length) return;
    const firstAvailable = catalog.find(item => item.available) || catalog[0];
    const current = typeof selectedBook !== "undefined" ? selectedBook : firstAvailable.book;
    const selected = catalog.some(item => item.book === current) ? current : firstAvailable.book;

    window.marketCatalogMap = new Map(catalog.map(item => [item.book, item]));
    window.displayMarketSymbol = book => window.marketCatalogMap.get(book)?.symbol || book.toUpperCase();
    window.displayMarketName = book => window.marketCatalogMap.get(book)?.name || book.toUpperCase();

    dashboardBooks.id = "marketBooks";
    dashboardBooks.classList.add("curated-watchlist");
    dashboardBooks.innerHTML = catalog.map(item => {
      const action = item.signal?.action || "hold";
      const actionLabel = actionLabels[action] || action.toUpperCase();
      const state = item.available ? "" : " market-unavailable";
      return `
        <button type="button" class="book market-book signal-${action}${state} ${item.book === selected ? "active" : ""}" data-book="${item.book}">
          <span class="market-card-head">
            <span><strong class="market-symbol">${item.symbol}</strong><small>${item.name}</small></span>
            <strong class="market-action">${actionLabel}</strong>
          </span>
          <span class="market-price">${money(item.last)}</span>
          <small>${feeLabel(item)}</small>
          <small class="market-route">${routeLabel(item)}</small>
        </button>`;
    }).join("");

    const tradeable = catalog.filter(item => item.available && item.tradeable);
    const selectedTradeable = tradeable.some(item => item.book === selected)
      ? selected
      : tradeable[0]?.book;
    orderBook.innerHTML = tradeable.map(item =>
      `<option value="${item.book}" ${item.book === selectedTradeable ? "selected" : ""}>${item.symbol} · ${item.name} · ${feeLabel(item)}</option>`
    ).join("");

    if (typeof selectedBook !== "undefined") selectedBook = selected;

    let status = document.querySelector("#marketCatalogStatus");
    if (!status) {
      status = document.createElement("p");
      status.id = "marketCatalogStatus";
      status.className = "market-catalog-status";
      dashboardBooks.before(status);
    }
    const availableCount = catalog.filter(item => item.available).length;
    status.textContent = `${availableCount} de ${catalog.length} activos con precio disponible · verde comprar · azul mantener · rojo vender`;
  }

  function renderPerformance() {
    if (!performanceChecks || !catalog.length) return;
    performanceChecks.innerHTML = catalog
      .filter(item => item.tradeable)
      .map(item => `
        <label class="book-check">
          <input type="checkbox" name="performanceBook" value="${item.book}" checked>
          <span>${item.symbol}</span>
        </label>`).join("");
  }

  dashboardBooks?.addEventListener("click", event => {
    const button = event.target.closest("[data-book]");
    if (!button) return;
    const item = window.marketCatalogMap?.get(button.dataset.book);
    dashboardBooks.querySelectorAll(".book").forEach(element => element.classList.remove("active"));
    button.classList.add("active");
    if (typeof selectedBook !== "undefined") selectedBook = button.dataset.book;
    if (orderBook && item?.tradeable && item?.available) orderBook.value = button.dataset.book;
    if (typeof refreshMarket === "function") refreshMarket();
  });

  async function loadCatalog() {
    try {
      const response = await fetch(`/api/markets?ts=${Date.now()}`, {
        cache: "no-store",
        headers: {"Cache-Control": "no-cache", "Pragma": "no-cache"}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo cargar la lista de activos");
      catalog = data.items || [];
      if (!catalog.length) throw new Error("No se recibieron activos");
      renderDashboard();
      renderPerformance();
      if (dashboardBooks && typeof refreshMarket === "function") refreshMarket();
      if (performanceChecks && typeof loadPerformance === "function") loadPerformance();
    } catch(error) {
      const status = document.querySelector("#marketCatalogStatus") || document.querySelector("#performanceUpdated");
      if (status) status.textContent = `Activos: ${error.message}`;
    }
  }

  loadCatalog();
})();
