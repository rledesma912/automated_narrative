/**
 * Relatos Client (extraído de relatos.ejs siguiendo el patrón de Spec-318 §9.C).
 *
 * Maneja:
 *  - Selección de tabs y panels (data-relato-tab / data-relato-panel).
 *  - Copia del contenido al portapapeles con fallback execCommand para HTTP-LAN.
 *
 * `copyRelatoContent` queda expuesta como global porque los botones la invocan
 * con onclick="copyRelatoContent(...)" desde el HTML server-rendered.
 */
(function () {
  "use strict";

  function selectRelato(relatoId) {
    document.querySelectorAll("[data-relato-panel]").forEach((panel) => {
      const isTarget = panel.getAttribute("data-relato-panel") === relatoId;
      panel.classList.toggle("hidden", !isTarget);
      panel.classList.toggle("active", isTarget);
    });

    document.querySelectorAll("[data-relato-tab]").forEach((tab) => {
      const isActive = tab.getAttribute("data-relato-tab") === relatoId;
      if (isActive) {
        tab.classList.add("!border-forge-accent", "!text-forge-text", "!bg-forge-accent/5");
        tab.classList.remove("!text-forge-muted");
      } else {
        tab.classList.remove("!border-forge-accent", "!text-forge-text", "!bg-forge-accent/5");
        tab.classList.add("!text-forge-muted");
      }
    });
  }

  function activateFirstTab() {
    const tabs = document.querySelectorAll("[data-relato-tab]");
    if (tabs.length === 0) return;
    const firstId = tabs[0].getAttribute("data-relato-tab");
    if (firstId) selectRelato(firstId);
  }

  // El listener click delegado se registra UNA sola vez por carga de página.
  // Bajo hx-boost el body se reemplaza pero `document` persiste, así que el
  // flag global evita acumular handlers en navegaciones sucesivas.
  if (!window.__relatosTabClickBound) {
    document.addEventListener("click", (e) => {
      const tab = e.target.closest("[data-relato-tab]");
      if (tab) {
        const relatoId = tab.getAttribute("data-relato-tab");
        if (relatoId) selectRelato(relatoId);
      }
      const guion = e.target.closest("[data-armar-guion]");
      if (guion && !guion.disabled) armarGuion(guion);
    });
    window.__relatosTabClickBound = true;
  }

  /**
   * Spec-610: «Armar el guion para el video» lanza el job `video_script` con el modal
   * que bloquea la página; al terminar se abre «Para el video».
   */
  async function armarGuion(button) {
    const narrativeId = button.dataset.armarGuion;
    const storyId = button.dataset.storyId;
    const error = document.querySelector(`[data-guion-error="${narrativeId}"]`);
    const ok = await window.ForgeConfirm.ask({
      title: "¿Armar el guion para el video?",
      message: button.dataset.detalle,
      confirmLabel: "Armar el guion",
    });
    if (!ok) return;
    if (error) error.classList.add("hidden");
    const resp = await fetch(`/api/v1/stories/${storyId}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "video_script", narrative_id: narrativeId }),
    });
    if (resp.status !== 202) {
      if (error) {
        error.textContent =
          resp.status === 409
            ? "La IA ya está trabajando en esta historia: esperá a que termine."
            : "No se pudo armar el guion. Probá de nuevo.";
        error.classList.remove("hidden");
      }
      return;
    }
    const job = await resp.json();
    window.ForgeIaModal.open(job, {
      titulo: "Armando el guion para el video…",
      detalle: "Reparte el relato en bloques, escribe la intro y el outro de la calabaza y arma lo que va en pantalla.",
      onDone: () => (location.href = `/historia/${storyId}/relatos/${narrativeId}/video`),
    });
  }

  // Bajo hx-boost no se dispara DOMContentLoaded en la primera navegación;
  // ejecutar inmediato al cargarse el script (vive al final del body).
  activateFirstTab();

  document.addEventListener("htmx:afterSwap", activateFirstTab);
})();

function copyRelatoContent(relatoId, button) {
  const contentElement = document.getElementById(`relato-content-${relatoId}`);
  if (!contentElement) {
    console.warn("[copyRelato] elemento no encontrado:", relatoId);
    return;
  }

  // Spec-490: solo rótulos y prosa (data-copy-part); los botones de cada acto
  // viven dentro del contenido y no se copian.
  const textToCopy = Array.from(contentElement.querySelectorAll("[data-copy-part]"))
    .map((part) => part.innerText.trim())
    .filter(Boolean)
    .join("\n\n");
  if (!textToCopy) {
    console.warn("[copyRelato] sin texto para copiar:", relatoId);
    return;
  }

  function showFeedback(btn, ok) {
    if (!btn) return;
    const originalHTML = btn.innerHTML;
    const icon = ok ? "check" : "alert-triangle";
    const label = ok ? "¡Copiado!" : "Error al copiar";
    btn.innerHTML = `<i data-lucide="${icon}" class="w-4 h-4"></i> ${label}`;
    btn.disabled = true;
    if (typeof lucide !== "undefined") lucide.createIcons();
    setTimeout(() => {
      btn.innerHTML = originalHTML;
      btn.disabled = false;
      if (typeof lucide !== "undefined") lucide.createIcons();
    }, 2000);
  }

  function fallbackCopy(text) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-9999px";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (err) {
      console.error("[copyRelato] fallback execCommand falló:", err);
    }
    document.body.removeChild(textarea);
    return ok;
  }

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard
      .writeText(textToCopy)
      .then(() => showFeedback(button, true))
      .catch((err) => {
        console.warn("[copyRelato] clipboard API falló, intentando fallback:", err);
        showFeedback(button, fallbackCopy(textToCopy));
      });
  } else {
    showFeedback(button, fallbackCopy(textToCopy));
  }
}
