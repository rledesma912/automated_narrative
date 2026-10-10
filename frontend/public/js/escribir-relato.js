/**
 * «Escribir el relato» desde donde se toca el botón (Spec-660 B1).
 *
 * Todo [data-escribir-relato] (en «Los actos», «El relato» y la sala en modo lectura):
 *   1. pregunta con ForgeConfirm (pluma, tiempo estimado de data-estimado y, con
 *      data-version-nueva, la nota de que se escribe una versión nueva);
 *   2. en el asistente, guarda lo pendiente (ForgeAsistente.flushAll);
 *   3. POST /api/v1/stories/{id}/jobs → 202, o 409 con el job que ya corre → la sala;
 *   4. si falla, una nota de error al lado del botón y el botón vuelve a estar listo.
 *
 * El botón lleva también data-generation-trigger: generation-guard.js lo bloquea
 * mientras la historia tiene un job, pero no al tocarlo (eso lo hace este archivo
 * recién cuando se acepta). UMD para testearlo en Vitest con `run(btn, deps)`.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ForgeEscribir = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const SIN_CONEXION = "No se pudo arrancar: no hay conexión. Probá de nuevo.";
  const FALLO = "No se pudo arrancar. Probá de nuevo en un rato.";

  /** Lo que dice el diálogo según el botón. */
  function textos(dataset = {}) {
    const nueva = "versionNueva" in dataset;
    const tarda = dataset.estimado ? `Tarda ${dataset.estimado}. ` : "";
    return {
      icon: "escribir",
      title: nueva ? "¿Regeneramos la historia?" : "¿Escribimos el relato?", // Spec-630 B19: «Regenerar»
      message: `${tarda}Podés cerrar la pestaña: la IA sigue escribiendo.`,
      note: nueva
        ? "Se escribe una versión nueva con lo que tenés en «Los actos». Las que ya tenés quedan en «El relato»."
        : undefined,
      confirmLabel: nueva ? "Regenerar historia" : "Escribir el relato",
    };
  }

  /** Corre el flujo para un botón; `deps` reemplaza al navegador en los tests. */
  async function run(btn, deps) {
    const storyId = btn.dataset.storyId;
    if (!storyId || btn.dataset.busy === "1" || btn.dataset.pending === "1") return "ocupado";
    deps.clearError(btn);
    btn.dataset.pending = "1";
    try {
      const ok = await deps.confirm(textos(btn.dataset));
      if (!ok) return "cancelado";
      deps.busy(btn);
      if (deps.before) await deps.before();
      let resp;
      try {
        resp = await deps.fetch(`/api/v1/stories/${storyId}/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ kind: "full_generation" }),
        });
      } catch {
        deps.restore(btn);
        deps.error(btn, SIN_CONEXION);
        return "error";
      }
      const body = await resp.json().catch(() => ({}));
      if ((resp.status === 202 || resp.status === 409) && body.job_id) {
        deps.go(`/generar/stream/${storyId}`);
        return "sala";
      }
      deps.restore(btn);
      deps.error(btn, typeof body.detail === "string" && body.detail ? body.detail : FALLO);
      return "error";
    } finally {
      delete btn.dataset.pending;
    }
  }

  // ── Navegador ─────────────────────────────────────────────────────────────

  function busy(btn) {
    if (btn.dataset.busy === "1") return;
    btn.dataset.busy = "1";
    btn.dataset.originalHtml = btn.innerHTML; // generation-guard.js lo restaura al volver atrás
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    btn.classList.add("opacity-60", "cursor-wait");
    btn.textContent = btn.dataset.busyLabel || "Arrancando…";
  }

  function restore(btn) {
    if (btn.dataset.busy !== "1") return;
    btn.innerHTML = btn.dataset.originalHtml || btn.innerHTML;
    delete btn.dataset.busy;
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
    btn.classList.remove("opacity-60", "cursor-wait");
    if (window.lucide) window.lucide.createIcons();
  }

  function nota(btn) {
    const next = btn.nextElementSibling;
    return next && next.matches("[data-escribir-error]") ? next : null;
  }

  function error(btn, mensaje) {
    const p = nota(btn) || document.createElement("p");
    p.className = "nota-forge nota-forge--error mt-2 w-full";
    p.setAttribute("data-escribir-error", "");
    p.setAttribute("role", "alert");
    p.textContent = mensaje;
    if (!p.parentNode) btn.insertAdjacentElement("afterend", p);
  }

  function clearError(btn) {
    const p = nota(btn);
    if (p) p.remove();
  }

  if (typeof document !== "undefined") {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest && e.target.closest("[data-escribir-relato]");
      if (!btn) return;
      e.preventDefault();
      run(btn, {
        confirm: (o) => window.ForgeConfirm.ask(o),
        // Solo en el asistente: con hx-boost ForgeAsistente queda de una página anterior.
        before: btn.closest("[data-asistente]") && window.ForgeAsistente ? window.ForgeAsistente.flushAll : undefined,
        fetch: (url, init) => window.fetch(url, init),
        go: (url) => (window.location.href = url),
        busy,
        restore,
        error,
        clearError,
      });
    });
  }

  return { run, textos };
});
