import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/**
 * Spec-760 A1: ningún campo del asistente corta en silencio. En vez de `maxlength`
 * (el navegador recorta lo que se pega sin avisar) los campos llevan `data-tope`
 * con los topes de config, y public/js/tope.js avisa.
 */
const VIEWS = path.join(process.cwd(), "src/views");
const FIX = path.join(process.cwd(), "tests/fixtures/asistente");
const state = JSON.parse(fs.readFileSync(path.join(FIX, "estado.json"), "utf8"));
const TOPES = { premise: 20000, final: 20000, answer: 2000, event: 800, rule: 300, title: 120 };
const locals = { state, estimateLabels: {}, assetVersion: "v", topes: TOPES, options: { tellings: [], structures: [] }, genres: [] };

const render = (paso: string, extra = {}) =>
  ejs.renderFile(path.join(VIEWS, "asistente", `${paso}.ejs`), { ...locals, pasoActual: paso, ...extra });

describe("sin maxlength en el asistente", () => {
  const archivos = [
    ...fs.readdirSync(path.join(VIEWS, "asistente")).map((f) => path.join(VIEWS, "asistente", f)),
    path.join(process.cwd(), "public/js/asistente.js"),
  ];
  it.each(archivos.map((f) => [path.relative(process.cwd(), f), f]))("%s", (_rel, f) => {
    expect(fs.readFileSync(f, "utf8")).not.toMatch(/maxlength/i);
  });
});

describe("los campos traen el tope de config", () => {
  it("«¿De qué trata?» con 20 000 y alto máximo", async () => {
    const html = await render("direccion");
    const idea = html.match(/<textarea id="a-premise"[^>]*>/)![0];
    expect(idea).toContain('data-tope="20000"');
    expect(idea).toContain("max-h-[70vh]");
  });

  it("los hechos de un acto con 800", async () => {
    const html = await render("escaleta");
    expect(html).toMatch(/<textarea name="events" rows="1" data-tope="800"/);
  });

  it("«Cómo termina» con el tope del final y las demás respuestas con el de siempre", async () => {
    const html = await render("taller");
    const cambios = [...html.matchAll(/data-pregunta="(\w+)"[\s\S]*?<textarea data-texto-mia[^>]*data-tope="(\d+)"/g)].map(
      (m) => [m[1], m[2]],
    );
    expect(cambios.length).toBeGreaterThan(0);
    for (const [criterio, t] of cambios) expect(t).toBe(criterio === "final" ? "20000" : "2000");
  });

  it("los textos del contador están en la vista", async () => {
    const html = await render("escaleta");
    const t = html.match(/<template id="tope-textos"[^>]*>/)![0];
    expect(t).toContain('data-cuenta="{n} de {tope} letras"');
    expect(t).toContain("data-sobra=");
    expect(t).toContain("&#34;event&#34;:800");
    expect(html).toContain('<script src="/js/tope.js?v=v"></script>');
  });

  it("sin topes (el Core no los mandó) la vista igual se arma", async () => {
    await expect(render("escaleta", { topes: undefined })).resolves.toContain('data-tope=""');
  });
});
