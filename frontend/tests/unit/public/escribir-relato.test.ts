import { describe, it, expect, vi } from "vitest";
import path from "path";

/** Spec-660 T2.1: «Escribir el relato» confirma donde se toca y va a la sala. */
// eslint-disable-next-line @typescript-eslint/no-require-imports
const escribir = require(path.join(process.cwd(), "public/js/escribir-relato.js"));

const boton = (dataset: Record<string, string> = {}) => ({ dataset: { storyId: "s-1", ...dataset } });

function deps(over: Record<string, unknown> = {}) {
  const orden: string[] = [];
  const d = {
    orden,
    confirm: vi.fn(async () => true),
    before: vi.fn(async () => void orden.push("guardar")),
    fetch: vi.fn(async () => {
      orden.push("post");
      return { status: 202, json: async () => ({ job_id: "j-1" }) };
    }),
    go: vi.fn(),
    busy: vi.fn(),
    restore: vi.fn(),
    error: vi.fn(),
    clearError: vi.fn(),
    ...over,
  };
  return d;
}

const respuesta = (status: number, body: unknown) => async () => ({ status, json: async () => body });

describe("escribir-relato", () => {
  it("cancelar el diálogo no crea nada", async () => {
    const d = deps({ confirm: vi.fn(async () => false) });
    expect(await escribir.run(boton(), d)).toBe("cancelado");
    expect(d.fetch).not.toHaveBeenCalled();
    expect(d.busy).not.toHaveBeenCalled();
    expect(d.go).not.toHaveBeenCalled();
  });

  it("aceptar guarda lo pendiente, crea el job y va a la sala", async () => {
    const d = deps();
    expect(await escribir.run(boton(), d)).toBe("sala");
    expect(d.orden).toEqual(["guardar", "post"]);
    expect(d.busy).toHaveBeenCalled();
    expect(d.fetch).toHaveBeenCalledWith("/api/v1/stories/s-1/jobs", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(d.fetch.mock.calls[0][1].body)).toEqual({ kind: "full_generation" });
    expect(d.go).toHaveBeenCalledWith("/generar/stream/s-1");
  });

  it("si ya hay un relato escribiéndose (409), va a la sala de ese", async () => {
    const d = deps({ fetch: vi.fn(respuesta(409, { job_id: "j-viejo", detail: "ya hay uno" })) });
    expect(await escribir.run(boton(), d)).toBe("sala");
    expect(d.go).toHaveBeenCalledWith("/generar/stream/s-1");
  });

  it("si falla, avisa al lado del botón, lo deja listo y no navega", async () => {
    for (const [fetch, mensaje] of [
      [vi.fn(respuesta(422, { detail: "La historia todavía no tiene actos." })), "La historia todavía no tiene actos."],
      [vi.fn(respuesta(503, {})), "No se pudo arrancar. Probá de nuevo en un rato."],
      [vi.fn(async () => Promise.reject(new Error("red"))), "No se pudo arrancar: no hay conexión. Probá de nuevo."],
    ] as const) {
      const d = deps({ fetch });
      const b = boton();
      expect(await escribir.run(b, d)).toBe("error");
      expect(d.go).not.toHaveBeenCalled();
      expect(d.restore).toHaveBeenCalledWith(b);
      expect(d.error).toHaveBeenCalledWith(b, mensaje);
      expect(b.dataset).not.toHaveProperty("pending");
    }
  });

  it("un botón ocupado no vuelve a preguntar", async () => {
    const d = deps();
    expect(await escribir.run(boton({ busy: "1" }), d)).toBe("ocupado");
    expect(await escribir.run(boton({ pending: "1" }), d)).toBe("ocupado");
    expect(d.confirm).not.toHaveBeenCalled();
  });

  it("fuera del asistente (sin nada que guardar) igual arranca", async () => {
    const d = deps({ before: undefined });
    expect(await escribir.run(boton(), d)).toBe("sala");
  });

  it("el diálogo: pluma, tiempo estimado y la nota solo para una versión nueva", () => {
    const primera = escribir.textos({ estimado: "≈ 2 min" });
    expect(primera).toMatchObject({
      icon: "escribir",
      title: "¿Escribimos el relato?",
      message: "Tarda ≈ 2 min. Podés cerrar la pestaña: la IA sigue escribiendo.",
      confirmLabel: "Escribir el relato",
    });
    expect(primera.note).toBeUndefined();

    const nueva = escribir.textos({ versionNueva: "" });
    expect(nueva.title).toBe("¿Regeneramos la historia?");
    expect(nueva.message).toBe("Podés cerrar la pestaña: la IA sigue escribiendo.");
    expect(nueva.note).toContain("Las que ya tenés quedan en «El relato»");
    expect(nueva.confirmLabel).toBe("Regenerar historia");
  });
});
