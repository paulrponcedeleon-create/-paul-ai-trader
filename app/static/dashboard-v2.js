(() => {
  const tabs = [...document.querySelectorAll('[data-dashboard-tab]')];
  const panels = [...document.querySelectorAll('[data-dashboard-panel]')];
  if (!tabs.length || !panels.length) return;

  const endpoints = {
    health: ['/health', '#healthModule'], readiness: ['/ready', '#readinessModule'],
    runtime: ['/runtime/status', '#runtimeModule'], system: ['/system/status', '#systemModule'],
    paper: ['/paper/status', '#paperModule'], analytics: ['/analytics/performance', '#analyticsModule'],
    adaptive: ['/adaptive/status', '#strategiesModule'], validation: ['/validation/status', '#validationModule']
  };

  const text = value => {
    if (value === null || value === undefined || value === '') return 'Todavía no hay información';
    if (typeof value === 'boolean') return value ? 'Sí' : 'No';
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
    if (Array.isArray(value)) return value.length ? `${value.length} registro${value.length === 1 ? '' : 's'}` : 'Ninguno todavía';
    if (typeof value === 'object') return 'Disponible';
    return String(value).replaceAll('_', ' ');
  };

  const metric = (label, value, help = '') => `<div class="module-metric"><span>${label}${help ? `<small class="muted">${help}</small>` : ''}</span><strong>${value}</strong></div>`;

  function friendlyRender(name, data) {
    if (name === 'runtime') return [
      metric('Motor automático', data.running ? 'Trabajando' : 'Iniciando', 'Analiza el mercado y toma decisiones con dinero simulado.'),
      metric('Ciclos completados', text(data.cycles), 'Cada ciclo revisa los activos configurados.'),
      metric('Fuente de precios', data.provider_label || 'Bitso, solo lectura'),
      metric('Tipo de dinero', data.broker_label || 'Dinero simulado'),
      metric('Última decisión', data.last_decision?.action ? String(data.last_decision.action).toUpperCase() : 'Esperando suficientes datos'),
      metric('Último problema', data.last_error ? 'Se detectó un problema y se reintentará' : 'Ninguno')
    ].join('');
    if (name === 'validation') return [
      metric('Estado', data.status === 'idle' ? 'Esperando historial suficiente' : text(data.status), 'Aquí se decide qué estrategias merecen seguir usándose.'),
      metric('Operaciones registradas', text(data.runs ?? 0)),
      metric('Estrategias aprobadas', text(data.active_strategies ?? data['active strategies'] ?? [])),
      metric('Días mínimos antes de evaluar', text(data.rules?.min_active_days ?? 30)),
      metric('Operaciones mínimas antes de evaluar', text(data.rules?.min_trades ?? 100)),
      metric('Pérdida máxima aceptada', `${text(data.rules?.max_drawdown_pct ?? 12)}%`)
    ].join('');
    if (name === 'system') return [
      metric('Estado general', data.health?.state === 'HEALTHY' ? 'Todo funcionando normalmente' : text(data.health?.state ?? data.status)),
      metric('Conexión al mercado', data.circuit_breakers?.['Market Data']?.state === 'CLOSED' ? 'Normal' : 'Revisando conexión'),
      metric('Simulador de órdenes', data.circuit_breakers?.Broker?.state === 'CLOSED' ? 'Normal' : 'Revisando'),
      metric('Aplicación congelada', data.watchdog?.frozen?.length ? 'Sí, requiere revisión' : 'No'),
      metric('Errores repetidos', data.watchdog?.error_loops?.length ? 'Detectados' : 'Ninguno')
    ].join('');
    if (name === 'readiness') return [
      metric('Aplicación lista', data.status === 'ready' ? 'Sí' : 'Requiere atención'),
      metric('Base de datos', data.checks?.database?.ok ? 'Conectada' : 'No disponible'),
      metric('Tablas necesarias', data.checks?.required_tables?.ok ? 'Completas' : 'Faltan tablas'),
      metric('Carpeta de datos', data.checks?.paul_data_dir?.ok ? 'Disponible' : 'No disponible'),
      metric('Modo actual', data.mode === 'simulation' ? 'Simulación, sin dinero real' : 'Dinero real')
    ].join('');
    if (name === 'paper') return [
      metric('Simulación automática', data.running ? 'Activa' : 'Lista para iniciar'),
      metric('Estrategia', data.strategy_name || 'La seleccionará el motor'),
      metric('Activo actual', data.book ? data.book.toUpperCase() : 'Varios activos'),
      metric('Cuenta', data.account_id === 'unconfigured' ? 'Cuenta simulada' : text(data.account_id))
    ].join('');
    return null;
  }

  function flatten(data, prefix = '', output = []) {
    if (!data || typeof data !== 'object') return output;
    Object.entries(data).forEach(([key, value]) => {
      const label = prefix ? `${prefix} · ${key}` : key;
      if (value && typeof value === 'object' && !Array.isArray(value) && output.length < 12) flatten(value, label, output);
      else if (output.length < 12) output.push([label, value]);
    });
    return output;
  }

  function render(name, target, data, error) {
    const node = document.querySelector(target);
    if (!node) return;
    if (error) { node.innerHTML = `<p class="module-message">${error}</p>`; return; }
    const friendly = friendlyRender(name, data);
    if (friendly) { node.innerHTML = friendly; return; }
    const rows = flatten(data);
    node.innerHTML = rows.length ? rows.map(([label, value]) => metric(label.replaceAll('_', ' '), text(value))).join('') : '<p class="module-message">Conectado. Todavía no hay operaciones suficientes.</p>';
  }

  function setDot(id, ok) {
    const dot = document.querySelector(id); if (!dot) return;
    dot.classList.remove('pending', 'ok', 'error'); dot.classList.add(ok ? 'ok' : 'error');
  }

  async function loadModule(name) {
    const [url, target] = endpoints[name];
    try {
      const response = await fetch(`${url}?ts=${Date.now()}`, {cache: 'no-store'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok && !(name === 'readiness' && data?.checks)) throw new Error(data.detail || `No se pudo consultar ${name}.`);
      render(name, target, data, null); return data;
    } catch (error) { render(name, target, null, error.message); return null; }
  }

  async function refreshSystem() {
    const [health, readiness, runtime, system, paper, adaptive, validation] = await Promise.all([
      loadModule('health'), loadModule('readiness'), loadModule('runtime'), loadModule('system'),
      loadModule('paper'), loadModule('adaptive'), loadModule('validation')
    ]);
    loadModule('analytics');
    const databaseOk = readiness?.checks?.database?.ok;
    const missingTables = readiness?.checks?.required_tables?.missing || [];
    document.querySelector('#statusRuntime').textContent = runtime?.running ? 'Analizando automáticamente' : 'Iniciando simulación';
    document.querySelector('#statusMarket').textContent = health ? 'Precios conectados' : 'Sin respuesta';
    document.querySelector('#statusDatabase').textContent = databaseOk === true ? 'Conectada' : databaseOk === false ? (missingTables.length ? 'Faltan tablas' : 'No disponible') : 'Sin confirmar';
    setDot('#statusRuntimeDot', Boolean(runtime?.running)); setDot('#statusMarketDot', Boolean(health)); setDot('#statusDatabaseDot', databaseOk === true);
    document.querySelector('#systemLastUpdated').textContent = new Date().toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    document.querySelector('#overviewPaperState').textContent = runtime?.running ? 'Simulación automática activa' : 'Preparando simulación';
    document.querySelector('#overviewPaperDetail').textContent = 'El sistema analiza precios y puede abrir o cerrar operaciones con dinero simulado.';
    document.querySelector('#overviewStrategyState').textContent = runtime?.last_decision?.action ? `Última decisión: ${String(runtime.last_decision.action).toUpperCase()}` : 'Recopilando datos';
    document.querySelector('#overviewValidationState').textContent = validation?.status === 'idle' ? 'Aprendiendo del historial' : text(validation?.status);
    document.querySelector('#overviewValidationDetail').textContent = 'Las estrategias se evaluarán cuando exista suficiente historial de operaciones.';
  }

  tabs.forEach(tab => tab.addEventListener('click', () => {
    const name = tab.dataset.dashboardTab;
    tabs.forEach(item => item.classList.toggle('active', item === tab));
    panels.forEach(panel => panel.classList.toggle('hidden', panel.dataset.dashboardPanel !== name));
    if (name === 'markets') document.querySelector('#refreshBtn')?.click();
  }));
  document.addEventListener('click', event => {
    const button = event.target.closest('.module-refresh'); if (!button) return;
    const match = Object.entries(endpoints).find(([, value]) => value[0] === button.dataset.moduleEndpoint);
    if (match) loadModule(match[0]);
  });
  refreshSystem(); window.setInterval(refreshSystem, 30000);
})();
