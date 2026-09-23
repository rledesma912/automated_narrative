import { test, expect, type Page } from "@playwright/test";

/**
 * Sala de generación sobre jobs (Spec-460 S4).
 *
 * Corre contra el arnés de playwright.config.ts: Core con DB descartable y LLM
 * mock con demora (~0.15 s por llamada, 17 llamadas por historia).
 * Usa "La ofrenda" del seed; los tests de relatos usan otra historia.
 */
const STORY_ID = "314a7ca8-2695-470f-af34-b8b913f56528";

test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Genera historias: solo contra el arnés con DB descartable");

function countJobPosts(page: Page): () => number {
  let posts = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes(`/stories/${STORY_ID}/jobs`)) posts++;
  });
  return () => posts;
}

async function activeJob(page: Page): Promise<{ job_id: string } | null> {
  const resp = await page.request.get(`/api/v1/stories/${STORY_ID}/jobs/active`);
  return resp.ok() ? resp.json() : null;
}

async function logLines(page: Page): Promise<string[]> {
  return page.locator("#log-container > div").allTextContents();
}

test("regenerar desde la ficha: confirmación, avance por etapas y fin", async ({ page }) => {
  const posts = countJobPosts(page);
  await page.goto(`/historia/${STORY_ID}`);
  await page.getByRole("button", { name: "Regenerar" }).click();

  await expect(page).toHaveURL(/regenerate=1/);
  await page.getByRole("button", { name: "Iniciar regeneración" }).click();

  await expect(page.locator("#status-line")).toHaveText("Historia generada con éxito", {
    timeout: 30_000,
  });
  await expect(page.locator("#badge-text")).toHaveText("COMPLETO");
  expect(posts()).toBe(1);

  const lines = await logLines(page);
  const idx = (text: string) => lines.findIndex((l) => l.includes(text));
  expect(idx("Mapeando acto 1 de 5")).toBeGreaterThan(-1);
  // Cada acto: sus etapas y después "completado" (antes "Narrando Beat N" llegaba tarde).
  expect(idx("Mapeando acto 1 de 5")).toBeLessThan(idx("Beat 1 completado"));
  expect(idx("Actualizando la memoria del acto 1")).toBeLessThan(idx("Beat 1 completado"));
  expect(idx("Consolidando el relato")).toBeGreaterThan(idx("Beat 5 completado"));
  expect(lines.some((l) => l.includes("Narrando Beat"))).toBe(false);
});

test("recargar a mitad de camino se ata al mismo job sin lanzar otro", async ({ page }) => {
  const posts = countJobPosts(page);
  await page.goto(`/generar/stream/${STORY_ID}?regenerate=1`);
  await page.getByRole("button", { name: "Iniciar regeneración" }).click();
  await expect(page.locator("#log-container")).toContainText("Narrando acto 2 de 5", {
    timeout: 15_000,
  });
  const before = await activeJob(page);
  expect(before).not.toBeNull();

  await page.reload();

  // La sala se ata sola: sin panel de inicio, con el mismo job.
  await expect(page.locator("#start-panel")).toBeHidden();
  expect(await page.evaluate(() => (window as unknown as { ACTIVE_JOB_ID: string }).ACTIVE_JOB_ID)).toBe(
    before!.job_id,
  );
  await expect(page.locator("#status-line")).toHaveText("Historia generada con éxito", {
    timeout: 30_000,
  });
  expect(posts()).toBe(1);
});

test("cancelar detiene el job en el servidor", async ({ page }) => {
  await page.goto(`/generar/stream/${STORY_ID}?regenerate=1`);
  await page.getByRole("button", { name: "Iniciar regeneración" }).click();
  await expect(page.locator("#log-container")).toContainText("Narrando acto 1 de 5", {
    timeout: 15_000,
  });
  const job = await activeJob(page);
  expect(job).not.toBeNull();

  await page.getByRole("button", { name: "Cancelar generación" }).click();

  await expect(page.locator("#badge-text")).toHaveText("CANCELADA");
  await expect(page.locator("#error-msg")).toContainText("cancelada");
  const cancelled = await (await page.request.get(`/api/v1/jobs/${job!.job_id}`)).json();
  expect(cancelled.status).toBe("failed");
  expect(cancelled.error).toBe("cancelada por el usuario");

  // Si el pipeline siguiera vivo, en 2 s avanzaría varios actos y pisaría el estado.
  await page.waitForTimeout(2_000);
  const later = await (await page.request.get(`/api/v1/jobs/${job!.job_id}`)).json();
  expect(later.beat).toBe(cancelled.beat);
  const story = await (await page.request.get(`/api/v1/stories/${STORY_ID}`)).json();
  expect(story.status).toBe("failed");
});

test("generar desde la ficha lanza el job en el servidor y la sala se ata", async ({ page }) => {
  const posts = countJobPosts(page); // el POST lo hace Express, no el browser
  await page.goto(`/historia/${STORY_ID}`); // quedó `failed` en el test anterior

  await page.locator("form[action$='/generar'] button").first().click();

  await expect(page).toHaveURL(new RegExp(`/generar/stream/${STORY_ID}$`));
  await expect(page.locator("#start-panel")).toBeHidden();
  await expect(page.locator("#status-line")).toHaveText("Historia generada con éxito", {
    timeout: 30_000,
  });
  expect(posts()).toBe(0);
  expect(await activeJob(page)).toBeNull();
});
