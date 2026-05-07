/**
 * Streaming Room Client (Spec-318 §9.C)
 *
 * Paridad 1:1 con el <script> inline original de streaming-room.ejs.
 * Lee STREAM_URL, STORY_ID y TOTAL_BEATS desde window.* (inyectadas
 * por un <script> previo del template antes de cargar este archivo).
 *
 * Eventos SSE consumidos (Spec-210):
 *   status, beat_start, beat_done, heartbeat, done, stream_error
 *
 * Handlers expuestos a window (los botones del template los referencian
 * con onclick="..."):
 *   initiateGeneration, initiateRegeneration, retryStream, cancelGeneration
 */
(function () {
  "use strict";

  const STREAM_URL = window.STREAM_URL;
  const STORY_ID = window.STORY_ID;
  const TOTAL_BEATS = window.TOTAL_BEATS || 5;

  let beatCount = 0;
  let es = null;
  const loadingIntervals = {};

  /* ── UI helpers ────────────────────────────────────────────────────────── */

  function setBadge(text, color) {
    const badge = document.getElementById("connection-badge");
    const textSpan = document.getElementById("badge-text");
    const spinner = document.getElementById("spinner-icon");
    if (!badge || !textSpan || !spinner) return;

    textSpan.textContent = text;
    badge.className = `px-5 py-2 text-sm font-bold rounded border ${color} flex items-center gap-3`;

    if (text === "GENERANDO") {
      spinner.classList.remove("hidden");
    } else {
      spinner.classList.add("hidden");
    }
  }

  function setStatus(msg) {
    const el = document.getElementById("status-line");
    if (el) el.textContent = msg;
  }

  function markDot(num, state) {
    const dot = document.getElementById(`dot-${num}`);
    const label = document.getElementById(`label-${num}`);
    const line = document.getElementById(`line-${num - 1}`);
    if (!dot) return;

    if (state === "active") {
      dot.className =
        "w-14 h-14 -mt-1 rounded-full border-4 border-forge-accent bg-forge-surface flex items-center justify-center z-10 animate-pulse shadow-[0_0_20px_rgba(var(--forge-accent-rgb),0.3)]";
      dot.innerHTML = `<i data-lucide="loader" class="w-6 h-6 text-forge-accent animate-spin"></i>`;
      if (label) {
        label.classList.remove("text-forge-muted");
        label.classList.add("text-forge-accent", "scale-110");
      }
      if (window.lucide) lucide.createIcons();
    } else if (state === "done") {
      dot.className =
        "w-12 h-12 rounded-full border-4 border-forge-accent bg-forge-accent flex items-center justify-center z-10 shadow-inner";
      dot.innerHTML = `<i data-lucide="check" class="w-6 h-6 text-forge-bg"></i>`;
      if (label) {
        label.classList.remove("text-forge-accent", "scale-110");
        label.classList.add("text-forge-muted");
      }
      if (line) {
        line.classList.remove("bg-forge-border");
        line.classList.add("bg-forge-accent");
      }
      if (window.lucide) lucide.createIcons();
    }
  }

  // Bug 7: separadas. revealLogs() solo muestra el log-container; el spinner
  // permanece visible mientras dure la generación y se oculta solo al cierre
  // del flujo (showDone, showError, cancelGeneration).
  function revealLogs() {
    const log = document.getElementById("log-container");
    if (log) log.classList.remove("hidden");
  }

  function hideSpinner() {
    const spinner = document.getElementById("initial-spinner");
    if (spinner) spinner.classList.add("hidden");
  }

  function appendLog(msg, isProgress = false) {
    const container = document.getElementById("log-container");
    if (!container) return null;

    const now = new Date();
    const time = now.toTimeString().slice(0, 5);
    const el = document.createElement("div");
    el.className = "text-forge-muted border-l-2 border-forge-accent/20 pl-4 py-1";

    let dotsHtml = "";
    if (isProgress) {
      dotsHtml = '<span class="loading-dots text-forge-accent font-bold ml-1">...</span>';
    }

    el.innerHTML = `<span class="text-forge-accent font-bold opacity-60">[${time}]</span> ${msg}${dotsHtml}`;
    container.appendChild(el);
    el.scrollIntoView({ behavior: "smooth", block: "end" });

    if (isProgress) {
      const dotsSpan = el.querySelector(".loading-dots");
      const msgId = Date.now().toString();
      let dotIndex = 0;
      const dotStates = [" . ", " .. ", " ... "];

      loadingIntervals[msgId] = setInterval(() => {
        dotIndex = (dotIndex + 1) % dotStates.length;
        if (dotsSpan) dotsSpan.textContent = dotStates[dotIndex];
      }, 400);

      el.dataset.intervalId = msgId;
    }

    return el;
  }

  function clearLoadingDot(element) {
    if (element && element.dataset.intervalId) {
      const intervalId = element.dataset.intervalId;
      if (loadingIntervals[intervalId]) {
        clearInterval(loadingIntervals[intervalId]);
        delete loadingIntervals[intervalId];
      }
      const dotsSpan = element.querySelector(".loading-dots");
      if (dotsSpan) dotsSpan.textContent = "";
    }
  }

  function showError(msg) {
    setBadge("ERROR", "border-red-900 text-red-400");
    hideSpinner();

    let displayMsg = msg;
    if (msg && (msg.includes("All connection attempts failed") || msg.includes("connection"))) {
      displayMsg =
        "El servicio de IA (Ollama) no está disponible. Asegurate de tener Ollama corriendo en tu máquina.";
    }

    const errorMsg = document.getElementById("error-msg");
    const errorPanel = document.getElementById("error-panel");
    if (errorMsg) errorMsg.textContent = displayMsg;
    if (errorPanel) errorPanel.classList.remove("hidden");

    if (es) {
      es.close();
      es = null;
    }
  }

  function showDone(filePath) {
    setBadge("COMPLETO", "border-green-900 text-green-400");
    setStatus("Historia generada con éxito");
    hideSpinner();

    const panel = document.getElementById("done-panel");
    if (panel) panel.classList.remove("hidden");

    if (filePath) {
      const dlBtn = document.getElementById("download-md-btn");
      if (dlBtn) {
        dlBtn.href = `/historia/${STORY_ID}/descargar-markdown`;
        dlBtn.classList.remove("hidden");
        dlBtn.classList.add("inline-flex");
      }
    }

    if (es) {
      es.close();
      es = null;
    }
    if (window.lucide) lucide.createIcons();
  }

  /* ── Acciones del usuario ──────────────────────────────────────────────── */

  async function cancelGeneration() {
    if (es) {
      es.close();
      es = null;
    }
    try {
      // Spec-221: path relativo, mismo origen → Express proxia /api/* al backend.
      await fetch(`/api/v1/stories/${STORY_ID}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "failed" }),
      });
    } catch {
      /* ignorar — el backend lo resolverá por cancelación del SSE */
    }

    const initialSpinner = document.getElementById("initial-spinner");
    if (initialSpinner) initialSpinner.classList.add("hidden");
    const logContainer = document.getElementById("log-container");
    if (logContainer) logContainer.classList.add("hidden");
    const errorPanel = document.getElementById("error-panel");
    if (errorPanel) errorPanel.classList.remove("hidden");

    const errorMsg = document.getElementById("error-msg");
    if (errorMsg) errorMsg.textContent = "La generación fue cancelada antes de completarse.";

    const errorActions = document.querySelector("#error-panel .flex.gap-4");
    if (errorActions) {
      errorActions.innerHTML = `
        <a href="/historia/${STORY_ID}" class="px-6 py-3 bg-forge-accent text-forge-text text-sm uppercase tracking-widest hover:opacity-80 transition-opacity">
          Ver historia
        </a>
        <a href="/galeria" class="px-6 py-3 border border-forge-border text-forge-muted text-sm uppercase tracking-widest hover:text-forge-text transition-colors">
          Galería
        </a>
      `;
    }
    if (window.lucide) lucide.createIcons();
  }

  function retryStream() {
    activateAnimations();
    const errorPanel = document.getElementById("error-panel");
    if (errorPanel) errorPanel.classList.add("hidden");
    startStream();
  }

  function initiateGeneration() {
    const startPanel = document.getElementById("start-panel");
    if (startPanel) startPanel.classList.add("hidden");
    const initialSpinner = document.getElementById("initial-spinner");
    if (initialSpinner) initialSpinner.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
    startStream();
  }

  // Spec-219: regeneración no destructiva — el PATCH (que dispara la limpieza
  // de beats/journal/anchors/MD por Spec-216) solo se ejecuta cuando el usuario
  // confirma desde acá. Hasta este click, la historia mantiene status=completed.
  async function initiateRegeneration() {
    const startPanel = document.getElementById("start-panel");
    if (startPanel) startPanel.classList.add("hidden");
    const initialSpinner = document.getElementById("initial-spinner");
    if (initialSpinner) initialSpinner.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();

    try {
      const resp = await fetch(`/api/v1/stories/${STORY_ID}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "processing" }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        showError(`No se pudo iniciar la regeneración: ${detail || resp.status}`);
        return;
      }
    } catch {
      showError("Error de red al iniciar la regeneración. Verificá la conexión con el servidor.");
      return;
    }
    startStream();
  }

  function activateAnimations() {
    const spin = document.getElementById("spinner-spin");
    if (spin) spin.classList.add("animate-spin");
    const sparkles = document.getElementById("sparkles-icon");
    if (sparkles) sparkles.classList.add("animate-pulse");
    const processing = document.getElementById("processing-text");
    if (processing) processing.classList.add("animate-pulse");
  }

  /* ── SSE ───────────────────────────────────────────────────────────────── */

  function startStream() {
    activateAnimations();
    setBadge("CONECTANDO", "border-forge-border text-forge-muted");
    setStatus("Conectando con el sistema...");

    es = new EventSource(STREAM_URL);

    es.addEventListener("status", (e) => {
      revealLogs();
      try {
        const d = JSON.parse(e.data);
        setStatus(d.msg);
        appendLog(`🔍 ${d.msg}`);
      } catch {
        /* payload mal formado — ignorar */
      }
    });

    es.addEventListener("beat_start", (e) => {
      revealLogs();
      try {
        const d = JSON.parse(e.data);
        setBadge("GENERANDO", "border-forge-accent text-forge-accent");
        setStatus(`Narrando beat ${d.number} de ${TOTAL_BEATS}...`);
        markDot(d.number, "active");
        appendLog(`✍️ Narrando Beat ${d.number}/${TOTAL_BEATS}`, true);
      } catch {
        /* ignorar */
      }
    });

    es.addEventListener("beat_done", (e) => {
      try {
        const d = JSON.parse(e.data);
        beatCount = d.number;
        markDot(d.number, "done");

        const logs = document.querySelectorAll("#log-container > div");
        if (logs.length > 0) {
          clearLoadingDot(logs[logs.length - 1]);
        }

        appendLog(`✅ Beat ${d.number} completado`);
      } catch {
        /* ignorar */
      }
    });

    // Heartbeat: mantiene canal vivo, sin acción visual.
    es.addEventListener("heartbeat", () => {
      /* alive */
    });

    es.addEventListener("done", (e) => {
      try {
        const d = JSON.parse(e.data);
        showDone(d.file_path);
        appendLog(`🏁 Historia completa — ${d.total_beats} beats generados`);
      } catch {
        showDone(null);
      }
    });

    es.addEventListener("stream_error", (e) => {
      try {
        const d = JSON.parse(e.data);
        showError(d.msg ?? "Error desconocido en el pipeline");
      } catch {
        showError("Error de conexión con el servidor");
      }
    });

    es.onerror = () => {
      if (beatCount === TOTAL_BEATS) {
        showDone(null);
        return;
      }
      showError("Conexión interrumpida. El servidor no responde.");
    };
  }

  /* ── Exposición a window (onclick handlers del template) ───────────────── */

  window.initiateGeneration = initiateGeneration;
  window.initiateRegeneration = initiateRegeneration;
  window.retryStream = retryStream;
  window.cancelGeneration = cancelGeneration;
})();
