import { describe, it, expect } from "vitest";
import path from "path";

/** Spec-630 B17: una página con otra versión de los estáticos se carga entera. */
// eslint-disable-next-line @typescript-eslint/no-require-imports
const v = require(path.join(process.cwd(), "public/js/version-check.js"));

const pagina = (version: string) =>
  `<!doctype html><html><head><meta name="asset-version" content="${version}"></head><body></body></html>`;

describe("version-check", () => {
  it("lee la versión de una página completa; un fragmento no trae", () => {
    expect(v.versionIn(pagina("abc"))).toBe("abc");
    expect(v.versionIn('<section data-acto="1">…</section>')).toBeNull();
    expect(v.versionIn(undefined)).toBeNull();
  });

  it("pide carga completa solo si llega una página con otra versión", () => {
    expect(v.needsFullLoad("abc", pagina("abd"))).toBe(true);
    expect(v.needsFullLoad("abc", pagina("abc"))).toBe(false);
    expect(v.needsFullLoad("abc", "<div>fragmento</div>")).toBe(false);
    expect(v.needsFullLoad("", pagina("abd"))).toBe(false); // sin versión cargada: no se toca
  });
});
