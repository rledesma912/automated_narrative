/**
 * Streaming Monitor Client (extraído del bloque inline de streaming-room.ejs).
 *
 * Modo MONITOR: cuando una historia ya está en `processing` y el usuario
 * abre la sala desde otra pestaña, este script se conecta al broadcaster SSE
 * (Spec-220 Slice C/D) que garantiza idempotencia con replay buffer. Una sola
 * pestaña dispara el pipeline; las demás se atan vía `manager.attach()`
 * recibiendo replay + en vivo.
 *
 * Lee `window.MONITOR_STREAM_URL` (inyectada por <script> inline previo).
 *
 * Bug latente arreglado en esta extracción: el inline original usaba
 * `window.addEventListener("DOMContentLoaded", monitorAttach)`, que NO se
 * dispara bajo `<body hx-boost="true">` en navegaciones internas. Ahora el
 * script se ejecuta inmediato (vive al final del body, DOM ya existe) y se
 * registra `htmx:afterSwap` para re-enganchar tras swaps futuros.
 */
(function () {
  "use strict";

  const MONITOR_STREAM_URL = window.MONITOR_STREAM_URL;
  const MONITOR_TOTAL_BEATS = 5;
  let monitorEs = null;

  function monitorAppendLog(msg) {
    const container = document.getElementById("monitor-log");
    if (!container) return;
    const time = new Date().toTimeString().slice(0, 5);
    const el = document.createElement("div");
    el.className = "text-forge-muted border-l-2 border-forge-accent/20 pl-4 py-1";
    el.innerHTML = `<span class="text-forge-accent font-bold opacity-60">[${time}]</span> ${msg}`;
    container.appendChild(el);
    el.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  function monitorSetStatus(msg) {
    const el = document.getElementById("monitor-status");
    if (el) el.textContent = msg;
  }

  function monitorHideSpinner() {
    const el = document.getElementById("monitor-spinner");
    if (el) el.classList.add("hidden");
  }

  function monitorAttach() {
    if (!MONITOR_STREAM_URL) return;
    if (monitorEs) return; // ya conectado

    monitorEs = new EventSource(MONITOR_STREAM_URL);

    monitorEs.addEventListener("status", (e) => {
      try {
        const d = JSON.parse(e.data);
        monitorSetStatus(d.msg);
        monitorAppendLog(`🔍 ${d.msg}`);
      } catch {
        /* ignorar payload mal formado */
      }
    });

    monitorEs.addEventListener("beat_start", (e) => {
      try {
        const d = JSON.parse(e.data);
        monitorSetStatus(`Narrando beat ${d.number}/${MONITOR_TOTAL_BEATS}…`);
        monitorAppendLog(`✍️ Narrando Beat ${d.number}/${MONITOR_TOTAL_BEATS}`);
      } catch {
        /* ignorar */
      }
    });

    monitorEs.addEventListener("beat_done", (e) => {
      try {
        const d = JSON.parse(e.data);
        monitorAppendLog(`✅ Beat ${d.number} completado`);
      } catch {
        /* ignorar */
      }
    });

    monitorEs.addEventListener("heartbeat", () => {
      /* alive */
    });

    monitorEs.addEventListener("done", () => {
      monitorAppendLog(`🏁 Historia completa — recargando…`);
      monitorEs.close();
      monitorEs = null;
      setTimeout(() => window.location.reload(), 800);
    });

    monitorEs.addEventListener("stream_error", (e) => {
      try {
        const d = JSON.parse(e.data);
        monitorAppendLog(`⚠️ Error en pipeline: ${d.msg ?? "desconocido"}`);
      } catch {
        monitorAppendLog(`⚠️ Error desconocido en el stream`);
      }
      monitorHideSpinner();
      monitorSetStatus("Stream finalizado con error");
      if (monitorEs) {
        monitorEs.close();
        monitorEs = null;
      }
    });

    monitorEs.onerror = () => {
      monitorAppendLog(`⚠️ Conexión SSE interrumpida — reintentando…`);
      // EventSource hace auto-reconnect; no cerramos manualmente.
    };
  }

  // Bajo hx-boost no se dispara DOMContentLoaded en la primera navegación.
  // Ejecutar inmediato (script vive al final del body, DOM ya existe).
  monitorAttach();

  // Re-attach en navegaciones hx-boost si el endpoint sigue siendo válido.
  document.addEventListener("htmx:afterSwap", monitorAttach);
})();
