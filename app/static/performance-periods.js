(() => {
  const content = document.querySelector("#performanceContent");
  if (!content || content.classList.contains("hidden")) return;

  const money = value => Number(value || 0).toLocaleString("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });

  const pnlClass = value => {
    const number = Number(value || 0);
    if (number > 0) return "positive";
    if (number < 0) return "negative";
    return "neutral";
  };

  function selectedBooks() {
    return [...document.querySelectorAll('input[name="performanceBook"]:checked')]
      .map(input => input.value);
  }

  function ensureCards() {
    if (document.querySelector("#periodQuickSummary")) return;
    const filters = document.querySelector(".filters-card");
    if (!filters) return;
    const section = document.createElement("section");
    section.id = "periodQuickSummary";
    section.className = "summary-grid performance-summary";
    section.setAttribute("aria-label", "Resumen rápido por periodo");
    section.innerHTML = [
      ["day", "Hoy"],
      ["week", "Semana"],
      ["month", "Mes"]
    ].map(([key, label]) => `
      <article class="card metric">
        <span>${label}</span>
        <strong id="quick-${key}-pnl">$0.00</strong>
        <small id="quick-${key}-detail">Consultando…</small>
      </article>`).join("");
    filters.insertAdjacentElement("afterend", section);
  }

  function ensureSourceComparison() {
    if (document.querySelector("#sourceComparison")) return;
    const quick = document.querySelector("#periodQuickSummary");
    if (!quick) return;
    const wrapper = document.createElement("section");
    wrapper.id = "sourceComparison";
    wrapper.className = "source-comparison";
    wrapper.innerHTML = `
      <div class="section-title source-comparison-title">
        <div>
          <p class="eyebrow">MANUAL VS BOT / IA</p>
          <h2>Comparación del mes actual</h2>
          <p class="muted">El origen de cada posición permanece guardado aunque otra fuente la cierre.</p>
        </div>
      </div>
      <div class="summary-grid source-summary-grid">
        <article class="card metric source-card source-manual">
          <span>Tus operaciones manuales</span>
          <strong id="source-manual-pnl">$0.00</strong>
          <small id="source-manual-detail">Sin operaciones cerradas.</small>
        </article>
        <article class="card metric source-card source-bot">
          <span>Bot + IA</span>
          <strong id="source-bot-pnl">$0.00</strong>
          <small id="source-bot-detail">Sin operaciones cerradas.</small>
        </article>
        <article class="card metric source-card source-learning">
          <span>Datos para aprendizaje</span>
          <strong id="source-learning-count">0</strong>
          <small id="source-learning-detail">Manual y bot se conservan separados.</small>
        </article>
      </div>`;
    quick.insertAdjacentElement("afterend", wrapper);
  }

  function renderPeriod(key, data) {
    const amount = document.querySelector(`#quick-${key}-pnl`);
    const detail = document.querySelector(`#quick-${key}-detail`);
    if (!amount || !detail) return;
    amount.textContent = `${Number(data.realized_pnl_mxn || 0) > 0 ? "+" : ""}${money(data.realized_pnl_mxn)}`;
    amount.className = pnlClass(data.realized_pnl_mxn);
    detail.textContent = `${data.trades} operaciones · ${Number(data.win_rate_pct || 0).toFixed(2)}% aciertos · ${money(data.fees_mxn)} comisiones`;
  }

  function sourceItem(period, source) {
    return (period.by_source || []).find(item => item.source === source) || {trades: 0};
  }

  function renderSourceComparison(period) {
    ensureSourceComparison();
    const manual = period.comparison?.manual || {trades: 0, realized_pnl_mxn: 0, win_rate_pct: 0};
    const bot = period.comparison?.bot || {trades: 0, realized_pnl_mxn: 0, win_rate_pct: 0};
    const runtime = sourceItem(period, "runtime");
    const exploration = sourceItem(period, "exploration");
    const learning = period.learning || {};

    const manualPnl = document.querySelector("#source-manual-pnl");
    const botPnl = document.querySelector("#source-bot-pnl");
    if (manualPnl) {
      manualPnl.textContent = `${Number(manual.realized_pnl_mxn || 0) > 0 ? "+" : ""}${money(manual.realized_pnl_mxn)}`;
      manualPnl.className = pnlClass(manual.realized_pnl_mxn);
    }
    if (botPnl) {
      botPnl.textContent = `${Number(bot.realized_pnl_mxn || 0) > 0 ? "+" : ""}${money(bot.realized_pnl_mxn)}`;
      botPnl.className = pnlClass(bot.realized_pnl_mxn);
    }
    const manualDetail = document.querySelector("#source-manual-detail");
    const botDetail = document.querySelector("#source-bot-detail");
    const learningCount = document.querySelector("#source-learning-count");
    const learningDetail = document.querySelector("#source-learning-detail");
    if (manualDetail) manualDetail.textContent = `${manual.trades || 0} cerradas · ${Number(manual.win_rate_pct || 0).toFixed(2)}% aciertos`;
    if (botDetail) botDetail.textContent = `${bot.trades || 0} cerradas · ${runtime.trades || 0} bot · ${exploration.trades || 0} IA`;
    if (learningCount) learningCount.textContent = String(learning.samples || 0);
    if (learningDetail) learningDetail.textContent = `${learning.manual_samples || 0} manuales + ${learning.bot_samples || 0} del bot/IA; ambas fuentes aprenden sin perder su etiqueta.`;
  }

  async function loadQuickSummary() {
    ensureCards();
    ensureSourceComparison();
    const params = new URLSearchParams({
      timezone: "America/Ciudad_Juarez",
      ts: String(Date.now())
    });
    const books = selectedBooks();
    if (books.length) params.set("books", books.join(","));

    try {
      const response = await fetch(`/api/performance/summary?${params.toString()}`, {
        cache: "no-store",
        headers: {
          "Cache-Control": "no-cache",
          "Pragma": "no-cache"
        }
      });
      const payload = await response.json().catch(() => ({detail: "Respuesta inválida"}));
      if (!response.ok) throw new Error(payload.detail || "No fue posible calcular el resumen.");
      renderPeriod("day", payload.periods.day);
      renderPeriod("week", payload.periods.week);
      renderPeriod("month", payload.periods.month);
      renderSourceComparison(payload.periods.month);
    } catch (error) {
      ["day", "week", "month"].forEach(key => {
        const detail = document.querySelector(`#quick-${key}-detail`);
        if (detail) detail.textContent = error.message;
      });
      const learningDetail = document.querySelector("#source-learning-detail");
      if (learningDetail) learningDetail.textContent = error.message;
    }
  }

  ensureCards();
  ensureSourceComparison();
  loadQuickSummary();
  document.querySelector("#performanceFilters")?.addEventListener("submit", () => {
    window.setTimeout(loadQuickSummary, 0);
  });
  window.setInterval(loadQuickSummary, 60000);
})();
