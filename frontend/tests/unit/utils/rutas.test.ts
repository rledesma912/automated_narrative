import { describe, it, expect } from "vitest";
import { editarHref } from "../../../src/utils/rutas";

/** Spec-630 B1: editar una historia siempre abre «Los actos». */
describe("editarHref", () => {
  it("lleva a «Los actos» del asistente", () => {
    expect(editarHref("s-1")).toBe("/asistente/s-1/escaleta");
  });
});
