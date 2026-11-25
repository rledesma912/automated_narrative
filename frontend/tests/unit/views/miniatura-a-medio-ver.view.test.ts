import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";

/** Spec-790 T3.3: si la relación pide esconderlo, «Miniaturas» dice que todavía no lo hacemos. */
const vista = path.join(process.cwd(), "src/views/miniaturas/historia.ejs");
const TANDA = { n: 1, color: "desaturado", tone: "verde", images: [{ template: "A_der" }] };
const render = (texts: unknown, batches: unknown[] = [TANDA]) =>
  ejs.renderFile(vista, {
    story: { id: "s-1", title: "Peter" },
    thumb: {
      input: { figure: "entidad", figure_description: "", place_description: "", color: "desaturado", tone: "" },
      batches,
      tonos: [{ id: "verde", nombre: "Verde" }],
      plantillas: [{ id: "A_der", nombre: "A la derecha" }],
      tono_propuesto: "verde",
      comfy_disponible: true,
      texts,
    },
    bust: 1,
  });
const nota = (html: string) =>
  (html.match(/<p[^>]*data-a-medio-ver[\s\S]*?<\/p>/) || [""])[0].replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();

describe("«a medio ver» en Miniaturas (Spec-790 T3.3)", () => {
  it("escondido: lo dice con lo que contó y que por ahora se pierde en la sombra", async () => {
    const html = await render({ a_medio_ver: "mucho", relacion: "se esconde detrás del árbol" });
    expect(nota(html)).toContain("(«se esconde detrás del árbol»)");
    expect(nota(html)).toContain("todavía no lo hacemos: por ahora se pierde en la sombra del lugar");
  });

  it("sin relación contada, la nota va igual sin la cita", async () => {
    expect(nota(await render({ a_medio_ver: "mucho", relacion: "" }))).toMatch(/^Contaste que está escondido\. /);
  });

  it("en la niebla, sin decir nada o sin tanda, no hay nota", async () => {
    for (const html of [
      await render({ a_medio_ver: "poco", relacion: "se pierde en la niebla" }),
      await render({ a_medio_ver: "no", relacion: "" }),
      await render(null),
      await render({ a_medio_ver: "mucho", relacion: "" }, []),
    ]) {
      expect(html).not.toContain("data-a-medio-ver");
    }
  });
});
