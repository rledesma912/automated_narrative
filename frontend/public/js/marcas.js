/**
 * Lo remarcado en un bloque del guion (Spec-610 §3.7.2, D22).
 *
 * Una marca es un tramo de palabras del bloque ([desde, hasta], desde 0). Tocar una
 * palabra la marca o la desmarca (solo esa, no las iguales); arrastrar sobre varias
 * marca o desmarca la frase entera. Las palabras marcadas que quedan juntas forman una
 * sola frase. `reubicar` es la misma regla que `src/application/services/video/state.py`
 * (casos compartidos en tests/fixtures/video/marcas_casos.json).
 *
 * Script clásico UMD: `window.ForgeMarcas` en el browser, `module.exports` en Vitest.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ForgeMarcas = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /** Una palabra para comparar: minúsculas y sin signos alrededor («¿Qué?» → «qué»). */
  function clave(palabra) {
    return String(palabra).toLowerCase().replace(/^[^\p{L}\p{N}_]+|[^\p{L}\p{N}_]+$/gu, "");
  }

  /** Posiciones marcadas → tramos [[desde, hasta], …], juntando las seguidas. */
  function tramos(posiciones) {
    const ks = [...new Set(posiciones)].sort((a, b) => a - b);
    const out = [];
    ks.forEach((k) => {
      const ultimo = out[out.length - 1];
      if (ultimo && ultimo[1] === k - 1) ultimo[1] = k;
      else out.push([k, k]);
    });
    return out;
  }

  function posiciones(marcas) {
    const out = [];
    marcas.forEach(([d, h]) => {
      for (let k = d; k <= h; k++) out.push(k);
    });
    return out;
  }

  /** Tocar la palabra `k`: la marca o la desmarca. */
  function alternarPalabra(marcas, k) {
    const ps = new Set(posiciones(marcas));
    if (ps.has(k)) ps.delete(k);
    else ps.add(k);
    return tramos([...ps]);
  }

  /** Arrastrar de `a` a `b`: si ya estaba todo marcado lo desmarca; si no, lo marca. */
  function alternarTramo(marcas, a, b) {
    const [d, h] = a <= b ? [a, b] : [b, a];
    const ps = new Set(posiciones(marcas));
    let todas = true;
    for (let k = d; k <= h; k++) if (!ps.has(k)) todas = false;
    for (let k = d; k <= h; k++) (todas ? ps.delete(k) : ps.add(k));
    return tramos([...ps]);
  }

  function coincide(palabras, inicio, buscadas) {
    if (inicio < 0 || inicio + buscadas.length > palabras.length) return false;
    return buscadas.every((w, j) => clave(palabras[inicio + j]) === w);
  }

  /**
   * Marcas guardadas ({desde_palabra, hasta_palabra, texto}) frente al texto actual del
   * bloque: siguen en su lugar, se reubican por su texto o se pierden.
   */
  function reubicar(palabras, marcas) {
    const tomadas = new Set();
    const libre = (d, n) => [...Array(n).keys()].every((j) => !tomadas.has(d + j));
    const tomar = (d, n) => [...Array(n).keys()].forEach((j) => tomadas.add(d + j));
    const quedan = [];
    const pendientes = [];
    const buscadasDe = (m) => m.texto.split(/\s+/).map(clave).filter(Boolean);
    marcas.forEach((m) => {
      const b = buscadasDe(m);
      if (b.length && coincide(palabras, m.desde_palabra, b) && libre(m.desde_palabra, b.length)) {
        quedan.push({ desde_palabra: m.desde_palabra, hasta_palabra: m.desde_palabra + b.length - 1, texto: m.texto });
        tomar(m.desde_palabra, b.length);
      } else pendientes.push(m);
    });
    const perdidas = [];
    pendientes.forEach((m) => {
      const b = buscadasDe(m);
      let inicio = -1;
      for (let i = 0; b.length && i + b.length <= palabras.length; i++) {
        if (coincide(palabras, i, b) && libre(i, b.length)) {
          inicio = i;
          break;
        }
      }
      if (inicio < 0) {
        perdidas.push(m.texto);
        return;
      }
      const fin = inicio + b.length - 1;
      quedan.push({ desde_palabra: inicio, hasta_palabra: fin, texto: palabras.slice(inicio, fin + 1).join(" ") });
      tomar(inicio, b.length);
    });
    quedan.sort((x, y) => x.desde_palabra - y.desde_palabra);
    return { quedan, perdidas };
  }

  return { clave, tramos, alternarPalabra, alternarTramo, reubicar };
});
