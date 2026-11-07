/**
 * Spec-740 C6: los botones de IA de una historia de un largo deshabilitado vienen con
 * `data-ia-apagada` y `disabled`. Varios scripts vuelven a habilitar sus botones al
 * terminar algo (asistente.js, generation-guard.js…): este guardia, en captura, corta el
 * clic igual. La API responde 409 de todos modos.
 */
(function () {
  document.addEventListener(
    "click",
    function (e) {
      const el = e.target && e.target.closest && e.target.closest("[data-ia-apagada]");
      if (!el) return;
      e.preventDefault();
      e.stopImmediatePropagation();
    },
    true,
  );
})();
