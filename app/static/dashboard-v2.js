(() => {
  const REQUEST_TIMEOUT_MS = 8000;
  const tabs = () => [...document.querySelectorAll('[data-dashboard-tab]')];
  const panels = () => [...document.querySelectorAll('[data-dashboard-panel]')];
  const loadedTabs = new Set(['overview']);

  const endpoints = {
    health: ['/health', '#healthModule'],
    readiness: ['/ready', '#readinessModule'],
    runtime: ['/runtime/status', '#runtimeModule'],
    system: ['/system/status', '#systemModule'],
    paper: ['/paper/status', '#paperModule'],
    adaptive: ['/adaptive/status', '#strategiesModule'],
    validation: ['/validation/status', '#validationModule'],
    analytics: ['/analytics/performance', '#analyticsModule']
  };

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  const text = value => {
    if (value === null || value === undefined || value === '') return 'Todavía no hay información';
    if (typeof value === 'boolean') return value ? 'Sí' : 'No';
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
    if (Array.isArray(value)) return value.length ? `${value.length} registros` : 'Ninguno todavía';
    if (typeof value === 'object') return 'Disponible';
    return String(value).replaceAll('_', ' ');
  };
  const money = value => Number(value || 0).toLocaleString('es-MX', {
    style: 'currency', currency: 'MXN', minimumFractionDigits: 2, maximumFractionDigits: 2
  });
  const metric = (label, value, help = '') =>
    `<div class="module-metric"><span>${esc(label)}${help ? `<small class="muted">${esc(help)}</small>` : ''}</span><strong>${esc(value)}</strong></div>`;
  const setText = (selector, value) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = value;
  };
  const setDot = (selector, state) => {
    const node = document.querySelector(selector);
    if (!node) return;
    node.classList.remove('pending', 'ok', 'error');
    node.classList.add(state);
  };

  function activateTab(name, focus = false) {
    tabs().forEach(tab => {
      const active = tab.dataset.dashboardTab === name;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      if (active && focus) tab.scrollIntoView({behavior: 'smooth', block: 'nearest', inline: 'center'});
    });
    panels().forEach(panel => panel.classList.toggle('hidden', panel.dataset.dashboardPanel !== name));
    loadTab(name);
  }

  document.addEventListener('click', event => {
    const tab = event.target.closest('[data-dashboard-tab]');
    if (tab) {
      event.preventDefault();
      activateTab(tab.dataset.dashboardTab, true);
      return;
    }
    const refresh = event.target.closest('.module-refresh');
    if (refresh) {
      event.preventDefault();
      const match = Object.entries(endpoints).find(([, item]) => item[0] === refresh.dataset.moduleEndpoint);
      if (match) loadModule(match[0], true);
    }
  }, true);

  async function requestJson(url) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const separator = url.includes('?') ? '&' : '?';
      const response = await fetch(`${url}${separator}ts=${Date.now()}`, {
        cache: 'no-store', signal: controller.signal
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `No se pudo consultar ${url}.`);
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('La consulta tardó demasiado. La pantalla sigue disponible.');
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function flatten(data, prefix = '', output = []) {
    if (!data || typeof data !== 'object') return output;
    Object.entries(data).forEach(([key, value]) => {
      if (output.length >= 12) return;
      const label = prefix ? `${prefix} · ${key}` : key;
      if (value && typeof value === 'object' && !Array.isArray(value)) flatten(value, label, output);
      else output.push([label, value]);
    });
    return output;
  }

  function render(name, target, data, error = null) {
    const node = document.querySelector(target);
    if (!node) return;
    if (error) {
      node.innerHTML = `<p class="module-message">${esc(error)}</p><button type="button" class="secondary module-refresh" data-module-endpoint="${endpoints[name][0]}">Reintentar</button>`;
      return;
    }
    if (name === 'runtime') {
      const exploration = data.exploration || {};
      node.innerHTML = [
        metric('Motor automático', data.running ? 'Trabajando' : 'Pausado o iniciando'),
        metric('Proceso en segundo plano', data.background_task_active ? 'Activo' : 'No activo'),
        metric('Ciclos completados', text(data.cycles || 0)),
        metric('Observaciones', text(data.observations || 0)),
        metric('Posiciones abiertas', text(data.open_positions || 0)),
        metric('Operaciones cerradas', text(data.closed_trades || 0)),
        metric('Experiencia exploratoria', exploration.enabled ? 'Activa en simulación' : 'Desactivada'),
        metric('Experiencias activas', `${text(exploration.active_positions || 0)} / ${text(exploration.max_positions || 0)}`),
        metric('Experiencias cerradas', text(exploration.completed_trades || exploration.exits || 0))
      ].join('');
      return;
    }
    if (name === 'validation') {
      const learning = data.learning_sources || {};
      node.innerHTML = [
        metric('Abiertas en seguimiento', text(learning.active_tracking_samples || 0)),
        metric('Operaciones cerradas aprendidas', text(learning.completed_result_samples || 0)),
        metric('Estado', text(data.status || 'recolectando'))
      ].join('');
      return;
    }
    if (name === 'analytics') {
      const rows = data.by_source || data.learning_sources?.by_source || [];
      node.innerHTML = rows.length ? rows.map(row => [
        metric(row.source_label || row.source || 'Origen', `${row.open_positions || 0} abiertas · ${row.closed_positions || 0} cerradas`),
        metric('P&L realizado', money(row.realized_pnl_mxn || 0), `${row.wins || 0} ganadas · ${row.losses || 0} perdidas`)
      ].join('')).join('') : '<p class="module-message">Todavía no hay operaciones cerradas.</p>';
      return;
    }
    const rows = flatten(data);
    node.innerHTML = rows.length
      ? rows.map(([label, value]) => metric(label.replaceAll('_', ' '), text(value))).join('')
      : '<p class="module-message">Conectado. Todavía no hay información suficiente.</p>';
  }

  async function loadModule(name, force = false) {
    if (!endpoints[name]) return null;
    const [url, target] = endpoints[name];
    const node = document.querySelector(target);
    if (node && force) node.innerHTML = '<p>Consultando…</p>';
    try {
      const data = await requestJson(url);
      render(name, target, data);
      return data;
    } catch (error) {
      render(name, target, null, error.message);
      return null;
    }
  }

  async function refreshStatusStrip() {
    const [health, readiness, runtime] = await Promise.all([
      requestJson('/health').catch(() => null),
      requestJson('/ready').catch(() => null),
      requestJson('/runtime/status').catch(() => null)
    ]);
    const databaseOk = readiness?.checks?.database?.ok;
    setText('#statusRuntime', runtime?.running ? 'Analizando' : runtime ? 'Pausado' : 'Sin respuesta');
    setText('#statusMarket', health ? 'Conectado' : 'Sin respuesta');
    setText('#statusDatabase', databaseOk === true ? 'Conectada' : databaseOk === false ? 'No disponible' : 'Sin confirmar');
    setDot('#statusRuntimeDot', runtime?.running ? 'ok' : runtime ? 'error' : 'pending');
    setDot('#statusMarketDot', health ? 'ok' : 'error');
    setDot('#statusDatabaseDot', databaseOk === true ? 'ok' : databaseOk === false ? 'error' : 'pending');
    setText('#systemLastUpdated', new Date().toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit'}));
    setText('#overviewPaperState', runtime?.running ? 'Simulación automática activa' : 'Simulación pausada o iniciando');
  }

  function loadTab(name) {
    if (loadedTabs.has(name)) return;
    loadedTabs.add(name);
    if (name === 'paper') {
      loadModule('paper');
      window.loadHistory?.({reset: true});
      window.loadPositions?.();
    } else if (name === 'strategies') {
      loadModule('runtime');
      loadModule('adaptive');
      loadModule('analytics');
    } else if (name === 'validation') {
      loadModule('validation');
    } else if (name === 'system') {
      ['health', 'readiness', 'runtime', 'system'].forEach(loadModule);
    } else if (name === 'markets') {
      window.refreshMarket?.();
    }
  }

  activateTab(document.querySelector('[data-dashboard-tab].active')?.dataset.dashboardTab || 'overview');
  window.setTimeout(refreshStatusStrip, 0);
  window.setInterval(refreshStatusStrip, 30000);
  window.dashboardActivateTab = activateTab;
})();