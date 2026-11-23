/**
 * Spec-790 §10.7: la página de la miniatura de una historia.
 *
 * - Autoguardado: cada campo `[data-campo]` hace PUT /api/v1/stories/{id}/thumbnail (los
 *   textos, medio segundo después de dejar de escribir). Cambiar el color o el tono con una
 *   tanda armada la recolorea en el Core y se recarga la página para verla.
 * - Bocetos: `[data-subir-boceto]` sube el archivo (PNG o JPG) y muestra la vista previa.
 * - «Armar las 4»: confirma, lanza el job `thumbnail_build` y abre el modal de la IA; al
 *   terminar recarga. Si al entrar hay un job de miniatura en curso, se reengancha.
 */
(function () {
  "use strict";

  const root = () => document.querySelector("[data-miniatura]");
  const api = () => `/api/v1/stories/${root().dataset.storyId}/thumbnail`;
  const timers = {};

  async function guardar(campo, valor) {
    const resp = await fetch(api(), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [campo]: valor }),
    });
    return resp.ok ? resp.json() : null;
  }

  async function onCampo(el) {
    const campo = el.name;
    const valor = el.value;
    if (campo === "color") {
      const tono = root().querySelector("[data-tono]");
      if (tono) tono.classList.toggle("hidden", valor === "byn");
    }
    const vista = await guardar(campo, valor);
    // con una tanda armada, el color y el tono se rehacen en el Core: recargar para verlas
    if (vista && vista.batches && vista.batches.length && ["color", "tone", "place_description"].includes(campo)) {
      location.reload();
    }
  }

  async function subir(input) {
    const tipo = input.dataset.subirBoceto;
    const error = root().querySelector(`[data-boceto-error="${tipo}"]`);
    const file = input.files && input.files[0];
    if (!file) return;
    if (error) error.classList.add("hidden");
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${api()}/sketches/${tipo}`, { method: "POST", body: form });
    if (!resp.ok) {
      let msg = "No se pudo subir el boceto.";
      try { msg = (await resp.json()).detail || msg; } catch (e) { /* sin detalle */ }
      if (error) { error.textContent = msg; error.classList.remove("hidden"); }
      return;
    }
    location.reload();
  }

  function abrirModal(job) {
    window.ForgeIaModal.open(job, {
      titulo: "Armando las 4 miniaturas…",
      detalle: "La compu arma el personaje y el escenario desde tus bocetos, y después las 4 opciones.",
      onDone: () => location.reload(),
      etapas: {
        esperando_gpu: "Esperando que se libere la compu que hace las imágenes…",
        personaje: "Paso 1: el personaje desde tu boceto",
        escenario: "Paso 2: el escenario desde tu boceto",
        componiendo: "Paso 3: la miniatura {n} de {total}",
      },
    });
  }

  async function armar(button) {
    const error = root().querySelector("[data-armar-error]");
    const ok = await window.ForgeConfirm.ask({
      title: "¿Armar las 4 miniaturas?",
      message: button.dataset.detalle,
      confirmLabel: "Armar",
    });
    if (!ok) return;
    if (error) error.classList.add("hidden");
    const storyId = root().dataset.storyId;
    const resp = await fetch(`/api/v1/stories/${storyId}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "thumbnail_build" }),
    });
    if (resp.status !== 202) {
      let msg = resp.status === 409
        ? "Ya hay algo armándose para esta historia: esperá a que termine."
        : "No se pudo empezar. Probá de nuevo.";
      if (resp.status === 422) {
        try { msg = (await resp.json()).detail || msg; } catch (e) { /* sin detalle */ }
      }
      if (error) { error.textContent = msg; error.classList.remove("hidden"); }
      return;
    }
    abrirModal(await resp.json());
  }

  async function reenganchar() {
    const r = root();
    if (!r || r.dataset.enganchado) return;
    r.dataset.enganchado = "1";
    try {
      const resp = await fetch(`/api/v1/stories/${r.dataset.storyId}/jobs/active`);
      if (!resp.ok) return;
      const job = await resp.json();
      if (job.kind === "thumbnail_build" && window.ForgeIaModal) abrirModal(job);
    } catch (e) { /* sin Core: nada que reenganchar */ }
  }

  if (!window.__miniaturasBound) {
    window.__miniaturasBound = true;
    document.addEventListener("change", (e) => {
      if (!root()) return;
      const el = e.target;
      if (el.matches("[data-subir-boceto]")) subir(el);
      else if (el.matches("[data-campo]") && el.type !== "textarea") onCampo(el);
    });
    document.addEventListener("input", (e) => {
      if (!root()) return;
      const el = e.target;
      if (!el.matches("textarea[data-campo]")) return;
      clearTimeout(timers[el.name]);
      timers[el.name] = setTimeout(() => guardar(el.name, el.value), 600);
    });
    document.addEventListener("focusout", (e) => {
      if (!root()) return;
      const el = e.target;
      if (el.matches("textarea[data-campo]") && el.name === "place_description") {
        clearTimeout(timers[el.name]);
        onCampo(el);
      }
    });
    document.addEventListener("click", (e) => {
      if (!root()) return;
      const b = e.target.closest("[data-armar]");
      if (b && !b.disabled) armar(b);
    });
    document.addEventListener("htmx:load", reenganchar);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", reenganchar);
  else reenganchar();
})();
