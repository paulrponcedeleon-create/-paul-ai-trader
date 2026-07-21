(() => {
  const firstMetric = document.querySelector(".summary-grid .metric:first-child");
  const amountInput = document.querySelector("#orderAmount");
  const submitButton = document.querySelector('#orderForm button[type="submit"]');
  if (!firstMetric) return;

  const label = firstMetric.querySelector("span");
  const value = firstMetric.querySelector("strong");
  const note = firstMetric.querySelector("small");
  let availableCash = 0;

  function money(number) {
    return Number(number || 0).toLocaleString("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function validateAmount() {
    if (!amountInput || !submitButton) return;
    const requested = Number(amountInput.value || 0);
    const insufficient = requested > availableCash + 0.000001;
    amountInput.setCustomValidity(insufficient ? `Saldo disponible: ${money(availableCash)}` : "");
    submitButton.disabled = insufficient || requested <= 0;
  }

  async function refreshCapital() {
    try {
      const response = await fetch(`/api/capital?ts=${Date.now()}`, {
        cache: "no-store",
        headers: {"Cache-Control": "no-cache", "Pragma": "no-cache"}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No se pudo cargar el saldo");
      availableCash = Number(data.available_cash_mxn || 0);
      label.textContent = "Efectivo disponible";
      value.textContent = money(availableCash);
      note.textContent = `Capital inicial ${money(data.initial_capital_mxn)} · realizado ${money(data.realized_pnl_mxn)}`;
      if (amountInput) amountInput.max = String(Math.max(0, availableCash));
      validateAmount();
    } catch (_) {
      note.textContent = "Saldo temporalmente no disponible";
    }
  }

  amountInput?.addEventListener("input", validateAmount);
  window.addEventListener("focus", refreshCapital);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshCapital();
  });
  refreshCapital();
  window.setInterval(refreshCapital, 5000);
})();
