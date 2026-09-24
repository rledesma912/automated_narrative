import { test, expect } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Tiempo estimado antes de lanzar un job (Spec-510 S3).
 * Solo lee páginas: no lanza generaciones.
 */
let STORY_ID = process.env.TEST_STORY_ID || "";
test.beforeAll(async ({ request }) => {
  if (!STORY_ID) STORY_ID = await storyIdByTitle(request, "El monte prohibido");
});

test("la galería muestra cuánto tarda generar", async ({ page }) => {
  await page.goto("/galeria");
  const estimate = page.locator('[data-estimate="full_generation"]').first();
  await expect(estimate).toHaveText(/^≈ \d+ min$/);
});

test("la ficha muestra la estimación junto a Regenerar", async ({ page }) => {
  await page.goto(`/historia/${STORY_ID}`);
  await expect(page.locator('[data-estimate="full_generation"]')).toHaveText(/^≈ \d+ min$/);
});

test("la confirmación de la sala dice cuánto tarda y que se puede cerrar la pestaña", async ({
  page,
}) => {
  await page.goto(`/generar/stream/${STORY_ID}?regenerate=1`);
  await expect(page.locator("#start-panel [data-start-estimate]").first()).toHaveText(
    /Tarda ≈ \d+ min\. Podés cerrar la pestaña: sigue generándose\./,
  );
});

test("regenerar un acto pide confirmación con la estimación", async ({ page }) => {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const panel = page.locator("[data-relato-panel]").first();
  if ((await panel.count()) === 0) test.skip(true, "La historia no tiene relatos");
  await expect(panel.locator("[data-regenerar-acto]").first()).toHaveAttribute(
    "hx-confirm",
    /^¿Regenerar este acto\? Tarda ≈ \d+ min\. Se reemplazará el texto actual\.$/,
  );
});
