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

// Spec-630 B12/B14: la galería ya no lanza generaciones y la ficha se fue; la
// estimación se ve donde se lanza: la sala y regenerar un acto.
test("la galería no ofrece generar ni muestra estimación", async ({ page }) => {
  await page.goto("/galeria");
  await expect(page.locator("[data-story-card]").first()).toBeVisible();
  await expect(page.locator('[data-estimate="full_generation"]')).toHaveCount(0);
  await expect(page.locator("[data-story-card] [data-generation-trigger]")).toHaveCount(0);
});

test("la confirmación de la sala dice cuánto tarda y que se puede cerrar la pestaña", async ({
  page,
}) => {
  await page.goto(`/generar/stream/${STORY_ID}?regenerate=1`);
  await expect(page.locator("#start-panel [data-start-estimate]").first()).toHaveText(
    /Tarda ≈ \d+ min\. Podés cerrar la pestaña: la IA sigue escribiendo\./,
  );
});

test("regenerar un acto pide confirmación con la estimación", async ({ page }) => {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const panel = page.locator("[data-relato-panel]").first();
  if ((await panel.count()) === 0) test.skip(true, "La historia no tiene relatos");
  await expect(panel.locator("[data-regenerar-acto]").first()).toHaveAttribute(
    "hx-confirm",
    /^Tarda ≈ \d+ min\. Se reemplaza el texto actual del acto \d\.$/,
  );
});
