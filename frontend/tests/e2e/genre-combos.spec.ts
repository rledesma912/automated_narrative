import { test, expect } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Combos Género → Subgénero desde el catálogo del Core (Spec-440 §2, S3).
 */
test.describe.configure({ mode: "serial" });

const genre = (page: import("@playwright/test").Page) => page.locator('[name="atmosfera"]');
const subgenre = (page: import("@playwright/test").Page) =>
  page.locator('[name="atmosphere_subgenre"]');

async function optionLabels(page: import("@playwright/test").Page): Promise<string[]> {
  return subgenre(page).locator("option:not([value=''])").allInnerTexts();
}

test("sin género el subgénero está deshabilitado; body_horror lista solo los suyos", async ({
  page,
}) => {
  await page.goto("/generar");

  await expect(subgenre(page)).toBeDisabled();
  await expect(subgenre(page).locator("option").first()).toHaveText("Elegí primero el tipo de horror");
  await expect(genre(page).locator("option:not([value=''])")).toHaveCount(8);

  await genre(page).selectOption("body_horror");

  await expect(subgenre(page)).toBeEnabled();
  expect(await optionLabels(page)).toEqual([
    "Mutación y transformación",
    "Infección y contagio",
    "Médico / quirúrgico",
    "Parásitos y simbiosis",
    "Enfermedad y decadencia del cuerpo",
    "Otro estilo",
  ]);
});

test("cambiar de género resetea un subgénero que no le pertenece y lo guarda", async ({ page }) => {
  await page.goto("/generar");
  await genre(page).selectOption("folk_horror");
  await subgenre(page).selectOption("rural");

  const saved = page.waitForRequest(
    (r) => r.method() === "PATCH" && (r.postData() ?? "").includes('"atmosphere_subgenre"'),
  );
  await genre(page).selectOption("suspenso");
  await saved;

  await expect(subgenre(page)).toHaveValue("");
  expect(await optionLabels(page)).toContain("Policial / noir");

  // `otro` existe en todos los géneros: se conserva al cambiar.
  const subSaved = page.waitForResponse(
    (r) => r.request().method() === "PATCH" && (r.request().postData() ?? "").includes('"otro"'),
  );
  await subgenre(page).selectOption("otro");
  await subSaved;
  const genreSaved = page.waitForResponse(
    (r) => r.request().method() === "PATCH" && (r.request().postData() ?? "").includes('"paranormal"'),
  );
  await genre(page).selectOption("paranormal");
  await genreSaved;
  await expect(subgenre(page)).toHaveValue("otro");

  // Lo auto-guardado sobrevive a recargar la página.
  await page.reload();
  await expect(genre(page)).toHaveValue("paranormal");
  await expect(subgenre(page)).toHaveValue("otro");
});

test("editar una historia folk_horror/rural precarga ambos combos", async ({ page }) => {
  const id = await storyIdByTitle(page.request, "El monte prohibido");
  await page.goto(`/generar/cargar/${id}`);

  await expect(page).toHaveURL(/\/generar\/paso\/1$/);
  await expect(genre(page)).toHaveValue("folk_horror");
  await expect(subgenre(page)).toHaveValue("rural");
  await expect(subgenre(page).locator("option[value='rural']")).toHaveText("Leyendas del campo");
});
