/**
 * Tiempos del episodio (Spec-610 §3.2): palabras / ritmo de lectura, sin IA.
 *
 * La misma cuenta que `src/application/services/video/timing.py`: los dos pasan los
 * casos de `tests/fixtures/video/tiempos_casos.json`. Script clásico con patrón UMD:
 * en el browser queda en `window.ForgeTiempos`; en Node (Vitest), `module.exports`.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ForgeTiempos = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /** Cantidad de palabras: lo que hay entre espacios, tabulaciones o saltos de línea. */
  function palabras(texto) {
    const tokens = String(texto || "").trim().split(/\s+/);
    return tokens[0] === "" ? 0 : tokens.length;
  }

  /** Segundos que lleva leer `cantidad` palabras al ritmo dado (la mitad, para arriba). */
  function segundos(cantidad, porMinuto) {
    return Math.floor((cantidad / porMinuto) * 60 + 0.5);
  }

  /** `m:ss`, como en un reproductor («15:36»). */
  function reloj(total) {
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  /** Para leer: «45 s», «1 min», «3 min 11 s». */
  function largo(total) {
    const minutos = Math.floor(total / 60);
    const resto = total % 60;
    if (!minutos) return `${resto} s`;
    return resto ? `${minutos} min ${String(resto).padStart(2, "0")} s` : `${minutos} min`;
  }

  /** «corto», «entra» o «largo» frente al largo del canal (en minutos). */
  function episodio(total, desde, hasta) {
    if (total < desde * 60) return "corto";
    if (total > hasta * 60) return "largo";
    return "entra";
  }

  return { palabras, segundos, reloj, largo, episodio };
});
