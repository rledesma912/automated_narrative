/**
 * Asistente de autoría (Spec-530 S4): Dirección, Taller y Escaleta.
 *
 * - Guardado automático (decisión 10): cada formulario se guarda solo, con una
 *   cola por formulario; antes de cualquier acción se descargan los pendientes.
 * - La IA nunca corre sola (decisión 11): solo con los botones [data-analizar].
 * - Modal bloqueante (decisión 12) atado al job real: lo sigue por el bus de
 *   eventos (forge:job-*) y, por si se pierde un evento, consultando el job.
 *   Si se entra con un análisis en curso, el modal reaparece solo.
 *
 * Se carga al final de cada vista del asistente. Con hx-boost el script se vuelve
 * a ejecutar en cada navegación: los listeners globales se registran una sola vez
 * y cada página llama a `init()`.
 */
(function () {
  "use strict";

  if (window.ForgeAsistente) {
    window.ForgeAsistente.init();
    return;
  }

  const API = "/api/v1";
  const DEBOUNCE_MS = 700;
  const POLL_MS = 3000;
  const AUTHORING = {
    consult: { titulo: "Leyendo tu historia…", detalle: "La IA lee tu idea para ver qué le falta." },
    plan_outline: { titulo: "Armando los actos…", detalle: "La IA reparte tu historia en cinco actos y después los revisa." },
    verify_outline: { titulo: "Revisando los actos…", detalle: "La IA busca respuestas tuyas que quedaron afuera, repeticiones y secretos que nunca se descubren." },
  };
  const STAGE_TEXT = {
    consultor: "Leyendo tu historia…",
    planificador: "Armando los actos…",
    verificador: "Revisando los actos…",
  };

  let page = null; // { root, storyId, data }

  // ── Utilidades ────────────────────────────────────────────────────────────

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  async function api(method, path, body) {
    const resp = await fetch(`${API}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try {
      data = await resp.json();
    } catch {
      /* sin cuerpo */
    }
    if (!resp.ok) {
      const err = new Error(errorText(data) || `Error ${resp.status}`);
      err.status = resp.status;
      err.jobId = resp.headers.get("X-Job-Id");
      throw err;
    }
    return data;
  }

  function errorText(data) {
    if (!data || !data.detail) return "";
    if (typeof data.detail === "string") return data.detail;
    const first = Array.isArray(data.detail) ? data.detail[0] : null;
    return first ? `${(first.loc || []).slice(-1)[0] || ""}: ${first.msg}` : "Datos inválidos";
  }

  function icons() {
    if (window.lucide) window.lucide.createIcons();
  }

  function reloadKeepingScroll() {
    const main = $("main");
    try {
      sessionStorage.setItem(`asistente-scroll:${location.pathname}`, String(main ? main.scrollTop : 0));
    } catch {
      /* sin storage */
    }
    location.reload();
  }

  function restoreScroll() {
    const key = `asistente-scroll:${location.pathname}`;
    let top = null;
    try {
      top = sessionStorage.getItem(key);
      if (top !== null) sessionStorage.removeItem(key);
    } catch {
      /* sin storage */
    }
    if (top === null) return;
    // Spec-630 B5: con la página a medio armar el navegador recorta el scroll al alto
    // que tiene en ese momento (se pedía 1480 y quedaba en 475): se aplica ya cargada.
    const apply = () =>
      requestAnimationFrame(() => {
        const main = $("main");
        if (main) main.scrollTop = Number(top);
      });
    if (document.readyState === "complete") apply();
    else window.addEventListener("load", apply, { once: true });
  }

  // ── Actualizar sin recargar (Spec-630 B5) ─────────────────────────────────

  async function fragment(paso) {
    const resp = await fetch(`/asistente/${page.storyId}/fragmento/${paso}`, { headers: { Accept: "text/html" } });
    if (!resp.ok) throw new Error(`fragmento ${resp.status}`);
    const tpl = document.createElement("template");
    tpl.innerHTML = await resp.text();
    return tpl.content;
  }

  /** Lo escrito y elegido en cada pregunta del taller que no se mandó todavía. */
  function tallerDrafts(root) {
    return new Map(
      $$("[data-pregunta]", root).map((box) => {
        const checked = $("input[type=radio]:checked", box);
        const text = $("[data-texto-mia]", box);
        const cambio = $("[data-cambio]", box);
        return [
          box.dataset.pregunta,
          {
            radio: checked ? checked.value : null,
            text: text ? text.value : "",
            textVisible: text ? !text.classList.contains("hidden") : false,
            cambioVisible: cambio ? !cambio.classList.contains("hidden") : false,
          },
        ];
      }),
    );
  }

  function restoreTallerDrafts(root, drafts, skip) {
    $$("[data-pregunta]", root).forEach((box) => {
      const d = drafts.get(box.dataset.pregunta);
      if (!d || box.dataset.pregunta === skip) return;
      if (d.radio !== null) {
        const radio = $$("input[type=radio]", box).find((r) => r.value === d.radio);
        if (radio) radio.checked = true;
      }
      const text = $("[data-texto-mia]", box);
      if (text) {
        text.value = d.text;
        if (!text.closest("[data-cambio]")) text.classList.toggle("hidden", !d.textVisible);
      }
      const cambio = $("[data-cambio]", box);
      if (cambio) cambio.classList.toggle("hidden", !d.cambioVisible);
    });
  }

  /**
   * Reemplaza solo lo que cambió, sin recargar, y deja la pantalla donde estaba:
   * la primera de `anclas` (selectores) que está antes y después queda a la misma
   * altura. «Los actos»: el resumen y la tarjeta del acto (o todas, si cambió algo
   * que comparten: personajes, lugares). «Preguntas»: todo el contenido, sin perder
   * lo que se estaba escribiendo en otras preguntas.
   */
  async function refresh({ paso, actos, anclas = [], foco, skip, mostrar }) {
    const frag = await fragment(paso);
    const main = $("main");
    const before = anclas.map((sel) => {
      const el = $(sel);
      return el ? el.getBoundingClientRect().top : null;
    });

    if (paso === "escaleta") {
      const oldActs = $$("[data-acto]");
      const newActs = $$("[data-acto]", frag);
      if (!oldActs.length || oldActs.length !== newActs.length) throw new Error("cambió la estructura");
      const resumen = $("[data-resumen-actos]");
      const nuevoResumen = $("[data-resumen-actos]", frag);
      if (resumen && nuevoResumen) resumen.replaceWith(nuevoResumen);
      newActs.forEach((li) => {
        if (actos !== "todos" && li.dataset.acto !== String(actos)) return;
        const old = $(`[data-acto="${li.dataset.acto}"]`);
        const form = $("form[data-autosave]", old);
        if (form) pending.delete(form);
        old.replaceWith(li);
      });
    } else {
      const box = $("[data-preguntas-contenido]");
      if (!box) throw new Error("sin contenido");
      const drafts = tallerDrafts(box);
      box.replaceChildren(frag);
      restoreTallerDrafts(box, drafts, skip);
    }
    if (mostrar && $(mostrar)) $(mostrar).classList.remove("hidden");
    icons();

    const i = anclas.findIndex((sel, n) => before[n] !== null && $(sel));
    if (i >= 0 && main) main.scrollTop += $(anclas[i]).getBoundingClientRect().top - before[i];
    const target = (foco && $(foco)) || (i >= 0 ? $(anclas[i]) : null);
    if (target) {
      if (!target.matches("a, button, input, textarea, select, [tabindex]")) target.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
    }
  }

  // ── Indicador de guardado ─────────────────────────────────────────────────

  // Spec-550 H6: notificación flotante. «Guardado» ~2 s y se va; «Guardando…» solo
  // si tarda más de 1 s; un error queda hasta que un guardado sale bien o se cierra.
  const TOAST_MS = 2000;
  const SLOW_MS = 1000;
  let toastTimer = null;
  let slowTimer = null;

  function showToast(kind, text) {
    const el = $("[data-guardado]");
    if (!el) return;
    const icon = kind === "ok" ? "check" : kind === "error" ? "alert-circle" : "loader";
    $("[data-guardado-icono]", el).innerHTML = `<i data-lucide="${icon}" class="w-4 h-4${kind === "saving" ? " animate-spin" : ""}"></i>`;
    $("[data-guardado-texto]", el).textContent = text;
    el.setAttribute("role", kind === "error" ? "alert" : "status");
    el.dataset.estado = kind;
    icons();
  }

  function hideToast() {
    const el = $("[data-guardado]");
    if (el) el.dataset.estado = "oculto";
  }

  /** kind: pending (tecleando) | saving | ok | error | hint (no se muestra). */
  function status(kind, text) {
    clearTimeout(toastTimer);
    clearTimeout(slowTimer);
    const toast = $("[data-guardado]");
    const current = toast && toast.dataset.estado;
    // Marca «hay un guardado en curso» (no se ve; la usan los E2E para esperar).
    if (toast) toast.dataset.pendiente = kind === "pending" || kind === "saving" ? "1" : "";
    if (kind === "saving") {
      slowTimer = setTimeout(() => showToast("saving", text), SLOW_MS);
    } else if (kind === "ok") {
      showToast("ok", text);
      toastTimer = setTimeout(hideToast, TOAST_MS);
    } else if (kind === "error") {
      showToast("error", text);
    } else if (kind === "hint" && current !== "error") {
      hideToast();
    }
  }

  // ── Guardado automático ───────────────────────────────────────────────────

  const pending = new Map(); // form → { timer, promise }

  function schedule(form) {
    const entry = pending.get(form) || { timer: null, promise: Promise.resolve() };
    clearTimeout(entry.timer);
    entry.timer = setTimeout(() => runSave(form), DEBOUNCE_MS);
    pending.set(form, entry);
    status("pending", "Sin guardar…");
  }

  function runSave(form) {
    const entry = pending.get(form);
    if (!entry) return Promise.resolve();
    clearTimeout(entry.timer);
    entry.timer = null;
    entry.promise = entry.promise.then(() => save(form)).catch(() => {});
    return entry.promise;
  }

  /** Descarga los guardados pendientes (antes de cualquier acción). */
  async function flushAll() {
    await Promise.all([...pending.keys()].map((form) => (pending.get(form).timer ? runSave(form) : pending.get(form).promise)));
  }

  async function save(form) {
    const kind = form.dataset.autosave;
    try {
      status("saving", "Guardando…");
      if (kind === "direction") await saveDirection(form);
      else if (kind === "act") await api("PUT", `/authoring/stories/${page.storyId}/outline/${form.dataset.number}`, actPayload(form));
      status("ok", "Guardado");
    } catch (err) {
      if (err.status === 409) {
        status("error", "No se guardó: la IA está trabajando");
        attachToActiveJob();
      } else {
        status("error", `No se guardó: ${err.message}`);
      }
      throw err;
    }
  }

  async function saveDirection(form) {
    const payload = directionPayload(form);
    if (!payload.title) {
      status("hint", "Se guarda solo cuando escribas el título");
      return;
    }
    if (page.storyId) {
      await api("PUT", `/authoring/stories/${page.storyId}/direction`, payload);
      return;
    }
    const state = await api("POST", "/authoring/stories", payload);
    page.storyId = state.story_id;
    page.root.dataset.storyId = state.story_id;
    history.replaceState(null, "", `/asistente/${state.story_id}/direccion`);
    $$("[data-analizar]").forEach((b) => (b.disabled = false));
    const pista = $("[data-pista-titulo]");
    if (pista) pista.remove();
  }

  function value(form, name) {
    const el = form.elements.namedItem(name);
    if (!el) return "";
    if (el instanceof RadioNodeList) return el.value || "";
    if (el.type === "checkbox") return el.checked;
    return el.value.trim();
  }

  function directionPayload(form) {
    const nature = value(form, "threat_nature");
    return {
      title: value(form, "title"),
      genero: value(form, "genero"),
      subgenero: value(form, "subgenero"),
      premise: value(form, "premise"),
      effect: value(form, "effect"),
      effect_other: value(form, "effect_other"),
      ending: value(form, "ending"),
      telling: value(form, "telling"),
      protagonist_name: value(form, "protagonist_name"),
      protagonist_role: value(form, "protagonist_role"),
      narrator: value(form, "narrator"),
      threat: nature
        ? {
            nature,
            name: value(form, "threat_name"),
            description: value(form, "threat_description"),
            manifestations: value(form, "threat_manifestations"),
            limits: value(form, "threat_limits"),
            reveal_level: value(form, "threat_reveal_level") || "insinuada",
          }
        : null,
    };
  }

  function texts(form, name) {
    return $$(`[name="${name}"]`, form)
      .map((el) => el.value.trim())
      .filter(Boolean);
  }

  function actPayload(form) {
    const keep = JSON.parse(form.elements.namedItem("keep").value || "{}");
    return {
      bridge: value(form, "bridge") || "",
      goal: value(form, "goal"),
      events: texts(form, "events"),
      change_from: value(form, "change_from"),
      change_to: value(form, "change_to"),
      // Spec-630 B6: el lugar se elige siempre con la opción (los nuevos se suman antes, aparte).
      scenario: value(form, "scenario"),
      on_stage: $$('[name="on_stage"]', form)
        .filter((el) => el.checked)
        .map((el) => el.value),
      held_back: value(form, "held_back"),
      reveal_act: Number(value(form, "reveal_act") || 0),
      rules: texts(form, "rules"),
      seeds: keep.seeds || [],
      payoffs: keep.payoffs || [],
      decisions: keep.decisions || [],
    };
  }

  // ── Dirección: selects que dependen del género ────────────────────────────

  function fillSelect(select, options, selected, emptyLabel) {
    select.innerHTML = "";
    select.append(new Option(emptyLabel, ""));
    options.forEach((o) => select.append(new Option(o.label, o.id, false, o.id === selected)));
    select.disabled = options.length === 0;
  }

  function onGenreChange(form) {
    const genres = (page.data && page.data.genres) || [];
    const genre = genres.find((g) => g.id === value(form, "genero"));
    fillSelect(form.elements.namedItem("subgenero"), genre ? genre.subgenres : [], "", "Elegí uno…");
    const nature = form.elements.namedItem("threat_nature");
    if (nature) fillSelect(nature, genre && genre.entity_natures ? genre.entity_natures : [], "", "Sin amenaza");
  }

  // ── Listas editables (hechos, reglas) ─────────────────────────────────────

  function addItem(form, name) {
    const list = $(`[data-lista="${name}"]`, form);
    const li = document.createElement("li");
    li.className = "group flex items-start gap-2";
    li.dataset.item = "";
    const upBtn =
      name === "events"
        ? '<button type="button" class="mt-2 text-forge-muted hover:text-forge-accent" data-subir title="Subir"><i data-lucide="arrow-up" class="w-4 h-4"></i></button>'
        : "";
    li.innerHTML = `${upBtn}<textarea name="${name}" rows="1" maxlength="400" class="flex-1 [field-sizing:content] resize-none bg-forge-bg border border-forge-border px-3 py-2"></textarea><button type="button" class="mt-2 text-forge-muted hover:text-forge-error" data-quitar title="Quitar"><i data-lucide="x" class="w-4 h-4"></i></button>`;
    list.append(li);
    icons();
    $("textarea", li).focus();
  }

  // ── Acciones sin IA (taller y escaleta) ───────────────────────────────────

  /** Spec-630 B6: suma el lugar a la historia, lo elige en este acto y deja el campo abierto para otro. */
  function agregarLugar(form) {
    const input = $("[data-lugar-nombre]", form);
    const name = input.value.trim();
    if (!name) return input.focus();
    const n = Number(form.dataset.number);
    const acto = `[data-acto="${n}"]`;
    return run(() => api("POST", `/authoring/stories/${page.storyId}/scenarios`, { name, act: n }), {
      ...enActo(n, { todos: true }),
      mostrar: `${acto} [data-lugar-form]`,
      foco: `${acto} [data-lugar-nombre]`,
    });
  }

  /** Spec-630 B7: borrar un lugar o un personaje, diciendo en qué actos se usa. */
  async function borrar(form, btn, coleccion, name, { titulo, label }) {
    const usos = (btn.dataset.usos || "").split(",").filter(Boolean);
    const message = usos.length
      ? `Se quita ${usos.length === 1 ? "del acto" : "de los actos"} ${usos.join(", ").replace(/, (\d)$/, " y $1")}.`
      : "Ningún acto lo usa.";
    const ok = await window.ForgeConfirm.ask({ title: titulo, message, confirmLabel: label });
    if (!ok) return;
    const n = Number(form.dataset.number);
    return run(() => api("POST", `/authoring/stories/${page.storyId}/${coleccion}/remove`, { name }), enActo(n, { todos: true }));
  }

  /** Cómo se actualiza «Los actos» después de una acción en el acto `n`. */
  function enActo(n, { todos = false } = {}) {
    const acto = `[data-acto="${n}"]`;
    return { paso: "escaleta", actos: todos ? "todos" : n, anclas: [acto], foco: acto };
  }

  /** Una acción sin IA: guarda lo pendiente, la hace y actualiza la pantalla sin recargar. */
  async function run(action, { error: errorEl, ...vista } = {}) {
    try {
      await flushAll();
      await action();
    } catch (err) {
      if (err.status === 409) return attachToActiveJob();
      if (errorEl) {
        errorEl.textContent = err.message;
        errorEl.classList.remove("hidden");
      } else {
        status("error", err.message);
      }
      return;
    }
    try {
      await refresh(vista);
    } catch {
      reloadKeepingScroll(); // la pantalla cambió de forma (p. ej. aparecieron los actos)
    }
  }

  function tallerAction(btn) {
    const box = btn.closest("[data-pregunta]");
    const criterion = box.dataset.pregunta;
    const action = btn.dataset.taller;
    const body = { action, text: "" };
    if (action === "answer") {
      const checked = $("input[type=radio]:checked", box);
      const own = $("[data-texto-mia]", box);
      body.text = checked && checked.value ? checked.value : own ? own.value.trim() : "";
      if (!body.text) {
        const err = $("[data-error]", box);
        err.textContent = "Elegí una opción o escribí tu respuesta.";
        err.classList.remove("hidden");
        return;
      }
    }
    // Responder mueve la pregunta a «Ya lo tenés»: la pantalla se ancla en la que sigue.
    const sel = (c) => `[data-preguntas-contenido] [data-pregunta="${c}"]`;
    const todas = $$("[data-preguntas-contenido] [data-pregunta]").map((el) => el.dataset.pregunta);
    const siguientes = todas.slice(todas.indexOf(criterion) + 1).map(sel);
    const abierta = !box.closest("li");
    run(() => api("PATCH", `/authoring/stories/${page.storyId}/workshop/${criterion}`, body), {
      error: $("[data-error]", box),
      paso: "taller",
      skip: criterion,
      anclas: abierta ? [...siguientes, sel(criterion)] : [sel(criterion), ...siguientes],
    });
  }

  // ── La IA trabajando: el modal ────────────────────────────────────────────

  const modal = {
    job: null,
    destino: null,
    poll: null,
    tick: null,

    el: () => $("#asistente-analizando"),

    open(job, opts = {}) {
      const el = this.el();
      if (!el) return;
      document.body.append(el); // fuera de <main>: si no, quedaría inerte con la página
      this.job = job;
      this.destino = opts.destino || null;
      const texts = AUTHORING[job.kind] || { titulo: "La IA está trabajando…", detalle: "" };
      $("#analizando-titulo", el).textContent = opts.titulo || texts.titulo;
      $("#analizando-detalle", el).textContent = opts.detalle || texts.detalle;
      $("[data-analizando-error]", el).classList.add("hidden");
      $("[data-analizando-cerrar]", el).classList.add("hidden");
      $("[data-analizando-cancelar]", el).classList.remove("hidden");
      $("[data-analizando-spinner]", el).classList.remove("hidden");
      $("[data-analizando-nota]", el).classList.remove("hidden");
      [...document.body.children].forEach((c) => c !== el && c.tagName !== "SCRIPT" && c.setAttribute("inert", ""));
      el.classList.remove("hidden");
      $("[data-analizando-cancelar]", el).focus();
      this.render();
      clearInterval(this.poll);
      clearInterval(this.tick);
      this.poll = setInterval(() => this.refresh(), POLL_MS);
      this.tick = setInterval(() => this.render(), 1000);
    },

    render() {
      const job = this.job;
      if (!job) return;
      const el = this.el();
      if (job.stage && STAGE_TEXT[job.stage]) $("#analizando-titulo", el).textContent = STAGE_TEXT[job.stage];
      const estimate = job.params && job.params.estimated_seconds;
      const base = typeof job.elapsed_seconds === "number" ? job.elapsed_seconds : 0;
      const elapsed = base + (Date.now() - (job.received_at || Date.now())) / 1000;
      const eta = $("[data-analizando-eta]", el);
      if (!estimate) eta.textContent = "";
      else if (elapsed >= estimate) eta.textContent = "Está tardando un poco más de lo habitual…";
      else eta.textContent = `Falta ≈ ${remaining(estimate - elapsed)}`;
    },

    update(job) {
      if (!this.job || job.job_id !== this.job.job_id) return;
      job.received_at = job.received_at || Date.now();
      this.job = job;
      if (job.status === "done") this.done();
      else if (job.status === "failed") this.failed(job.error);
      else this.render();
    },

    async refresh() {
      if (!this.job) return;
      try {
        const job = await api("GET", `/jobs/${this.job.job_id}`);
        job.received_at = Date.now();
        this.update(job);
      } catch {
        /* el próximo intento */
      }
    },

    stop() {
      clearInterval(this.poll);
      clearInterval(this.tick);
      this.poll = this.tick = null;
    },

    close() {
      this.stop();
      this.job = null;
      const el = this.el();
      if (el) el.classList.add("hidden");
      [...document.body.children].forEach((c) => c.removeAttribute("inert"));
    },

    done() {
      const destino = this.destino;
      this.stop();
      this.job = null;
      if (destino && page) location.href = `/asistente/${page.storyId}/${destino}`;
      else reloadKeepingScroll();
    },

    failed(error) {
      this.stop();
      const el = this.el();
      const cancelled = /cancelada/.test(error || "");
      if (cancelled) return this.close();
      $("#analizando-titulo", el).textContent = "La IA no pudo terminar";
      $("[data-analizando-eta]", el).textContent = "";
      $("[data-analizando-nota]", el).classList.add("hidden");
      $("[data-analizando-spinner]", el).classList.add("hidden");
      const msg = $("[data-analizando-error]", el);
      msg.textContent = error || "Algo falló. Probá de nuevo.";
      msg.classList.remove("hidden");
      $("[data-analizando-cancelar]", el).classList.add("hidden");
      $("[data-analizando-cerrar]", el).classList.remove("hidden");
      $("[data-analizando-cerrar]", el).focus();
    },
  };

  function remaining(seconds) {
    if (seconds >= 90) return `${Math.round(seconds / 60)} min`;
    return `${Math.max(5, Math.round(seconds / 5) * 5)} s`;
  }

  async function analyze(btn) {
    if (!page.storyId) return;
    if (btn.dataset.confirmar) {
      const ok = await window.ForgeConfirm.ask({
        title: btn.dataset.confirmarTitulo,
        message: btn.dataset.confirmar,
        confirmLabel: btn.dataset.confirmarLabel,
      });
      if (!ok) return;
    }
    try {
      await flushAll();
    } catch {
      return; // el indicador ya dice por qué no se guardó
    }
    const kind = btn.dataset.analizar;
    const opts = { titulo: btn.dataset.titulo, detalle: btn.dataset.detalle, destino: btn.dataset.destino };
    try {
      const job = await api("POST", `/stories/${page.storyId}/jobs`, { kind });
      job.received_at = Date.now();
      modal.open(job, opts);
    } catch (err) {
      if (err.status === 409) return attachToActiveJob();
      modal.open({ job_id: "", kind }, opts);
      modal.failed(err.message);
    }
  }

  async function attachToActiveJob() {
    if (!page || !page.storyId || modal.job) return;
    try {
      const job = await api("GET", `/stories/${page.storyId}/jobs/active`);
      job.received_at = Date.now();
      modal.open(job);
    } catch {
      /* ya terminó */
    }
  }

  // ── Listeners globales (una sola vez por pestaña) ─────────────────────────

  document.addEventListener("input", (e) => {
    const form = e.target.closest && e.target.closest("form[data-autosave]");
    if (!form || !page) return;
    if (e.target.matches("[data-lugar-nombre], [data-p-nombre], [data-p-relacion]")) return; // no son del acto
    schedule(form);
  });

  // Spec-630 B6: Enter en «Nombre del lugar» lo agrega (el form del acto no se envía nunca).
  document.addEventListener("keydown", (e) => {
    if (!page || e.key !== "Enter" || !e.target.matches || !e.target.matches("[data-lugar-nombre]")) return;
    e.preventDefault();
    agregarLugar(e.target.closest("form[data-autosave]"));
  });

  document.addEventListener("change", (e) => {
    if (!page || !e.target.closest) return;
    // Taller: «Escribir la mía…» muestra el campo; otra opción lo oculta.
    const pregunta = e.target.closest("[data-pregunta]");
    if (pregunta && e.target.type === "radio") {
      const text = $("[data-texto-mia]", pregunta);
      if (text && !text.closest("[data-cambio]")) {
        text.classList.toggle("hidden", !e.target.matches("[data-mia]"));
        if (e.target.matches("[data-mia]")) text.focus();
      }
      return;
    }
    const form = e.target.closest("form[data-autosave]");
    if (!form) return;
    if (e.target.name === "genero") onGenreChange(form);
    if (e.target.name === "effect") {
      $$("[data-solo-si-efecto]", form).forEach((el) => el.classList.toggle("hidden", el.dataset.soloSiEfecto !== e.target.value));
    }
    if (e.target.matches("[data-p-tipo]")) return; // del formulario de personaje, no del acto
    schedule(form);
  });

  document.addEventListener("click", (e) => {
    if (!page) return;
    const t = e.target.closest("button, a");
    if (!t) return;
    const form = t.closest("form[data-autosave]");

    if (t.closest("[data-guardado-cerrar]")) return hideToast();
    if (t.matches("[data-analizar]")) return analyze(t);
    if (t.matches("[data-taller]")) return tallerAction(t);
    if (t.matches("[data-cambiar]")) {
      $("[data-cambio]", t.closest("[data-pregunta]")).classList.toggle("hidden");
      return;
    }
    if (t.matches("[data-agregar]") && form) return addItem(form, t.dataset.agregar);
    if (t.matches("[data-quitar]") && form) {
      t.closest("[data-item]").remove();
      return schedule(form);
    }
    if (t.matches("[data-subir]") && form) {
      const li = t.closest("[data-item]");
      if (li.previousElementSibling) li.parentElement.insertBefore(li, li.previousElementSibling);
      return schedule(form);
    }
    if (t.matches("[data-escenario-nuevo]") && form) {
      $("[data-lugar-form]", form).classList.remove("hidden");
      $("[data-lugar-nombre]", form).focus();
      return;
    }
    if (t.matches("[data-lugar-agregar]") && form) return agregarLugar(form);
    if (t.matches("[data-borrar-lugar]") && form) {
      return borrar(form, t, "scenarios", t.dataset.borrarLugar, {
        titulo: `¿Borrar el lugar «${t.dataset.borrarLugar}»?`,
        label: "Borrar el lugar",
      });
    }
    if (t.matches("[data-borrar-personaje]") && form) {
      return borrar(form, t, "characters", t.dataset.borrarPersonaje, {
        titulo: `¿Borrar a «${t.dataset.borrarPersonaje}»?`,
        label: "Borrar el personaje",
      });
    }
    if (t.matches("[data-personaje-nuevo]") && form) {
      $("[data-personaje-form]", form).classList.toggle("hidden");
      $("[data-p-nombre]", form).focus();
      return;
    }
    if (t.matches("[data-personaje-guardar]") && form) {
      const name = $("[data-p-nombre]", form).value.trim();
      if (!name) return $("[data-p-nombre]", form).focus();
      const n = Number(form.dataset.number);
      const character = { name, kind: $("[data-p-tipo]", form).value, relation: $("[data-p-relacion]", form).value.trim(), act: n };
      return run(() => api("POST", `/authoring/stories/${page.storyId}/characters`, character), enActo(n, { todos: true }));
    }
    if (t.matches("[data-sumar-personaje]") && form) {
      const n = form.dataset.number;
      // Spec-630 B2: un clic; queda en «Quiénes están» del acto y el aviso se resuelve (no se ignora).
      return run(async () => {
        await api("POST", `/authoring/stories/${page.storyId}/characters`, { name: t.dataset.sumarPersonaje, kind: "persona", act: Number(n) });
        await api("POST", `/authoring/stories/${page.storyId}/outline/${n}/warnings/resolve`, { key: t.dataset.aviso });
      }, enActo(n, { todos: true }));
    }
    if (t.matches("[data-ignorar]") && form) {
      const n = form.dataset.number;
      return run(() => api("POST", `/authoring/stories/${page.storyId}/outline/${n}/warnings/dismiss`, { key: t.dataset.ignorar }), enActo(n));
    }
    if (t.matches("[data-restaurar]") && form) {
      const n = form.dataset.number;
      return run(() => api("POST", `/authoring/stories/${page.storyId}/outline/${n}/warnings/restore`, { key: t.dataset.restaurar }), enActo(n));
    }
    if (t.matches("[data-generar]")) {
      e.preventDefault();
      flushAll().finally(() => (location.href = t.href));
      return;
    }
    if (t.matches("[data-analizando-cancelar]") && modal.job && modal.job.job_id) {
      t.disabled = true;
      api("POST", `/jobs/${modal.job.job_id}/cancel`)
        .catch(() => {})
        .finally(() => {
          t.disabled = false;
          modal.close();
        });
      return;
    }
    if (t.matches("[data-analizando-cerrar]")) return modal.close();
  });

  ["job-progress", "job-done", "job-failed"].forEach((name) =>
    document.addEventListener(`forge:${name}`, (e) => modal.update({ ...e.detail })),
  );

  window.addEventListener("beforeunload", (e) => {
    if ([...pending.values()].some((p) => p.timer)) {
      [...pending.keys()].forEach(runSave);
      e.preventDefault();
    }
  });

  // ── Por página ────────────────────────────────────────────────────────────

  function init() {
    const root = $("[data-asistente]");
    if (!root) {
      page = null;
      return;
    }
    let data = {};
    try {
      data = JSON.parse(($("#asistente-datos") || {}).textContent || "{}");
    } catch {
      /* sin datos */
    }
    pending.clear();
    modal.stop();
    modal.job = null;
    page = { root, storyId: root.dataset.storyId || "", data };
    restoreScroll();
    const active = data.state && data.state.active_job;
    if (active && active.status !== "done" && active.status !== "failed") {
      active.received_at = Date.now();
      modal.open(active);
    }
  }

  window.ForgeAsistente = { init, flushAll };
  init();
})();
