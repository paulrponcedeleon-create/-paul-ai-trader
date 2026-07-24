(() => {
  const tabs = [...document.querySelectorAll('[data-dashboard-tab]')];
  const panels = [...document.querySelectorAll('[data-dashboard-panel]')];
  if (!tabs.length || !panels.length) return;

  const endpoints = {
    health: ['/health', '#healthModule'],
    readiness: ['/ready', '#readinessModule'],
    runtime: ['/runtime/status', '#runtimeModule'],
    system: ['/system/status', '#systemModule'],
    paper: ['/paper/status', '#paperModule'],
    adaptive: ['/adaptive/status', '#strategiesModule'],
    validation: ['/validation/status', '#validationModule']
  };

  const sourceLabels = {
    manual: 'Manual · Paul',
    runtime: 'Bot · estrategia',
    exploration: 'IA exploratoria'
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

  const money = value => Number(value || 0).toLocaleString('es-MX', {
    style: 'currency', currency: 'MXN', minimumFractionDigits: 2, maximumFractionDigits: 2
  });
  const signedMoney = value => `${Number(value || 0) > 0 ? '+' : ''}${money(value)}`;
  const metric = (label, value, help = '', className = '') =>
    `<div class="module-metric ${className}"><span>${label}${help ? `<small class="muted">${help}</small>` : ''}</span><strong>${value}</strong></div>`;

  const startupLabel = state => ({
    automatic_running: 'Iniciado automáticamente',
    manual_running: 'Iniciado manualmente',
    disabled: 'Desactivado por configuración',
    test_disabled: 'Desactivado en pruebas',
    blocked_live_mode: 'Bloqueado en modo real',
    blocked_non_paper_broker: 'Bloqueado: broker no paper',
    stopped: 'Detenido',
    error: 'Error de arranque'
  }[state] || 'Esperando arranque');

  function sourceRow(learning, source) {
    return (learning?.by_source || []).find(item => item.source === source) || {
      source,
      source_label: sourceLabels[source],
      open_positions: 0,
      closed_positions: 0,
      realized_pnl_mxn: 0,
      wins: 0,
      losses: 0,
      win_rate_pct: 0
    };
  }

  function openPnlBySource(positions) {
    const result = {
      manual: {open: 0, pnl: 0},
      runtime: {open: 0, pnl: 0},
      exploration: {open: 0, pnl: 0}
    };
    (positions?.items || []).forEach(position => {
      const source = Object.hasOwn(result, position.source) ? position.source : 'manual';
      result[source].open += 1;
      result[source].pnl += Number(position.unrealized_pnl_mxn || 0);
    });
    return result;
  }

  function renderDecisionPanel(runtime, adaptive) {
    const node = document.querySelector('#strategiesModule');
    if (!node) return;
    const brains = Object.values(runtime?.asset_brains || {});
    const lastBrain = brains.find(item => item.last_action && item.last_action !== 'hold') || brains[0];
    const strategy = runtime?.last_decision?.strategy || lastBrain?.last_strategy || 'momentum';
    const regime = runtime?.last_decision?.regime || runtime?.last_decision?.market_regime || 'Aún no clasificado';
    const counts = runtime?.decision_counts || {};
    const profiles = adaptive?.profiles || adaptive?.registry_size || 0;
    node.innerHTML = [
      metric('Motor', runtime?.running ? 'Operando en simulación' : 'No está ejecutando ciclos', 'Estado real del Runtime.'),
      metric('Estrategia activa', String(strategy).replaceAll('_', ' '), 'La que produjo las decisiones más recientes.'),
      metric('Régimen detectado', String(regime).replaceAll('_', ' '), 'Aparecerá cuando exista historial suficiente.'),
      metric('Activos listos', text(runtime?.books_ready || []), (runtime?.books_ready || []).map(book => String(book).toUpperCase()).join(', ')),
      metric('Observaciones del mercado', text(runtime?.observations || 0), 'Lecturas usadas por el motor, no son operaciones.'),
      metric('Decisiones', `${counts.buy || 0} BUY · ${counts.sell || 0} SELL · ${counts.hold || 0} HOLD`),
      metric('Perfiles candidatos', text(profiles), profiles ? 'Estrategias disponibles para comparación.' : 'Todavía no hay perfiles alternativos validados.'),
      metric('Última acción', runtime?.last_decision?.action ? String(runtime.last_decision.action).toUpperCase() : 'Esperando decisión')
    ].join('');
  }

  function renderSourcePerformance(validation, positions) {
    const node = document.querySelector('#analyticsModule');
    if (!node) return;
    const learning = validation?.learning_sources || {};
    const openPnl = openPnlBySource(positions);
    const blocks = ['manual', 'runtime', 'exploration'].map(source => {
      const row = sourceRow(learning, source);
      const open = openPnl[source];
      return `
        <section class="source-result-block source-result-${source}">
          <h3>${row.source_label || sourceLabels[source]}</h3>
          <div class="source-result-grid">
            ${metric('Abiertas', open.open, `${signedMoney(open.pnl)} P&L flotante`)}
            ${metric('Cerradas', row.closed_positions || 0, 'Resultados que ya cuentan para aprendizaje')}
            ${metric('P&L realizado', signedMoney(row.realized_pnl_mxn), `${row.wins || 0} ganadas · ${row.losses || 0} perdidas`)}
            ${metric('Aciertos', `${Number(row.win_rate_pct || 0).toFixed(2)}%`, 'Solo operaciones cerradas con resultado definido')}
          </div>
        </section>`;
    });
    const manual = learning.comparison?.manual || {};
    const bot = learning.comparison?.bot || {};
    node.innerHTML = `
      <div class="source-result-summary">
        ${metric('Manual · cerradas', manual.closed_positions || 0, signedMoney(manual.realized_pnl_mxn))}
        ${metric('Bot + IA · cerradas', bot.closed_positions || 0, signedMoney(bot.realized_pnl_mxn))}
        ${metric('En seguimiento', learning.active_tracking_samples || 0, 'Posiciones abiertas; todavía no son ganancia o pérdida final')}
        ${metric('Resultados aprendidos', learning.completed_result_samples || 0, 'Operaciones cerradas con origen conservado')}
      </div>
      ${blocks.join('')}`;
  }

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
        metric('Arranque después de despliegue', startupLabel(data.startup_state), data.startup_error || 'Se recupera solo cuando Render inicia o vuelve a desplegar.'),
        metric('Proceso en segundo plano', data.background_task_active ? 'Activo' : 'No activo'),
        metric('Ciclos completados', text(data.cycles), 'Cada ciclo revisa los activos configurados.'),
        metric('Observaciones', text(data.observations || 0), 'Lecturas del mercado; no confundir con operaciones.'),
        metric('Posiciones abiertas', text(data.open_positions || 0)),
        metric('Operaciones cerradas', text(data.closed_trades || 0)),
        metric('P&L realizado del Runtime', signedMoney(data.realized_pnl_mxn || 0)),
        metric('P&L flotante del Runtime', signedMoney(data.unrealized_pnl_mxn || 0)),
        metric('Experiencia exploratoria autónoma', exploration.enabled ? 'Activa solo en simulación' : 'Desactivada'),
        metric('HOLD consecutivos', text(maxHolds), `Entrada exploratoria después de ${text(exploration.hold_cycles_before_entry ?? 20)} ciclos.`),
        metric('Experiencias activas', `${text(exploration.active_positions ?? 0)} / ${text(exploration.max_positions ?? 0)}`),
        metric('Experiencias cerradas', text(exploration.completed_trades ?? exploration.exits ?? 0)),
        metric('P&L exploratorio', signedMoney(exploration.realized_pnl_mxn ?? 0)),
        metric('Última experiencia', lastExperienceText)
      ].join('');
    }
    if (name === 'validation') {
      const learning = data.learning_sources || {};
      const progress = learning.learning_progress || {};
      const manual = sourceRow(learning, 'manual');
      const runtime = sourceRow(learning, 'runtime');
      const exploration = sourceRow(learning, 'exploration');
      return [
        metric('Estado', data.status === 'idle' ? 'Recolectando resultados reales' : text(data.status), 'No inventa operaciones para llenar métricas.'),
        metric('Posiciones abiertas en seguimiento', text(learning.active_tracking_samples || 0), 'Aportan contexto, pero todavía no cuentan como victoria o derrota.'),
        metric('Operaciones cerradas aprendidas', text(learning.completed_result_samples || 0), 'Resultados completos BUY + SELL.'),
        metric('Manual · Paul', `${manual.open_positions || 0} abiertas · ${manual.closed_positions || 0} cerradas`, signedMoney(manual.realized_pnl_mxn)),
        metric('Bot · estrategia', `${runtime.open_positions || 0} abiertas · ${runtime.closed_positions || 0} cerradas`, signedMoney(runtime.realized_pnl_mxn)),
        metric('IA exploratoria', `${exploration.open_positions || 0} abiertas · ${exploration.closed_positions || 0} cerradas`, signedMoney(exploration.realized_pnl_mxn)),
        metric('Progreso inicial', `${Number(progress.percent || 0).toFixed(2)}%`, `${progress.completed_results || 0} de ${progress.minimum_results || 100} resultados cerrados`),
        metric('Regla de atribución', learning.source_is_preserved ? 'Origen conservado' : 'Requiere revisión', 'Cerrar manualmente una posición del bot no la convierte en manual.')
      ].join('');
    }
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
    node.innerHTML = rows.length
      ? rows.map(([label, value]) => metric(label.replaceAll('_', ' '), text(value))).join('')
      : '<p class="module-message">Conectado. Todavía no hay información suficiente.</p>';
  }

  function setDot(id, ok) {
    const dot = document.querySelector(id); if (!dot) return;
    dot.classList.remove('pending', 'ok', 'error'); dot.classList.add(ok ? 'ok' : 'error');
  }

  async function requestJson(url) {
    const response = await fetch(`${url}${url.includes('?') ? '&' : '?'}ts=${Date.now()}`, {cache: 'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `No se pudo consultar ${url}.`);
    return data;
  }

  async function loadModule(name) {
    if (!endpoints[name]) return null;
    const [url, target] = endpoints[name];
    try {
      const data = await requestJson(url);
      render(name, target, data, null);
      return data;
    } catch (error) {
      render(name, target, null, error.message);
      return null;
    }
  }

  async function refreshSystem() {
    const [health, readiness, runtime, system, paper, adaptive, validation, positions] = await Promise.all([
      loadModule('health'), loadModule('readiness'), loadModule('runtime'), loadModule('system'),
      loadModule('paper'), loadModule('adaptive'), loadModule('validation'),
      requestJson('/api/positions').catch(() => ({items: [], summary: {}}))
    ]);
    renderDecisionPanel(runtime || {}, adaptive || {});
    renderSourcePerformance(validation || {}, positions || {});

    const databaseOk = readiness?.checks?.database?.ok;
    const missingTables = readiness?.checks?.required_tables?.missing || [];
    setText('#statusRuntime', runtime?.running ? 'Analizando automáticamente' : (runtime?.startup_state === 'error' ? 'Error de arranque' : 'Iniciando simulación'));
    setText('#statusMarket', health ? 'Precios conectados' : 'Sin respuesta');
    setText('#statusDatabase', databaseOk === true ? 'Conectada' : databaseOk === false ? (missingTables.length ? 'Faltan tablas' : 'No disponible') : 'Sin confirmar');
    setDot('#statusRuntimeDot', Boolean(runtime?.running));
    setDot('#statusMarketDot', Boolean(health));
    setDot('#statusDatabaseDot', databaseOk === true);
    setText('#systemLastUpdated', new Date().toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit', second: '2-digit'}));
    setText('#overviewPaperState', runtime?.running ? 'Simulación automática activa' : 'Preparando simulación');
    setText('#overviewPaperDetail', runtime?.exploration?.enabled ? 'Analiza precios y genera operaciones manuales, del bot y de IA con origen separado.' : 'El sistema analiza precios y puede abrir o cerrar operaciones con dinero simulado.');
    setText('#overviewStrategyState', runtime?.last_decision?.action ? `Última decisión: ${String(runtime.last_decision.action).toUpperCase()}` : 'Recopilando datos');
    const learning = validation?.learning_sources || {};
    setText('#overviewValidationState', `${learning.completed_result_samples || 0} resultados aprendidos`);
    setText('#overviewValidationDetail', `${learning.active_tracking_samples || 0} posiciones abiertas en seguimiento; Manual, Bot e IA se conservan separados.`);
  }

  tabs.forEach(tab => tab.addEventListener('click', () => {
    const name = tab.dataset.dashboardTab;
    tabs.forEach(item => item.classList.toggle('active', item === tab));
    panels.forEach(panel => panel.classList.toggle('hidden', panel.dataset.dashboardPanel !== name));
    if (name === 'markets') document.querySelector('#refreshBtn')?.click();
    if (name === 'strategies' || name === 'validation') refreshSystem();
  }));

  document.addEventListener('click', event => {
    const button = event.target.closest('.module-refresh');
    if (!button) return;
    if (['/adaptive/status', '/analytics/performance', '/validation/status'].includes(button.dataset.moduleEndpoint)) {
      refreshSystem();
      return;
    }
    const match = Object.entries(endpoints).find(([, value]) => value[0] === button.dataset.moduleEndpoint);
    if (match) loadModule(match[0]);
  });

  refreshSystem();
  window.setInterval(refreshSystem, 30000);
})();
