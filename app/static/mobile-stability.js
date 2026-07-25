(() => {
  const REQUEST_TIMEOUT_MS = 8000;
  const RESPONSE_CACHE_MS = 15000;
  const MAX_CONCURRENT = 2;
  const originalFetch = window.fetch.bind(window);
  const queue = [];
  const inflight = new Map();
  const responseCache = new Map();
  let active = 0;

  const activeTab = () => document.querySelector('[data-dashboard-tab].active')?.dataset.dashboardTab || 'overview';

  function requestInfo(input, init = {}) {
    try {
      const raw = typeof input === 'string' ? input : input?.url || '';
      const url = new URL(raw, window.location.origin);
      const method = String(init.method || (typeof input !== 'string' ? input?.method : '') || 'GET').toUpperCase();
      url.searchParams.delete('ts');
      const sorted = [...url.searchParams.entries()].sort(([a], [b]) => a.localeCompare(b));
      url.search = '';
      sorted.forEach(([key, value]) => url.searchParams.append(key, value));
      return {pathname: url.pathname, method, key: `${method}:${url.pathname}${url.search}`};
    } catch (_) {
      return {pathname: '', method: 'GET', key: ''};
    }
  }

  function allowedForCurrentTab(pathname) {
    if (!pathname || !pathname.startsWith('/')) return true;
    if (
      pathname === '/health' ||
      pathname === '/api/login' ||
      pathname === '/api/logout' ||
      pathname === '/api/register' ||
      pathname.startsWith('/api/account') ||
      pathname === '/api/capital' ||
      pathname === '/api/release'
    ) return true;

    const tab = activeTab();
    if (pathname.startsWith('/api/market/') || pathname.startsWith('/market/rfq/')) return tab === 'markets';
    if (pathname === '/api/positions') return tab === 'overview' || tab === 'paper';
    if (pathname.startsWith('/api/simulations') || pathname === '/paper/status') return tab === 'paper';
    if (pathname === '/api/orders') return tab === 'markets' || tab === 'paper';
    if (pathname === '/runtime/status' || pathname === '/adaptive/status' || pathname === '/analytics/performance') return tab === 'strategies' || tab === 'system';
    if (pathname === '/validation/status') return tab === 'validation' || tab === 'system';
    if (pathname === '/ready' || pathname === '/system/status') return tab === 'system';
    return true;
  }

  function runNext() {
    while (active < MAX_CONCURRENT && queue.length) {
      const job = queue.shift();
      active += 1;
      job().finally(() => {
        active -= 1;
        runNext();
      });
    }
  }

  window.fetch = (input, init = {}) => {
    const info = requestInfo(input, init);
    if (!allowedForCurrentTab(info.pathname)) {
      return Promise.reject(new Error('Este módulo se carga al abrir su pestaña.'));
    }

    if (info.method === 'GET' && info.key) {
      const cached = responseCache.get(info.key);
      if (cached && Date.now() - cached.savedAt < RESPONSE_CACHE_MS) {
        return Promise.resolve(cached.response.clone());
      }
      const existing = inflight.get(info.key);
      if (existing) return existing.then(response => response.clone());
    }

    const requestPromise = new Promise((resolve, reject) => {
      queue.push(async () => {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        const externalSignal = init.signal;
        const abortFromExternal = () => controller.abort();
        externalSignal?.addEventListener?.('abort', abortFromExternal, {once: true});
        try {
          const response = await originalFetch(input, {...init, signal: controller.signal});
          if (info.method === 'GET' && info.key && response.ok) {
            responseCache.set(info.key, {savedAt: Date.now(), response: response.clone()});
          }
          resolve(response);
        } catch (error) {
          if (error?.name === 'AbortError') reject(new Error('La consulta tardó demasiado. Puedes seguir usando las pestañas y reintentar.'));
          else reject(error);
        } finally {
          window.clearTimeout(timer);
          externalSignal?.removeEventListener?.('abort', abortFromExternal);
        }
      });
      runNext();
    });

    if (info.method === 'GET' && info.key) {
      inflight.set(info.key, requestPromise);
      requestPromise.finally(() => inflight.delete(info.key));
    }
    return requestPromise;
  };

  function switchTab(name) {
    document.querySelectorAll('[data-dashboard-tab]').forEach(tab => {
      const selected = tab.dataset.dashboardTab === name;
      tab.classList.toggle('active', selected);
      tab.setAttribute('aria-selected', String(selected));
    });
    document.querySelectorAll('[data-dashboard-panel]').forEach(panel => {
      panel.classList.toggle('hidden', panel.dataset.dashboardPanel !== name);
    });
    window.setTimeout(() => {
      document.dispatchEvent(new Event('visibilitychange'));
      if (name === 'markets') window.refreshMarket?.();
      if (name === 'paper') {
        window.loadPositions?.();
        window.loadHistory?.({reset: true});
      }
    }, 0);
  }

  document.addEventListener('click', event => {
    const tab = event.target.closest('[data-dashboard-tab]');
    if (!tab) return;
    event.preventDefault();
    switchTab(tab.dataset.dashboardTab);
  }, true);

  document.addEventListener('touchend', event => {
    const tab = event.target.closest('[data-dashboard-tab]');
    if (!tab) return;
    switchTab(tab.dataset.dashboardTab);
  }, {capture: true, passive: true});

  const style = document.createElement('style');
  style.textContent = `
    [data-dashboard-tab], button, a, input, select { touch-action: manipulation; }
    .workspace-tabs { position: relative; z-index: 20; -webkit-overflow-scrolling: touch; }
    [data-dashboard-panel] { position: relative; z-index: 1; }
  `;
  document.head.appendChild(style);

  window.mobileStabilitySwitchTab = switchTab;
})();
