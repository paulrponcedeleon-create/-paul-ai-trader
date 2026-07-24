(() => {
  const ORDER_LIMIT = 10;
  const REFRESH_MS = 5000;
  let loading = false;
  let timer = null;
  let offset = 0;
  let accumulated = [];
  let selectedPartialPosition = null;
  const filters = {book: "", side: "", source: ""};

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

  function ensureControls() {
    const container = document.querySelector("#orderEvents");
    if (!container || document.querySelector("#orderEventFilters")) return;
    const controls = document.createElement("div");
    controls.id = "orderEventFilters";
    controls.className = "order-event-filters";
    controls.innerHTML = `
      <label>Activo<input id="orderFilterBook" placeholder="BTC, ETH…"></label>
      <label>Tipo<select id="orderFilterSide"><option value="">BUY y SELL</option><option value="buy">BUY</option><option value="sell">SELL</option></select></label>
      <label>Origen<select id="orderFilterSource"><option value="">Todos</option><option value="manual">Manual</option><option value="runtime">Bot automático</option><option value="automatic_exit">Salida automática</option></select></label>
      <button type="button" class="secondary" id="clearOrderFilters">Limpiar</button>`;
    container.parentElement.insertBefore(controls, container);

    const more = document.createElement("button");
    more.type = "button";
    more.id = "loadMoreOrders";
    more.className = "secondary hidden";
    more.textContent = "Ver más";
    container.parentElement.appendChild(more);

    const reset = () => {
      offset = 0;
      accumulated = [];
      loadOrders(false);
    };
    document.querySelector("#orderFilterBook").addEventListener("input", event => {
      filters.book = String(event.target.value || "").trim().toLowerCase();
      window.clearTimeout(timer);
      timer = window.setTimeout(reset, 300);
    });
    document.querySelector("#orderFilterSide").addEventListener("change", event => {
      filters.side = event.target.value;
      reset();
    });
    document.querySelector("#orderFilterSource").addEventListener("change", event => {
      filters.source = event.target.value;
      reset();
    });
    document.querySelector("#clearOrderFilters").addEventListener("click", () => {
      filters.book = filters.side = filters.source = "";
      document.querySelector("#orderFilterBook").value = "";
      document.querySelector("#orderFilterSide").value = "";
      document.querySelector("#orderFilterSource").value = "";
      reset();
    });
    more.addEventListener("click", () => {
      offset = accumulated.length;
      loadOrders(true);
    });
  }

  function render(items) {
    const container = document.querySelector("#orderEvents");
    if (!container) return;
    if (!items.length) {
      container.innerHTML = "<p>Sin órdenes que coincidan con estos filtros.</p>";
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

  function queryUrl() {
    const params = new URLSearchParams({
      limit: String(ORDER_LIMIT),
      offset: String(offset),
      ts: String(Date.now())
    });
    if (filters.book) params.set("books", filters.book.includes("_") ? filters.book : `${filters.book}_mxn`);
    if (filters.side) params.set("side", filters.side);
    if (filters.source) params.set("source", filters.source);
    return `/api/orders?${params.toString()}`;
  }

  async function loadOrders(append = false) {
    if (loading || document.hidden) return;
    const container = document.querySelector("#orderEvents");
    if (!container) return;
    loading = true;
    try {
      const data = await requestJson(queryUrl());
      accumulated = append ? accumulated.concat(data.items || []) : (data.items || []);
      render(accumulated);
      const meta = document.querySelector("#orderEventsMeta");
      if (meta) {
        meta.textContent = data.total
          ? `Mostrando ${accumulated.length} de ${data.total} órdenes · actualizado ${new Date(data.updated_at).toLocaleTimeString("es-MX")}`
          : "Sin resultados para los filtros seleccionados";
      }
      document.querySelector("#loadMoreOrders")?.classList.toggle("hidden", !data.has_more);
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
    if (offset === 0) await loadOrders(false);
    timer = window.setTimeout(refreshLoop, REFRESH_MS);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshLoop();
  });

  const appContent = document.querySelector("#appContent");
  if (appContent && !appContent.classList.contains("hidden")) {
    ensureControls();
    ensurePartialCloseControl();
    loadRelease();
    refreshLoop();
  }
})();