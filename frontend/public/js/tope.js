/**
 * Cuántas letras entran en un campo del asistente (Spec-760 A1).
 *
 * Ningún campo corta en silencio: en vez de `maxlength`, el campo lleva
 * `data-tope="N"`. Desde el 80 % se ve un contador debajo y, pasado el tope, un
 * aviso con cuánto sobra. El autoguardado no manda un campo pasado
 * (`ForgeTope.excedido`, lo usa asistente.js): el texto queda en el cuadro.
 *
 * Los textos están en la vista (`#tope-textos`, partial `_tope.ejs`). Script
 * clásico con patrón UMD: en el browser queda en `window.ForgeTope`; en Node
 * (Vitest) se exportan las funciones puras.
 */
(function (root, factory) {
  const api = factory(typeof document !== "undefined" ? document : null);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ForgeTope = api;
})(typeof self !== "undefined" ? self : this, function (doc) {
  "use strict";

  const AVISO_DESDE = 0.8; // el contador aparece desde el 80 % del tope
  const CAMPOS = "[data-tope]";

  /** Letras como las cuenta la API (Python `len`: un emoji es una, no dos). */
  function largo(text) {
    return Array.from(text || "").length;
  }

  /** 21300 → «21.300», como en el resto del sitio. */
  function miles(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function estado(text, tope) {
    const n = largo(text);
    return { n, tope, sobra: Math.max(0, n - tope), visible: tope > 0 && n >= tope * AVISO_DESDE, excedido: tope > 0 && n > tope };
  }

  function llenar(plantilla, datos) {
    return String(plantilla || "").replace(/\{(\w+)\}/g, (_, k) => (k in datos ? datos[k] : ""));
  }

  /** El texto del contador: «16.200 de 20.000 letras» o «Sobran 1.300 letras: …». */
  function texto(est, textos) {
    return est.excedido
      ? llenar(textos.sobra, { sobra: miles(est.sobra) })
      : llenar(textos.cuenta, { n: miles(est.n), tope: miles(est.tope) });
  }

  // ── DOM ─────────────────────────────────────────────────────────────────

  function textos() {
    const t = doc && doc.getElementById("tope-textos");
    return t ? { cuenta: t.dataset.cuenta, sobra: t.dataset.sobra } : { cuenta: "", sobra: "" };
  }

  /** Los topes de config, para los campos que arma el JS (un hecho o una regla nuevos). */
  function de(campo) {
    const t = doc && doc.getElementById("tope-textos");
    try {
      return (t && JSON.parse(t.dataset.topes || "{}")[campo]) || 0;
    } catch {
      return 0;
    }
  }

  function topeDe(field) {
    return Number(field.dataset.tope) || 0;
  }

  function contador(field) {
    const next = field.nextElementSibling;
    if (next && next.hasAttribute("data-tope-contador")) return next;
    const p = doc.createElement("p");
    p.setAttribute("data-tope-contador", "");
    p.setAttribute("aria-live", "polite");
    p.hidden = true;
    field.insertAdjacentElement("afterend", p);
    return p;
  }

  /** Muestra, actualiza o esconde el contador del campo. */
  function actualizar(field) {
    const est = estado(field.value, topeDe(field));
    const p = est.visible ? contador(field) : field.nextElementSibling;
    field.toggleAttribute("aria-invalid", est.excedido);
    if (!p || !p.hasAttribute("data-tope-contador")) return est;
    p.hidden = !est.visible;
    p.className = est.excedido ? "nota-forge nota-forge--warning mt-1 mb-3" : "pista-forge mt-1 mb-3";
    p.textContent = est.visible ? texto(est, textos()) : "";
    return est;
  }

  /** Todos los campos con tope de `scope` (al cargar y después de reemplazar un fragmento). */
  function todos(scope) {
    if (!doc) return;
    (scope || doc).querySelectorAll(CAMPOS).forEach(actualizar);
  }

  /**
   * El aviso del primer campo de `scope` pasado de su tope ("" si ninguno). `excepto`:
   * selector de campos que no cuentan (los de «+ Lugar» o «+ Personaje» de un acto).
   */
  function excedido(scope, excepto) {
    if (!scope) return "";
    for (const field of scope.querySelectorAll(CAMPOS)) {
      if (excepto && field.matches(excepto)) continue;
      const est = estado(field.value, topeDe(field));
      if (est.excedido) {
        actualizar(field);
        return texto(est, textos());
      }
    }
    return "";
  }

  if (doc) {
    doc.addEventListener("input", (e) => {
      if (e.target && e.target.matches && e.target.matches(CAMPOS)) actualizar(e.target);
    });
    if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", () => todos());
    else todos();
  }

  return { AVISO_DESDE, largo, miles, estado, texto, todos, excedido, de };
});
