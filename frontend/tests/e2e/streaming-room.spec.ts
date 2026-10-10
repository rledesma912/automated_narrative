import { test, expect, type Page } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Sala de generación sobre jobs (Spec-460 S4).
 *
 * Corre contra el arnés de playwright.config.ts: Core con DB descartable y LLM
 * mock con demora (~0.15 s por llamada, 17 llamadas por historia).
 * Usa "La ofrenda" del seed; los tests de relatos usan otra historia.
 */
let STORY_ID = ""; // "La ofrenda" de la semilla
test.beforeAll(async ({ request }) => {
  STORY_ID = await storyIdByTitle(request, "La ofrenda");
});

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

// Spec-630 B12: sin ficha; se regenera desde la sala en modo lectura.
test("regenerar desde la sala: confirmación, avance por etapas y fin", async ({ page }) => {
  const posts = countJobPosts(page);
  await page.goto(`/generar/stream/${STORY_ID}`);
  // Spec-660 B1: pregunta en la misma página y la sala arranca ya escribiendo.
  await page.getByRole("button", { name: "Regenerar historia" }).click();
  await page.locator("#forge-confirm").getByRole("button", { name: "Regenerar historia" }).click();
  await expect(page).toHaveURL(new RegExp(`/generar/stream/${STORY_ID}$`));

  await expect(page.locator("#status-line")).toHaveText("Tu relato está listo", {
    timeout: 30_000,
  });
  await expect(page.locator("#badge-text")).toHaveText("Completo");
  expect(posts()).toBe(1);
  // Spec-510: al terminar, cuánto tardó; el restante ya no se muestra.
  await expect(page.locator("[data-done-duration]")).toHaveText(/^Lista en \d+ s$/);
  await expect(page.locator("#eta-line")).toHaveText("");

  const lines = await logLines(page);
  const idx = (text: string) => lines.findIndex((l) => l.includes(text));
  expect(idx("Escribiendo el acto 1 de 5")).toBeGreaterThan(-1);
  // Cada acto: sus etapas y después "completado" (antes "Narrando Beat N" llegaba tarde).
  expect(idx("Escribiendo el acto 1 de 5")).toBeLessThan(idx("Acto 1 escrito"));
  expect(idx("Repasando lo que pasó en el acto 1")).toBeLessThan(idx("Acto 1 escrito"));
  expect(idx("Juntando el relato")).toBeGreaterThan(idx("Acto 5 escrito"));
  expect(lines.some((l) => l.includes("Narrando Beat"))).toBe(false);
});

test("recargar a mitad de camino se ata al mismo job sin lanzar otro", async ({ page }) => {
  const posts = countJobPosts(page);
  await page.goto(`/generar/stream/${STORY_ID}?regenerate=1`);
  await page.getByRole("button", { name: "Regenerar historia" }).click();
  await expect(page.locator("#log-container")).toContainText("Escribiendo el acto 2 de 5", {
    timeout: 15_000,
  });
  const before = await activeJob(page);
  expect(before).not.toBeNull();
  // Spec-510: durante la generación, el tiempo restante.
  await expect(page.locator("#eta-line")).toHaveText(/^(faltan ≈ \d+ min|falta .+|tardando .+)$/);

  await page.reload();

  // La sala se ata sola: sin panel de inicio, con el mismo job.
  await expect(page.locator("#start-panel")).toBeHidden();
  expect(await page.evaluate(() => (window as unknown as { ACTIVE_JOB_ID: string }).ACTIVE_JOB_ID)).toBe(
    before!.job_id,
  );
  await expect(page.locator("#status-line")).toHaveText("Tu relato está listo", {
    timeout: 30_000,
  });
  expect(posts()).toBe(1);
});

test("cancelar detiene el job en el servidor", async ({ page }) => {
  await page.goto(`/generar/stream/${STORY_ID}?regenerate=1`);
  await page.getByRole("button", { name: "Regenerar historia" }).click();
  await expect(page.locator("#log-container")).toContainText("Escribiendo el acto 1 de 5", {
    timeout: 15_000,
  });
  const job = await activeJob(page);
  expect(job).not.toBeNull();

  await page.locator("#cancel-btn").click();

  await expect(page.locator("#badge-text")).toHaveText("Cancelada");
  await expect(page.locator("#error-msg")).toContainText("Cancelaste");
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

test("una historia fallida se regenera con la confirmación y la sala se ata", async ({ page }) => {
  const posts = countJobPosts(page);
  await page.goto(`/generar/stream/${STORY_ID}`); // quedó `failed` en el test anterior

  // Spec-660 D2: ya no hay un POST que lance sin preguntar.
  await expect(page.locator("form[action$='/generar']")).toHaveCount(0);
  await page.getByRole("button", { name: "Regenerar historia" }).click();
  const dialogo = page.locator("#forge-confirm");
  await expect(dialogo.locator("[data-confirm-nota]")).toBeHidden(); // fallida: no hay versión que conservar
  await dialogo.getByRole("button", { name: "Escribir el relato" }).click();

  await expect(page).toHaveURL(new RegExp(`/generar/stream/${STORY_ID}$`));
  await expect(page.locator("#start-panel")).toBeHidden();
  await expect(page.locator("#status-line")).toHaveText("Tu relato está listo", {
    timeout: 30_000,
  });
  expect(posts()).toBe(1);
  expect(await activeJob(page)).toBeNull();
});
