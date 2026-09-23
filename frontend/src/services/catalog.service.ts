import axios from "axios";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";
const TTL_MS = 5 * 60 * 1000;

export interface CatalogOption {
  id: string;
  label: string;
}

export interface CatalogGenre extends CatalogOption {
  subgenres: CatalogOption[];
}

let cache: { genres: CatalogGenre[]; at: number } | null = null;

/**
 * Catálogo de géneros del Core (Spec-440 §2), con caché en memoria de 5 min.
 * Core caído → la última copia si la hay; si no, `null` (el wizard se renderiza
 * igual, con los combos deshabilitados).
 * Los fallos no se cachean: el próximo pedido vuelve a intentar.
 */
export async function getGenreCatalog(): Promise<CatalogGenre[] | null> {
  if (cache && Date.now() - cache.at < TTL_MS) return cache.genres;
  try {
    const resp = await axios.get<CatalogGenre[]>(`${CORE_API_URL}/api/v1/catalog/genres`, {
      timeout: 3000,
    });
    cache = { genres: resp.data, at: Date.now() };
    return resp.data;
  } catch (err: unknown) {
    console.error("No se pudo leer el catálogo de géneros:", err instanceof Error ? err.message : err);
    return cache?.genres ?? null;
  }
}

export function clearGenreCatalogCache(): void {
  cache = null;
}

/** Subgéneros de un género del catálogo ([] si el género no existe). */
export function subgenresOf(catalog: CatalogGenre[], genreId: string): CatalogOption[] {
  return catalog.find((g) => g.id === genreId)?.subgenres ?? [];
}
