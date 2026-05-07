/**
 * Footer Activity Monitor (extraído de partials/footer.ejs).
 *
 * Polling cada 5s a `/internal/streaming/active` para mostrar:
 *  - Generación activa (con link al stream).
 *  - Último evento del sistema cuando no hay generación.
 *  - Estado de conexión con el Core API (puntito verde/rojo).
 *
 * Bug preexistente arreglado en esta extracción: bajo `<body hx-boost="true">`,
 * cada navegación re-incluía footer.ejs → re-ejecutaba el <script> inline →
 * acumulaba un nuevo `setInterval` sin clearear el anterior. Después de N
 * navegaciones había N intervals corriendo en paralelo (memory + network leak).
 * El guard `window.__footerIntervalId` ahora limpia el interval anterior
 * antes de crear uno nuevo.
 */
(function () {
  "use strict";

  let lastKnownEventTime = null;

  async function checkStatus() {
    try {
      const res = await fetch("/internal/streaming/active");
      if (!res.ok) {
        updateConnStatus(false);
        return;
      }
      updateConnStatus(true);
      const data = await res.json();

      const activeContainer = document.getElementById("footer-active-content");
      const idleContainer = document.getElementById("footer-idle-content");
      if (!activeContainer || !idleContainer) return;

      if (data.active && data.story) {
        activeContainer.classList.remove("hidden");
        idleContainer.classList.add("hidden");
        document.getElementById("footer-story-title").textContent = data.story.title || "Sin título";
        document.getElementById("footer-story-link").href = `/generar/stream/${data.story.id}`;
      } else {
        activeContainer.classList.add("hidden");
        idleContainer.classList.remove("hidden");

        if (data.lastEvent) {
          const event = data.lastEvent;
          const msg = `[${event.timestamp}] ${event.message}`;
          const el = document.getElementById("footer-last-event");
          if (!el) return;

          if (event.timestamp !== lastKnownEventTime) {
            el.classList.add("text-forge-accent");
            setTimeout(() => el.classList.remove("text-forge-accent"), 2000);
            lastKnownEventTime = event.timestamp;
          }
          el.textContent = msg;
        }
      }
    } catch (e) {
      updateConnStatus(false);
    }
  }

  function updateConnStatus(online) {
    const dot = document.getElementById("core-status-dot");
    if (!dot) return;
    dot.className = online
      ? "w-2 h-2 rounded-full bg-green-500"
      : "w-2 h-2 rounded-full bg-red-500 animate-pulse";
  }

  // Guard contra acumulación bajo hx-boost: limpiar el interval anterior si existe.
  if (window.__footerIntervalId) {
    clearInterval(window.__footerIntervalId);
  }
  checkStatus();
  window.__footerIntervalId = setInterval(checkStatus, 15000);
})();
