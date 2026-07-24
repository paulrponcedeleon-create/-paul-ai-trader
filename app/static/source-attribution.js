(() => {
  const REFRESH_MS = 5000;
  const labels = {
    manual: "Manual · Paul",
    runtime: "Bot · estrategia",
    exploration: "IA exploratoria",
    unknown: "Origen histórico"
  };
  let timer = null;
  let loading = false;

  function normalized(source) {
    const value = String(source || "unknown").toLowerCase();
    return labels[value] ? value : "unknown";
  }

  function badgeFor(row) {
    let badge = row.querySelector("[data-position-source]");
    if (!badge) {
      badge = document.createElement("span");
      badge.dataset.positionSource = "";
      const identity = row.querySelector(".position-identity");
      identity?.insertBefore(badge, identity.firstChild);
    }
    return badge;
  }

  function applyPositions(items) {
    const positions = new Map((items || []).map(item => [String(item.id), item]));
    document.querySelectorAll("[data-position-id]").forEach(row => {
      const position = positions.get(String(row.dataset.positionId));
      if (!position) return;
      const source = normalized(position.source);
      const badge = badgeFor(row);
      if (!badge) return;
      badge.className = `position-source-badge position-source-${source}`;
      badge.textContent = position.source_label || labels[source];
      row.dataset.positionOrigin = source;
      row.setAttribute("aria-label", `${position.source_label || labels[source]} · ${position.book}`);
    });
  }

  function patchOrderControls() {
    const select = document.querySelector("#orderFilterSource");
    if (!select) return;
    const manual = select.querySelector('option[value="manual"]');
    const runtime = select.querySelector('option[value="runtime"]');
    if (manual) manual.textContent = "Manual · Paul";
    if (runtime) runtime.textContent = "Bot · estrategia";
    if (!select.querySelector('option[value="exploration"]')) {
      const option = document.createElement("option");
      option.value = "exploration";
      option.textContent = "IA exploratoria";
      const automatic = select.querySelector('option[value="automatic_exit"]');
      select.insertBefore(option, automatic || null);
    }
  }

  function patchOrderRows() {
    document.querySelectorAll("#orderEvents .order-event-main strong").forEach(node => {
      if (node.dataset.sourceLabelPatched === "true") return;
      node.textContent = node.textContent
        .replace(" · Manual", " · Manual · Paul")
        .replace(" · Bot automático", " · Bot · estrategia")
        .replace(" · exploration", " · IA exploratoria");
      node.dataset.sourceLabelPatched = "true";
    });
  }

  async function refresh() {
    window.clearTimeout(timer);
    patchOrderControls();
    patchOrderRows();
    if (!loading && !document.hidden) {
      loading = true;
      try {
        const response = await fetch(`/api/positions?source_view=1&ts=${Date.now()}`, {
          cache: "no-store",
          headers: {"Cache-Control": "no-cache", "Pragma": "no-cache"}
        });
        if (response.ok) applyPositions((await response.json()).items || []);
      } catch (_) {
        // The main dashboard already owns user-facing API errors.
      } finally {
        loading = false;
      }
    }
    timer = window.setTimeout(refresh, REFRESH_MS);
  }

  const observer = new MutationObserver(() => {
    patchOrderControls();
    patchOrderRows();
  });
  observer.observe(document.body, {childList: true, subtree: true});

  const appContent = document.querySelector("#appContent");
  if (appContent && !appContent.classList.contains("hidden")) refresh();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refresh();
  });
})();
