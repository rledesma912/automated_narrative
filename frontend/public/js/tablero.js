/**
 * Spec-795: una entrega del tablero.
 *
 * - Visor: tocar una imagen la abre grande en un <dialog>; ← → pasan, Esc cierra.
 * - Votar: «Me gusta» / «No va», uno por navegador (D6: la cookie `forge_navegador`); tocar el
 *   propio de nuevo lo saca. «Dejar una nota» abre un campo. Sin nombres (D1).
 * - Sacar: la «×» de una opinión pregunta con ForgeConfirm y la borra.
 * Después de opinar o sacar, se pide la página de nuevo y se reemplaza solo el bloque de
 * opiniones de ese archivo (el HTML sale de la misma vista que al cargar).
 *
 * UMD: en Node (Vitest) exporta las funciones puras; en el browser se engancha solo.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else {
    root.ForgeTablero = api;
    api.enganchar(root.document);
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /** El índice siguiente (o anterior) en el visor, dando la vuelta. */
  function mover(i, paso, total) {
    if (!total) return 0;
    return (((i + paso) % total) + total) % total;
  }

  /** D6: el id de este navegador, de la cookie que pone la página (o "" si no hay). */
  function navegador(cookies) {
    const par = (cookies || "").split(";").map((c) => c.trim().split("=")).find(([k]) => k === "forge_navegador");
    return par && /^[A-Za-z0-9-]{8,64}$/.test(par[1]) ? par[1] : "";
  }

  /** El cuerpo del POST de una opinión, o null si no hay nada que mandar. */
  function cuerpoOpinion(archivo, tipo, texto, nav) {
    if (!archivo || !["me_gusta", "no_va", "nota"].includes(tipo)) return null;
    if (tipo !== "nota") return nav ? { archivo, tipo, navegador: nav } : null;
    const t = (texto || "").trim();
    return t ? { archivo, tipo, texto: t, navegador: nav || "" } : null;
  }

  function enganchar(doc) {
    if (!doc || doc.__forgeTablero) return;
    doc.__forgeTablero = true;
    const detalle = () => doc.querySelector("[data-tablero-detalle]");
    const entregaId = () => detalle().dataset.entrega;
    const base = () => `/api/v1/tablero/entregas/${encodeURIComponent(entregaId())}`;
    let actual = 0;

    // ── visor ──
    const items = () => Array.from(doc.querySelectorAll("[data-visor-item]"));
    function mostrar(i) {
      const lista = items();
      if (!lista.length) return;
      actual = mover(i, 0, lista.length);
      const it = lista[actual];
      const visor = doc.querySelector("[data-visor]");
      visor.querySelector("[data-visor-img]").src = it.dataset.src;
      visor.querySelector("[data-visor-img]").alt = it.dataset.leyenda || "";
      visor.querySelector("[data-visor-leyenda]").textContent = it.dataset.leyenda || "";
      const varias = lista.length > 1;
      visor.querySelector("[data-visor-anterior]").hidden = !varias;
      visor.querySelector("[data-visor-siguiente]").hidden = !varias;
      if (!visor.open) visor.showModal();
    }

    // ── opiniones ──
    async function refrescar(archivo) {
      const html = await (await fetch(window.location.href, { headers: { "Cache-Control": "no-store" } })).text();
      const nuevo = new DOMParser().parseFromString(html, "text/html");
      const sel = `[data-archivo="${CSS.escape(archivo)}"] [data-opiniones]`;
      const viejo = doc.querySelector(sel);
      const reemplazo = nuevo.querySelector(sel);
      if (viejo && reemplazo) {
        viejo.replaceWith(reemplazo);
        if (window.lucide) window.lucide.createIcons();
      }
    }

    async function opinar(archivo, tipo, texto) {
      const cuerpo = cuerpoOpinion(archivo, tipo, texto, navegador(doc.cookie));
      if (!cuerpo) return false;
      const r = await fetch(`${base()}/opiniones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      });
      if (!r.ok) return false;
      await refrescar(archivo);
      return true;
    }

    async function sacar(boton) {
      const archivo = boton.closest("[data-archivo]").dataset.archivo;
      const ok = await window.ForgeConfirm.ask({
        title: "¿Sacar esta opinión?",
        message: boton.getAttribute("aria-label") || "",
        confirmLabel: "Sacar",
        icon: "borrar",
      });
      if (!ok) return;
      await fetch(`/api/v1/tablero/opiniones/${encodeURIComponent(boton.dataset.sacar)}`, { method: "DELETE" });
      await refrescar(archivo);
    }

    doc.addEventListener("click", (e) => {
      if (!detalle()) return;
      const t = e.target;
      const item = t.closest("[data-visor-item]");
      if (item) return mostrar(items().indexOf(item));
      if (t.closest("[data-visor-anterior]")) return mostrar(actual - 1);
      if (t.closest("[data-visor-siguiente]")) return mostrar(actual + 1);
      if (t.closest("[data-visor-cerrar]")) return doc.querySelector("[data-visor]").close();
      const archivoDe = (el) => el.closest("[data-archivo]").dataset.archivo;
      const b = t.closest("[data-opinar]");
      if (b) {
        b.disabled = true;
        opinar(archivoDe(b), b.dataset.opinar).finally(() => (b.disabled = false));
        return;
      }
      const abrir = t.closest("[data-nota-abrir]");
      if (abrir) {
        const form = abrir.closest("[data-opiniones]").querySelector("[data-nota-form]");
        form.hidden = false;
        form.querySelector("textarea").focus();
        return;
      }
      const cancelar = t.closest("[data-nota-cancelar]");
      if (cancelar) {
        const form = cancelar.closest("[data-nota-form]");
        form.hidden = true;
        form.reset();
        return;
      }
      const quitar = t.closest("[data-sacar]");
      if (quitar) sacar(quitar);
    });

    doc.addEventListener("submit", (e) => {
      const form = e.target.closest && e.target.closest("[data-nota-form]");
      if (!form || !detalle()) return;
      e.preventDefault();
      opinar(form.closest("[data-archivo]").dataset.archivo, "nota", form.elements.texto.value);
    });

    doc.addEventListener("keydown", (e) => {
      const visor = doc.querySelector("[data-visor]");
      if (!visor || !visor.open) return;
      if (e.key === "ArrowLeft") mostrar(actual - 1);
      if (e.key === "ArrowRight") mostrar(actual + 1);
    });
  }

  return { mover, cuerpoOpinion, navegador, enganchar };
});
