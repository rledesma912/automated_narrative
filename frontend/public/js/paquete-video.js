/**
 * «Para el video» (Spec-610 §3.7.2 — D19, D22): el paquete de una variante en tres
 * pestañas (guion de lectura, la calabaza, el mapa de producción), todo editable y con
 * guardado automático. El texto del relato no se edita acá: se lee de los actos.
 *
 * Usa ForgeTiempos (tiempos.js), ForgeMarcas (marcas.js), ForgeGuardado (guardado.js),
 * ForgeIaModal (ia-modal.js) y ForgeConfirm.
 */
(function () {
  "use strict";

  const API = "/api/v1";
  const DEBOUNCE_MS = 800;
  const T = window.ForgeTiempos;
  const M = window.ForgeMarcas;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  const PAUSAS = [["ninguna", "Seguido"], ["corta", "Pausa corta"], ["larga", "Pausa larga"]];
  const TIPOS = ["imagen", "animacion", "video"];
  // Nombres de clase literales: Tailwind no ve las armadas con `${…}`.
  const COLOR = {
    imagen: "bg-forge-tipo-imagen",
    animacion: "bg-forge-tipo-animacion",
    video: "bg-forge-tipo-video",
    calabaza: "bg-forge-tipo-calabaza",
  };
  const PLURAL = { imagen: ["imagen", "imágenes"], animacion: ["animación", "animaciones"], video: ["video", "videos"] };
  const NARRA = { mujer: "narra una mujer", hombre: "narra un hombre" };

  let page = null;
  const pending = new Map(); // clave → { timer, promise }

  // ── Datos y cuentas ─────────────────────────────────────────────────────

  const S = () => page.script;
  const ppm = () => page.lectura.palabras_por_minuto;
  const actoDe = (n) => page.actos.find((a) => a.number === n) || { number: n, name: `Acto ${n}`, parrafos: [] };
  const parrafos = (acto, desde, hasta) => actoDe(acto).parrafos.slice(desde - 1, hasta);
  const palabrasDe = (b) => parrafos(b.acto, b.desde, b.hasta).flatMap((p) => p.split(/\s+/).filter(Boolean));
  const seg = (texto) => T.segundos(T.palabras(texto), ppm());
  const segRango = (acto, desde, hasta) => T.segundos(T.palabras(parrafos(acto, desde, hasta).join(" ")), ppm());
  const cambio = (acto) => S().estado.estado === "cambiaron_parrafos" && S().estado.actos.includes(acto);

  /** Segundo del video en que empieza cada párrafo (después de la intro). */
  function inicios() {
    const out = {};
    let t = seg(S().calabaza.intro);
    page.actos.forEach((a) => {
      a.parrafos.forEach((p, i) => {
        out[`${a.number}:${i + 1}`] = t;
        t += seg(p);
      });
    });
    return { porParrafo: out, finRelato: t };
  }

  function duracionTotal() {
    const { finRelato } = inicios();
    return finRelato + seg(`${S().calabaza.outro} ${S().cierre_fijo || ""}`);
  }

  // ── Guardado automático ─────────────────────────────────────────────────

  function schedule(key, save) {
    const entry = pending.get(key) || { timer: null, promise: Promise.resolve(), save };
    entry.save = save;
    clearTimeout(entry.timer);
    entry.timer = setTimeout(() => run(key), DEBOUNCE_MS);
    pending.set(key, entry);
    window.ForgeGuardado.status("pending", "Sin guardar…");
  }

  function run(key) {
    const entry = pending.get(key);
    if (!entry) return Promise.resolve();
    clearTimeout(entry.timer);
    entry.timer = null;
    entry.promise = entry.promise.then(entry.save).catch(() => {});
    return entry.promise;
  }

  async function flushAll() {
    await Promise.all([...pending.keys()].map((k) => (pending.get(k).timer ? run(k) : pending.get(k).promise)));
  }

  async function put(path, body) {
    const G = window.ForgeGuardado;
    G.status("saving", "Guardando…");
    const resp = await fetch(`${API}/generated-narratives/${page.narrativeId}/video-script${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
    return resp.json();
  }

  // ── Avisos y resumen ────────────────────────────────────────────────────

  function renderAvisos() {
    const box = $("[data-avisos-paquete]");
    const notas = [];
    const e = S().estado;
    if (e.estado === "cambio_el_texto") {
      notas.push(["info", "history", "Corregiste el relato después de armar el guion. Ya se ve el texto nuevo; si cambiaste mucho, armalo de nuevo para que las indicaciones y los prompts sigan al texto."]);
    } else if (e.estado === "cambiaron_parrafos") {
      const actos = e.actos.map((n) => `${n} (${actoDe(n).name})`).join(", ");
      notas.push(["warning", "alert-triangle", `Cambió la cantidad de párrafos en ${e.actos.length === 1 ? "el acto" : "los actos"} ${actos}: sus bloques y momentos ya no coinciden con el texto. Armalo de nuevo antes de bajar los archivos.`]);
    }
    if (S().marcas_perdidas.length) {
      const lista = S().marcas_perdidas.map((m) => `«${esc(m.texto)}» (bloque ${m.bloque})`).join(", ");
      notas.push(["info", "highlighter", `Estas palabras remarcadas ya no están en el texto corregido y se sacaron: ${lista}.`]);
    }
    box.innerHTML = notas
      .map(([tipo, icono, texto]) => `<p class="nota-forge nota-forge--${tipo}"><i data-lucide="${icono}" class="nota-forge__icono"></i><span>${texto}</span></p>`)
      .join("");
  }

  function renderResumen() {
    const s = S();
    const propuesto = NARRA[s.narra];
    const cuenta = (t) => s.momentos.filter((m) => m.tipo === t).length;
    $("[data-resumen]").innerHTML = `
      <div class="flex flex-col gap-1.5">
        <span class="text-forge-muted-caps !tracking-[0.15em]">Quién lee</span>
        <span class="flex flex-wrap gap-1" role="group" aria-label="Quién lee">${s.lectores
          .map((n) => `<button type="button" class="opcion-chica" data-lector="${esc(n)}" aria-pressed="${n === s.lector}">${esc(n)}</button>`)
          .join("")}</span>
        <span class="text-xs text-forge-muted">${propuesto ? `Lo propuso la IA porque ${propuesto}.` : "La IA no supo si narra una mujer o un hombre: elegí vos."}</span>
      </div>
      <div class="flex flex-col gap-1">
        <span class="text-forge-muted-caps !tracking-[0.15em]">Episodio</span>
        <span class="font-serif text-xl tabular-nums" data-resumen-duracion>≈ ${T.largo(duracionTotal())}</span>
        <span class="text-xs text-forge-muted">con la calabaza, a ${ppm()} palabras por minuto</span>
      </div>
      <div class="flex flex-col gap-1">
        <span class="text-forge-muted-caps !tracking-[0.15em]">En pantalla</span>
        <span class="font-serif text-xl">${s.momentos.length} momentos</span>
        <span class="text-xs text-forge-muted flex flex-wrap gap-3">${TIPOS.map((t) => `<span class="inline-flex items-center gap-1"><i class="tipo-punto ${COLOR[t]}"></i>${cuenta(t)} ${PLURAL[t][cuenta(t) === 1 ? 0 : 1]}</span>`).join("")}</span>
      </div>`;
  }

  /** «Descargar PDF» (T4.4): se arma al bajar con lo último guardado; sin él si
   *  cambiaron los párrafos de algún acto (el Core respondería 409). */
  function botonPdf(nombre) {
    if (S().estado.estado === "cambiaron_parrafos") {
      return `<span class="btn-forge-sm opacity-40 cursor-not-allowed" aria-disabled="true" title="Armá el guion de nuevo: cambiaron los párrafos" data-pdf="${nombre}"><i data-lucide="download" class="w-4 h-4"></i> Descargar PDF</span>`;
    }
    return `<a class="btn-forge-sm" hx-boost="false" download href="${API}/generated-narratives/${page.narrativeId}/video-script/${nombre}.pdf" data-pdf="${nombre}"><i data-lucide="download" class="w-4 h-4"></i> Descargar PDF</a>`;
  }

  // ── Guion de lectura ────────────────────────────────────────────────────

  function textoBloque(b, i) {
    const marcadas = new Set();
    b.marcas.forEach((m) => {
      for (let k = m.desde_palabra; k <= m.hasta_palabra; k++) marcadas.add(k);
    });
    let k = 0;
    return parrafos(b.acto, b.desde, b.hasta)
      .map((p) => {
        const ws = p.split(/\s+/).filter(Boolean);
        let html = "";
        let abierto = false;
        ws.forEach((w, j) => {
          const m = marcadas.has(k);
          if (m && !abierto) {
            html += `${j ? " " : ""}<span class="remarcado">`;
            abierto = true;
          } else if (!m && abierto) {
            html += "</span> ";
            abierto = false;
          } else if (j) html += " ";
          html += `<span class="palabra-video" data-b="${i}" data-k="${k}">${esc(w)}</span>`;
          k++;
        });
        return `<p>${html}${abierto ? "</span>" : ""}</p>`;
      })
      .join("");
  }

  function frases(b) {
    const palabras = palabrasDe(b);
    return b.marcas.map((m) => ({ ...m, texto: palabras.slice(m.desde_palabra, m.hasta_palabra + 1).join(" ") || m.texto }));
  }

  function renderGuion() {
    const s = S();
    const acto = actoDe(page.actoSel);
    const indices = s.bloques.map((b, i) => [b, i]).filter(([b]) => b.acto === acto.number);
    const segActo = T.segundos(T.palabras(acto.parrafos.join(" ")), ppm());
    const nums = page.actos.map((a) => a.number);
    const pos = nums.indexOf(acto.number);
    const prev = page.actos[pos - 1];
    const next = page.actos[pos + 1];
    $('[data-panel="guion"]').innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p class="pista-forge"><i data-lucide="info"></i><span>Lo que lee ${esc(s.lector || "quien elijas")}, en bloques cortos. Tocá una palabra para remarcarla, o arrastrá sobre varias para remarcar una frase. Las palabras se cambian en «Corregir el relato».</span></p>
        ${botonPdf("guion")}
      </div>
      <div class="grid gap-4 lg:grid-cols-[13rem_minmax(0,1fr)_15rem] items-start">
        <nav class="card-forge !p-2 flex lg:flex-col gap-1 overflow-x-auto" aria-label="Actos">${page.actos
          .map((a) => {
            const n = s.bloques.filter((b) => b.acto === a.number).length;
            const t = T.segundos(T.palabras(a.parrafos.join(" ")), ppm());
            return `<button type="button" class="corregir-acto text-left rounded-lg px-3 py-2 min-w-[9rem] lg:min-w-0" data-acto-guion="${a.number}" aria-current="${a.number === acto.number}"><span class="block text-sm font-medium">${a.number} · ${esc(a.name)}</span><span class="block text-xs tabular-nums opacity-80">${n} ${n === 1 ? "bloque" : "bloques"} · ${T.reloj(t)}</span></button>`;
          })
          .join("")}</nav>
        <div class="card-forge !p-5 flex flex-col gap-4 min-w-0">
          <h3 class="font-serif text-2xl text-forge-accent">Acto ${acto.number} · ${esc(acto.name)}</h3>
          ${cambio(acto.number) ? `<p class="nota-forge nota-forge--warning"><i data-lucide="alert-triangle" class="nota-forge__icono"></i><span>Este acto cambió de párrafos: los bloques ya no coinciden con el texto. Armá el guion de nuevo.</span></p>` : ""}
          ${indices
            .map(
              ([b, i]) => `
            <article class="rounded-lg border border-forge-border bg-forge-bg p-4 flex flex-col gap-3" data-bloque="${i + 1}">
              <div class="flex flex-wrap items-baseline justify-between gap-2">
                <span class="text-forge-muted-caps !tracking-[0.15em]">Bloque ${i + 1}</span>
                <span class="chip-forge tabular-nums">${T.reloj(segRango(b.acto, b.desde, b.hasta))}</span>
              </div>
              <label class="flex flex-col gap-1 text-sm text-forge-muted">Cómo se lee
                <input type="text" class="rounded-md border border-forge-border bg-forge-surface px-3 py-2 text-forge-text" data-indicacion="${i}" value="${esc(b.indicacion)}">
              </label>
              <div class="prose-forge flex flex-col gap-3 select-text" data-texto-bloque="${i}">${textoBloque(b, i)}</div>
            </article>
            <div class="flex items-center gap-3 text-sm text-forge-muted" role="group" aria-label="Después del bloque ${i + 1}">
              <span class="flex-1 border-t border-dashed border-forge-border"></span>
              ${PAUSAS.map(([v, t]) => `<button type="button" class="opcion-chica" data-pausa="${i}" data-v="${v}" aria-pressed="${b.pausa === v}">${t}</button>`).join("")}
              <span class="flex-1 border-t border-dashed border-forge-border"></span>
            </div>`,
            )
            .join("")}
          <div class="flex flex-wrap justify-between gap-2 pt-3 border-t border-forge-border">
            ${prev ? `<button type="button" class="btn-forge-outline-sm" data-acto-guion="${prev.number}"><i data-lucide="arrow-left" class="w-4 h-4"></i> ${esc(prev.name)}</button>` : "<span></span>"}
            ${next ? `<button type="button" class="btn-forge-outline-sm" data-acto-guion="${next.number}">${esc(next.name)} <i data-lucide="arrow-right" class="w-4 h-4"></i></button>` : ""}
          </div>
        </div>
        <aside class="card-forge !p-4 flex flex-col gap-3 text-sm">
          <span class="text-forge-muted-caps !tracking-[0.15em]">Este acto</span>
          <span class="tabular-nums">${indices.length} bloques · ≈ ${T.largo(segActo)}</span>
          <span class="text-forge-muted-caps !tracking-[0.15em]">Remarcado</span>
          <div class="flex flex-wrap gap-1.5" data-frases>${
            indices.flatMap(([b, i]) => frases(b).map((f) => `<button type="button" class="opcion-chica" data-quitar="${i}" data-d="${f.desde_palabra}" data-h="${f.hasta_palabra}" title="Sacar el remarcado">${esc(f.texto)} ×</button>`)).join("") ||
            '<span class="text-forge-muted">Nada remarcado en este acto.</span>'
          }</div>
          <span class="text-forge-muted-caps !tracking-[0.15em]">En el PDF</span>
          <span class="text-forge-muted">Letra grande, un acto por hoja, «cómo se lee» en gris y las pausas como una línea.</span>
        </aside>
      </div>`;
  }

  function guardarMarcas(i, tramos) {
    const b = S().bloques[i];
    b.marcas = tramos.map(([d, h]) => ({ desde_palabra: d, hasta_palabra: h, texto: "" }));
    renderGuion();
    icons();
    schedule(`bloque-marcas-${i}`, async () => {
      const saved = await put(`/blocks/${i + 1}`, { marcas: tramos });
      S().bloques[i].marcas = saved.marcas;
    });
  }

  const tramosDe = (b) => b.marcas.map((m) => [m.desde_palabra, m.hasta_palabra]);

  // ── La calabaza ─────────────────────────────────────────────────────────

  const CALABAZA_SVG = `<svg viewBox="0 0 120 120" class="w-16 h-16 shrink-0" aria-hidden="true">
    <path d="M60 22c2-8 6-12 12-13" class="stroke-forge-success" stroke-width="6" fill="none" stroke-linecap="round"/>
    <ellipse cx="60" cy="70" rx="44" ry="38" class="fill-forge-accent"/>
    <ellipse cx="44" cy="70" rx="18" ry="37" fill="none" class="stroke-forge-surface" stroke-opacity="0.4" stroke-width="2.5"/>
    <ellipse cx="76" cy="70" rx="18" ry="37" fill="none" class="stroke-forge-surface" stroke-opacity="0.4" stroke-width="2.5"/>
    <path d="M38 60l12-7 2 12z M82 60l-12-7-2 12z" class="fill-forge-tipo-video"/>
    <path d="M40 86q20 14 40 0l-6 3-4-4-5 5-5-5-5 5-5-5-4 4z" class="fill-forge-text"/>
    <path d="M14 66a46 46 0 0 1 92 0" class="stroke-forge-text" stroke-width="6" fill="none"/>
    <rect x="6" y="58" width="14" height="26" rx="6" class="fill-forge-text"/>
    <rect x="100" y="58" width="14" height="26" rx="6" class="fill-forge-text"/>
  </svg>`;

  function cajaCalabaza(k, titulo, ayuda, extra) {
    const texto = S().calabaza[k];
    return `<section class="card-forge !p-5 flex flex-col gap-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-serif text-xl text-forge-accent">${titulo}</h3>
        <button type="button" class="btn-forge-outline-sm" data-copiar="${k}"><i data-lucide="copy" class="w-4 h-4"></i> Copiar para ElevenLabs</button>
      </div>
      <p class="pista-forge"><i data-lucide="info"></i><span>${ayuda}</span></p>
      <label class="sr-only" for="calabaza-${k}">${titulo}</label>
      <textarea id="calabaza-${k}" class="prose-forge w-full min-h-[8rem] overflow-hidden rounded-lg border border-forge-border bg-forge-bg px-4 py-3" data-calabaza="${k}">${esc(texto)}</textarea>
      <span class="text-xs text-forge-muted tabular-nums" data-calabaza-dato="${k}">${T.palabras(texto)} palabras · ≈ ${seg(texto)} s</span>
      ${extra || ""}
    </section>`;
  }

  function renderCalabaza() {
    const cierre = S().cierre_fijo
      ? `<div class="rounded-lg border border-dashed border-forge-border px-4 py-3 text-sm text-forge-muted"><span class="text-forge-muted-caps !tracking-[0.15em]">Después, siempre igual</span><br>${esc(S().cierre_fijo)}</div>`
      : `<p class="text-xs text-forge-muted">El pedido de like y suscripción va aparte, igual en todos los episodios; todavía no está cargado.</p>`;
    $('[data-panel="calabaza"]').innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p class="pista-forge"><i data-lucide="info"></i><span>Lo que dice la calabaza. Se pega tal cual en ElevenLabs: sin etiquetas ni marcas.</span></p>
        <a class="btn-forge-sm" hx-boost="false" download href="${API}/generated-narratives/${page.narrativeId}/video-script/calabaza.txt" data-bajar-txt><i data-lucide="download" class="w-4 h-4"></i> Descargar .txt</a>
      </div>
      <div class="flex flex-col gap-4 max-w-3xl">
        <section class="card-forge !p-4 flex items-center gap-4 text-sm text-forge-muted">${CALABAZA_SVG}<div><strong class="text-forge-text">La calabaza de la cripta</strong><br>Presenta y despide. Habla en rioplatense, con humor negro.</div></section>
        ${cajaCalabaza("intro", "Intro", "Presenta la historia sin contar nada que no pase en el acto 1. Unos 20 a 30 segundos.")}
        ${cajaCalabaza("outro", "Outro", "Un chiste sobre lo que pasó y una última frase inquietante. Termina en «Buenas noches».", cierre)}
      </div>`;
    $$("[data-calabaza]").forEach(alto);
  }

  function alto(area) {
    area.style.height = "auto";
    area.style.height = `${area.scrollHeight + 4}px`;
  }

  // ── Mapa de producción ──────────────────────────────────────────────────

  function renderMapa() {
    const s = S();
    const { porParrafo, finRelato } = inicios();
    const introS = seg(s.calabaza.intro);
    const outroS = seg(`${s.calabaza.outro} ${s.cierre_fijo || ""}`);
    const total = finRelato + outroS;
    const m = s.momentos[page.momSel];
    const ini = porParrafo[`${m.acto}:${m.desde}`] ?? 0;
    const dur = segRango(m.acto, m.desde, m.hasta);
    const pct = (x) => `${(x / Math.max(total, 1)) * 100}%`;
    const tramo = (clase, ancho, contenido, extra = "") =>
      `<span class="relative block h-full ${clase}" style="width:${pct(ancho)}" ${extra}>${contenido}</span>`;
    const marcas = [];
    for (let t = 0; t < total; t += 120) marcas.push(`<span class="absolute -translate-x-1/2" style="left:${pct(t)}">${t / 60}′</span>`);
    $('[data-panel="mapa"]').innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p class="pista-forge"><i data-lucide="info"></i><span>Qué va en pantalla mientras se lee, en orden. Al copiar un prompt de imagen se le suma el estilo de todas las imágenes.</span></p>
        ${botonPdf("mapa")}
      </div>
      <section class="card-forge !p-4 flex flex-col gap-2" aria-label="Línea de tiempo">
        <div class="flex h-11 gap-0.5 rounded-md overflow-hidden">
          ${tramo(COLOR.calabaza, introS, "", 'title="Intro de la calabaza"')}
          ${s.momentos
            .map((x, i) => {
              const d = segRango(x.acto, x.desde, x.hasta);
              return `<button type="button" class="mapa-tramo ${COLOR[x.tipo]}" style="width:${pct(d)}" data-mom="${i}" aria-current="${i === page.momSel}" title="${i + 1}. ${esc(x.que_se_ve)}"><span class="mapa-tramo__num">${i + 1}</span></button>`;
            })
            .join("")}
          ${tramo(COLOR.calabaza, outroS, "", 'title="Outro de la calabaza"')}
        </div>
        <div class="relative h-4 text-xs text-forge-muted tabular-nums">${marcas.join("")}</div>
        <div class="flex flex-wrap gap-4 text-xs text-forge-muted">${TIPOS.map((t) => `<span class="inline-flex items-center gap-1.5"><i class="tipo-punto ${COLOR[t]}"></i>${esc(s.tipos[t].nombre)}</span>`).join("")}<span class="inline-flex items-center gap-1.5"><i class="tipo-punto ${COLOR.calabaza}"></i>La calabaza</span></div>
      </section>
      <div class="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] items-start">
        <section class="card-forge !p-5 flex flex-col gap-3 min-w-0">
          <span class="text-forge-muted-caps !tracking-[0.15em]">Mientras se lee · <span class="tabular-nums">${T.reloj(ini)} – ${T.reloj(ini + dur)}</span></span>
          ${cambio(m.acto) ? `<p class="nota-forge nota-forge--warning"><i data-lucide="alert-triangle" class="nota-forge__icono"></i><span>Este acto cambió de párrafos: este momento ya no coincide con el texto.</span></p>` : ""}
          <div class="prose-forge text-forge-muted flex flex-col gap-2">${parrafos(m.acto, m.desde, m.hasta).map((p) => `<p>${esc(p)}</p>`).join("")}</div>
        </section>
        <section class="card-forge !p-5 flex flex-col gap-4 min-w-0" data-ficha="${page.momSel}">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <h3 class="font-serif text-xl">${page.momSel + 1}. ${esc(m.que_se_ve)}</h3>
            <span class="chip-forge tabular-nums">${dur} s</span>
          </div>
          <div class="flex flex-col gap-1.5 text-sm text-forge-muted">Qué va
            <span class="flex flex-wrap gap-1" role="group" aria-label="Qué va">${TIPOS.map((t) => `<button type="button" class="opcion-chica" data-tipo="${t}" aria-pressed="${m.tipo === t}"><i class="tipo-punto ${COLOR[t]}"></i> ${esc(s.tipos[t].nombre)}</button>`).join("")}</span>
            <span class="text-xs">${esc(s.tipos[m.tipo].se_genera_con)}</span>
          </div>
          ${campo("que_se_ve", "Qué se ve (para quien edita)", m.que_se_ve)}
          ${campoLargo("prompt_imagen", "Prompt de la imagen", m.prompt_imagen, "img")}
          ${m.tipo === "imagen" ? "" : campoLargo("prompt_movimiento", "Prompt del movimiento", m.prompt_movimiento, "mov")}
          <div class="grid gap-4 sm:grid-cols-2">
            <label class="flex flex-col gap-1 text-sm text-forge-muted">Transición
              <select class="rounded-md border border-forge-border bg-forge-surface px-3 py-2 text-forge-text" data-campo="transicion">${s.transiciones.map((t) => `<option${t === m.transicion ? " selected" : ""}>${esc(t)}</option>`).join("")}</select>
            </label>
            ${campo("sonido", "Sonido", m.sonido)}
          </div>
          ${campo("lugar", "Lugar (para el nombre del archivo)", m.lugar)}
          <div class="flex flex-wrap justify-between gap-2 pt-3 border-t border-forge-border">
            ${page.momSel ? `<button type="button" class="btn-forge-outline-sm" data-mom="${page.momSel - 1}"><i data-lucide="arrow-left" class="w-4 h-4"></i> Anterior</button>` : "<span></span>"}
            ${page.momSel < s.momentos.length - 1 ? `<button type="button" class="btn-forge-outline-sm" data-mom="${page.momSel + 1}">Siguiente <i data-lucide="arrow-right" class="w-4 h-4"></i></button>` : ""}
          </div>
        </section>
      </div>`;
  }

  function campo(nombre, rotulo, valor) {
    return `<label class="flex flex-col gap-1 text-sm text-forge-muted">${rotulo}
      <input type="text" class="rounded-md border border-forge-border bg-forge-surface px-3 py-2 text-forge-text" data-campo="${nombre}" value="${esc(valor)}">
    </label>`;
  }

  function campoLargo(nombre, rotulo, valor, copiar) {
    return `<div class="flex flex-col gap-1 text-sm text-forge-muted">
      <div class="flex items-center justify-between gap-2"><label for="campo-${nombre}">${rotulo}</label>
        <button type="button" class="btn-forge-outline-sm" data-copiar="${copiar}"><i data-lucide="copy" class="w-4 h-4"></i> Copiar</button></div>
      <textarea id="campo-${nombre}" class="min-h-[6rem] rounded-md border border-forge-border bg-forge-surface px-3 py-2 font-mono text-sm text-forge-text" data-campo="${nombre}">${esc(valor)}</textarea>
    </div>`;
  }

  // ── Acciones ────────────────────────────────────────────────────────────

  async function copiar(que, boton) {
    const s = S();
    const m = s.momentos[page.momSel];
    const texto = {
      intro: s.calabaza.intro,
      outro: s.calabaza.outro,
      img: `${s.estilo_imagen} ${m.prompt_imagen}`,
      mov: m.prompt_movimiento,
    }[que];
    try {
      await navigator.clipboard.writeText(texto);
      window.ForgeGuardado.status("ok", "Copiado");
    } catch {
      window.ForgeGuardado.status("error", "No se pudo copiar: seleccioná el texto a mano");
    }
    boton.blur();
  }

  async function rearmar(boton) {
    const ok = await window.ForgeConfirm.ask({
      title: "¿Armar el guion de nuevo?",
      message: boton.dataset.detalle,
      confirmLabel: "Armar de nuevo",
    });
    if (!ok) return;
    await flushAll();
    const resp = await fetch(`${API}/stories/${page.storyId}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "video_script", narrative_id: page.narrativeId }),
    });
    if (resp.status !== 202) {
      window.ForgeGuardado.status("error", resp.status === 409 ? "La IA ya está trabajando en esta historia: esperá a que termine" : "No se pudo armar el guion de nuevo");
      return;
    }
    window.ForgeIaModal.open(await resp.json(), {
      titulo: "Armando el guion de nuevo…",
      detalle: "Reparte el relato en bloques, escribe la intro y el outro de la calabaza y arma lo que va en pantalla.",
      onDone: () => location.reload(),
    });
  }

  function mostrar(tab) {
    page.tab = tab;
    $$("[data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    $$("[data-panel]").forEach((p) => (p.hidden = p.dataset.panel !== tab));
    try {
      history.replaceState(history.state, "", `${location.pathname}${location.search}#${tab}`);
    } catch {
      /* sin history */
    }
    ({ guion: renderGuion, calabaza: renderCalabaza, mapa: renderMapa })[tab]();
    icons();
  }

  function icons() {
    if (window.lucide) window.lucide.createIcons();
  }

  function refrescarResumen() {
    const d = $("[data-resumen-duracion]");
    if (d) d.textContent = `≈ ${T.largo(duracionTotal())}`;
  }

  // ── Eventos ─────────────────────────────────────────────────────────────

  let ignorarClick = false;

  document.addEventListener("click", (e) => {
    if (!page || !e.target.closest) return;
    if (ignorarClick) {
      ignorarClick = false;
      return;
    }
    const t = e.target;
    const palabra = t.closest(".palabra-video");
    if (palabra) {
      const i = Number(palabra.dataset.b);
      return guardarMarcas(i, M.alternarPalabra(tramosDe(S().bloques[i]), Number(palabra.dataset.k)));
    }
    const b = t.closest("button, a");
    if (!b) return;
    const d = b.dataset;
    if (d.tab) return mostrar(d.tab);
    if (d.actoGuion) {
      page.actoSel = Number(d.actoGuion);
      renderGuion();
      return icons();
    }
    if (d.mom !== undefined) {
      page.momSel = Number(d.mom);
      renderMapa();
      return icons();
    }
    if (d.lector !== undefined) {
      const nuevo = S().lector === d.lector ? null : d.lector;
      S().lector = nuevo;
      renderResumen();
      return schedule("lector", () => put("/reader", { lector: nuevo }));
    }
    if (d.pausa !== undefined) {
      const i = Number(d.pausa);
      S().bloques[i].pausa = d.v;
      renderGuion();
      icons();
      return schedule(`bloque-pausa-${i}`, () => put(`/blocks/${i + 1}`, { pausa: d.v }));
    }
    if (d.quitar !== undefined) {
      const i = Number(d.quitar);
      return guardarMarcas(i, M.alternarTramo(tramosDe(S().bloques[i]), Number(d.d), Number(d.h)));
    }
    if (d.tipo) {
      const i = page.momSel;
      S().momentos[i].tipo = d.tipo;
      renderMapa();
      renderResumen();
      icons();
      return schedule(`momento-tipo-${i}`, () => put(`/moments/${i + 1}`, { tipo: d.tipo }));
    }
    if (d.copiar) return copiar(d.copiar, b);
    if (d.rearmar !== undefined) return rearmar(b);
  });

  /** Arrastrar sobre varias palabras de un bloque remarca (o saca) la frase. */
  function alSoltar() {
    if (!page) return;
    const sel = getSelection();
    if (!sel || sel.isCollapsed) return;
    const tocadas = $$(".palabra-video").filter((el) => sel.containsNode(el, true));
    if (tocadas.length < 2) return;
    const i = Number(tocadas[0].dataset.b);
    const ks = tocadas.filter((el) => Number(el.dataset.b) === i).map((el) => Number(el.dataset.k));
    sel.removeAllRanges();
    ignorarClick = true;
    setTimeout(() => (ignorarClick = false), 0);
    guardarMarcas(i, M.alternarTramo(tramosDe(S().bloques[i]), Math.min(...ks), Math.max(...ks)));
  }
  document.addEventListener("mouseup", alSoltar);
  document.addEventListener("touchend", () => setTimeout(alSoltar, 50));

  document.addEventListener("input", (e) => {
    if (!page) return;
    const t = e.target;
    const d = t.dataset || {};
    if (d.indicacion !== undefined) {
      const i = Number(d.indicacion);
      S().bloques[i].indicacion = t.value;
      return schedule(`bloque-indicacion-${i}`, () => put(`/blocks/${i + 1}`, { indicacion: t.value }));
    }
    if (d.calabaza) {
      const k = d.calabaza;
      S().calabaza[k] = t.value;
      alto(t);
      const dato = $(`[data-calabaza-dato="${k}"]`);
      if (dato) dato.textContent = `${T.palabras(t.value)} palabras · ≈ ${seg(t.value)} s`;
      refrescarResumen();
      return schedule(`calabaza-${k}`, () => put("/presenter", { [k]: t.value }));
    }
    if (d.campo) {
      const i = page.momSel;
      S().momentos[i][d.campo] = t.value;
      return schedule(`momento-${d.campo}-${i}`, () => put(`/moments/${i + 1}`, { [d.campo]: t.value }));
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if ([...pending.values()].some((p) => p.timer)) {
      [...pending.keys()].forEach(run);
      e.preventDefault();
    }
  });

  function init() {
    const root = $("[data-video]");
    if (!root) {
      page = null;
      return;
    }
    let data = {};
    try {
      data = JSON.parse(($("#video-datos") || {}).textContent || "{}");
    } catch {
      /* sin datos */
    }
    pending.clear();
    page = {
      storyId: root.dataset.storyId,
      narrativeId: root.dataset.narrativeId,
      script: data.script,
      actos: data.actos || [],
      lectura: data.lectura || { palabras_por_minuto: 150, episodio_minutos: { desde: 12, hasta: 17 } },
      actoSel: (data.actos && data.actos[0] && data.actos[0].number) || 1,
      momSel: 0,
      tab: "guion",
    };
    renderAvisos();
    renderResumen();
    const pedida = location.hash.replace("#", "");
    mostrar(["guion", "calabaza", "mapa"].includes(pedida) ? pedida : "guion");
  }

  window.ForgeVideo = { init, flushAll };
  init();
})();
