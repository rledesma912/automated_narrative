import { test, expect } from "@playwright/test";

/**
 * Editar una historia ya generada (Spec-440 §8, S0).
 * Arnés de playwright.config.ts: "El monte prohibido" del seed está completa y con relatos.
 */
const STORY_ID = "af608048-88a0-4234-b756-8867c1b64092";

test.skip(!!process.env.BASE_URL, "Modifica historias: solo contra el arnés con DB descartable");

test("editar una historia generada: el wizard se rehidrata completo y se conserva lo generado", async ({
  page,
}) => {
  const relatosAntes = (await (
    await page.request.get(`/api/v1/story-templates/${STORY_ID}/narratives`)
  ).json()) as unknown[];
  expect(relatosAntes.length).toBeGreaterThan(0);

  await page.goto(`/generar/cargar/${STORY_ID}`);
  await expect(page).toHaveURL(/\/generar\/paso\/1$/);
  const title = page.locator('[name="title"]');
  await expect(title).toHaveValue("El monte prohibido");
  await title.fill("El monte prohibido (editada)");

  // Del paso 1 al 5: todo lo obligatorio viene cargado desde la historia.
  for (let i = 0; i < 4; i++) {
    await page.getByRole("button", { name: "Siguiente" }).click();
  }
  await expect(page).toHaveURL(/\/generar\/paso\/5$/);
  for (const name of [
    "acto_1_exposicion",
    "acto_2_accion",
    "acto_3_climax",
    "acto_4_accion",
    "acto_5_desenlace",
  ]) {
    await expect(page.locator(`[name="${name}"]`), name).not.toHaveValue("");
  }
  await page.getByRole("button", { name: "Revisar" }).click();
  await page.getByRole("button", { name: "Guardar historia" }).click();

  await expect(page).toHaveURL(/success=saved_regenerar/);
  await expect(page.locator("#toast-notification")).toContainText("Regenerala");
  await expect(page.locator(`[data-story-card="${STORY_ID}"]`)).toContainText(
    "El monte prohibido (editada)",
  );
  await expect(page.locator(`[data-story-card="${STORY_ID}"]`)).toContainText("Completada");

  const relatosDespues = (await (
    await page.request.get(`/api/v1/story-templates/${STORY_ID}/narratives`)
  ).json()) as unknown[];
  expect(relatosDespues.length).toBe(relatosAntes.length);
});
