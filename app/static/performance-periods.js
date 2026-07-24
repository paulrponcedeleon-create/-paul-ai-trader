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

  function renderPeriod(key, data) {
    const amount = document.querySelector(`#quick-${key}-pnl`);
    const detail = document.querySelector(`#quick-${key}-detail`);
    if (!amount || !detail) return;
    amount.textContent = `${Number(data.realized_pnl_mxn || 0) > 0 ? "+" : ""}${money(data.realized_pnl_mxn)}`;
    amount.className = pnlClass(data.realized_pnl_mxn);
    detail.textContent = `${data.trades} operaciones · ${Number(data.win_rate_pct || 0).toFixed(2)}% aciertos · ${money(data.fees_mxn)} comisiones`;
  }

  async function loadQuickSummary() {
    ensureCards();
    const params = new URLSearchParams({
      timezone: "America/Chihuahua",
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
    } catch (error) {
      ["day", "week", "month"].forEach(key => {
        const detail = document.querySelector(`#quick-${key}-detail`);
        if (detail) detail.textContent = error.message;
      });
    }
  }

  ensureCards();
  loadQuickSummary();
  document.querySelector("#performanceFilters")?.addEventListener("submit", () => {
    window.setTimeout(loadQuickSummary, 0);
  });
  window.setInterval(loadQuickSummary, 60000);
})();
