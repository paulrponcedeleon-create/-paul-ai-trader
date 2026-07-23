(() => {
  const ORDER_LIMIT = 10;
  const REFRESH_MS = 5000;
  let loading = false;
  let timer = null;

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
    automatic_exit: "Salida automática"
  }[source] || source || "Sistema");

  const reasonLabel = reason => ({
    manual_close: "Cierre manual",
    strategy_buy: "Señal de compra",
    strategy_sell: "Señal de venta",
    stop_loss: "Stop-loss",
    take_profit: "Take-profit",
    trailing_stop: "Trailing stop",
    expired: "Expiración"
  }[reason] || reason || "Ejecución simulada");

  const pnlClass = value => {
    const number = Number(value || 0);
    if (number > 0) return "positive";
    if (number < 0) return "negative";
    return "neutral";
  };

  async function requestJson(url) {
    const response = await fetch(url, {
      cache: "no-store",
      headers: {
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
      }
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
    loadRelease();
    refreshLoop();
  }
})();
