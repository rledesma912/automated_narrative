/**
 * Menú lateral colapsable (Spec-550 H3).
 *
 * El estado vive en <html data-sidebar="collapsed"> (lo aplica un script chico en
 * <head> antes de pintar) y se recuerda por navegador en localStorage. Con hx-boost
 * el <html> no se reemplaza: solo hay que mantener al día el botón del menú nuevo.
 */
(function () {
  const KEY = "forge:sidebar";

  const collapsed = () => document.documentElement.dataset.sidebar === "collapsed";

  function syncButton() {
    const btn = document.querySelector("[data-sidebar-toggle]");
    if (!btn) return;
    const label = collapsed() ? "Mostrar el menú" : "Ocultar el menú";
    btn.setAttribute("aria-expanded", String(!collapsed()));
    btn.setAttribute("aria-label", label);
    btn.setAttribute("title", label);
  }

  function toggle() {
    if (collapsed()) delete document.documentElement.dataset.sidebar;
    else document.documentElement.dataset.sidebar = "collapsed";
    try {
      localStorage.setItem(KEY, collapsed() ? "collapsed" : "expanded");
    } catch {
      /* sin storage: vale para esta página */
    }
    syncButton();
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest && e.target.closest("[data-sidebar-toggle]")) toggle();
  });
  document.addEventListener("DOMContentLoaded", syncButton);
  document.addEventListener("htmx:afterSettle", syncButton);
})();
