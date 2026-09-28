/**
 * Confirmación con el tema (Spec-550 H8): reemplaza al diálogo «confirm» del navegador.
 *
 * `ForgeConfirm.ask({ title, message, confirmLabel }) → Promise<boolean>` abre el
 * <dialog id="forge-confirm"> del layout (partials/confirm_dialog.ejs): foco en
 * «Cancelar», `Esc` cancela y al cerrar el foco vuelve a donde estaba. Todo
 * `hx-confirm` de HTMX pasa por acá (evento `htmx:confirm`).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ForgeConfirm = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function ask({ title = "¿Seguro?", message = "", confirmLabel = "Confirmar" } = {}) {
    const dialog = document.getElementById("forge-confirm");
    if (!dialog || typeof dialog.showModal !== "function") return Promise.resolve(false);
    const previous = document.activeElement;
    dialog.querySelector("[data-confirm-titulo]").textContent = title;
    dialog.querySelector("[data-confirm-mensaje]").textContent = message;
    dialog.querySelector("[data-confirm-aceptar]").textContent = confirmLabel;

    return new Promise((resolve) => {
      function done(ok) {
        dialog.removeEventListener("click", onClick);
        dialog.removeEventListener("cancel", onCancel);
        if (dialog.open) dialog.close();
        if (previous && typeof previous.focus === "function") previous.focus();
        resolve(ok);
      }
      function onClick(e) {
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

  return { ask };
});
