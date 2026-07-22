(() => {
  const tabs = [...document.querySelectorAll('[data-dashboard-tab]')];
  const panels = [...document.querySelectorAll('[data-dashboard-panel]')];
  if (!tabs.length || !panels.length) return;

  const endpoints = {
    health: ['/health', '#healthModule'],
    readiness: ['/readiness', '#readinessModule'],
    runtime: ['/runtime/status', '#runtimeModule'],
    system: ['/system/status', '#systemModule'],
    paper: ['/paper-trading/status', '#paperModule'],
    analytics: ['/analytics/status', '#analyticsModule'],
    adaptive: ['/adaptive/status', '#strategiesModule'],
    validation: ['/validation/status', '#validationModule']
  };

  const text = value => {
    if (value === null || value === undefined || value === '') return 'No disponible';
    if (typeof value === 'boolean') return value ? 'Sí' : 'No';
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
    if (Array.isArray(value)) return value.length ? `${value.length} elemento${value.length === 1 ? '' : 's'}` : 'Sin registros';
    if (typeof value === 'object') return 'Disponible';
    return String(value).replaceAll('_', ' ');
  };

  function flatten(data, prefix = '', output = []) {
    if (!data || typeof data !== 'object') return output;
    Object.entries(data).forEach(([key, value]) => {
      const label = prefix ? `${prefix} · ${key}` : key;
      if (value && typeof value === 'object' && !Array.isArray(value) && output.length < 10) flatten(value, label, output);
      else if (output.length < 10) output.push([label, value]);
    });
    return output;
  }

  function render(target, data, error) {
    const node = document.querySelector(target);
    if (!node) return;
    if (error) {
      node.innerHTML = `<p class="module-message">No disponible todavía: ${error}</p>`;
      return;
    }
    const rows = flatten(data);
    if (!rows.length) {
      node.innerHTML = '<p class="module-message">El endpoint respondió, pero todavía no hay métricas para mostrar.</p>';
      return;
    }
    node.innerHTML = rows.map(([label, value]) => `<div class="module-metric"><span>${label.replaceAll('_', ' ')}</span><strong>${text(value)}</strong></div>`).join('');
  }

  function setDot(id, ok) {
    const dot = document.querySelector(id);
    if (!dot) return;
    dot.classList.remove('pending', 'ok', 'error');
    dot.classList.add(ok ? 'ok' : 'error');
  }

  async function loadModule(name) {
    const config = endpoints[name];
    if (!config) return null;
    const [url, target] = config;
    try {
      const response = await fetch(`${url}?ts=${Date.now()}`, {cache: 'no-store'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      render(target, data, null);
      return data;
    } catch (error) {
      render(target, null, error.message);
      return null;
    }
  }

  function summarize(data, fallback = 'Sin datos todavía') {
    if (!data || typeof data !== 'object') return fallback;
    return text(data.status ?? data.state ?? data.mode ?? data.ready ?? fallback);
  }

  async function refreshSystem() {
    const [health, readiness, runtime, system, paper, adaptive, validation] = await Promise.all([
      loadModule('health'), loadModule('readiness'), loadModule('runtime'), loadModule('system'),
      loadModule('paper'), loadModule('adaptive'), loadModule('validation')
    ]);
    loadModule('analytics');

    document.querySelector('#statusRuntime').textContent = summarize(runtime, 'No disponible');
    document.querySelector('#statusMarket').textContent = health ? 'Conectado' : 'Sin respuesta';
    document.querySelector('#statusDatabase').textContent = readiness ? 'Disponible' : 'Sin confirmar';
    setDot('#statusRuntimeDot', Boolean(runtime));
    setDot('#statusMarketDot', Boolean(health));
    setDot('#statusDatabaseDot', Boolean(readiness));
    document.querySelector('#systemLastUpdated').textContent = new Date().toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit', second: '2-digit'});

    const paperState = document.querySelector('#overviewPaperState');
    const paperDetail = document.querySelector('#overviewPaperDetail');
    if (paperState) paperState.textContent = summarize(paper, 'Sin iniciar');
    if (paperDetail) paperDetail.textContent = paper ? 'El backend de simulación está disponible.' : 'El backend no respondió.';
    const strategyState = document.querySelector('#overviewStrategyState');
    if (strategyState) strategyState.textContent = summarize(adaptive, 'Sin estrategia publicada');
    const validationState = document.querySelector('#overviewValidationState');
    if (validationState) validationState.textContent = summarize(validation, 'Sin validaciones todavía');
    const validationDetail = document.querySelector('#overviewValidationDetail');
    if (validationDetail) validationDetail.textContent = validation ? 'Pipeline conectado al dashboard.' : 'Endpoint no disponible.';
  }

  tabs.forEach(tab => tab.addEventListener('click', () => {
    const name = tab.dataset.dashboardTab;
    tabs.forEach(item => item.classList.toggle('active', item === tab));
    panels.forEach(panel => panel.classList.toggle('hidden', panel.dataset.dashboardPanel !== name));
    if (name === 'markets') document.querySelector('#refreshBtn')?.click();
  }));

  document.addEventListener('click', event => {
    const button = event.target.closest('.module-refresh');
    if (!button) return;
    const endpoint = button.dataset.moduleEndpoint;
    const match = Object.entries(endpoints).find(([, value]) => value[0] === endpoint);
    if (match) loadModule(match[0]);
  });

  refreshSystem();
  window.setInterval(refreshSystem, 30000);
})();