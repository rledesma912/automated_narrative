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

// Spec-660: un borrador se escribe desde su botón, que pregunta una sola vez.
test("doble click en «Escribir el relato» pregunta una vez y envía un solo pedido", async ({ page }) => {
  const posts = countPosts(page, `/api/v1/stories/${savedStoryId}/jobs`);
  await page.goto(`/generar/stream/${savedStoryId}`);
  const button = page.locator("[data-escribir-relato]");

  await button.dblclick();
  // El segundo clic no acepta ni cierra el diálogo recién abierto: hay que leerlo y aceptar.
  const dialogo = page.locator("#forge-confirm");
  await expect(dialogo).toBeVisible();
  expect(posts()).toBe(0);
  await dialogo.getByRole("button", { name: "Escribir el relato" }).click();

  await expect.poll(posts).toBe(1);
  await expect(page.locator("#status-line")).toHaveText("Tu relato está listo", {
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

// Spec-660 B1: se pregunta donde está el botón; cancelar no lanza nada ni lo deja trabado.
test("cancelar la confirmación no crea nada ni deja el botón trabado", async ({ page }) => {
  let posts = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes(`/stories/${OFRENDA}/jobs`)) posts++;
  });
  await page.goto(`/generar/stream/${OFRENDA}`);
  const regenerar = page.getByRole("button", { name: "Regenerar historia" });

  await regenerar.click();
  await page.locator("#forge-confirm").getByRole("button", { name: "Cancelar" }).click();

  await expect(page).toHaveURL(new RegExp(`/generar/stream/${OFRENDA}$`));
  await expect(regenerar).toBeEnabled();
  await expect(regenerar).not.toHaveAttribute("aria-busy", "true");
  expect(posts).toBe(0);
  const activo = await page.request.get(`/api/v1/stories/${OFRENDA}/jobs/active`);
  expect(activo.ok() ? await activo.json() : null).toBeNull();
});

