/**
 * Modal que bloquea la página mientras la IA trabaja (Spec-610; el mismo diseño y
 * comportamiento que el del asistente, Spec-530 decisión 12).
 *
 *   ForgeIaModal.open(job, { titulo, detalle, onDone })
 *
 * Deja el resto de la página `inert`, muestra el tiempo que falta (params del job,
 * Spec-510), sigue el job por el bus (`forge:job-*`) y además consulta cada 5 s.
 * Al terminar bien llama a `onDone(job)`; si falla, muestra el error con «Cerrar».
 * «Cancelar» cancela el job (POST /jobs/{id}/cancel).
 */
(function () {
  "use strict";

  if (window.ForgeIaModal) return;

  const API = "/api/v1";
  const POLL_MS = 5000;
  const $ = (sel, root = document) => root.querySelector(sel);
  let state = null; // { job, opts, poll, tick }

  const el = () => $("#ia-modal");

  function remaining(seconds) {
    const min = Math.round(seconds / 60);
    return min >= 1 ? `${min} min` : `${Math.max(5, Math.round(seconds / 5) * 5)} s`;
  }

  function render() {
    if (!state) return;
    const { job } = state;
    const estimate = job.params && job.params.estimated_seconds;
    const base = typeof job.elapsed_seconds === "number" ? job.elapsed_seconds : 0;
    const elapsed = base + (Date.now() - (job.received_at || Date.now())) / 1000;
    const eta = $("[data-ia-modal-eta]", el());
    if (!estimate) eta.textContent = "";
    else if (elapsed >= estimate) eta.textContent = "Está tardando un poco más de lo habitual…";
    else eta.textContent = `Falta ≈ ${remaining(estimate - elapsed)}`;
  }

  function stop() {
    if (!state) return;
    clearInterval(state.poll);
    clearInterval(state.tick);
  }

  function close() {
    stop();
    state = null;
    const modal = el();
    if (modal) modal.classList.add("hidden");
    [...document.body.children].forEach((c) => c.removeAttribute("inert"));
  }

  function failed(error) {
    stop();
    const modal = el();
    $("[data-ia-modal-spinner]", modal).classList.add("hidden");
    $("[data-ia-modal-nota]", modal).classList.add("hidden");
    $("[data-ia-modal-eta]", modal).textContent = "";
    $("[data-ia-modal-cancelar]", modal).classList.add("hidden");
    const err = $("[data-ia-modal-error]", modal);
    err.textContent = error || "No se pudo terminar.";
    err.classList.remove("hidden");
    $("[data-ia-modal-cerrar]", modal).classList.remove("hidden");
    $("[data-ia-modal-cerrar]", modal).focus();
  }

  function update(job) {
    if (!state || job.job_id !== state.job.job_id) return;
    job.received_at = job.received_at || Date.now();
    state.job = job;
    if (job.status === "done") {
      const { onDone } = state.opts;
      close();
      if (onDone) onDone(job);
    } else if (job.status === "failed") failed(job.error);
    else render();
  }

  async function refresh() {
    if (!state) return;
    try {
      const resp = await fetch(`${API}/jobs/${state.job.job_id}`);
      if (!resp.ok) return;
      const job = await resp.json();
      job.received_at = Date.now();
      update(job);
    } catch {
      /* el próximo intento */
    }
  }

  function open(job, opts = {}) {
    const modal = el();
    if (!modal) return;
    document.body.append(modal); // fuera de <main>: si no, quedaría inerte con la página
    job.received_at = job.received_at || Date.now();
    state = { job, opts, poll: null, tick: null };
    $("#ia-modal-titulo", modal).textContent = opts.titulo || "La IA está trabajando…";
    $("#ia-modal-detalle", modal).textContent = opts.detalle || "";
    $("[data-ia-modal-error]", modal).classList.add("hidden");
    $("[data-ia-modal-cerrar]", modal).classList.add("hidden");
    $("[data-ia-modal-cancelar]", modal).classList.remove("hidden");
    $("[data-ia-modal-spinner]", modal).classList.remove("hidden");
    $("[data-ia-modal-nota]", modal).classList.remove("hidden");
    [...document.body.children].forEach((c) => c !== modal && c.tagName !== "SCRIPT" && c.setAttribute("inert", ""));
    modal.classList.remove("hidden");
    $("[data-ia-modal-cancelar]", modal).focus();
    render();
    state.poll = setInterval(refresh, POLL_MS);
    state.tick = setInterval(render, 1000);
  }

  document.addEventListener("click", (e) => {
    const t = e.target;
    if (!state || !t.closest) return;
    if (t.closest("[data-ia-modal-cancelar]")) {
      const id = state.job.job_id;
      fetch(`${API}/jobs/${id}/cancel`, { method: "POST" }).catch(() => {}).finally(close);
    } else if (t.closest("[data-ia-modal-cerrar]")) close();
  });

  ["job-progress", "job-done", "job-failed"].forEach((name) =>
    document.addEventListener(`forge:${name}`, (e) => update({ ...e.detail })),
  );

  window.ForgeIaModal = { open, close };
})();
