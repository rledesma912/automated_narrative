/**
 * Streaming Room Client (Spec-318 §9.C)
 *
 * Lee STORY_ID, TOTAL_BEATS y ACTIVE_JOB_ID desde window.* (inyectadas
 * por un <script> previo del template antes de cargar este archivo).
 *
 * Spec-460: la generación es un job del servidor.
 *   - Iniciar/Regenerar → POST /api/v1/stories/{id}/jobs (202; 409 = ya hay uno
 *     en curso → nos atamos a ese).
 *   - Avance → EventSource /api/v1/jobs/{job_id}/events (replay + en vivo; ante
 *     un corte el browser reconecta solo y retoma con Last-Event-ID).
 *   - Cancelar → POST /api/v1/jobs/{job_id}/cancel (detiene el pipeline).
 *   - Si al cargar ya hay un job activo (ACTIVE_JOB_ID), la sala se ata sola.
 *
 * Eventos SSE consumidos (Spec-210 + Spec-460):
 *   status (con stage/beat), beat_start, beat_done, heartbeat, done, stream_error
 *
 * Handlers expuestos a window (los botones del template los referencian
 * con onclick="..."):
 *   initiateGeneration, initiateRegeneration, retryStream, cancelGeneration
 */
(function () {
  "use strict";

  const STORY_ID = window.STORY_ID;
  const TOTAL_BEATS = window.TOTAL_BEATS || 5;

  let beatCount = 0;
  let es = null;
  let currentJobId = window.ACTIVE_JOB_ID || null;
  let cancelling = false;
  let jobInfo = null; // GET /jobs/{id} + etapa en vivo, para el tiempo restante (Spec-510)
  let etaTimer = null;
  const ETA_TICK_MS = 15000;

  function jobEventsUrl(jobId) {
    return `/api/v1/jobs/${jobId}/events`;
  }
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
        "w-14 h-14 -mt-1 rounded-full border-4 border-forge-accent bg-forge-surface flex items-center justify-center z-10 animate-pulse shadow-lg shadow-forge-accent/30";
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
    stopEta();
    setBadge("ERROR", "border-forge-error-border text-forge-error");
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

  function showDone() {
    stopEta();
    showDuration(currentJobId);
    setBadge("COMPLETO", "border-forge-success-border text-forge-success");
    setStatus("Historia generada con éxito");
    hideSpinner();

    const panel = document.getElementById("done-panel");
    if (panel) panel.classList.remove("hidden");

    if (es) {
      es.close();
      es = null;
    }
    if (window.lucide) lucide.createIcons();
  }

  /* ── Tiempo restante (Spec-510) ────────────────────────────────────────── */

  async function fetchJob(jobId) {
    try {
      const resp = await fetch(`/api/v1/jobs/${jobId}`);
      if (!resp.ok) return null;
      const job = await resp.json();
      job.received_at = Date.now();
      return job;
    } catch {
      return null;
    }
  }

  function renderEta() {
    const el = document.getElementById("eta-line");
    const eta = window.ForgeEta;
    if (!el) return;
    if (!eta || !jobInfo) {
      el.textContent = "";
      return;
    }
    el.textContent = eta.formatRemaining(eta.remainingFor(jobInfo, eta.elapsedNow(jobInfo, Date.now())));
  }

  function startEta(jobId) {
    stopEta();
    fetchJob(jobId).then((job) => {
      if (!job || currentJobId !== jobId || !es) return;
      jobInfo = job;
      renderEta();
      etaTimer = setInterval(renderEta, ETA_TICK_MS);
    });
  }

  function trackStage(d) {
    if (!jobInfo || !d.stage) return;
    jobInfo.stage = d.stage;
    if (d.beat !== undefined) jobInfo.beat = d.beat;
    if (d.total_beats) jobInfo.total_beats = d.total_beats;
    renderEta();
  }

  function stopEta() {
    if (etaTimer) clearInterval(etaTimer);
    etaTimer = null;
    jobInfo = null;
    renderEta();
  }

  async function showDuration(jobId) {
    const el = document.querySelector("[data-done-duration]");
    const job = jobId ? await fetchJob(jobId) : null;
    const took = job && window.ForgeEta ? window.ForgeEta.formatDuration(job.elapsed_seconds) : "";
    if (!el || !took) return;
    el.textContent = `Lista en ${took}`;
    el.classList.remove("hidden");
  }

  /* ── Acciones del usuario ──────────────────────────────────────────────── */

  async function cancelGeneration() {
    cancelling = true;
    stopEta();
    if (es) {
      es.close();
      es = null;
    }
    if (currentJobId) {
      try {
        // Spec-460: cancela el job en el servidor (detiene el pipeline LLM).
        await fetch(`/api/v1/jobs/${currentJobId}/cancel`, { method: "POST" });
      } catch {
        /* sin red: el job sigue; la sala muestra igual el estado cancelado */
      }
    }

    const initialSpinner = document.getElementById("initial-spinner");
    if (initialSpinner) initialSpinner.classList.add("hidden");
    const logContainer = document.getElementById("log-container");
    if (logContainer) logContainer.classList.add("hidden");
    const errorPanel = document.getElementById("error-panel");
    if (errorPanel) errorPanel.classList.remove("hidden");
    setBadge("CANCELADA", "border-forge-border text-forge-muted");

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

  // Reintentar: si el job sigue en curso nos volvemos a atar; si terminó, se
  // lanza uno nuevo.
  async function retryStream() {
    activateAnimations();
    const errorPanel = document.getElementById("error-panel");
    if (errorPanel) errorPanel.classList.add("hidden");
    if (currentJobId) {
      try {
        const resp = await fetch(`/api/v1/jobs/${currentJobId}`);
        const job = resp.ok ? await resp.json() : null;
        if (job && (job.status === "queued" || job.status === "running")) {
          startStream(currentJobId);
          return;
        }
      } catch {
        /* sin red: intentamos lanzar uno nuevo */
      }
    }
    startJob();
  }

  function showStarting() {
    const startPanel = document.getElementById("start-panel");
    if (startPanel) startPanel.classList.add("hidden");
    const initialSpinner = document.getElementById("initial-spinner");
    if (initialSpinner) initialSpinner.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
  }

  // Crea el job en el servidor y se ata a su canal. Un 409 significa que ya hay
  // una generación en curso para la historia: nos atamos a esa.
  async function startJob() {
    showStarting();
    setBadge("INICIANDO", "border-forge-border text-forge-muted");
    try {
      const resp = await fetch(`/api/v1/stories/${STORY_ID}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "full_generation" }),
      });
      const body = await resp.json().catch(() => ({}));
      if ((resp.status === 202 || resp.status === 409) && body.job_id) {
        startStream(body.job_id);
        return;
      }
      showError(`No se pudo iniciar la generación: ${body.detail || resp.status}`);
    } catch {
      showError("Error de red al iniciar la generación. Verificá la conexión con el servidor.");
    }
  }

  // Spec-219: la regeneración sigue pidiendo confirmación en la UI; la limpieza
  // de la generación anterior la hace el job al arrancar (Spec-460).
  const initiateGeneration = startJob;
  const initiateRegeneration = startJob;

  function activateAnimations() {
    const spin = document.getElementById("spinner-spin");
    if (spin) spin.classList.add("animate-spin");
    const sparkles = document.getElementById("sparkles-icon");
    if (sparkles) sparkles.classList.add("animate-pulse");
    const processing = document.getElementById("processing-text");
    if (processing) processing.classList.add("animate-pulse");
  }

  /* ── SSE ───────────────────────────────────────────────────────────────── */

  function startStream(jobId) {
    currentJobId = jobId;
    cancelling = false;
    activateAnimations();
    setBadge("CONECTANDO", "border-forge-border text-forge-muted");
    setStatus("Conectando con el sistema...");

    es = new EventSource(jobEventsUrl(jobId));
    startEta(jobId);

    es.addEventListener("status", (e) => {
      revealLogs();
      try {
        const d = JSON.parse(e.data);
        setStatus(d.msg);
        appendLog(`🔍 ${d.msg}`);
        trackStage(d);
        if (d.stage) setBadge("GENERANDO", "border-forge-accent text-forge-accent");
      } catch {
        /* payload mal formado — ignorar */
      }
    });

    // beat_start abre el beat (llega antes de sus etapas): solo marca el punto;
    // el log ya muestra cada etapa ("Mapeando/Narrando acto N...").
    es.addEventListener("beat_start", (e) => {
      revealLogs();
      try {
        const d = JSON.parse(e.data);
        setBadge("GENERANDO", "border-forge-accent text-forge-accent");
        markDot(d.number, "active");
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

    // Heartbeat: mantiene el canal vivo. En la sala no hay canal global, así que
    // la sala avisa al pie que el Core responde (Spec-460).
    es.addEventListener("heartbeat", () => {
      document.dispatchEvent(new CustomEvent("forge:core-status", { detail: { alive: true } }));
    });
    es.addEventListener("open", () => {
      document.dispatchEvent(new CustomEvent("forge:core-status", { detail: { alive: true } }));
    });

    es.addEventListener("done", (e) => {
      try {
        const d = JSON.parse(e.data);
        showDone();
        appendLog(`🏁 Historia completa — ${d.total_beats ?? beatCount} beats generados`);
      } catch {
        showDone();
      }
    });

    es.addEventListener("stream_error", (e) => {
      if (cancelling) return; // el panel de cancelación ya está a la vista
      try {
        const d = JSON.parse(e.data);
        showError(d.msg ?? "Error desconocido en el pipeline");
      } catch {
        showError("Error de conexión con el servidor");
      }
    });

    es.onerror = () => {
      if (!es) return;
      // CONNECTING: el browser reintenta solo y retoma con Last-Event-ID.
      if (es.readyState === EventSource.CONNECTING) {
        setStatus("Conexión interrumpida — reconectando...");
        return;
      }
      if (beatCount === TOTAL_BEATS) {
        showDone();
        return;
      }
      showError("Conexión interrumpida. El servidor no responde.");
    };
  }

  // Si al cargar la sala ya hay un job en curso, nos atamos sin pedir confirmación.
  if (currentJobId) {
    showStarting();
    startStream(currentJobId);
  }

  /* ── Exposición a window (onclick handlers del template) ───────────────── */

  window.initiateGeneration = initiateGeneration;
  window.initiateRegeneration = initiateRegeneration;
  window.retryStream = retryStream;
  window.cancelGeneration = cancelGeneration;
})();
