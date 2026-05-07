import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";

const viewPath = path.join(process.cwd(), "src/views/gallery.ejs");

describe("gallery view", () => {
  it("exposes a delete story CTA for completed stories", async () => {
    const html = await ejs.renderFile(viewPath, {
      stories: [
        {
          id: "story-1",
          title: "La casa",
          status: "completed",
          created_at: "2026-05-05T10:00:00.000Z",
          atmosfera: "terror",
        },
      ],
    });

    expect(html).toContain('hx-get="/modales/confirmar-borrar/story-1"');
    expect(html).toContain('hx-target="#modal-slot"');
    expect(html).toContain("Eliminar");
    expect(html).toContain('id="modal-slot"');
    expect(html).toContain("Ver Relato");
  });
});
