(() => {
  const dashboardBooks = document.querySelector(".books");
  const orderBook = document.querySelector("#orderBook");
  const performanceChecks = document.querySelector(".book-checks");
  if (!dashboardBooks && !performanceChecks) return;

  let catalog = [];

  function sortedCatalog(mode) {
    const items = [...catalog];
    if (mode === "fee") {
      return items.sort((a, b) =>
        a.taker_fee_rate - b.taker_fee_rate ||
        b.range_24_pct - a.range_24_pct ||
        a.book.localeCompare(b.book)
      );
    }
    if (mode === "primary") {
      return items.sort((a, b) =>
        Number(b.is_primary) - Number(a.is_primary) ||
        b.range_24_pct - a.range_24_pct ||
        a.book.localeCompare(b.book)
      );
    }
    return items.sort((a, b) =>
      b.range_24_pct - a.range_24_pct ||
      a.taker_fee_rate - b.taker_fee_rate ||
      a.book.localeCompare(b.book)
    );
  }

  function tagMarkup(tags) {
    return (tags || []).map(tag => `<span class="market-tag">${tag}</span>`).join("");
  }

  function renderDashboard(mode = "volatility") {
    if (!dashboardBooks || !orderBook || !catalog.length) return;
    const items = sortedCatalog(mode);
    const current = typeof selectedBook !== "undefined" ? selectedBook : items[0].book;
    const selected = items.some(item => item.book === current) ? current : items[0].book;

    dashboardBooks.id = "marketBooks";
    dashboardBooks.innerHTML = items.map(item => `
      <button type="button" class="book market-book ${item.book === selected ? "active" : ""}" data-book="${item.book}">
        <span class="market-symbol">${item.symbol}</span>
        <small>Rango 24h ${Number(item.range_24_pct).toFixed(2)}% · Taker ${Number(item.taker_fee_percent).toFixed(3)}%</small>
        <span class="market-tags">${tagMarkup(item.tags)}</span>
      </button>`).join("");

    orderBook.innerHTML = items.map(item =>
      `<option value="${item.book}" ${item.book === selected ? "selected" : ""}>${item.symbol} · rango ${Number(item.range_24_pct).toFixed(2)}% · comisión ${Number(item.taker_fee_percent).toFixed(3)}%</option>`
    ).join("");

    if (typeof selectedBook !== "undefined") selectedBook = selected;

    let toolbar = document.querySelector("#marketCatalogToolbar");
    if (!toolbar) {
      toolbar = document.createElement("div");
      toolbar.id = "marketCatalogToolbar";
      toolbar.className = "market-catalog-toolbar";
      toolbar.innerHTML = `
        <label>Ordenar mercados
          <select id="marketSort">
            <option value="volatility">Más volátiles</option>
            <option value="fee">Menor comisión</option>
            <option value="primary">Principales</option>
          </select>
        </label>
        <small id="marketCatalogStatus"></small>`;
      dashboardBooks.before(toolbar);
      toolbar.querySelector("#marketSort").addEventListener("change", event => renderDashboard(event.target.value));
    }
    toolbar.querySelector("#marketSort").value = mode;
    toolbar.querySelector("#marketCatalogStatus").textContent = `${items.length} mercados reales de Bitso`;
  }

  function renderPerformance() {
    if (!performanceChecks || !catalog.length) return;
    performanceChecks.innerHTML = sortedCatalog("volatility").map(item => `
      <label class="book-check">
        <input type="checkbox" name="performanceBook" value="${item.book}" checked>
        <span>${item.symbol}</span>
      </label>`).join("");
  }

  dashboardBooks?.addEventListener("click", event => {
    const button = event.target.closest("[data-book]");
    if (!button) return;
    dashboardBooks.querySelectorAll(".book").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
    if (typeof selectedBook !== "undefined") selectedBook = button.dataset.book;
    if (orderBook) orderBook.value = button.dataset.book;
    if (typeof refreshMarket === "function") refreshMarket();
  });

  async function loadCatalog() {
    try {
      const response = await fetch(`/api/markets?ts=${Date.now()}`, {
        cache: "no-store",
        headers: {"Cache-Control": "no-cache", "Pragma": "no-cache"}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo cargar el catálogo");
      catalog = data.items || [];
      if (!catalog.length) throw new Error("Bitso no devolvió mercados MXN disponibles");
      renderDashboard();
      renderPerformance();
      if (dashboardBooks && typeof refreshMarket === "function") refreshMarket();
      if (performanceChecks && typeof loadPerformance === "function") loadPerformance();
    } catch(error) {
      const status = document.querySelector("#marketCatalogStatus") || document.querySelector("#performanceUpdated");
      if (status) status.textContent = `Catálogo: ${error.message}`;
    }
  }

  loadCatalog();
})();
