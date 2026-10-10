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

// Spec-660: la confirmación es el diálogo, en la misma página.
test("la confirmación de escribir dice cuánto tarda y que se puede cerrar la pestaña", async ({ page }) => {
  await page.goto(`/generar/stream/${STORY_ID}`);
  await page.getByRole("button", { name: "Regenerar historia" }).click();
  await expect(page.locator("#forge-confirm [data-confirm-mensaje]")).toHaveText(
    /^Tarda ≈ \d+ min\. Podés cerrar la pestaña: la IA sigue escribiendo\.$/,
  );
  await page.locator("#forge-confirm").getByRole("button", { name: "Cancelar" }).click();
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
