import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";

const viewPath = path.join(process.cwd(), "src/views/relatos.ejs");

describe("relatos view", () => {
  it("renders a top switcher for multiple generated narratives", async () => {
    const html = await ejs.renderFile(viewPath, {
      story: { title: "La casa" },
      relatos: [
        {
          id: "r-1",
          title: "Primera versión",
          content: "Texto 1",
          created_at: "2026-05-05T10:00:00.000Z",
        },
        {
          id: "r-2",
          title: "Segunda versión",
          content: "Texto 2",
          created_at: "2026-05-05T11:00:00.000Z",
        },
      ],
    });

    expect(html).toContain("data-relato-tab=\"r-1\"");
    expect(html).toContain("data-relato-tab=\"r-2\"");
    expect(html).toContain("data-relato-panel=\"r-1\"");
    expect(html).toContain("data-relato-panel=\"r-2\"");
    expect(html).toContain("Copiar Relato");
    expect(html).toContain("Primera versión");
    expect(html).toContain("Segunda versión");
  });

  it("renders an explicit empty state when there are no narratives", async () => {
    const html = await ejs.renderFile(viewPath, {
      story: { title: "La casa" },
      relatos: [],
    });

    expect(html).toContain("No hay relatos generados aún para esta historia.");
    expect(html).not.toContain("data-relato-tab=");
  });
});
