(() => {
  const ORDER_LIMIT = 10;
  const REFRESH_MS = 5000;
  let loading = false;
  let timer = null;
  let selectedPartialPosition = null;

  const money = value => Number(value || 0).toLocaleString("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });

  const price = value => Number(value || 0).toLocaleString("es-MX", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });

  const symbol = book => String(book || "").replace(/_mxn$|_cash$/i, "").toUpperCase();

  const sourceLabel = source => ({
    manual: "Manual",
    runtime: "Bot automático",
    automatic_exit: "Salida automática",
    history: "Histórico migrado"
  }[source] || source || "Sistema");

  const reasonLabel = reason => ({
    manual_close: "Cierre manual",
    manual_partial_close: "Venta parcial manual",
    strategy_buy: "Señal de compra",
    strategy_sell: "Señal de venta",
    stop_loss: "Stop-loss",
    take_profit: "Take-profit",
    trailing_stop: "Trailing stop",
    expired: "Expiración",
    historical_buy: "Compra histórica",
    historical_close: "Venta histórica"
  }[reason] || reason || "Ejecución simulada");

  const pnlClass = value => {
    const number = Number(value || 0);
    if (number > 0) return "positive";
    if (number < 0) return "negative";
    return "neutral";
  };

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        ...(options.headers || {})
      },
      ...options
    });
    const data = await response.json().catch(() => ({detail: "Respuesta inválida"}));
    if (!response.ok) throw new Error(data.detail || "Error");
    return data;
  }

  function render(items) {
    const container = document.querySelector("#orderEvents");
    if (!container) return;
    if (!items.length) {
      container.innerHTML = "<p>Sin órdenes BUY o SELL todavía.</p>";
      return;
    }
    container.innerHTML = items.map(item => {
      const side = String(item.side || "").toLowerCase();
      const pnl = item.realized_pnl_mxn;
      const pnlText = pnl == null
        ? `Comisión ${money(item.fee_mxn)}`
        : `P&L ${Number(pnl) > 0 ? "+" : ""}${money(pnl)}`;
      return `
        <article class="order-event-row">
          <span class="order-event-side ${side}">${side === "sell" ? "SELL" : "BUY"}</span>
          <div class="order-event-main">
            <strong>${symbol(item.book)} · ${sourceLabel(item.source)}</strong>
            <small>${reasonLabel(item.reason)} · ${new Date(item.created_at).toLocaleString("es-MX")}</small>
          </div>
          <div class="order-event-values">
            <strong>${money(item.amount_mxn)} @ ${price(item.price)}</strong>
            <small class="order-event-pnl ${pnlClass(pnl)}">${pnlText}</small>
          </div>
        </article>`;
    }).join("");
  }

  async function loadOrders() {
    if (loading || document.hidden) return;
    const container = document.querySelector("#orderEvents");
    if (!container) return;
    loading = true;
    try {
      const data = await requestJson(`/api/orders?limit=${ORDER_LIMIT}&offset=0&ts=${Date.now()}`);
      render(data.items || []);
      const meta = document.querySelector("#orderEventsMeta");
      if (meta) {
        const shown = Math.min((data.items || []).length, data.total || 0);
        meta.textContent = data.total
          ? `Mostrando ${shown} de ${data.total} órdenes · actualizado ${new Date(data.updated_at).toLocaleTimeString("es-MX")}`
          : "Esperando la primera orden simulada";
      }
    } catch (error) {
      container.innerHTML = `<p class="error">${error.message}</p>`;
    } finally {
      loading = false;
    }
  }

  function ensurePartialCloseControl() {
    const dialog = document.querySelector("#closePositionDialog .dialog-card");
    if (!dialog || document.querySelector("#partialCloseAmount")) return;
    const actions = dialog.querySelector(".dialog-actions");
    const block = document.createElement("div");
    block.className = "partial-close-control";
    block.innerHTML = `
      <label for="partialCloseAmount"><strong>Venta parcial opcional</strong></label>
      <input id="partialCloseAmount" type="number" min="0.01" step="0.01" placeholder="Déjalo vacío para cerrar todo">
      <small id="partialCloseHelp" class="muted">Escribe un monto menor al invertido para vender solo una parte.</small>`;
    dialog.insertBefore(block, actions);
  }

  async function preparePartialClose(positionId) {
    ensurePartialCloseControl();
    selectedPartialPosition = null;
    const input = document.querySelector("#partialCloseAmount");
    const help = document.querySelector("#partialCloseHelp");
    if (input) input.value = "";
    try {
      const data = await requestJson(`/api/positions?ts=${Date.now()}`);
      selectedPartialPosition = (data.items || []).find(item => item.id === positionId) || null;
      if (selectedPartialPosition && input) {
        input.max = String(Math.max(0.01, Number(selectedPartialPosition.amount_mxn) - 0.01));
        if (help) help.textContent = `Invertido actualmente: ${money(selectedPartialPosition.amount_mxn)}. Vacío = cerrar todo.`;
      }
    } catch (error) {
      if (help) help.textContent = `No se pudo preparar la venta parcial: ${error.message}`;
    }
  }

  document.addEventListener("click", event => {
    const closeButton = event.target.closest("[data-close-id]");
    if (closeButton) preparePartialClose(closeButton.dataset.closeId);
  }, true);

  document.querySelector("#confirmClosePosition")?.addEventListener("click", async event => {
    const input = document.querySelector("#partialCloseAmount");
    const requested = Number(input?.value || 0);
    if (!requested) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    const button = event.currentTarget;
    if (!selectedPartialPosition) {
      document.querySelector("#orderMessage").textContent = "No se encontró la posición abierta.";
      return;
    }
    if (requested >= Number(selectedPartialPosition.amount_mxn)) {
      document.querySelector("#orderMessage").textContent = "Para vender todo deja el campo vacío y usa Cerrar posición.";
      return;
    }

    button.disabled = true;
    button.textContent = "Vendiendo parte...";
    try {
      const result = await requestJson(
        `/api/simulations/${selectedPartialPosition.id}/partial-close`,
        {method: "POST", body: JSON.stringify({amount_mxn: requested})}
      );
      document.querySelector("#closePositionDialog")?.close();
      document.querySelector("#orderMessage").textContent = `Venta parcial registrada por ${money(result.closed_lot.amount_mxn)}. P&L realizado: ${money(result.realized_pnl_mxn)}.`;
      window.setTimeout(() => window.location.reload(), 500);
    } catch (error) {
      document.querySelector("#orderMessage").textContent = error.message;
    } finally {
      button.disabled = false;
      button.textContent = "Cerrar posición";
    }
  }, true);

  async function loadRelease() {
    const marker = document.querySelector("#releaseMarker");
    if (!marker) return;
    try {
      const data = await requestJson("/api/release");
      marker.innerHTML = `<strong>${data.release}</strong><span>· rama ${data.branch}</span><span>· commit ${data.commit}</span>`;
    } catch (error) {
      marker.textContent = `Versión no disponible: ${error.message}`;
    }
  }

  async function refreshLoop() {
    window.clearTimeout(timer);
    await loadOrders();
    timer = window.setTimeout(refreshLoop, REFRESH_MS);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshLoop();
  });

  const appContent = document.querySelector("#appContent");
  if (appContent && !appContent.classList.contains("hidden")) {
    ensurePartialCloseControl();
    loadRelease();
    refreshLoop();
  }
})();
