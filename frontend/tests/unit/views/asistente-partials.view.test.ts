import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/**
 * Spec-630 S2 T2.1: «Los actos» y «Preguntas» se arman con partials (la tarjeta de
 * cada acto, el contenido del taller) que también se piden solos para actualizar
 * sin recargar. Extraerlos no cambia el HTML de la página: se compara contra el
 * render guardado antes del cambio (`UPDATE_FIXTURES=1` para regenerarlo a propósito).
 */
const VIEWS = path.join(process.cwd(), "src/views");
const FIX = path.join(process.cwd(), "tests/fixtures/asistente");
const state = JSON.parse(fs.readFileSync(path.join(FIX, "estado.json"), "utf8"));
const locals = { state, pasoActual: "", estimateLabels: { verify_outline: "≈ 1 min" }, assetVersion: "v" };

/** Sin comentarios EJS ni espacios de más: lo que importa es el HTML. */
const norm = (html: string) => html.replace(/\s+/g, " ").replace(/> </g, "><").trim();

describe.each(["escaleta", "taller"])("%s", (paso) => {
  it("se ve igual que antes de extraer los partials", async () => {
    const html = norm(await ejs.renderFile(path.join(VIEWS, "asistente", `${paso}.ejs`), { ...locals, pasoActual: paso }));
    const file = path.join(FIX, `${paso}.html`);
    if (process.env.UPDATE_FIXTURES || !fs.existsSync(file)) fs.writeFileSync(file, html);
    expect(html).toBe(fs.readFileSync(file, "utf8"));
  });
});

// Spec-660 B1: «Escribir el relato» pregunta en «Los actos» y, con versiones, avisa que es nueva.
describe("escaleta: escribir el relato", () => {
  const boton = async (status: string) => {
    const html = await ejs.renderFile(path.join(VIEWS, "asistente", "escaleta.ejs"), {
      ...locals,
      estimateLabels: { full_generation: "≈ 2 min" },
      state: { ...state, status },
      pasoActual: "escaleta",
    });
    return html.match(/<button[^>]*data-escribir-relato[^>]*>/)![0];
  };

  it("es un botón con la historia y el tiempo estimado, sin link a la sala", async () => {
    const b = await boton("draft");
    expect(b).toContain(`data-story-id="${state.story_id}"`);
    expect(b).toContain('data-estimado="≈ 2 min"');
    expect(b).toContain("data-generation-trigger");
    expect(b).not.toContain("data-version-nueva");
  });

  it("con un relato terminado avisa que es una versión nueva", async () => {
    expect(await boton("completed")).toContain("data-version-nueva");
  });
});

// Con todo respondido o decidido, «Preguntame lo que falta» no haría nada: no se ofrece.
describe("taller: preguntar lo que falta", () => {
  const boton = async (kind: string) => {
    const html = await ejs.renderFile(path.join(VIEWS, "asistente", "taller.ejs"), {
      ...locals,
      state: { ...state, workshop: { ...state.workshop, finish: { kind, text: "…" } } },
      pasoActual: "taller",
    });
    return html.match(/<button[^>]*data-preguntar-falta[^>]*>[\s\S]*?<\/button>/)![0];
  };

  it("con preguntas abiertas se ofrece y dice lo que hace", async () => {
    const b = await boton("abierto");
    expect(b).toContain("Preguntame lo que falta");
    expect(b).not.toMatch(/class="[^"]*\bhidden\b/);
  });

  it("con todo respondido queda escondido", async () => {
    expect(await boton("respondido")).toMatch(/class="[^"]*\bhidden\b/);
  });
});

// Spec-700 A2/A5: la idea cambió después de las preguntas o de armar los actos.
describe("la idea cambió", () => {
  const render = (paso: string, idea_cambio: { preguntas: boolean; actos: boolean }, finish = "abierto") =>
    ejs.renderFile(path.join(VIEWS, "asistente", `${paso}.ejs`), {
      ...locals,
      state: { ...state, idea_cambio, workshop: { ...state.workshop, finish: { kind: finish, text: "…" } } },
      pasoActual: paso,
    });
  const nota = (html: string, paso: string) =>
    (html.match(new RegExp(`<div[^>]*data-idea-cambio="${paso}"[^>]*>[\\s\\S]*?</div>`)) || [""])[0];

  it("«Preguntas»: nota con volver a leer y «Dejarlo así»; el botón de la barra aparece aunque esté todo respondido", async () => {
    const html = await render("taller", { preguntas: true, actos: false }, "respondido");
    const n = nota(html, "preguntas");
    expect(n).toContain("Cambiaste tu idea después de estas preguntas.");
    expect(n).toMatch(/data-analizar="consult"[^>]*>Que la IA la vuelva a leer</);
    expect(n).toMatch(/data-idea-revisada="preguntas">Dejarlo así</);
    const boton = html.match(/<button[^>]*data-preguntar-falta[^>]*>/)![0];
    expect(boton).not.toMatch(/class="[^"]*\bhidden\b/);
  });

  it("«Los actos»: armar de nuevo siempre pide confirmar", async () => {
    const html = await render("escaleta", { preguntas: false, actos: true });
    const n = nota(html, "actos");
    expect(n).toContain("Cambiaste tu idea después de armar los actos.");
    const armar = n.match(/<button[^>]*data-analizar="plan_outline"[^>]*>/)![0];
    expect(armar).toMatch(/data-confirmar="[^"]*se reemplaza\."/);
    expect(armar).toContain('data-confirmar-titulo="¿Armar los actos de nuevo?"');
    expect(n).toMatch(/data-idea-revisada="actos">Dejarlo así</);
  });

  it("sin cambio (o sin saberlo) no hay notas", async () => {
    for (const paso of ["taller", "escaleta"]) {
      const html = await render(paso, { preguntas: false, actos: false });
      expect(html).not.toContain("data-idea-cambio");
    }
    const sinDato = await ejs.renderFile(path.join(VIEWS, "asistente", "escaleta.ejs"), { ...locals, pasoActual: "escaleta" });
    expect(sinDato).not.toContain("data-idea-cambio");
  });
});
