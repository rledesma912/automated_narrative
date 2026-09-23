import { test, expect, type Page } from "@playwright/test";

/**
 * Combo "quién cuenta la historia" dinámico (Spec-440 §5, S4).
 */
const narrador = (page: Page) => page.locator('[name="storyteller_id"]');
const nombre = (page: Page, n: number) => page.locator(`[name="protagonista_${n}_name"]`);

async function opciones(page: Page): Promise<string[]> {
  return narrador(page).locator("option:not([value=''])").allInnerTexts();
}

test("sin nombre está deshabilitado; con 1 personaje, 1 opción preseleccionada", async ({ page }) => {
  await page.goto("/generar/paso/2");

  await expect(narrador(page)).toBeDisabled();
  await expect(narrador(page).locator("option").first()).toHaveText("Primero nombrá un personaje");

  await nombre(page, 1).fill("Irene");

  await expect(narrador(page)).toBeEnabled();
  expect(await opciones(page)).toEqual(["Irene"]);
  await expect(narrador(page)).toHaveValue("protagonista_1");
});

test("agregar/borrar personajes actualiza el combo y el borrado se guarda", async ({ page }) => {
  await page.goto("/generar/paso/2");
  await nombre(page, 1).fill("Irene");

  await page.locator("#btn-add-personaje").click();
  await nombre(page, 2).fill("Ricardo");
  await page.locator("#btn-add-personaje").click();
  await nombre(page, 3).fill("María");
  expect(await opciones(page)).toEqual(["Irene", "Ricardo", "María"]);

  await narrador(page).selectOption("protagonista_3");
  await narrador(page).blur();

  const reset = page.waitForResponse(
    (r) =>
      r.request().method() === "PATCH" &&
      (r.request().postData() ?? "").includes('"fieldName":"storyteller_id","fieldValue":""'),
  );
  await page.locator("#personaje-delete-btn-3").click();
  await page.locator("#delete-modal-confirm").click();
  await reset;

  expect(await opciones(page)).toEqual(["Irene", "Ricardo"]);
  await expect(narrador(page)).toHaveValue("");

  // El render del servidor aplica el mismo filtro.
  await page.reload();
  expect(await opciones(page)).toEqual(["Irene", "Ricardo"]);
  await expect(narrador(page).locator("option:checked")).toHaveText("Seleccioná...");
});
