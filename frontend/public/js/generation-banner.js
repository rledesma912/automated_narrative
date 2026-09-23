/**
 * Banda de generación + punto del sidebar (Spec-460 S5).
 *
 * Pinta el estado que mantiene /js/event-bus.js (window.ForgeEvents):
 *   - running: el job más reciente, "y N más", acto N de 5 · etapa, barra de
 *     progreso y "Ver progreso" (link real a la sala; solo existe con un job).
 *   - done:    "«Título» está lista" + "Leer relato"; se oculta sola a los 15 s.
 *   - failed:  "Falló la generación de «Título»" + "Ver detalle"; queda hasta cerrarla.
 * No se muestra en la sala de generación (ya muestra todo).
 *
 * Se carga en <head> con defer: los listeners sobreviven a las navegaciones de
 * hx-boost y re-pintan el body nuevo en cada `forge:jobs-changed`.
 */
(function () {
  "use strict";

  if (window.__forgeBannerReady) return;
  window.__forgeBannerReady = true;

  const DONE_VISIBLE_MS = 15000;
  const STAGES = {
    analyst: { label: "Analizando la sinopsis", weight: 0 },
    resolver: { label: "Distribuyendo escenarios", weight: 0 },
    mapper: { label: "Mapeando", weight: 0.1 },
    voz: { label: "Narrando", weight: 0.4 },
    journal: { label: "Actualizando la memoria", weight: 0.85 },
    consolidando: { label: "Consolidando el relato", weight: 1 },
  };
  const dismissed = new Set(); // job_id de avisos cerrados (esta pestaña)

  function stepText(job) {
    const stage = STAGES[job.stage];
    if (!stage) return "Iniciando...";
    if (job.stage === "consolidando" || !job.beat) return stage.label;
    return `Acto ${job.beat} de ${job.total_beats || 5} · ${stage.label}`;
  }

  function progressPct(job) {
    if (job.stage === "consolidando") return 100;
    const stage = STAGES[job.stage];
    if (!stage || !job.beat) return 3;
    const total = job.total_beats || 5;
    return Math.min(99, Math.round(((job.beat - 1 + stage.weight) / total) * 100));
  }

  function setText(root, selector, text) {
    root.querySelectorAll(selector).forEach((el) => (el.textContent = text));
  }

  function showState(banner, state) {
    banner.querySelectorAll("[data-banner-state]").forEach((el) => {
      el.classList.toggle("hidden", el.dataset.bannerState !== state);
    });
    banner.classList.toggle("hidden", state === null);
    banner.classList.toggle("generation-banner--failed", state === "failed");
  }

  function lastFinished() {
    const now = Date.now();
    return window.ForgeEvents.finishedJobs().find(({ job, at }) => {
      if (dismissed.has(job.job_id)) return false;
      return job.status === "failed" || now - at < DONE_VISIBLE_MS;
    });
  }

  function render() {
    const bus = window.ForgeEvents;
    const banner = document.getElementById("generation-banner");
    const running = bus ? bus.activeJobs() : [];

    document.querySelectorAll("[data-forge-jobs-dot]").forEach((dot) => {
      dot.classList.toggle("hidden", running.length === 0);
    });

    if (!banner || !bus) return;
    if (document.querySelector("[data-forge-no-global-events]")) {
      showState(banner, null);
      return;
    }

    if (running.length > 0) {
      const job = running[0];
      const panel = banner.querySelector('[data-banner-state="running"]');
      setText(panel, "[data-banner-title]", `«${job.title || "Sin título"}»`);
      setText(panel, "[data-banner-more]", running.length > 1 ? `y ${running.length - 1} más` : "");
      setText(panel, "[data-banner-step]", stepText(job));
      panel.querySelector("[data-banner-progress]").style.width = `${progressPct(job)}%`;
      panel.querySelector("[data-banner-link]").href = `/generar/stream/${job.story_id}`;
      showState(banner, "running");
      return;
    }

    const finished = lastFinished();
    if (finished) {
      const { job } = finished;
      const state = job.status === "failed" ? "failed" : "done";
      const panel = banner.querySelector(`[data-banner-state="${state}"]`);
      setText(panel, "[data-banner-title]", `«${job.title || "Sin título"}»`);
      setText(panel, "[data-banner-error]", job.error || "");
      panel.querySelector("[data-banner-link]").href =
        state === "done" ? `/historia/${job.story_id}/relatos` : `/historia/${job.story_id}`;
      panel.querySelector("[data-banner-close]").dataset.jobId = job.job_id;
      showState(banner, state);
      if (state === "done") setTimeout(render, DONE_VISIBLE_MS + 100);
      return;
    }

    showState(banner, null);
  }

  document.addEventListener("click", (e) => {
    const close = e.target.closest("[data-banner-close]");
    if (!close) return;
    if (close.dataset.jobId) dismissed.add(close.dataset.jobId);
    render();
  });

  document.addEventListener("forge:jobs-changed", render);
  render();
})();
