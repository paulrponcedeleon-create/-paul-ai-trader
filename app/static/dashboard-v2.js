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

  const setText = (selector, value) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = value;
  };

  const text = value => {
    if (value === null || value === undefined || value === '') return 'Todavía no hay información';
    if (typeof value === 'boolean') return value ? 'Sí' : 'No';
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
    if (Array.isArray(value)) return value.length ? `${value.length} registro${value.length === 1 ? '' : 's'}` : 'Ninguno todavía';
    if (typeof value === 'object') return 'Disponible';
    return String(value).replaceAll('_', ' ');
  };

  const money = value => Number(value || 0).toLocaleString('es-MX', {style: 'currency', currency: 'MXN', minimumFractionDigits: 2, maximumFractionDigits: 2});
  const metric = (label, value, help = '') => `<div class="module-metric"><span>${label}${help ? `<small class="muted">${help}</small>` : ''}</span><strong>${value}</strong></div>`;

  function friendlyRender(name, data) {
    if (name === 'runtime') {
      const exploration = data.exploration || {};
      const states = Object.values(exploration.states || {});
      const maxHolds = states.length ? Math.max(...states.map(item => Number(item.consecutive_holds || 0))) : 0;
      const lastExperience = exploration.last_experience;
      const lastExperienceText = lastExperience?.book
        ? `${String(lastExperience.action || lastExperience.side || '').toUpperCase()} ${String(lastExperience.book).toUpperCase()}`
        : 'Todavía no hay una experiencia completa';
      return [
        metric('Motor automático', data.running ? 'Trabajando' : 'Iniciando', 'Analiza el mercado y toma decisiones con dinero simulado.'),
        metric('Ciclos completados', text(data.cycles), 'Cada ciclo revisa los activos configurados.'),
        metric('Fuente de precios', data.provider_label || 'Bitso, solo lectura'),
        metric('Tipo de dinero', data.broker_label || 'Dinero simulado'),
        metric('Última decisión', data.last_decision?.action ? String(data.last_decision.action).toUpperCase() : 'Esperando suficientes datos'),
        metric('Experiencia exploratoria autónoma', exploration.enabled ? 'Activa solo en simulación' : 'Desactivada', 'Nunca opera con dinero real y sigue las reglas de riesgo.'),
        metric('HOLD consecutivos', text(maxHolds), `Entrada exploratoria después de ${text(exploration.hold_cycles_before_entry ?? 20)} ciclos.`),
        metric('Experiencias activas', `${text(exploration.active_positions ?? 0)} / ${text(exploration.max_positions ?? 0)}`),
        metric('Intentos exploratorios', text(exploration.attempts ?? 0)),
        metric('Experiencias completadas · Operaciones completas', text(exploration.completed_trades ?? exploration.exits ?? 0), 'Cada operación completa incluye BUY y SELL.'),
        metric('Resultados', `${text(exploration.wins ?? 0)} ganadas · ${text(exploration.losses ?? 0)} perdidas · ${text(exploration.flat ?? 0)} neutras`),
        metric('P&L exploratorio', money(exploration.realized_pnl_mxn ?? 0), 'Separado del rendimiento normal de la estrategia.'),
        metric('Última experiencia', lastExperienceText),
        metric('Último problema', data.last_error ? 'Se detectó un problema y se reintentará' : 'Ninguno')
      ].join('');
    }
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
    if (!endpoints[name]) return null;
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
    setText('#statusRuntime', runtime?.running ? 'Analizando automáticamente' : 'Iniciando simulación');
    setText('#statusMarket', health ? 'Precios conectados' : 'Sin respuesta');
    setText('#statusDatabase', databaseOk === true ? 'Conectada' : databaseOk === false ? (missingTables.length ? 'Faltan tablas' : 'No disponible') : 'Sin confirmar');
    setDot('#statusRuntimeDot', Boolean(runtime?.running)); setDot('#statusMarketDot', Boolean(health)); setDot('#statusDatabaseDot', databaseOk === true);
    setText('#systemLastUpdated', new Date().toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit', second: '2-digit'}));
    setText('#overviewPaperState', runtime?.running ? 'Simulación automática activa' : 'Preparando simulación');
    setText('#overviewPaperDetail', runtime?.exploration?.enabled ? 'Analiza precios y genera operaciones completas de compra y venta simuladas.' : 'El sistema analiza precios y puede abrir o cerrar operaciones con dinero simulado.');
    setText('#overviewStrategyState', runtime?.last_decision?.action ? `Última decisión: ${String(runtime.last_decision.action).toUpperCase()}` : 'Recopilando datos');
    setText('#overviewValidationState', validation?.status === 'idle' ? 'Aprendiendo del historial' : text(validation?.status));
    setText('#overviewValidationDetail', 'Las estrategias se evaluarán cuando exista suficiente historial de operaciones.');
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
