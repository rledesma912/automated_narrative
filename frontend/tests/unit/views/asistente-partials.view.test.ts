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
