/**
 * Corregir el relato acto por acto (Spec-610 §3.1, §3.7.1 — D20).
 *
 * Un acto a la vez: la lista de la izquierda y los botones de abajo cambian de acto;
 * cada cuadro se guarda solo (PUT /api/v1/generated-narratives/{id}/acts/{n}) y,
 * después de guardar, se vuelven a pedir los avisos del control de repetición.
 * Las cuentas de tiempo son las de tiempos.js (las mismas que el Core).
 */
(function () {
  "use strict";

  const API = "/api/v1";
  const DEBOUNCE_MS = 800;
  const T = window.ForgeTiempos;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  let page = null;
  const pending = new Map(); // número de acto → { timer, promise }

  // ── Cuentas ─────────────────────────────────────────────────────────────

  const textOf = (n) => ($(`[data-acto-texto="${n}"]`) || {}).value || "";
  const actNumbers = () => $$("[data-acto-texto]").map((t) => Number(t.dataset.actoTexto));
  const secondsOf = (words) => T.segundos(words, page.lectura.palabras_por_minuto);

  function refreshCounts() {
    const numbers = actNumbers();
    const words = numbers.map((n) => T.palabras(textOf(n)));
    numbers.forEach((n, i) => {
      const seg = secondsOf(words[i]);
      const avisos = countWarnings(n);
      const resumen = $(`[data-acto-resumen="${n}"]`);
      if (resumen) resumen.textContent = `${words[i]} palabras · ${T.reloj(seg)}${avisos ? ` · ${avisos} ${avisos === 1 ? "aviso" : "avisos"}` : ""}`;
      const medida = $(`[data-acto-medida="${n}"]`);
      if (medida) medida.textContent = `${words[i]} palabras · ≈ ${T.largo(seg)}`;
    });
    renderDuration(words);
    refreshPrevious();
  }

  function renderDuration(words) {
    const total = words.reduce((a, b) => a + b, 0);
    const seg = secondsOf(total);
    const { desde, hasta } = page.lectura.episodio_minutos;
    $("[data-duracion-total]").textContent = `≈ ${T.largo(seg)}`;
    $("[data-duracion-palabras]").textContent = `${total.toLocaleString("es-AR")} palabras, leídas a ${page.lectura.palabras_por_minuto} por minuto`;
    const estado = T.episodio(seg, desde, hasta);
    const chip = { entra: ["cumple", "Entra en un episodio"], corto: ["parcial", "Le falta para un episodio"], largo: ["parcial", "Se pasa de un episodio"] }[estado];
    $("[data-duracion-estado]").innerHTML = `<span class="chip-forge chip-forge--${chip[0]}">${chip[1]} (${desde}–${hasta} min)</span>`;

    // Regla de 0 a 20 min (o más si se pasa) con la franja del episodio y cada acto.
    const escala = Math.max(20, Math.ceil(seg / 60) + 1) * 60;
    const pct = (s) => `${(Math.min(s, escala) / escala) * 100}%`;
    const marcas = [0, 5, 10, desde, hasta, escala / 60]
      .filter((m, i, a) => a.indexOf(m) === i)
      .map((m) => `<span class="absolute top-4 -translate-x-1/2 text-xs text-forge-muted tabular-nums" style="left:${pct(m * 60)}">${m}′</span>`)
      .join("");
    const tramos = words
      .map((w, i) => `<i class="block h-full bg-forge-accent border-r-2 border-forge-surface" style="flex:${w || 0.0001}" title="Acto ${i + 1}: ${T.reloj(secondsOf(w))}"></i>`)
      .join("");
    $("[data-duracion-regla]").innerHTML =
      `<div class="absolute inset-x-0 top-1.5 h-1.5 rounded bg-forge-neutral-bg"></div>` +
      `<div class="absolute top-1.5 h-1.5 bg-forge-success/40" style="left:${pct(desde * 60)};width:calc(${pct(hasta * 60)} - ${pct(desde * 60)})"></div>` +
      `<div class="absolute left-0 top-1.5 h-1.5 flex rounded overflow-hidden" style="width:${pct(seg)}">${tramos}</div>` +
      marcas;
  }

  /** «Así terminó el acto anterior»: las últimas palabras del acto de antes, al día. */
  function refreshPrevious() {
    $$("[data-anterior]").forEach((p) => {
      const n = Number(p.dataset.anterior);
      const prev = actNumbers().filter((m) => m < n).pop();
      const words = textOf(prev).trim().split(/\s+/).filter(Boolean);
      p.textContent = words.length ? `Así terminó el acto anterior: «…${words.slice(-24).join(" ")}»` : "";
    });
  }

  // ── Avisos (control de repetición) ──────────────────────────────────────

  function warningsOf(n) {
    const rep = page.repetition && (page.repetition.acts || []).find((a) => a.number === n);
    if (!rep) return [];
    const out = [];
    (rep.repeated || []).forEach((r) => out.push({ texto: `Repite ${r}`, buscar: (r.match(/«([^»]+)»/) || [])[1] }));
    (rep.cliches || []).forEach((c) => out.push({ texto: `Cliché: «${c}»`, buscar: c }));
    (rep.invented_names || []).forEach((name) => out.push({ texto: `Nombre que no está en la historia: ${name}`, buscar: name }));
    if (rep.too_cut) (rep.cut_sentences || []).forEach((s) => out.push({ texto: `Oración cortada: «${s}»`, buscar: s }));
    // Spec-640: comparaciones de escritor (desde la segunda del acto).
    if (rep.too_literary) (rep.comparisons || []).forEach((s) => out.push({ texto: `Comparación: «${s}…»`, buscar: s }));
    if (rep.dialogue) out.push({ texto: `Tiene diálogo: ${rep.dialogue} ${rep.dialogue === 1 ? "frase" : "frases"} con raya o entre comillas` });
    return out;
  }

  const countWarnings = (n) => warningsOf(n).length;

  function renderWarnings() {
    actNumbers().forEach((n) => {
      const box = $(`[data-avisos="${n}"]`);
      if (!box) return;
      const ws = warningsOf(n);
      box.innerHTML = ws.length
        ? ws.map((w, i) => `<div class="nota-forge nota-forge--warning !px-3 !py-2"><i data-lucide="repeat" class="nota-forge__icono"></i><span class="flex-1 min-w-0 break-words">${escapeHtml(w.texto)}</span>${w.buscar ? `<button type="button" class="nota-forge__accion" data-buscar="${n}:${i}">Buscar</button>` : ""}</div>`).join("")
        : `<span class="chip-forge chip-forge--cumple w-fit">Sin avisos</span>`;
    });
    if (window.lucide) window.lucide.createIcons();
  }

  function search(n, i) {
    const w = warningsOf(n)[i];
    const area = $(`[data-acto-texto="${n}"]`);
    if (!w || !w.buscar || !area) return;
    const at = area.value.toLowerCase().indexOf(w.buscar.toLowerCase());
    if (at < 0) return;
    area.focus();
    area.setSelectionRange(at, at + w.buscar.length);
    // Llevar la selección a la vista: medir con un espejo es mucho; alcanza la proporción.
    area.scrollTop = Math.max(0, (at / area.value.length) * area.scrollHeight - area.clientHeight / 3);
  }

  async function reloadWarnings() {
    try {
      const resp = await fetch(`${API}/generated-narratives/${page.narrativeId}/repetition`);
      if (resp.ok) page.repetition = await resp.json();
    } catch {
      /* se quedan los avisos que había */
    }
    renderWarnings();
    refreshCounts();
  }

  // ── Guardado automático ─────────────────────────────────────────────────

  function schedule(n) {
    const entry = pending.get(n) || { timer: null, promise: Promise.resolve() };
    clearTimeout(entry.timer);
    entry.timer = setTimeout(() => runSave(n), DEBOUNCE_MS);
    pending.set(n, entry);
    window.ForgeGuardado.status("pending", "Sin guardar…");
  }

  function runSave(n) {
    const entry = pending.get(n);
    if (!entry) return Promise.resolve();
    clearTimeout(entry.timer);
    entry.timer = null;
    entry.promise = entry.promise.then(() => save(n)).catch(() => {});
    return entry.promise;
  }

  async function flushAll() {
    await Promise.all([...pending.keys()].map((n) => (pending.get(n).timer ? runSave(n) : pending.get(n).promise)));
  }

  async function save(n) {
    const G = window.ForgeGuardado;
    if (!textOf(n).trim()) {
      G.status("error", "No se guardó: el acto no puede quedar vacío");
      return;
    }
    G.status("saving", "Guardando…");
    const resp = await fetch(`${API}/generated-narratives/${page.narrativeId}/acts/${n}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: textOf(n) }),
    });
    if (!resp.ok) {
      let detail = "";
      try {
        detail = (await resp.json()).detail;
      } catch {
        /* sin cuerpo */
      }
      G.status("error", resp.status === 409 ? "No se guardó: la IA está trabajando en esta historia" : `No se guardó: ${detail || resp.status}`);
      throw new Error(String(resp.status));
    }
    G.status("ok", "Guardado");
    await reloadWarnings();
  }

  // ── Cambiar de acto y regenerar ─────────────────────────────────────────

  function show(n) {
    $$("[data-acto-panel]").forEach((el) => (el.hidden = Number(el.dataset.actoPanel) !== n));
    $$("[data-acto-lado]").forEach((el) => (el.hidden = Number(el.dataset.actoLado) !== n));
    $$("nav [data-acto-tab]").forEach((el) => el.setAttribute("aria-current", String(Number(el.dataset.actoTab) === n)));
    try {
      history.replaceState(history.state, "", `${location.pathname}?acto=${n}`);
    } catch {
      /* sin history */
    }
  }

  async function regenerate(button) {
    const n = Number(button.dataset.regenerar);
    const ok = await window.ForgeConfirm.ask({
      title: button.dataset.confirmarTitulo,
      message: button.dataset.detalle,
      confirmLabel: "Regenerar el acto",
    });
    if (!ok) return;
    await flushAll();
    const resp = await fetch(`${API}/stories/${page.storyId}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "regenerate_voz", beat: n, narrative_id: page.narrativeId }),
    });
    if (resp.status !== 202) {
      // Spec-650 D11: un 422 trae el motivo (p. ej. una versión de cuando la historia tenía otro largo).
      const detail = resp.status === 422 ? ((await resp.json().catch(() => ({}))).detail || "") : "";
      window.ForgeGuardado.status(
        "error",
        resp.status === 409 ? "La IA ya está trabajando en esta historia: esperá a que termine" : detail || "No se pudo regenerar el acto",
      );
      return;
    }
    page.regenerating = { job: (await resp.json()).job_id, acto: n };
    button.disabled = true;
    $(`[data-acto-texto="${n}"]`).readOnly = true;
    $(`[data-regenerando="${n}"]`).classList.remove("hidden");
  }

  function onJobFinished(e) {
    const job = e.detail || {};
    if (!page || !page.regenerating || job.job_id !== page.regenerating.job) return;
    location.href = `${location.pathname}?acto=${page.regenerating.acto}`;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  }

  // ── Eventos ─────────────────────────────────────────────────────────────

  document.addEventListener("input", (e) => {
    const area = e.target.closest && e.target.closest("[data-acto-texto]");
    if (!page || !area) return;
    schedule(Number(area.dataset.actoTexto));
    refreshCounts();
  });

  document.addEventListener("click", (e) => {
    if (!page) return;
    const tab = e.target.closest("[data-acto-tab]");
    if (tab) return show(Number(tab.dataset.actoTab));
    const find = e.target.closest("[data-buscar]");
    if (find) {
      const [n, i] = find.dataset.buscar.split(":").map(Number);
      return search(n, i);
    }
    const regen = e.target.closest("[data-regenerar]");
    if (regen) regenerate(regen);
  });

  document.addEventListener("forge:job-done", onJobFinished);
  document.addEventListener("forge:job-failed", onJobFinished);

  window.addEventListener("beforeunload", (e) => {
    if ([...pending.values()].some((p) => p.timer)) {
      [...pending.keys()].forEach(runSave);
      e.preventDefault();
    }
  });

  function init() {
    const root = $("[data-corregir]");
    if (!root) {
      page = null;
      return;
    }
    let data = {};
    try {
      data = JSON.parse(($("#corregir-datos") || {}).textContent || "{}");
    } catch {
      /* sin datos */
    }
    pending.clear();
    page = {
      storyId: root.dataset.storyId,
      narrativeId: root.dataset.narrativeId,
      repetition: data.repetition || null,
      lectura: data.lectura || { palabras_por_minuto: 150, episodio_minutos: { desde: 12, hasta: 17 } },
      regenerating: null,
    };
    renderWarnings();
    refreshCounts();
  }

  window.ForgeCorregir = { init, flushAll };
  init();
})();
