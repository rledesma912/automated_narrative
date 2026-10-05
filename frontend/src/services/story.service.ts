import axios from "axios";
import { fechaVersion } from "../utils/fechas";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

export interface Story {
  id: string;
  title: string;
  status: string;
  /** Spec-560 A2: actos escritos con la versión anterior de un acto previo. */
  stale_acts?: number[];
  created_at: string;
  atmosfera?: string;
  protagonista?: string;
  relator?: string;
  sinopsis?: string;
}

export interface ActRepetition {
  number: number;
  repeated: string[];
  cliches: string[];
  invented_names?: string[];
  /** Spec-590 F: oraciones cortadas (hasta 3 ejemplos, total y %) y diálogo directo. */
  cut_sentences?: string[];
  cut_count?: number;
  cut_pct?: number;
  too_cut?: boolean;
  dialogue?: number;
}

export interface Relato {
  id: string;
  story_template_id: string;
  title: string;
  content: string;
  status: string;
  created_at: string;
  /** Spec-530 §8.3: frases repetidas entre actos y clichés (null si el Core no respondió). */
  repetition?: { acts: ActRepetition[] } | null;
  /** Spec-610: si la variante ya tiene su paquete para el video. */
  hasVideoScript?: boolean;
  /** Spec-630 B21: sin guion propio, la versión más nueva que sí lo tiene. */
  guionEn?: { id: string; fecha: string } | null;
}

async function withRepetition(relato: Relato): Promise<Relato> {
  const [repetition, script] = await Promise.all([
    axios
      .get<{ acts: ActRepetition[] }>(`${CORE_API_URL}/api/v1/generated-narratives/${relato.id}/repetition`, {
        timeout: 3000,
      })
      .then((r) => r.data)
      .catch(() => null),
    getVideoScript(relato.id),
  ]);
  return { ...relato, repetition, hasVideoScript: script !== null };
}

/**
 * Spec-630 B21: el guion es de una versión. A cada versión sin guion le dice en
 * cuál está (la más nueva que lo tenga), para no armar otro sin saberlo.
 */
export function conGuionEn(relatos: Relato[]): Relato[] {
  const conGuion = relatos
    .filter((r) => r.hasVideoScript)
    .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
  return relatos.map((r) => ({
    ...r,
    guionEn: !r.hasVideoScript && conGuion ? { id: conGuion.id, fecha: fechaVersion(conGuion.created_at) } : null,
  }));
}

export const getStoryById = async (storyId: string): Promise<Story | null> => {
  try {
    const response = await axios.get<Story>(
      `${CORE_API_URL}/api/v1/stories/${storyId}`,
      { timeout: 5000 }
    );
    return response.data;
  } catch (error) {
    console.error(`Error fetching story ${storyId}:`, error);
    return null;
  }
};

export const getRelatosForStory = async (storyId: string): Promise<Relato[]> => {
  try {
    const response = await axios.get<Relato[]>(
      `${CORE_API_URL}/api/v1/story-templates/${storyId}/narratives`,
      { timeout: 5000 }
    );
    return conGuionEn(await Promise.all(response.data.map(withRepetition)));
  } catch (error) {
    console.error(`Error fetching narratives for story ${storyId}:`, error);
    return [];
  }
};

/** Resultado de lanzar la regeneración de un acto (Spec-460 S7: es un job). */
export interface ActoRegenerationStart {
  status: number; // 202 lanzado · 409 ya hay un job · 404/422 inválido
  jobId: string | null;
  detail: string | null;
}

/** Lanza la re-narración de la Voz de un acto como job y responde al instante. */
export const startActoRegeneration = async (
  storyId: string,
  narrativeId: string,
  actoNumero: number
): Promise<ActoRegenerationStart> => {
  const response = await axios.post(
    `${CORE_API_URL}/api/v1/stories/${storyId}/jobs`,
    { kind: "regenerate_voz", beat: actoNumero, narrative_id: narrativeId },
    { timeout: 5000, validateStatus: (s) => [202, 404, 409, 422].includes(s) }
  );
  const detail = response.data?.detail;
  return {
    status: response.status,
    jobId: response.data?.job_id ?? null,
    detail: typeof detail === "string" ? detail : null,
  };
};

/** Spec-610: ritmo de lectura y largo del episodio (`config/video/lectura.yaml`). */
export interface ReadingSettings {
  palabras_por_minuto: number;
  episodio_minutos: { desde: number; hasta: number };
}

const DEFAULT_READING: ReadingSettings = { palabras_por_minuto: 150, episodio_minutos: { desde: 12, hasta: 17 } };

export const getReadingSettings = async (): Promise<ReadingSettings> => {
  try {
    const resp = await axios.get<ReadingSettings>(`${CORE_API_URL}/api/v1/video/lectura`, { timeout: 3000 });
    return resp.data;
  } catch {
    return DEFAULT_READING;
  }
};

/** Spec-610: el paquete para el video de una variante (null si todavía no se armó). */
export interface VideoScript {
  id: string;
  narrative_id: string;
  narra: "mujer" | "hombre" | "no_se_sabe";
  lector: string | null;
  bloques: Array<{
    acto: number;
    desde: number;
    hasta: number;
    indicacion: string;
    pausa: "ninguna" | "corta" | "larga";
    marcas: Array<{ desde_palabra: number; hasta_palabra: number; texto: string }>;
  }>;
  momentos: Array<{
    acto: number;
    desde: number;
    hasta: number;
    fuerte: boolean;
    tipo: "imagen" | "animacion" | "video";
    que_se_ve: string;
    lugar: string;
    prompt_imagen: string;
    prompt_movimiento: string;
    transicion: string;
    sonido: string;
  }>;
  calabaza: { intro: string; outro: string };
  parrafos_por_acto: Record<string, number>;
  updated_at: string;
  /** Frente al relato actual (Spec-610 T3.1). */
  estado: { estado: "al_dia" | "cambio_el_texto" | "cambiaron_parrafos"; actos: number[] };
  marcas_perdidas: Array<{ bloque: number; texto: string }>;
  estilo_imagen: string;
  transiciones: string[];
  lectores: string[];
  cierre_fijo: string;
  tipos: Record<string, { nombre: string; se_genera_con: string }>;
}

export async function getVideoScript(narrativeId: string): Promise<VideoScript | null> {
  try {
    const resp = await axios.get<VideoScript>(
      `${CORE_API_URL}/api/v1/generated-narratives/${narrativeId}/video-script`,
      { timeout: 3000 },
    );
    return resp.data;
  } catch {
    return null;
  }
}

