(() => {
  const grid = document.querySelector("#marketGridV2");
  const filters = document.querySelector("#marketFiltersV2");
  const status = document.querySelector("#marketCatalogStatusV2");
  const orderBook = document.querySelector("#orderBook");
  const performanceChecks = document.querySelector(".book-checks");
  if (!grid) return;

  const actionLabels = {buy: "COMPRAR", hold: "MANTENER", sell: "VENDER"};
  let catalog = [];
  let typeFilter = "all";
  let signalFilter = "all";

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
    if (item.fee_included_in_quote) return "Costo incluido en cotización Bitso";
    if (item.effective_fee_percent === null || item.effective_fee_percent === undefined) {
      return item.asset_type === "cash" ? "Sin comisión" : "Comisión no disponible";
    }
    if (Number(item.effective_fee_percent) === 0) return "Comisión 0%";
    return `Comisión estimada ${Number(item.effective_fee_percent).toFixed(3)}%`;
  }

  function routeLabel(item) {
    if (item.route_label) return item.route_label;
    if (!item.route?.length) return item.asset_type === "cash" ? "Efectivo" : "Ruta no disponible";
    return item.route.map(value => value.toUpperCase()).join(" → ");
  }

  function matches(item) {
    const typeMatches = typeFilter === "all"
      || (typeFilter === "stocks" && item.asset_type === "stock")
      || (typeFilter === "markets" && item.asset_type !== "stock");
    const signal = item.signal?.action || "hold";
    return typeMatches && (signalFilter === "all" || signalFilter === signal);
  }

  function cardMarkup(item, selectedBook) {
    const action = item.signal?.action || "hold";
    const actionLabel = actionLabels[action] || "MANTENER";
    return `
      <button type="button"
        class="book market-book-v2 signal-${action}${item.book === selectedBook ? " active" : ""}"
        data-book="${item.book}">
        <span class="market-card-head">
          <span><strong class="market-symbol">${item.symbol}</strong><small>${item.name}</small></span>
          <strong class="market-action">${actionLabel}</strong>
        </span>
        <span class="market-price">${money(item.last)}</span>
        <small>${item.available ? feeLabel(item) : "Precio temporalmente no disponible"}</small>
        <small class="market-route">${routeLabel(item)}</small>
      </button>`;
  }

  function render() {
    const visible = catalog.filter(matches);
    const current = window.marketBridge?.getSelected?.() || "btc_mxn";
    const selected = visible.some(item => item.book === current)
      ? current
      : visible.find(item => item.available)?.book || visible[0]?.book;

    grid.innerHTML = visible.length
      ? visible.map(item => cardMarkup(item, selected)).join("")
      : '<p class="market-empty">No hay activos que coincidan con estos filtros.</p>';

    const tradeable = catalog.filter(item => item.available && item.tradeable);
    if (orderBook) {
      orderBook.innerHTML = tradeable.map(item =>
        `<option value="${item.book}">${item.symbol} · ${item.name} · ${feeLabel(item)}</option>`
      ).join("");
      if (tradeable.some(item => item.book === selected)) orderBook.value = selected;
    }

    window.marketCatalogMap = new Map(catalog.map(item => [item.book, item]));
    window.displayMarketSymbol = book => window.marketCatalogMap.get(book)?.symbol || String(book).toUpperCase();
    window.displayMarketName = book => window.marketCatalogMap.get(book)?.name || String(book).toUpperCase();

    const availableCount = catalog.filter(item => item.available).length;
    status.textContent = `${availableCount} de ${catalog.length} activos con precio · verde comprar · azul mantener · rojo vender`;
  }

  filters?.addEventListener("click", event => {
    const typeButton = event.target.closest("[data-type-filter]");
    const signalButton = event.target.closest("[data-signal-filter]");

    if (typeButton) {
      typeFilter = typeButton.dataset.typeFilter;
      filters.querySelectorAll("[data-type-filter]").forEach(button => {
        button.classList.toggle("active", button === typeButton);
      });
    }

    if (signalButton) {
      signalFilter = signalButton.dataset.signalFilter;
      filters.querySelectorAll("[data-signal-filter]").forEach(button => {
        button.classList.toggle("active", button === signalButton);
      });
    }

    render();
  });

  grid.addEventListener("click", event => {
    const button = event.target.closest("[data-book]");
    if (!button) return;
    grid.querySelectorAll(".book").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
    window.marketBridge?.select?.(button.dataset.book);
  });

  async function loadCatalog() {
    status.textContent = "Cargando señales y precios…";
    try {
      const response = await fetch(`/api/markets?ts=${Date.now()}`, {
        cache: "no-store",
        headers: {"Cache-Control": "no-cache", "Pragma": "no-cache"}
      });
      const data = await response.json().catch(() => ({detail: "Respuesta inválida"}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      catalog = data.items || [];
      if (!catalog.length) throw new Error("Bitso no devolvió activos");
      render();
      window.marketBridge?.refresh?.();

      if (performanceChecks) {
        performanceChecks.innerHTML = catalog.filter(item => item.tradeable).map(item => `
          <label class="book-check">
            <input type="checkbox" name="performanceBook" value="${item.book}" checked>
            <span>${item.symbol}</span>
          </label>`).join("");
      }
    } catch (error) {
      status.textContent = `No se pudieron cargar las señales: ${error.message}`;
      status.classList.add("error");
    }
  }

  loadCatalog();
})();
