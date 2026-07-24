(() => {
  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const money = value => Number(value || 0).toLocaleString('es-MX', {
    style: 'currency', currency: 'MXN', minimumFractionDigits: 2, maximumFractionDigits: 2
  });

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      cache: 'no-store',
      headers: {'Content-Type': 'application/json', ...(options.headers || {})},
      ...options
    });
    const data = await response.json().catch(() => ({detail: 'Respuesta inválida'}));
    if (!response.ok) throw new Error(data.detail || 'No fue posible completar la solicitud.');
    return data;
  }

  function setupLogin() {
    const card = document.querySelector('#loginCard');
    const loginForm = document.querySelector('#loginForm');
    const password = document.querySelector('#password');
    if (!card || !loginForm || !password || card.classList.contains('hidden')) return;

    loginForm.classList.add('account-login-grid');
    if (!document.querySelector('#username')) {
      const username = document.createElement('input');
      username.id = 'username';
      username.name = 'username';
      username.placeholder = 'Usuario';
      username.autocomplete = 'username';
      username.value = 'paul';
      username.required = true;
      loginForm.insertBefore(username, password);
    }

    const originalIntro = card.querySelector('p:not(.error)');
    if (originalIntro) {
      originalIntro.innerHTML = 'Entra con tu cuenta, crea una nueva o recupera tu contraseña por correo.';
    }

    const switcher = document.createElement('div');
    switcher.className = 'auth-switcher';
    switcher.innerHTML = `
      <button type="button" class="auth-switch active" data-auth-view="login">Iniciar sesión</button>
      <button type="button" class="auth-switch" data-auth-view="register">Crear cuenta</button>
      <button type="button" class="auth-switch" data-auth-view="forgot">Olvidé mi contraseña</button>`;
    card.insertBefore(switcher, loginForm);

    const registerEnabled = card.dataset.registrationEnabled === 'true';
    const registerPanel = document.createElement('div');
    registerPanel.id = 'registerPanel';
    registerPanel.className = 'auth-panel hidden';
    registerPanel.innerHTML = registerEnabled ? `
      <p class="muted">Cada persona recibe $5,000 MXN simulados, su propio historial y su propio Bot/IA.</p>
      <form id="registerForm" class="account-register-grid">
        <input id="registerName" placeholder="Nombre completo" autocomplete="name" required>
        <input id="registerUsername" placeholder="Nombre de usuario" autocomplete="username" required>
        <input id="registerEmail" type="email" placeholder="Correo para recuperar contraseña" autocomplete="email" required>
        <input id="registerPassword" type="password" minlength="8" placeholder="Contraseña, mínimo 8 caracteres" autocomplete="new-password" required>
        <input id="registerCode" type="password" class="full" placeholder="Código de invitación familiar" required>
        <button type="submit">Crear cuenta e iniciar sesión</button>
      </form>
      <p id="registerMessage" class="account-message"></p>` : `
      <p class="account-security-note">La creación de cuentas está desactivada por el administrador.</p>`;
    card.appendChild(registerPanel);

    const forgotPanel = document.createElement('div');
    forgotPanel.id = 'forgotPanel';
    forgotPanel.className = 'auth-panel hidden';
    forgotPanel.innerHTML = `
      <p class="muted">Escribe el correo registrado. Recibirás un enlace de un solo uso para crear una contraseña nueva.</p>
      <form id="forgotForm" class="account-recovery-grid">
        <input id="forgotEmail" type="email" placeholder="Correo electrónico" autocomplete="email" required>
        <button type="submit">Enviar enlace de recuperación</button>
      </form>
      <p id="forgotMessage" class="account-message"></p>`;
    card.appendChild(forgotPanel);

    const resetPanel = document.createElement('div');
    resetPanel.id = 'resetPanel';
    resetPanel.className = 'auth-panel hidden';
    resetPanel.innerHTML = `
      <p class="muted">Crea una contraseña nueva. El enlace solo funciona una vez.</p>
      <form id="resetForm" class="account-recovery-grid">
        <input id="resetPassword" type="password" minlength="8" placeholder="Nueva contraseña" autocomplete="new-password" required>
        <input id="resetPasswordConfirm" type="password" minlength="8" placeholder="Confirma la contraseña" autocomplete="new-password" required>
        <button type="submit">Guardar nueva contraseña</button>
      </form>
      <p id="resetMessage" class="account-message"></p>`;
    card.appendChild(resetPanel);

    const loginError = document.querySelector('#loginError');
    const loginButton = loginForm.querySelector('button[type="submit"]');
    loginForm.addEventListener('submit', async event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (loginButton) { loginButton.disabled = true; loginButton.textContent = 'Entrando…'; }
      if (loginError) loginError.textContent = '';
      try {
        await requestJson('/api/login', {
          method: 'POST',
          body: JSON.stringify({
            username: document.querySelector('#username')?.value || 'paul',
            password: password.value
          })
        });
        location.reload();
      } catch (failure) {
        if (loginError) loginError.textContent = failure.message;
        if (loginButton) { loginButton.disabled = false; loginButton.textContent = 'Entrar'; }
      }
    }, true);

    function showView(view) {
      loginForm.classList.toggle('hidden', view !== 'login');
      if (loginError) loginError.classList.toggle('hidden', view !== 'login');
      registerPanel.classList.toggle('hidden', view !== 'register');
      forgotPanel.classList.toggle('hidden', view !== 'forgot');
      resetPanel.classList.toggle('hidden', view !== 'reset');
      switcher.classList.toggle('hidden', view === 'reset');
      switcher.querySelectorAll('[data-auth-view]').forEach(button => {
        button.classList.toggle('active', button.dataset.authView === view);
      });
    }

    switcher.addEventListener('click', event => {
      const button = event.target.closest('[data-auth-view]');
      if (button) showView(button.dataset.authView);
    });

    document.querySelector('#registerForm')?.addEventListener('submit', async event => {
      event.preventDefault();
      const submit = event.currentTarget.querySelector('button[type="submit"]');
      const message = document.querySelector('#registerMessage');
      submit.disabled = true;
      submit.textContent = 'Creando…';
      message.textContent = '';
      try {
        const result = await requestJson('/api/register', {
          method: 'POST',
          body: JSON.stringify({
            username: document.querySelector('#registerUsername').value,
            display_name: document.querySelector('#registerName').value,
            email: document.querySelector('#registerEmail').value,
            password: document.querySelector('#registerPassword').value,
            registration_code: document.querySelector('#registerCode').value
          })
        });
        message.textContent = result.message || 'Cuenta creada.';
        location.reload();
      } catch (failure) {
        message.textContent = failure.message;
        submit.disabled = false;
        submit.textContent = 'Crear cuenta e iniciar sesión';
      }
    });

    document.querySelector('#forgotForm')?.addEventListener('submit', async event => {
      event.preventDefault();
      const submit = event.currentTarget.querySelector('button[type="submit"]');
      const message = document.querySelector('#forgotMessage');
      submit.disabled = true;
      submit.textContent = 'Enviando…';
      message.textContent = '';
      try {
        const result = await requestJson('/api/password/forgot', {
          method: 'POST',
          body: JSON.stringify({email: document.querySelector('#forgotEmail').value})
        });
        message.textContent = result.message;
        event.currentTarget.reset();
      } catch (failure) {
        message.textContent = failure.message;
      } finally {
        submit.disabled = false;
        submit.textContent = 'Enviar enlace de recuperación';
      }
    });

    const resetToken = new URLSearchParams(location.search).get('reset_token');
    document.querySelector('#resetForm')?.addEventListener('submit', async event => {
      event.preventDefault();
      const submit = event.currentTarget.querySelector('button[type="submit"]');
      const message = document.querySelector('#resetMessage');
      const newPassword = document.querySelector('#resetPassword').value;
      const confirmation = document.querySelector('#resetPasswordConfirm').value;
      if (newPassword !== confirmation) {
        message.textContent = 'Las contraseñas no coinciden.';
        return;
      }
      submit.disabled = true;
      submit.textContent = 'Guardando…';
      message.textContent = '';
      try {
        const result = await requestJson('/api/password/reset', {
          method: 'POST',
          body: JSON.stringify({token: resetToken, password: newPassword})
        });
        message.textContent = result.message;
        history.replaceState({}, document.title, location.pathname);
        event.currentTarget.reset();
        window.setTimeout(() => showView('login'), 1000);
      } catch (failure) {
        message.textContent = failure.message;
      } finally {
        submit.disabled = false;
        submit.textContent = 'Guardar nueva contraseña';
      }
    });

    showView(resetToken ? 'reset' : 'login');
  }

  function injectAccountPanel() {
    const appContent = document.querySelector('#appContent');
    const tabs = document.querySelector('.workspace-tabs');
    if (!appContent || appContent.classList.contains('hidden') || !tabs) return false;
    if (!document.querySelector('[data-dashboard-tab="account"]')) {
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'workspace-tab';
      tab.dataset.dashboardTab = 'account';
      tab.textContent = 'Cuenta';
      tabs.appendChild(tab);
    }
    if (!document.querySelector('[data-dashboard-panel="account"]')) {
      const panel = document.createElement('div');
      panel.dataset.dashboardPanel = 'account';
      panel.className = 'hidden';
      panel.innerHTML = '<section class="card"><p>Consultando tu cuenta…</p></section>';
      const dialog = appContent.querySelector('dialog');
      if (dialog) dialog.insertAdjacentElement('beforebegin', panel);
      else appContent.appendChild(panel);
    }
    return true;
  }

  function renderHeader(account) {
    const headerActions = document.querySelector('header .section-title');
    if (!headerActions || document.querySelector('#accountUserChip')) return;
    const chip = document.createElement('span');
    chip.id = 'accountUserChip';
    chip.className = 'account-user-chip';
    chip.innerHTML = `<strong>${esc(account.display_name)}</strong><small>@${esc(account.username)}</small>`;
    headerActions.insertBefore(chip, headerActions.querySelector('#logoutBtn'));
  }

  function switchRow(id, title, help, checked) {
    return `<label class="account-switch"><span><strong>${title}</strong><small>${help}</small></span><input id="${id}" type="checkbox" ${checked ? 'checked' : ''}></label>`;
  }

  function renderAccount(account, community = null, users = null) {
    const panel = document.querySelector('[data-dashboard-panel="account"]');
    if (!panel) return;
    const simulation = account.simulation || {};
    const bitso = account.bitso || {};
    panel.innerHTML = `
      <section class="account-grid">
        <article class="card account-card">
          <p class="eyebrow">MI CUENTA</p><h2>${esc(account.display_name)} · @${esc(account.username)}</h2>
          <p class="muted">${account.email ? esc(account.email) : 'Agrega OWNER_EMAIL en Render para recuperar la contraseña de esta cuenta.'}</p>
          <div class="account-stat-grid">
            <div class="account-stat"><span>Capital inicial</span><strong>${money(account.simulated_initial_capital_mxn)}</strong></div>
            <div class="account-stat"><span>Efectivo disponible</span><strong>${money(simulation.available_cash_mxn)}</strong></div>
            <div class="account-stat"><span>Posiciones abiertas</span><strong>${Number(simulation.open_positions || 0)}</strong></div>
            <div class="account-stat"><span>Operaciones cerradas</span><strong>${Number(simulation.closed_positions || 0)}</strong></div>
          </div>
          <p class="muted">Este capital, posiciones e historial son independientes de todos los demás usuarios.</p>
        </article>

        <article class="card account-card">
          <p class="eyebrow">AUTOMATIZACIÓN</p><h2>Bot e IA de esta cuenta</h2>
          <div class="account-switch-list">
            ${switchRow('accountBotEnabled', 'Bot automático', 'Analiza y compra/vende únicamente en esta simulación.', account.bot_enabled)}
            ${switchRow('accountAiEnabled', 'IA exploratoria', 'Hace experiencias pequeñas después de rachas HOLD.', account.ai_exploration_enabled)}
            ${switchRow('accountSharedLearning', 'Aprendizaje comunitario', 'Comparte métricas anónimas, nunca usuario ni claves.', account.shared_learning_enabled)}
          </div>
          <p id="accountPreferenceMessage" class="account-message"></p>
        </article>

        <article class="card account-card">
          <p class="eyebrow">BITSO OPCIONAL</p><h2>${bitso.connected ? 'Cuenta conectada' : 'Conectar Bitso'}</h2>
          <p class="account-security-note">La simulación y el bot funcionan sin Bitso privado. Esta app usa las credenciales guardadas solo para consultar información; crea una API sin retiros y preferentemente de solo lectura.</p>
          <form id="accountBitsoForm" class="account-bitso-grid">
            <input id="accountBitsoKey" autocomplete="off" placeholder="API key" required>
            <input id="accountBitsoSecret" type="password" autocomplete="new-password" placeholder="API secret" required>
            <button type="submit">Validar y guardar cifrado</button>
          </form>
          <div class="account-login-actions">
            <button type="button" class="secondary" id="accountBitsoBalance" ${bitso.connected ? '' : 'disabled'}>Consultar saldo</button>
            <button type="button" class="secondary" id="accountBitsoDisconnect" ${bitso.connected ? '' : 'disabled'}>Desconectar</button>
          </div>
          <p id="accountBitsoMessage" class="account-message">${bitso.connected ? 'Las claves están cifradas y no se vuelven a mostrar.' : 'No es obligatorio conectarlo.'}</p>
        </article>

        <article class="card account-card">
          <p class="eyebrow">APRENDIZAJE GLOBAL</p><h2>Experiencia compartida</h2>
          <div class="account-stat-grid">
            <div class="account-stat"><span>Participantes</span><strong>${Number(community?.participants || 0)}</strong></div>
            <div class="account-stat"><span>Resultados agregados</span><strong>${Number(community?.learning_sources?.completed_result_samples || 0)}</strong></div>
          </div>
          <p class="muted">Cada usuario aprende de su propio historial. El aprendizaje comunitario agrega patrones anónimos para mejorar las propuestas generales, sin mezclar portafolios.</p>
          ${account.is_admin ? `<div class="account-users"><h3>Usuarios activos</h3>${(users?.items || []).map(user => `<div class="account-user-row"><span><strong>${esc(user.display_name)}</strong><small>@${esc(user.username)}${user.email ? ` · ${esc(user.email)}` : ''}</small></span><small>${user.bot_enabled ? 'Bot activo' : 'Bot pausado'}</small></div>`).join('') || '<p>Solo está la cuenta principal.</p>'}</div>` : ''}
        </article>
      </section>`;
    bindAccountControls();
  }

  async function savePreference(field, value) {
    const message = document.querySelector('#accountPreferenceMessage');
    if (message) message.textContent = 'Aplicando…';
    try {
      await requestJson('/api/account/preferences', {
        method: 'PATCH',
        body: JSON.stringify({[field]: value})
      });
      if (message) message.textContent = 'Configuración guardada para esta cuenta.';
      window.setTimeout(loadAccount, 400);
    } catch (failure) {
      if (message) message.textContent = failure.message;
      window.setTimeout(loadAccount, 700);
    }
  }

  function bindAccountControls() {
    document.querySelector('#accountBotEnabled')?.addEventListener('change', event => savePreference('bot_enabled', event.target.checked));
    document.querySelector('#accountAiEnabled')?.addEventListener('change', event => savePreference('ai_exploration_enabled', event.target.checked));
    document.querySelector('#accountSharedLearning')?.addEventListener('change', event => savePreference('shared_learning_enabled', event.target.checked));

    document.querySelector('#accountBitsoForm')?.addEventListener('submit', async event => {
      event.preventDefault();
      const message = document.querySelector('#accountBitsoMessage');
      const submit = event.currentTarget.querySelector('button[type="submit"]');
      submit.disabled = true;
      submit.textContent = 'Validando con Bitso…';
      message.textContent = '';
      try {
        const result = await requestJson('/api/account/bitso', {
          method: 'POST',
          body: JSON.stringify({
            api_key: document.querySelector('#accountBitsoKey').value,
            api_secret: document.querySelector('#accountBitsoSecret').value
          })
        });
        document.querySelector('#accountBitsoKey').value = '';
        document.querySelector('#accountBitsoSecret').value = '';
        message.textContent = result.message;
        window.setTimeout(loadAccount, 500);
      } catch (failure) {
        message.textContent = failure.message;
        submit.disabled = false;
        submit.textContent = 'Validar y guardar cifrado';
      }
    });

    document.querySelector('#accountBitsoDisconnect')?.addEventListener('click', async () => {
      const message = document.querySelector('#accountBitsoMessage');
      try {
        await requestJson('/api/account/bitso', {method: 'DELETE'});
        message.textContent = 'Bitso fue desconectado de esta cuenta.';
        window.setTimeout(loadAccount, 400);
      } catch (failure) { message.textContent = failure.message; }
    });

    document.querySelector('#accountBitsoBalance')?.addEventListener('click', async () => {
      const message = document.querySelector('#accountBitsoMessage');
      message.textContent = 'Consultando Bitso…';
      try {
        const result = await requestJson('/api/account/bitso/balance');
        const balances = result.payload?.payload?.balances || result.payload?.balances || [];
        message.textContent = `Conexión correcta · ${balances.length} saldos recibidos desde Bitso.`;
      } catch (failure) { message.textContent = failure.message; }
    });
  }

  async function loadAccount() {
    try {
      const account = await requestJson('/api/account');
      const [community, users] = await Promise.all([
        requestJson('/api/learning/community').catch(() => null),
        account.is_admin ? requestJson('/api/users').catch(() => null) : Promise.resolve(null)
      ]);
      renderHeader(account);
      renderAccount(account, community, users);
    } catch (failure) {
      const panel = document.querySelector('[data-dashboard-panel="account"]');
      if (panel) panel.innerHTML = `<section class="card"><p class="error">${esc(failure.message)}</p></section>`;
    }
  }

  setupLogin();
  if (injectAccountPanel()) loadAccount();
})();
