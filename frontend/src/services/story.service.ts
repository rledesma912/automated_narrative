import axios from "axios";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

export interface Story {
  id: string;
  title: string;
  status: string;
  created_at: string;
  atmosfera?: string;
  protagonista?: string;
  relator?: string;
  sinopsis?: string;
}

export interface Relato {
  id: string;
  story_template_id: string;
  title: string;
  content: string;
  status: string;
  created_at: string;
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
    return response.data;
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
