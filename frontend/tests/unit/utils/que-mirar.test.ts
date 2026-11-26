import { describe, it, expect } from "vitest";
import { queMirarHtml } from "../../../src/utils/que_mirar";

/** Spec-795 D4: «Qué mirar» sin motor de Markdown. */
describe("queMirarHtml", () => {
  it("párrafos, listas y negritas", () => {
    expect(queMirarHtml("Elegí una.\n\n- **A** más oscura\n- B")).toBe(
      "<p>Elegí una.</p><ul><li><strong>A</strong> más oscura</li><li>B</li></ul>"
    );
  });

  it("un salto simple queda dentro del párrafo", () => {
    expect(queMirarHtml("uno\ndos")).toBe("<p>uno<br>dos</p>");
  });

  it("escapa todo antes: nada de HTML de afuera", () => {
    expect(queMirarHtml('<script>alert(1)</script> **<b>x</b>**')).toBe(
      "<p>&lt;script&gt;alert(1)&lt;/script&gt; <strong>&lt;b&gt;x&lt;/b&gt;</strong></p>"
    );
  });

  it("vacío o sin texto: nada", () => {
    expect(queMirarHtml("")).toBe("");
    expect(queMirarHtml(undefined)).toBe("");
  });
});
