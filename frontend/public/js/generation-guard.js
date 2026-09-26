/**
 * Botones de generación + listados en vivo (Spec-460 S6).
 *
 * 1) Estado "ocupado": todo [data-generation-trigger] (botón de un form, o link)
 *    al activarse deshabilita TODOS los triggers de la página, muestra un spinner
 *    y el texto de data-busy-label. Evita el doble envío.
 *    - Al volver atrás (bfcache, `pageshow` persisted) se restauran.
 *    - Con data-story-id, reaccionan a los jobs de esa historia:
 *      job-started → ocupado; job-done / job-failed → se restauran.
 *
 * 2) Listados en vivo: un contenedor [data-jobs-live] (con id) se recarga solo
 *    (htmx.ajax + select) con el primer avance de un job cuya tarjeta todavía no
 *    lo muestra, y cuando termina o falla; los elementos
 *    [data-job-progress="<story_id>"] muestran "Acto N de 5 · etapa" en vivo.
 *
 * 3) Fragmentos atados a un job: [data-refresh-on-job="<job_id>"] se recarga
 *    (data-refresh-url → data-refresh-target) cuando ese job termina o falla.
 *
 * Se carga en <head> con defer: listeners únicos por pestaña, válidos para
 * cualquier body que llegue por hx-boost.
 */
(function () {
  "use strict";

  if (window.__forgeGuardReady) return;
  window.__forgeGuardReady = true;

  const SPINNER =
    '<svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.25"></circle>' +
    '<path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round"></path></svg>';

  const STAGE_LABELS = {
    planificador: "Armando la escaleta",
    verificador: "Revisando la escaleta",
    voz: "Narrando",
    journal: "Actualizando memoria",
    consolidando: "Consolidando",
  };

  function triggers(storyId) {
    const all = [...document.querySelectorAll("[data-generation-trigger]")];
    return storyId ? all.filter((el) => el.dataset.storyId === storyId) : all;
  }

  function setBusy(el) {
    if (el.dataset.busy === "1") return;
    el.dataset.busy = "1";
    el.dataset.originalHtml = el.innerHTML;
    el.setAttribute("aria-busy", "true");
    el.setAttribute("aria-disabled", "true");
    if ("disabled" in el) el.disabled = true;
    el.classList.add("opacity-60", "cursor-wait", "pointer-events-none");
    el.innerHTML = `${SPINNER}<span>${el.dataset.busyLabel || "Iniciando..."}</span>`;
  }

  // "pending" se marca en el mismo tick del click/submit: un doble click dispara
  // los dos eventos antes de que corra cualquier setTimeout.
  function isLocked(el) {
    return el.dataset.busy === "1" || el.dataset.pending === "1";
  }

  function lock(trigger) {
    trigger.dataset.pending = "1";
    // Diferido: deshabilitar el botón en el mismo tick puede cancelar el envío.
    setTimeout(() => triggers().forEach(setBusy), 0);
  }

  function restore(el) {
    delete el.dataset.pending;
    if (el.dataset.busy !== "1") return;
    el.innerHTML = el.dataset.originalHtml || el.innerHTML;
    delete el.dataset.busy;
    el.removeAttribute("aria-busy");
    el.removeAttribute("aria-disabled");
    if ("disabled" in el) el.disabled = false;
    el.classList.remove("opacity-60", "cursor-wait", "pointer-events-none");
  }

  // Captura: corre antes que htmx (hx-boost) procese el submit/click.
  document.addEventListener(
    "submit",
    (e) => {
      const trigger = e.submitter && e.submitter.closest("[data-generation-trigger]");
      if (!trigger) return;
      if (isLocked(trigger)) {
        e.preventDefault(); // doble envío
        e.stopImmediatePropagation();
        return;
      }
      lock(trigger);
    },
    true,
  );

  document.addEventListener(
    "click",
    (e) => {
      const trigger = e.target.closest("a[data-generation-trigger], button[data-generation-trigger]:not([type='submit'])");
      if (!trigger) return;
      if (isLocked(trigger)) {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
      lock(trigger);
    },
    true,
  );

  // Volver atrás desde la sala: la página sale del bfcache con los botones "ocupados".
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) triggers().forEach(restore);
  });

  // ── Jobs en vivo ──────────────────────────────────────────────────────────
  function refreshLiveLists() {
    if (!window.htmx) return;
    document.querySelectorAll("[data-jobs-live][id]").forEach((el) => {
      window.htmx.ajax("GET", window.location.pathname + window.location.search, {
        target: `#${el.id}`,
        select: `#${el.id}`,
        swap: "outerHTML",
      });
    });
  }

  function progressText(job) {
    const stage = STAGE_LABELS[job.stage] || "Iniciando";
    if (!job.beat || job.stage === "consolidando") return stage;
    return `Acto ${job.beat} de ${job.total_beats || 5} · ${stage}`;
  }

  document.addEventListener("forge:job-started", (e) => {
    triggers(e.detail.story_id).forEach(setBusy);
  });

  // La lista se recarga con el primer avance del job, no con job_started: en ese
  // instante la historia todavía figura `completed`/`draft` (el pipeline la pasa a
  // `processing` un momento después) y se volvería a pintar el estado viejo.
  document.addEventListener("forge:job-progress", (e) => {
    const job = e.detail;
    const shown = document.querySelectorAll(`[data-job-progress="${job.story_id}"]`);
    shown.forEach((el) => (el.textContent = progressText(job)));
    if (shown.length === 0 && document.querySelector(`[data-story-card="${job.story_id}"]`)) {
      refreshLiveLists();
    }
  });

  // ── Fragmentos atados a un job ────────────────────────────────────────────
  // [data-refresh-on-job="<job_id>"] (p.ej. el panel de un relato mientras se
  // regenera un acto) se recarga con data-refresh-url cuando el job termina;
  // si falló, con ?error=<motivo>.
  function refreshBound(job) {
    const error = job.status === "failed" ? job.error || "falló" : null;
    document.querySelectorAll(`[data-refresh-on-job="${job.job_id}"]`).forEach((el) => {
      if (!window.htmx || el.dataset.refreshing === "1") return;
      el.dataset.refreshing = "1";
      const url = el.dataset.refreshUrl + (error ? `?error=${encodeURIComponent(error)}` : "");
      window.htmx.ajax("GET", url, { target: el.dataset.refreshTarget, swap: "outerHTML" });
    });
  }

  // El job pudo terminar antes de que el fragmento llegara al DOM (respuesta rápida).
  function catchUpBound() {
    if (!window.ForgeEvents || !document.querySelector("[data-refresh-on-job]")) return;
    window.ForgeEvents.finishedJobs().forEach(({ job }) => refreshBound(job));
  }
  document.addEventListener("htmx:afterSwap", catchUpBound);

  ["forge:job-done", "forge:job-failed"].forEach((name) => {
    document.addEventListener(name, (e) => {
      triggers(e.detail.story_id).forEach(restore);
      refreshBound(e.detail);
      refreshLiveLists();
    });
  });

  // Snapshot / navegación: completar el progreso de los jobs ya en curso.
  document.addEventListener("forge:jobs-changed", () => {
    if (!window.ForgeEvents) return;
    window.ForgeEvents.activeJobs().forEach((job) => {
      document.querySelectorAll(`[data-job-progress="${job.story_id}"]`).forEach((el) => {
        if (job.stage) el.textContent = progressText(job);
      });
    });
  });
})();
