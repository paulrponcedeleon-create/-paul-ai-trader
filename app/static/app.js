const qs = s => document.querySelector(s);
let selectedBook = document.querySelector(".book.active")?.dataset.book || "btc_mxn";

async function api(url, options={}) {
  const response = await fetch(url, {
    headers: {"Content-Type":"application/json", ...(options.headers||{})},
    ...options
  });
  const data = await response.json().catch(()=>({detail:"Respuesta inválida"}));
  if (!response.ok) throw new Error(data.detail || "Error");
  return data;
}

document.querySelectorAll(".book").forEach(btn => btn.addEventListener("click", () => {
  document.querySelectorAll(".book").forEach(x=>x.classList.remove("active"));
  btn.classList.add("active");
  selectedBook = btn.dataset.book;
  qs("#orderBook").value = selectedBook;
}));

qs("#loginForm")?.addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api("/api/login", {method:"POST", body:JSON.stringify({password:qs("#password").value})});
    location.reload();
  } catch(err) { qs("#loginError").textContent = err.message; }
});

async function refreshMarket() {
  qs("#statusText").textContent = "Consultando...";
  try {
    const data = await api(`/api/market/${selectedBook}`);
    const s = data.signal;
    qs("#marketResult").innerHTML = `
      <div class="signal ${s.action}">${s.action.toUpperCase()}</div>
      <p><strong>Precio:</strong> $${Number(s.reference_price).toLocaleString("es-MX")}</p>
      <p><strong>Confianza:</strong> ${s.confidence}%</p>
      <p>${s.reason}</p>`;
    qs("#statusText").textContent = "Actualizado";
  } catch(err) {
    qs("#marketResult").innerHTML = `<p class="error">${err.message}</p>`;
    qs("#statusText").textContent = "Error";
  }
}

qs("#refreshBtn")?.addEventListener("click", refreshMarket);

qs("#orderForm")?.addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const data = await api("/api/orders", {
      method:"POST",
      body:JSON.stringify({
        book:qs("#orderBook").value,
        side:qs("#orderSide").value,
        amount_mxn:Number(qs("#orderAmount").value),
        daily_pnl_mxn:0,
        open_orders:0
      })
    });
    qs("#orderMessage").textContent = `Operación ${data.status}: ${data.side} $${data.amount_mxn} MXN`;
    loadHistory();
  } catch(err) { qs("#orderMessage").textContent = err.message; }
});

async function loadHistory() {
  try {
    const data = await api("/api/simulations");
    qs("#history").innerHTML = data.items.length ? data.items.map(x => `
      <div class="history-item">
        <div><strong>${x.book.toUpperCase()}</strong><br><small>${x.side.toUpperCase()}</small></div>
        <div><strong>$${x.amount_mxn} MXN</strong><br><small>${new Date(x.created_at).toLocaleString("es-MX")}</small></div>
      </div>`).join("") : "<p>Sin operaciones todavía.</p>";
  } catch(err) { qs("#history").innerHTML = `<p class="error">${err.message}</p>`; }
}

if (!qs("#appContent")?.classList.contains("hidden")) {
  loadHistory();
  refreshMarket();
}
