(() => {
  const grid = document.querySelector('#marketGridV2');
  const filters = document.querySelector('#marketFiltersV2');
  const status = document.querySelector('#marketCatalogStatusV2');
  if (!grid) return;

  const actionLabels = {buy: 'COMPRAR', hold: 'MANTENER', sell: 'VENDER SI TIENES'};
  const CACHE_KEY = 'paul-market-card-cache-v4';
  const REQUEST_TIMEOUT_MS = 15000;
  const CRYPTO_REFRESH_MS = 15000;
  const STOCK_REFRESH_MS = 60000;
  let typeFilter = 'all';
  let signalFilter = 'all';

  const cards = [...grid.querySelectorAll('[data-book]')];
  const stockBooks = new Set(['algn_mxn', 'tsla_mxn', 'aapl_mxn']);
  const catalog = new Map(cards.map(card => {
    const book = card.dataset.book;
    const symbol = card.querySelector('.market-symbol')?.textContent?.trim() || book.toUpperCase();
    const name = card.querySelector('.market-card-head small')?.textContent?.trim() || symbol;
    return [book, {book, symbol, name, asset_type: stockBooks.has(book) ? 'stock' : 'market', signal: {action: 'hold'}}];
  }));

  function money(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Sin precio';
    return Number(value).toLocaleString('es-MX', {style: 'currency', currency: 'MXN', minimumFractionDigits: 2, maximumFractionDigits: 2});
  }

  function elapsed(timestamp) {
    if (!timestamp) return 'Sin actualizar';
    const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
    if (seconds < 60) return `Actualizado hace ${seconds} s`;
    return `Actualizado hace ${Math.round(seconds / 60)} min`;
  }

  function feeLabel(item) {
    if (item.fee_included_in_quote) return 'Costo incluido en cotización Bitso';
    const fee = item.effective_fee_percent;
    if (fee === null || fee === undefined) return item.asset_type === 'stock' ? 'Referencia analítica' : 'Comisión no disponible';
    if (Number(fee) === 0) return 'Comisión 0%';
    return `Comisión estimada ${Number(fee).toFixed(3)}%`;
  }

  function routeLabel(item) {
    if (item.error && item.last !== undefined) return `Último dato válido · ${item.error}`;
    if (item.route_label) return item.route_label;
    if (item.source) return item.asset_type === 'stock' ? `Fuente analítica: ${item.source}` : `Precio: ${item.source}`;
    if (!item.route?.length) return item.asset_type === 'stock' ? 'Fuente externa para análisis' : 'Consultando Bitso';
    return item.route.map(value => String(value).toUpperCase()).join(' → ');
  }

  function saveCache() {
    try {
      const values = [...catalog.values()].filter(item => item.last !== undefined);
      localStorage.setItem(CACHE_KEY, JSON.stringify({savedAt: Date.now(), values}));
    } catch (_) {}
  }

  function restoreCache() {
    try {
      const parsed = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
      if (!parsed?.values || Date.now() - Number(parsed.savedAt || 0) > 24 * 60 * 60 * 1000) return;
      parsed.values.forEach(item => {
        if (catalog.has(item.book)) catalog.set(item.book, {...catalog.get(item.book), ...item, cached: true});
      });
    } catch (_) {}
  }

  function updateCard(book) {
    const item = catalog.get(book);
    const card = grid.querySelector(`[data-book="${book}"]`);
    if (!item || !card) return;
    const action = item.signal?.action || 'hold';
    card.classList.remove('signal-buy', 'signal-hold', 'signal-sell', 'market-load-error', 'stale-data');
    card.classList.add(`signal-${action}`);
    if (item.error && item.last === undefined) card.classList.add('market-load-error');
    if (item.error && item.last !== undefined) card.classList.add('stale-data');
    const actionElement = card.querySelector('.market-action');
    const priceElement = card.querySelector('.market-price');
    const smalls = card.querySelectorAll(':scope > small');
    if (actionElement) actionElement.textContent = item.error && item.last === undefined ? 'NO DISPONIBLE' : (actionLabels[action] || 'MANTENER');
    if (priceElement) priceElement.textContent = item.last !== undefined ? money(item.last) : (item.loading ? 'Actualizando…' : 'Proveedor no disponible');
    if (smalls[0]) smalls[0].textContent = item.last !== undefined ? feeLabel(item) : 'Se reintentará automáticamente';
    if (smalls[1]) smalls[1].textContent = routeLabel(item);
    if (smalls[2]) smalls[2].textContent = elapsed(item.updatedAt);
    card.dataset.assetType = item.asset_type === 'stock' ? 'stocks' : 'markets';
    card.dataset.signal = action;
    applyFilters();
  }

  function applyFilters() {
    cards.forEach(card => {
      const typeMatches = typeFilter === 'all' || card.dataset.assetType === typeFilter;
      const signalMatches = signalFilter === 'all' || card.dataset.signal === signalFilter;
      card.hidden = !(typeMatches && signalMatches);
    });
  }

  function updateStatus() {
    const values = [...catalog.values()];
    const ready = values.filter(item => item.last !== undefined).length;
    const loading = values.filter(item => item.loading).length;
    const unavailable = values.filter(item => item.error && item.last === undefined).length;
    status.textContent = `${ready} con precio · ${loading} actualizando · ${unavailable} no disponibles · refresco automático`;
  }

  async function loadBook(book) {
    const card = grid.querySelector(`[data-book="${book}"]`);
    const current = catalog.get(book);
    if (!card || current?.loading) return;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    catalog.set(book, {...current, loading: true});
    card.classList.add('market-loading');
    updateCard(book);
    updateStatus();
    try {
      const response = await fetch(`/api/market/${book}?ts=${Date.now()}`, {cache: 'no-store', signal: controller.signal});
      const data = await response.json().catch(() => ({detail: 'Respuesta inválida'}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      const ticker = data.ticker || {};
      catalog.set(book, {...current, ...ticker, signal: data.signal || {action: 'hold'}, available: true, error: null, loading: false, cached: false, updatedAt: Date.now()});
      saveCache();
    } catch (error) {
      const message = error.name === 'AbortError' ? 'Tiempo de respuesta excedido' : error.message;
      catalog.set(book, {...catalog.get(book), error: message, loading: false});
    } finally {
      clearTimeout(timer);
      card.classList.remove('market-loading');
      updateCard(book);
      updateStatus();
    }
  }

  function refreshByType(type) {
    [...catalog.values()].filter(item => item.asset_type === type).forEach((item, index) => {
      window.setTimeout(() => loadBook(item.book), index * 350);
    });
  }

  filters?.addEventListener('click', event => {
    event.preventDefault();
    const typeButton = event.target.closest('[data-type-filter]');
    const signalButton = event.target.closest('[data-signal-filter]');
    if (typeButton) {
      typeFilter = typeButton.dataset.typeFilter;
      filters.querySelectorAll('[data-type-filter]').forEach(button => button.classList.toggle('active', button === typeButton));
    }
    if (signalButton) {
      signalFilter = signalButton.dataset.signalFilter;
      filters.querySelectorAll('[data-signal-filter]').forEach(button => button.classList.toggle('active', button === signalButton));
    }
    applyFilters();
  });

  grid.addEventListener('click', event => {
    const card = event.target.closest('[data-book]');
    if (!card) return;
    grid.querySelectorAll('.book').forEach(element => element.classList.remove('active'));
    card.classList.add('active');
    window.marketBridge?.select?.(card.dataset.book);
    loadBook(card.dataset.book);
  });

  document.querySelector('#refreshBtn')?.addEventListener('click', () => {
    refreshByType('market');
    refreshByType('stock');
  });

  restoreCache();
  cards.forEach(card => updateCard(card.dataset.book));
  applyFilters();
  refreshByType('market');
  refreshByType('stock');
  window.setInterval(() => refreshByType('market'), CRYPTO_REFRESH_MS);
  window.setInterval(() => refreshByType('stock'), STOCK_REFRESH_MS);
  window.setInterval(() => cards.forEach(card => updateCard(card.dataset.book)), 5000);
})();