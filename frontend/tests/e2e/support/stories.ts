import type { APIRequestContext } from "@playwright/test";

/**
 * ID de una historia de la semilla por título (Spec-440 T2.6): la DB del arnés
 * se crea en cada corrida desde input_stories/, así que los IDs no son fijos.
 */
export async function storyIdByTitle(request: APIRequestContext, title: string): Promise<string> {
  const resp = await request.get("/api/v1/stories");
  const stories = (await resp.json()) as Array<{ id: string; title: string }>;
  const story = stories.find((s) => s.title === title);
  if (!story) throw new Error(`No está en la semilla E2E: «${title}»`);
  return story.id;
}
