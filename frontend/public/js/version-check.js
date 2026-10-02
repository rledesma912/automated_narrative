/**
 * Spec-630 B17: con hx-boost el <head> no se vuelve a cargar al navegar, así que
 * el CSS y los scripts de la primera carga siguen vivos aunque haya otros (pasó en
 * dev al cambiar los estilos y pasa en prod después de un deploy). Si la página
 * que llega trae otra versión de los estáticos (`<meta name="asset-version">`),
 * en vez de reemplazar el contenido se navega a esa URL de forma completa.
 *
 * Script clásico con patrón UMD (como eta.js): en el browser se instala solo; en
 * Node (Vitest) exporta las funciones puras.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else {
    root.ForgeVersion = api;
    api.install(root.document);
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const META = /<meta\s+name="asset-version"\s+content="([^"]*)"/i;

  /** La versión que trae una página completa; null si es un fragmento. */
  function versionIn(html) {
    const m = typeof html === "string" ? html.match(META) : null;
    return m ? m[1] : null;
  }

  /** Hace falta una carga completa si llega una página con otra versión. */
  function needsFullLoad(current, html) {
    const incoming = versionIn(html);
    return !!current && incoming !== null && incoming !== current;
  }

  function install(doc) {
    if (!doc || doc.__forgeVersionCheck) return;
    doc.__forgeVersionCheck = true;
    doc.addEventListener("htmx:beforeSwap", (e) => {
      const xhr = e.detail && e.detail.xhr;
      const meta = doc.querySelector('meta[name="asset-version"]');
      if (!xhr || !meta || !needsFullLoad(meta.content, xhr.responseText)) return;
      e.detail.shouldSwap = false;
      window.location.assign(xhr.responseURL || window.location.href);
    });
  }

  return { versionIn, needsFullLoad, install };
});
