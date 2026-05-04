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

export async function updateFilePath(storyId: string, filePath: string | null): Promise<void> {
  await axios.patch(
    `${CORE_API_URL}/api/v1/stories/${storyId}/file-path`,
    { file_path: filePath },
    { timeout: 5000 },
  );
}
