import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/** Spec-670 D8: un criterio «No va en tu historia» se dibuja (sin romper la página) con su motivo. */
const VIEWS = path.join(process.cwd(), "src/views");
const state = JSON.parse(fs.readFileSync(path.join(process.cwd(), "tests/fixtures/asistente/estado.json"), "utf8"));

describe("Preguntas con un criterio que no va", () => {
  it("muestra el chip y el motivo, y se puede reabrir", async () => {
    const items = [
      ...state.workshop.items.filter((i: { criterion: string }) => i.criterion !== "transgresion"),
      { criterion: "transgresion", status: "no_aplica", question: "Nadie provoca a la criatura.", answer: "", options: [], nombre: "Lo que Tito no tendría que haber hecho", por_que: "…" },
    ];
    const html = await ejs.renderFile(path.join(VIEWS, "asistente", "_taller_contenido.ejs"), {
      state: { ...state, workshop: { ...state.workshop, items } },
      estimateLabels: {},
    });
    const li = html.match(/<li[^>]*data-pregunta="transgresion"[\s\S]*?<\/li>/)![0];
    expect(li).toContain("No va en tu historia");
    expect(li).toContain("La IA no te lo pregunta: Nadie provoca a la criatura.");
    expect(li).toContain('data-taller="reopen"');
  });
});
