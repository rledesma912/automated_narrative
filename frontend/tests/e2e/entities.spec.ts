import { test, expect, type Page } from "@playwright/test";

/**
 * Grupo «La Amenaza» del paso 4 (Spec-450 S4).
 * Arnés de playwright.config.ts (Core con DB descartable).
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés");

const nature = (page: Page, n: number) => page.locator(`[name="entity_${n}_nature"]`);

async function next(page: Page, label = "Siguiente") {
  await page.getByRole("button", { name: label }).click();
}

let storyId = "";

test("agregar 2 entidades, guardar y verlas rehidratadas al editar", async ({ page }) => {
  await page.goto("/generar");
  await page.fill('[name="title"]', "Historia con amenaza");
  await page.locator('[name="atmosfera"]').selectOption("folk_horror");
  await next(page);
  await page.fill('[name="protagonista_1_name"]', "Rosa");
  await page.fill('[name="protagonista_1_role"]', "Peona");
  await next(page);
  await next(page); // paso 3: sin obligatorios

  // Paso 4: escenario y regla son obligatorios; el grupo de entidades arranca vacío.
  await page.fill('[name="scenario_1_name"]', "El galpón");
  await page.fill('[name="rule_1_text"]', "Nadie entra de noche");
  await expect(page.locator("#entity-card-1")).toBeHidden();
  await page.locator("#btn-add-entidad").click();
  await expect(page.locator("#entity-card-1")).toBeVisible();
  await expect(page.locator("#entity-card-1")).toContainText("ENTIDAD 1 — PRINCIPAL");
  expect(await nature(page, 1).locator("option:not([value=''])").allInnerTexts()).toContain(
    "Ser del folklore",
  );
  await page.fill('[name="entity_1_name"]', "La Mala Hora");
  await nature(page, 1).selectOption("folklorica");
  await page.fill('[name="entity_1_limits"]', "No cruza el agua");
  await page.locator('[name="entity_1_reveal"][value^="nunca"]').check();

  await page.locator("#btn-add-entidad").click();
  await nature(page, 2).selectOption("culto");
  await next(page);

  for (const name of ["acto_1_exposicion", "acto_2_accion", "acto_3_climax", "acto_4_accion", "acto_5_desenlace"]) {
    await page.fill(`[name="${name}"]`, `Texto de ${name}.`);
  }
  await next(page, "Revisar");
  await expect(page.getByText("Ser del folklore")).toBeVisible(); // confirmación con etiqueta
  await page.getByRole("button", { name: "Guardar historia" }).click();
  await expect(page).toHaveURL(/\/galeria\?success=saved&guardada=/);
  storyId = new URL(page.url()).searchParams.get("guardada")!;

  const story = await (await page.request.get(`/api/v1/stories/${storyId}`)).json();
  expect(story.storyteller_config.entities).toEqual([
    {
      name: "La Mala Hora",
      nature: "folklorica",
      description: "",
      manifestations: "",
      limits: "No cruza el agua",
      reveal_level: "nunca",
    },
    { name: "", nature: "culto", description: "", manifestations: "", limits: "", reveal_level: "insinuada" },
  ]);

  await page.goto(`/generar/cargar/${storyId}`);
  await page.goto("/generar/paso/4");
  await expect(page.locator("#entity-card-1")).toBeVisible();
  await expect(page.locator("#entity-card-2")).toBeVisible();
  await expect(page.locator("#entity-card-3")).toBeHidden();
  await expect(page.locator('[name="entity_1_name"]')).toHaveValue("La Mala Hora");
  await expect(nature(page, 1)).toHaveValue("folklorica");
  await expect(page.locator('[name="entity_1_reveal"][value^="nunca"]')).toBeChecked();
});

test("cambiar a un género donde la naturaleza no corresponde la deja vacía", async ({ page }) => {
  await page.goto(`/generar/cargar/${storyId}`);
  const saved = page.waitForResponse(
    (r) => r.request().method() === "PATCH" && (r.request().postData() ?? "").includes('"suspenso"'),
  );
  await page.locator('[name="atmosfera"]').selectOption("suspenso");
  await saved;

  await page.goto("/generar/paso/4");
  await expect(nature(page, 1)).toHaveValue(""); // folklórica no existe en suspenso
  await expect(nature(page, 2)).toHaveValue("culto"); // culto sí

  // Guardar sin elegirla lo explica y no pierde la entidad en silencio.
  await page.goto("/generar/confirmar");
  await page.getByRole("button", { name: "Guardar historia" }).click();
  await expect(page.locator("[data-save-error]")).toContainText("La entidad 1 quedó sin «Qué es»");
});

test("enviar el paso 4 con una entidad sin «Qué es» muestra el error (422 con hx-boost)", async ({
  page,
}) => {
  await page.goto("/generar");
  const saved = page.waitForResponse(
    (r) => r.request().method() === "PATCH" && (r.request().postData() ?? "").includes('"folk_horror"'),
  );
  await page.locator('[name="atmosfera"]').selectOption("folk_horror");
  await saved;

  await page.goto("/generar/paso/4");
  // El género llegó por auto-save (sin enviar el paso 1): las naturalezas ya están.
  await expect(nature(page, 1)).toBeEnabled();
  await page.fill('[name="scenario_1_name"]', "El galpón");
  await page.fill('[name="rule_1_text"]', "Nadie entra de noche");
  await page.locator("#btn-add-entidad").click();
  await page.fill('[name="entity_1_name"]', "Sin naturaleza");
  await next(page);

  await expect(page).toHaveURL(/\/generar\/paso\/4$/);
  await expect(page.locator('[data-field-error="entity_1_nature"]')).toHaveText(
    "Elegí qué es la entidad 1 (o borrala con el tacho).",
  );
  await expect(page.locator("#entity-card-1")).toBeVisible(); // la card no se pierde
});
