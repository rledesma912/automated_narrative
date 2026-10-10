import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/** Spec-670 (S5): «Preguntas» con grupos, lo que no va, la forma mal elegida y las respuestas guardadas. */
const VIEWS = path.join(process.cwd(), "src/views");
const state = JSON.parse(fs.readFileSync(path.join(process.cwd(), "tests/fixtures/asistente/estado.json"), "utf8"));

const render = (workshop: Record<string, unknown>) =>
  ejs.renderFile(path.join(VIEWS, "asistente", "_taller_contenido.ejs"), {
    state: { ...state, workshop: { ...state.workshop, ...workshop } },
    estimateLabels: {},
  });

const NO_VA = {
  criterion: "transgresion",
  status: "no_aplica",
  question: "Nadie provoca a la criatura.",
  answer: "",
  options: [],
  nombre: "Lo que Tito no tendría que haber hecho",
  por_que: "…",
  grupo: "forma",
};
const items = () => [...state.workshop.items.filter((i: { criterion: string }) => i.criterion !== "transgresion"), NO_VA];

describe("Preguntas (Spec-670)", () => {
  it("lo que no va: chip tachado, motivo y «Preguntármelo igual» (D8, D12)", async () => {
    const html = await render({ items: items() });
    const li = html.match(/<li[^>]*data-pregunta="transgresion"[^>]*data-no-va[\s\S]*?<\/li>/)![0];
    expect(li).toContain("No va en tu historia");
    expect(li).toContain("Nadie provoca a la criatura.");
    expect(li).toMatch(/data-taller="reopen">Preguntármelo igual</);
    expect(html).toContain("No van en tu historia");
  });

  it("los chips van por grupo: de toda historia, de la forma y del giro", async () => {
    const html = await render({
      items: items(),
      molde: { form: "regla", form_name: "Alguien rompe una regla", ingredient: "", ingredient_name: "" },
    });
    expect(html).toContain("De toda historia");
    expect(html).toContain("De «Alguien rompe una regla»");
    expect(html).toContain("Son 10 como mucho y ninguna es obligatoria.");
  });

  it("forma mal elegida: aviso con el link a «Tu idea»", async () => {
    const html = await render({ finish: { kind: "mal_elegida", text: "Parece que tu historia no es de esta clase." } });
    expect(html).toMatch(/nota-forge--warning" data-fin="mal_elegida"/);
    expect(html).toContain(`href="/asistente/${state.story_id}/direccion#forma"`);
  });

  it("avisa las respuestas guardadas de otra forma (D2)", async () => {
    expect(await render({ hidden_answers: 2 })).toContain("Tenés 2 respuestas de otra clase de historia");
    expect(await render({ hidden_answers: 0 })).not.toContain("data-guardadas");
  });
});
