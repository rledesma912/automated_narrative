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

async function next(page: Page, label = "Siguiente") {
  await page.getByRole("button", { name: label }).click();
}

test("el wizard termina en «Guardar historia» y vuelve a la galería resaltada", async ({ page }) => {
  const jobPosts = countPosts(page, "/jobs");
  await page.goto("/generar");

  await page.fill('[name="title"]', "Historia E2E");
  await page.locator('[name="atmosfera"]').selectOption({ index: 1 });
  await next(page);
  await page.fill('[name="protagonista_1_name"]', "Irene");
  await page.fill('[name="protagonista_1_role"]', "Narradora");
  await page.locator('[name="storyteller_id"]').selectOption({ index: 1 });
  await next(page);
  // paso 3: sin obligatorios; se eligen valores para verificar el contrato (Spec-440 S1)
  await page
    .locator('[name="perception_reliability"]')
    .selectOption("poco_confiable: A veces ve bien, a veces no");
  await page.locator('[name="language_register"][value="rural_tradicional: Del campo"]').check();
  await next(page);
  await page.fill('[name="scenario_1_name"]', "La casa");
  await page.fill('[name="rule_1_text"]', "Los espejos muestran el pasado");
  await page.locator('[name="rule_1_type"]').selectOption("fenomeno: Sobrenatural");
  await next(page);
  for (const name of [
    "acto_1_exposicion",
    "acto_2_accion",
    "acto_3_climax",
    "acto_4_accion",
    "acto_5_desenlace",
  ]) {
    await page.fill(`[name="${name}"]`, `Texto de ${name}.`);
  }
  await next(page, "Revisar");

  await expect(page).toHaveURL(/\/generar\/confirmar$/);
  await expect(page.getByRole("button", { name: /Generar historia/i })).toHaveCount(0);
  await page.getByRole("button", { name: "Guardar historia" }).click();

  await expect(page).toHaveURL(/\/galeria\?success=saved&guardada=/);
  savedStoryId = new URL(page.url()).searchParams.get("guardada")!;
  await expect(page.locator("#toast-notification")).toContainText("Historia guardada");
  const card = page.locator(`[data-story-card="${savedStoryId}"]`);
  await expect(card).toHaveClass(/card-forge-active/);
  await expect(card).toContainText("Borrador");
  expect(jobPosts()).toBe(0); // guardar no genera

  const story = await (await page.request.get(`/api/v1/stories/${savedStoryId}`)).json();
  expect(story.status).toBe("draft");
  // Contrato wizard → API (Spec-440 §4 y §9): campos explícitos, solo IDs, reglas tipadas.
  expect(story.genero).not.toBe("");
  expect(story.genero).not.toContain(":");
  const sc = story.storyteller_config;
  expect(sc.perception.reliability).toBe("poco_confiable");
  expect(sc.language.register).toBe("rural_tradicional");
  expect(sc.rules[0]).toMatchObject({ text: "Los espejos muestran el pasado", type: "fenomeno" });
  expect(story.relator).toContain("Registro: rural_tradicional.");
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
