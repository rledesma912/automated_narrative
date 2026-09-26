/**
 * Pie global (Spec-460 S5): sin polling.
 *
 * - Punto "Core API": verde mientras llegan señales del canal global (snapshot,
 *   eventos o heartbeat cada 15 s), rojo si se corta. Lo emite /js/event-bus.js
 *   como `forge:core-status`; en la sala lo emite la propia sala.
 * - "Actividad": último evento de jobs recibido.
 *
 * Se carga en <head> con defer: los listeners se registran una vez por pestaña y
 * el estado se re-aplica al footer nuevo tras cada navegación de hx-boost.
 */
(function () {
  "use strict";

  if (window.__forgeFooterReady) return;
  window.__forgeFooterReady = true;

  let alive = null; // null = sin señales todavía
  let lastEvent = null;

  const STAGE_LABELS = {
    planificador: "armando la escaleta",
    verificador: "revisando la escaleta",
    voz: "narrando",
    journal: "actualizando la memoria",
    consolidando: "consolidando el relato",
  };

  function describe(kind, job) {
    const title = `«${job.title || "Sin título"}»`;
    if (kind === "job-started") return `${title}: generación iniciada`;
    if (kind === "job-done") return `${title}: lista`;
    if (kind === "job-failed") return `${title}: falló${job.error ? ` (${job.error})` : ""}`;
    const stage = STAGE_LABELS[job.stage] || "en curso";
    return job.beat ? `${title}: acto ${job.beat} · ${stage}` : `${title}: ${stage}`;
  }

  function apply() {
    const dot = document.getElementById("core-status-dot");
    if (dot) {
      dot.className =
        alive === null
          ? "w-2 h-2 rounded-full bg-forge-border"
          : alive
            ? "w-2 h-2 rounded-full bg-forge-success"
            : "w-2 h-2 rounded-full bg-forge-error animate-pulse";
    }
    const el = document.getElementById("footer-last-event");
    if (el && lastEvent) {
      const time = new Date(lastEvent.at).toTimeString().slice(0, 5);
      el.textContent = `[${time}] ${lastEvent.text}`;
    }
  }

  document.addEventListener("forge:core-status", (e) => {
    alive = !!(e.detail && e.detail.alive);
    apply();
  });

  ["job-started", "job-progress", "job-done", "job-failed"].forEach((kind) => {
    document.addEventListener(`forge:${kind}`, (e) => {
      lastEvent = { text: describe(kind, e.detail), at: Date.now() };
      apply();
    });
  });

  document.addEventListener("htmx:afterSwap", apply);
  apply();
})();
