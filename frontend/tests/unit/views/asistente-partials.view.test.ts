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

// Spec-700 D27: la IA no pudo revisar las respuestas; qué cambió, sin IA.
describe("taller: lo que cambió sin revisar", () => {
  const render = (idea_sin_revisar: unknown) =>
    ejs.renderFile(path.join(VIEWS, "asistente", "taller.ejs"), {
      ...locals,
      state: { ...state, idea_sin_revisar },
      pasoActual: "taller",
    });
  const nota = (html: string) =>
    (html.match(/<div[^>]*data-idea-cambio="respuestas"[^>]*>[\s\S]*?Listo, ya las revisé<\/button>/) || [""])[0];

  it("nota de información con lo que se sacó tachado, lo que se agregó y «Listo, ya las revisé»", async () => {
    const n = nota(await render({ sacado: ["Ximena se va del pueblo."], agregado: ["Ximena se queda.", "Enfrenta a Yadira."] }));
    expect(n).toContain("nota-forge--info");
    expect(n).toContain("la IA no pudo fijarse si tus respuestas siguen yendo");
    expect(n).toMatch(/Ya no dice[\s\S]*<li class="[^"]*line-through[^"]*">Ximena se va del pueblo\.<\/li>/);
    expect(n).toMatch(/Ahora dice[\s\S]*>Ximena se queda\.<\/li>[\s\S]*>Enfrenta a Yadira\.<\/li>/);
    expect(n).toMatch(/data-idea-revisada="respuestas">Listo, ya las revisé</);
  });

  it("solo lo que hay: sin oraciones sacadas no dice «Ya no dice»", async () => {
    const n = nota(await render({ sacado: [], agregado: ["Y se muda."] }));
    expect(n).not.toContain("Ya no dice");
    expect(n).toContain("Ahora dice");
  });

  it("sin nada pendiente no hay nota", async () => {
    expect(await render(null)).not.toContain('data-idea-cambio="respuestas"');
  });
});

// Spec-720 D7: lo hizo la IA de la compu porque la de la nube no respondió.
describe("los actos: hechos por la IA de la compu", () => {
  const render = (hecho_local: unknown) =>
    ejs.renderFile(path.join(VIEWS, "asistente", "escaleta.ejs"), {
      ...locals,
      state: { ...state, hecho_local },
      pasoActual: "escaleta",
    });
  const nota = (html: string) =>
    (html.match(/<div[^>]*data-hecho-local="[^"]*"[^>]*>[\s\S]*?Dejarlo así<\/button>/) || [""])[0];

  it("actos: nota de información con armar de nuevo (con confirmación) y «Dejarlo así»", async () => {
    const n = nota(await render({ actos: true, revision: true }));
    expect(n).toContain('data-hecho-local="actos"');
    expect(n).toContain("nota-forge--info");
    expect(n).toContain("Estos actos los armó la IA de tu compu porque la de la nube no respondió.");
    expect(n).toMatch(/data-analizar="plan_outline"[^>]*data-confirmar="[^"]*se reemplaza\."/);
    expect(n).toMatch(/data-idea-revisada="local">Dejarlo así</);
  });

  it("solo la revisión: ofrece revisar de nuevo", async () => {
    const n = nota(await render({ actos: false, revision: true }));
    expect(n).toContain('data-hecho-local="revision"');
    expect(n).toContain("La revisión la hizo la IA de tu compu");
    expect(n).toMatch(/data-analizar="verify_outline"[^>]*>Revisar de nuevo</);
  });

  it("con la nube (o sin dato) no hay nota", async () => {
    expect(await render({ actos: false, revision: false })).not.toContain("data-hecho-local");
    expect(await render(undefined)).not.toContain("data-hecho-local");
  });
});

// Spec-730 D12: la nota de un personaje que sumó la IA.
describe("acto: personaje que sumó la IA", () => {
  const nota = { text: "La IA sumó a «Don Ramón», el sereno de la terminal: le advierte que no pare.", key: "propuesto:don ramon", source: "regla", dismissed: false };
  const render = (warnings: unknown[]) => {
    const acts = state.outline.acts.map((a: { number: number }) => (a.number === 2 ? { ...a, warnings } : a));
    return ejs.renderFile(path.join(VIEWS, "asistente", "escaleta.ejs"), {
      ...locals,
      state: { ...state, outline: { ...state.outline, acts } },
      pasoActual: "escaleta",
    });
  };

  it("nota de información con «Entendido», sin «Ignorar» ni «Sumarlo»", async () => {
    const html = await render([nota]);
    const n = html.match(/<div[^>]*data-propuesto[^>]*>[\s\S]*?<\/div>/)![0];
    expect(n).toContain("nota-forge--info");
    expect(n).toContain("La IA sumó a «Don Ramón», el sereno de la terminal");
    expect(n).toMatch(/data-ignorar="propuesto:don ramon">Entendido</);
    expect(n).not.toContain("Ignorar");
    expect(n).not.toContain("data-sumar-personaje");
  });

  it("cerrada, no aparece ni entre los avisos ignorados", async () => {
    const html = (await render([{ ...nota, dismissed: true }])).replace(/<script[\s\S]*?<\/script>/g, "");
    expect(html).not.toContain("data-propuesto");
    expect(html).not.toContain("Don Ramón», el sereno");
  });

  it("no cuenta como aviso en el resumen", async () => {
    const acts = state.outline.acts.map((a: { number: number }) => ({ ...a, warnings: a.number === 2 ? [nota] : [] }));
    const html = await ejs.renderFile(path.join(VIEWS, "asistente", "escaleta.ejs"), {
      ...locals,
      state: { ...state, outline: { ...state.outline, acts } },
      pasoActual: "escaleta",
    });
    expect(html).toContain("Nada para marcar");
  });
});

// Spec-700 A3: una respuesta que ya no va con la idea nueva se marca, no se pisa.
describe("taller: ya no coincide", () => {
  it("la respuesta sigue, con la nota del motivo y «Está bien así»", async () => {
    const items = state.workshop.items.map((i: { status: string; answer: string }, n: number) =>
      n === state.workshop.items.findIndex((x: { status: string; answer: string }) => x.status === "cumple" && x.answer)
        ? { ...i, no_coincide: "Ahora tu idea dice que se queda." }
        : i,
    );
    const html = await ejs.renderFile(path.join(VIEWS, "asistente", "taller.ejs"), {
      ...locals,
      state: { ...state, workshop: { ...state.workshop, items } },
      pasoActual: "taller",
    });
    const nota = html.match(/<div[^>]*data-no-coincide[^>]*>[\s\S]*?<\/div>/g)!;
    expect(nota).toHaveLength(1);
    expect(nota[0]).toContain("Esto ya no va con tu idea nueva: Ahora tu idea dice que se queda.");
    expect(nota[0]).toMatch(/data-taller="keep">Está bien así</);
    const li = html.match(/<li[^>]*data-pregunta="[^"]*"[^>]*>(?:(?!<\/li>)[\s\S])*data-no-coincide[\s\S]*?<\/li>/)![0];
    expect(li).toContain("data-cambiar");
  });
});
