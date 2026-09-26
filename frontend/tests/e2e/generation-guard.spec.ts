import { test, expect, type Page } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Guardar / generar desacoplados + botones en estado ocupado (Spec-460 S6).
 * Arnés de playwright.config.ts (Core con DB descartable + LLM mock con demora).
 */
let OFRENDA = ""; // "La ofrenda" de la semilla
test.beforeAll(async ({ request }) => {
  OFRENDA = await storyIdByTitle(request, "La ofrenda");
});

test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea y genera historias: solo contra el arnés");

let savedStoryId = "";

function countPosts(page: Page, fragment: string): () => number {
  let n = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes(fragment)) n++;
  });
  return () => n;
}

test("una historia guardada desde el asistente queda como borrador y no genera", async ({ page }) => {
  const jobPosts = countPosts(page, "/jobs");
  const created = await page.request.post("/api/v1/authoring/stories", {
    data: { title: "Historia E2E", premise: "Algo pasa en la casa.", protagonist_name: "Irene" },
  });
  expect(created.status()).toBe(201);
  savedStoryId = (await created.json()).story_id;

  await page.goto("/galeria");
  const card = page.locator(`[data-story-card="${savedStoryId}"]`);
  await expect(card).toContainText("Borrador");
  expect(jobPosts()).toBe(0); // guardar no genera
  const story = await (await page.request.get(`/api/v1/stories/${savedStoryId}`)).json();
  expect(story.status).toBe("draft");
});

test("doble click en «Generar» de la galería envía un solo pedido", async ({ page }) => {
  const posts = countPosts(page, `/historia/${savedStoryId}/generar`);
  await page.goto("/galeria");
  const button = page.locator(`[data-story-card="${savedStoryId}"] [data-generation-trigger]`);

  await button.dblclick();

  await expect(page).toHaveURL(new RegExp(`/generar/stream/${savedStoryId}$`));
  expect(posts()).toBe(1);
  await expect(page.locator("#status-line")).toHaveText("Historia generada con éxito", {
    timeout: 30_000,
  });
});

test("la galería se actualiza sola mientras se genera", async ({ page }) => {
  await page.goto("/galeria");
  await expect(page.locator("#core-status-dot")).toHaveClass(/bg-forge-success/);
  await page.evaluate(() => ((window as unknown as { __sinRecargar: boolean }).__sinRecargar = true));
  const card = page.locator(`[data-story-card="${OFRENDA}"]`);
  await expect(card).toContainText("Completada");

  const resp = await page.request.post(`/api/v1/stories/${OFRENDA}/jobs`, {
    data: { kind: "full_generation" },
  });
  expect(resp.status()).toBe(202);

  await expect(card).toContainText("Generando", { timeout: 3_000 });
  await expect(card.locator(`[data-job-progress="${OFRENDA}"]`)).toContainText(/Acto \d de 5/, {
    timeout: 5_000,
  });
  await expect(card).toContainText("Completada", { timeout: 30_000 });
  // Todo sin recargar la página.
  expect(
    await page.evaluate(() => (window as unknown as { __sinRecargar?: boolean }).__sinRecargar),
  ).toBe(true);
});

test("volver atrás desde la confirmación no deja el botón trabado", async ({ page }) => {
  await page.goto(`/historia/${OFRENDA}`);
  const regenerar = page.locator("form[action$='/generar'] [data-generation-trigger]");

  await regenerar.click();
  await expect(page).toHaveURL(/regenerate=1/);
  await page.goBack();

  await expect(page).toHaveURL(new RegExp(`/historia/${OFRENDA}$`));
  await expect(regenerar).toBeEnabled();
  await expect(regenerar).not.toHaveAttribute("aria-busy", "true");
  await expect(regenerar).toContainText("Regenerar");
});
