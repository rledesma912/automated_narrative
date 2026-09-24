import axios from "axios";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

export interface CoreHealthStatus {
  reachable: boolean;
  status?: string;
  provider?: string;
  active_profile?: string;
  checks?: Record<string, string>;
  error?: string;
}

export async function checkCoreHealth(): Promise<CoreHealthStatus> {
  try {
    const response = await axios.get(`${CORE_API_URL}/api/v1/health`, { timeout: 3000 });
    return {
      reachable: true,
      status:         response.data?.status,
      provider:       response.data?.checks?.provider,
      active_profile: response.data?.active_profile,
      checks:         response.data?.checks,
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return { reachable: false, error: message };
  }
}

export async function createStory(
  payload: Record<string, unknown>,
  action: string = "generate",
): Promise<{ id: string }> {
  const response = await axios.post(
    `${CORE_API_URL}/api/v1/stories?action=${encodeURIComponent(action)}`,
    payload,
    { timeout: 5000 },
  );
  return response.data;
}

export async function deleteStory(storyId: string): Promise<void> {
  await axios.delete(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
}

export async function updateStory(
  storyId: string,
  payload: Record<string, unknown>,
): Promise<{ id: string }> {
  const response = await axios.patch(
    `${CORE_API_URL}/api/v1/stories/${storyId}`,
    payload,
    { timeout: 5000 },
  );
  return response.data;
}

export interface GeneratedNarrative {
  id: string;
  story_template_id: string;
  title: string;
  content: string;
  status: string;
  created_at: string;
}

export async function generateNarrative(
  storyTemplateId: string,
  title: string,
): Promise<GeneratedNarrative> {
  const response = await axios.post(
    `${CORE_API_URL}/api/v1/story-templates/${storyTemplateId}/generate-narrative?title=${encodeURIComponent(title)}`,
    {},
    { timeout: 30000 },
  );
  return response.data;
}

export async function listNarratives(storyTemplateId: string): Promise<GeneratedNarrative[]> {
  const response = await axios.get(
    `${CORE_API_URL}/api/v1/story-templates/${storyTemplateId}/narratives`,
    { timeout: 5000 },
  );
  return response.data;
}

export async function getNarrativeText(narrativeId: string): Promise<{ text: string }> {
  const response = await axios.get(
    `${CORE_API_URL}/api/v1/generated-narratives/${narrativeId}/text`,
    { timeout: 5000 },
  );
  return response.data;
}

export async function deleteNarrative(narrativeId: string): Promise<void> {
  await axios.delete(
    `${CORE_API_URL}/api/v1/generated-narratives/${narrativeId}`,
    { timeout: 5000 },
  );
}

// ── Jobs de generación (Spec-460) ───────────────────────────────────────────

export interface CoreJob {
  job_id: string;
  story_id: string;
  kind: string;
  status: string;
  stage: string | null;
  beat: number | null;
  total_beats: number | null;
  error: string | null;
  narrative_id: string | null;
}

/**
 * Lanza la generación completa de una historia. Si ya hay una en curso (409),
 * devuelve ese job en vez de fallar: el llamador redirige a su sala.
 */
export async function startGeneration(
  storyId: string,
): Promise<{ jobId: string; alreadyRunning: boolean }> {
  const response = await axios.post(
    `${CORE_API_URL}/api/v1/stories/${storyId}/jobs`,
    { kind: "full_generation" },
    { timeout: 5000, validateStatus: (s) => s === 202 || s === 409 },
  );
  return { jobId: response.data.job_id, alreadyRunning: response.status === 409 };
}

/** Job en curso de la historia, o null si no hay. */
export async function getActiveJob(storyId: string): Promise<CoreJob | null> {
  try {
    const response = await axios.get(
      `${CORE_API_URL}/api/v1/stories/${storyId}/jobs/active`,
      { timeout: 5000 },
    );
    return response.data;
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 404) return null;
    throw err;
  }
}

// ── Spec-510: duración estimada de los jobs ──────────────────────────────────

export interface JobEstimate {
  seconds: number;
  source: "history" | "default";
  samples: number;
}

export type JobEstimates = Record<"full_generation" | "regenerate_voz", JobEstimate>;

export async function getJobEstimates(timeoutMs = 1500): Promise<JobEstimates> {
  const response = await axios.get(`${CORE_API_URL}/api/v1/jobs/estimates`, {
    timeout: timeoutMs,
  });
  return response.data;
}
