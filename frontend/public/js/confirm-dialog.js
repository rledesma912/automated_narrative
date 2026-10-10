/**
 * Confirmación con el tema (Spec-550 H8): reemplaza al diálogo «confirm» del navegador.
 *
 * `ForgeConfirm.ask({ title, message, confirmLabel, icon, note }) → Promise<boolean>` abre el
 * <dialog id="forge-confirm"> del layout (partials/confirm_dialog.ejs): foco en
 * «Cancelar», `Esc` cancela y al cerrar el foco vuelve a donde estaba. Spec-660:
 * `icon` = "aviso" (por defecto) | "escribir" | "borrar"; `note` = una nota de info
 * debajo del mensaje (sin `note`, no se ve). Todo
 * `hx-confirm` de HTMX pasa por acá (evento `htmx:confirm`).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ForgeConfirm = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const ICONOS = ["aviso", "escribir", "borrar"];
  /**
   * Spec-660: el segundo clic de un doble clic cae sobre el diálogo recién abierto y lo
   * aceptaba (o cerraba) sin que se leyera. El navegador lo marca con `detail` ≥ 2
   * (un clic suelto es 1; con el teclado, 0): ese se ignora.
   */
  function isRepeatClick(e) {
    return (e && e.detail) > 1;
  }

  /** Llena el diálogo; sin `icon` ni `note` queda como siempre. */
  function paint(dialog, { title = "¿Seguro?", message = "", confirmLabel = "Confirmar", icon, note } = {}) {
    dialog.querySelector("[data-confirm-titulo]").textContent = title;
    dialog.querySelector("[data-confirm-mensaje]").textContent = message;
    dialog.querySelector("[data-confirm-aceptar]").textContent = confirmLabel;
    const elegido = ICONOS.includes(icon) ? icon : "aviso";
    for (const el of dialog.querySelectorAll("[data-confirm-icono]")) {
      el.hidden = el.dataset.confirmIcono !== elegido;
    }
    const nota = dialog.querySelector("[data-confirm-nota]");
    if (nota) {
      nota.hidden = !note;
      dialog.querySelector("[data-confirm-nota-texto]").textContent = note || "";
    }
  }

  function ask(options = {}) {
    const dialog = document.getElementById("forge-confirm");
    if (!dialog || typeof dialog.showModal !== "function") return Promise.resolve(false);
    const previous = document.activeElement;
    paint(dialog, options);

    return new Promise((resolve) => {
      function done(ok) {
        dialog.removeEventListener("click", onClick);
        dialog.removeEventListener("cancel", onCancel);
        if (dialog.open) dialog.close();
        if (previous && typeof previous.focus === "function") previous.focus();
        resolve(ok);
      }
      function onClick(e) {
        if (isRepeatClick(e)) return;
        if (e.target.closest("[data-confirm-aceptar]")) done(true);
        else if (e.target.closest("[data-confirm-cancelar]") || e.target === dialog) done(false);
      }
      function onCancel(e) {
        e.preventDefault(); // Esc: se cierra por done(), no por el navegador
        done(false);
      }
      dialog.addEventListener("click", onClick);
      dialog.addEventListener("cancel", onCancel);
      dialog.showModal();
      dialog.querySelector("[data-confirm-cancelar]").focus();
    });
  }

  if (typeof document !== "undefined") {
    document.addEventListener("htmx:confirm", (e) => {
      if (!e.detail || !e.detail.question) return;
      e.preventDefault();
      const elt = e.detail.elt || {};
      const data = elt.dataset || {};
      ask({ title: data.confirmarTitulo, message: e.detail.question, confirmLabel: data.confirmarLabel }).then(
        (ok) => ok && e.detail.issueRequest(true),
      );
    });
  }

  return { ask, paint, isRepeatClick };
});
