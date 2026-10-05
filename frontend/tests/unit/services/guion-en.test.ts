import { describe, it, expect } from "vitest";
import { conGuionEn, type Relato } from "../../../src/services/story.service";

function relato(id: string, created_at: string, hasVideoScript: boolean): Relato {
  return { id, created_at, hasVideoScript, story_template_id: "s-1", title: "t", content: "", status: "completed" };
}

// Spec-630 B21: cada versión sin guion sabe en cuál está (la más nueva que lo tenga).
describe("conGuionEn", () => {
  it("apunta a la versión más nueva con guion, con su fecha en hora de Argentina", () => {
    const [nueva, media, vieja] = conGuionEn([
      relato("r-3", "2026-10-02T14:47:20.000Z", false),
      relato("r-2", "2026-09-30T10:53:00.000Z", true),
      relato("r-1", "2026-09-30T04:43:00.000Z", true),
    ]);
    expect(nueva.guionEn).toEqual({ id: "r-2", fecha: "30/09/2026 07:53" });
    expect(media.guionEn).toBeNull();
    expect(vieja.guionEn).toBeNull();
  });

  it("si ninguna tiene guion, nadie apunta a otra", () => {
    const relatos = conGuionEn([relato("r-1", "2026-10-01T00:00:00.000Z", false)]);
    expect(relatos[0].guionEn).toBeNull();
  });
});
