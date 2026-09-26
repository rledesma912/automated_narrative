/**
 * Banda de generación + punto del sidebar (Spec-460 S5).
 *
 * Pinta el estado que mantiene /js/event-bus.js (window.ForgeEvents):
 *   - running: el job más reciente, "y N más", acto N de 5 · etapa — tiempo
 *     restante (Spec-510), barra de progreso y "Ver progreso" (link real a la
 *     sala; solo existe con un job).
 *   - done:    "«Título» está lista · en N min" + "Leer relato"; se oculta sola a los 15 s.
 *   - failed:  "Falló la generación de «Título»" + "Ver detalle"; queda hasta cerrarla.
 * No se muestra en la sala de generación (ya muestra todo).
 *
 * Se carga en <head> con defer: los listeners sobreviven a las navegaciones de
 * hx-boost y re-pintan el body nuevo en cada `forge:jobs-changed`.
 * El avance sale de /js/eta.js (window.ForgeEta, Spec-510), cargado antes.
 */
(function () {
  "use strict";

  if (window.__forgeBannerReady) return;
  window.__forgeBannerReady = true;

  const DONE_VISIBLE_MS = 15000;
  const TICK_MS = 15000; // recalcula el tiempo restante (Spec-510)
  const eta = window.ForgeEta;
  const dismissed = new Set(); // job_id de avisos cerrados (esta pestaña)
  // Spec-530: los jobs del asistente (taller, escaleta, revisión) se siguen con el
  // modal de su propia vista; no son generaciones de relato.
  const AUTHORING_KINDS = ["consult", "plan_outline", "verify_outline"];
  const isGeneration = (job) => !AUTHORING_KINDS.includes(job.kind);

  function stepText(job) {
    if (job.kind === "regenerate_voz") {
      return `Regenerando el acto ${(job.params && job.params.beat) || job.beat || ""}`.trim();
    }
    const stage = eta.STAGES[job.stage];
    if (!stage) return "Iniciando...";
    if (job.stage === "consolidando" || !job.beat) return stage.label;
    return `Acto ${job.beat} de ${job.total_beats || 5} · ${stage.label}`;
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
      if (dismissed.has(job.job_id) || !isGeneration(job)) return false;
      return job.status === "failed" || now - at < DONE_VISIBLE_MS;
    });
  }

  function render() {
    const bus = window.ForgeEvents;
    const banner = document.getElementById("generation-banner");
    const running = bus ? bus.activeJobs().filter(isGeneration) : [];

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
      const remaining = eta.formatRemaining(eta.remainingFor(job, eta.elapsedNow(job, Date.now())));
      setText(panel, "[data-banner-step]", remaining ? `${stepText(job)} — ${remaining}` : stepText(job));
      panel.querySelector("[data-banner-progress]").style.width = `${Math.round(eta.progress(job) * 100)}%`;
      // Regenerar un acto se sigue en la vista de relatos, no en la sala.
      panel.querySelector("[data-banner-link]").href =
        job.kind === "regenerate_voz"
          ? `/historia/${job.story_id}/relatos`
          : `/generar/stream/${job.story_id}`;
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
      const took = state === "done" ? eta.formatDuration(job.elapsed_seconds) : "";
      setText(panel, "[data-banner-duration]", took ? ` · en ${took}` : "");
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
  setInterval(() => {
    if (window.ForgeEvents && window.ForgeEvents.activeJobs().some(isGeneration)) render();
  }, TICK_MS);
  render();
})();
