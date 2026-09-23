/** Spec-440 T3.1: catálogo de géneros con caché y Core caído. */
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("axios", () => ({ default: { get: vi.fn() } }));

import axios from "axios";
import {
  getGenreCatalog,
  clearGenreCatalogCache,
  subgenresOf,
} from "../../../src/services/catalog.service";

const get = axios.get as unknown as ReturnType<typeof vi.fn>;
const CATALOG = [
  { id: "body_horror", label: "Horror Corporal", subgenres: [{ id: "contagio", label: "Contagio" }] },
];

describe("getGenreCatalog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    clearGenreCatalogCache();
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  it("pide el catálogo al Core una vez y lo cachea", async () => {
    get.mockResolvedValue({ data: CATALOG });

    expect(await getGenreCatalog()).toEqual(CATALOG);
    expect(await getGenreCatalog()).toEqual(CATALOG);
    expect(get).toHaveBeenCalledTimes(1);
    expect(get.mock.calls[0][0]).toMatch(/\/api\/v1\/catalog\/genres$/);
  });

  it("vuelve a pedirlo cuando vence el TTL de 5 minutos", async () => {
    vi.useFakeTimers();
    get.mockResolvedValue({ data: CATALOG });
    await getGenreCatalog();

    vi.advanceTimersByTime(5 * 60 * 1000 + 1);
    await getGenreCatalog();

    expect(get).toHaveBeenCalledTimes(2);
  });

  it("Core caído sin copia previa → null, y no cachea el fallo", async () => {
    get.mockRejectedValueOnce(new Error("ECONNREFUSED"));
    expect(await getGenreCatalog()).toBeNull();

    get.mockResolvedValueOnce({ data: CATALOG });
    expect(await getGenreCatalog()).toEqual(CATALOG);
  });

  it("Core caído con copia vencida → devuelve la última copia", async () => {
    vi.useFakeTimers();
    get.mockResolvedValueOnce({ data: CATALOG });
    await getGenreCatalog();
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);

    get.mockRejectedValueOnce(new Error("ECONNREFUSED"));
    expect(await getGenreCatalog()).toEqual(CATALOG);
  });
});

describe("subgenresOf", () => {
  it("subgéneros del género, o [] si no existe", () => {
    expect(subgenresOf(CATALOG, "body_horror").map((s) => s.id)).toEqual(["contagio"]);
    expect(subgenresOf(CATALOG, "nada")).toEqual([]);
  });
});
