/**
 * Aviso flotante del guardado automático (Spec-550 H6), para las pantallas de la
 * Spec-610 (corregir el relato, el paquete para el video). Usa el parcial
 * `asistente/_guardado.ejs`: «Guardado» ~2 s y se va; «Guardando…» solo si tarda más
 * de 1 s; un error queda hasta que un guardado sale bien o se cierra.
 * `data-pendiente="1"` marca un guardado en curso (lo esperan los E2E).
 */
(function () {
  "use strict";

  const TOAST_MS = 2000;
  const SLOW_MS = 1000;
  let toastTimer = null;
  let slowTimer = null;

  const el = () => document.querySelector("[data-guardado]");

  function show(kind, text) {
    const toast = el();
    if (!toast) return;
    const icon = kind === "ok" ? "check" : kind === "error" ? "alert-circle" : "loader";
    toast.querySelector("[data-guardado-icono]").innerHTML =
      `<i data-lucide="${icon}" class="w-4 h-4${kind === "saving" ? " animate-spin" : ""}"></i>`;
    toast.querySelector("[data-guardado-texto]").textContent = text;
    toast.setAttribute("role", kind === "error" ? "alert" : "status");
    toast.dataset.estado = kind;
    if (window.lucide) window.lucide.createIcons();
  }

  function hide() {
    const toast = el();
    if (toast) toast.dataset.estado = "oculto";
  }

  /** kind: pending (tecleando) | saving | ok | error. */
  function status(kind, text) {
    clearTimeout(toastTimer);
    clearTimeout(slowTimer);
    const toast = el();
    if (toast) toast.dataset.pendiente = kind === "pending" || kind === "saving" ? "1" : "";
    if (kind === "saving") slowTimer = setTimeout(() => show("saving", text), SLOW_MS);
    else if (kind === "ok") {
      show("ok", text);
      toastTimer = setTimeout(hide, TOAST_MS);
    } else if (kind === "error") show("error", text);
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest && e.target.closest("[data-guardado-cerrar]")) hide();
  });

  window.ForgeGuardado = { status, hide };
})();
