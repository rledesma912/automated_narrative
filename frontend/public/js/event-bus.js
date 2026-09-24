/**
 * Event bus del cliente (Spec-460 S5).
 *
 * Abre UNA conexión SSE por pestaña al canal global del Core (/api/v1/events)
 * y re-emite cada evento como CustomEvent en `document`:
 *
 *   forge:snapshot      { active: [job], recent: [job] }
 *   forge:job-started   job     forge:job-progress  job
 *   forge:job-done      job     forge:job-failed    job
 *   forge:jobs-changed  —       (cualquier cambio del estado de jobs)
 *   forge:core-status   { alive: boolean }
 *
 * Los componentes (banda, pie, sidebar, botones) escuchan eventos del DOM y no
 * saben de SSE. Estado consultable en `window.ForgeEvents`.
 *
 * - Se carga en <head> con defer: bajo hx-boost el <head> no se re-ejecuta, así
 *   que la conexión sobrevive a las navegaciones (no se reabre por página).
 * - En la sala de generación (marcador [data-forge-no-global-events]) la conexión
 *   se cierra: la sala ya tiene la suya con el detalle del job (1 SSE por pestaña).
 * - Ante un corte el browser reconecta solo y el Core reenvía lo perdido
 *   (Last-Event-ID).
 */
(function () {
  "use strict";

  if (window.ForgeEvents) return; // ya inicializado en esta pestaña

  const ALIVE_WINDOW_MS = 20000; // heartbeat del Core: cada 15 s

  const activeJobs = new Map(); // job_id → job
  const finishedJobs = new Map(); // job_id → { job, at }  (vistos en vivo)
  let source = null;
  let lastSignal = 0;

  function emit(name, detail) {
    document.dispatchEvent(new CustomEvent(`forge:${name}`, { detail }));
  }

  function markAlive() {
    lastSignal = Date.now();
    emit("core-status", { alive: true });
  }

  function parse(e) {
    try {
      return JSON.parse(e.data);
    } catch {
      return null;
    }
  }

  // Spec-510: cuándo llegó cada job, para sumarle el tiempo local a su
  // `elapsed_seconds` sin depender de la hora del Core.
  function stamp(job) {
    job.received_at = Date.now();
    return job;
  }

  function onJob(kind) {
    return (e) => {
      const job = parse(e);
      if (!job) return;
      stamp(job);
      markAlive();
      if (kind === "job-done" || kind === "job-failed") {
        activeJobs.delete(job.job_id);
        finishedJobs.set(job.job_id, { job, at: Date.now() });
      } else {
        activeJobs.set(job.job_id, job);
      }
      emit(kind, job);
      emit("jobs-changed");
    };
  }

  function wantsGlobal() {
    return !document.querySelector("[data-forge-no-global-events]");
  }

  function connect() {
    if (source || !wantsGlobal()) return;
    source = new EventSource("/api/v1/events");

    source.addEventListener("snapshot", (e) => {
      const snap = parse(e);
      if (!snap) return;
      markAlive();
      activeJobs.clear();
      (snap.active || []).forEach((job) => activeJobs.set(job.job_id, stamp(job)));
      emit("snapshot", snap);
      emit("jobs-changed");
    });
    source.addEventListener("job_started", onJob("job-started"));
    source.addEventListener("job_progress", onJob("job-progress"));
    source.addEventListener("job_done", onJob("job-done"));
    source.addEventListener("job_failed", onJob("job-failed"));
    source.addEventListener("heartbeat", markAlive);
    source.onerror = () => emit("core-status", { alive: false });
  }

  function disconnect() {
    if (!source) return;
    source.close();
    source = null;
  }

  function sync() {
    if (wantsGlobal()) connect();
    else disconnect();
    emit("jobs-changed"); // el body nuevo re-renderiza banda/sidebar con el estado actual
  }

  // Sin señales del Core en 20 s → desconectado.
  setInterval(() => {
    if (source && Date.now() - lastSignal > ALIVE_WINDOW_MS) {
      emit("core-status", { alive: false });
    }
  }, 5000);

  document.addEventListener("htmx:afterSwap", sync);

  window.ForgeEvents = {
    /** Jobs en curso, el más reciente primero. */
    activeJobs: () => [...activeJobs.values()].reverse(),
    /** Jobs terminados vistos en vivo en esta pestaña, el más reciente primero. */
    finishedJobs: () =>
      [...finishedJobs.values()].sort((a, b) => b.at - a.at),
    isConnected: () => source !== null,
  };

  // defer: el DOM ya está parseado.
  sync();
})();
