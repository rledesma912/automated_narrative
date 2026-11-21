import { test, expect, type Page } from "@playwright/test";

/**
 * Spec-670 S5: la clase de historia en «Tu idea» y las preguntas por grupo
 * en «Preguntas», con el LLM simulado (el mock sugiere «Algo viene por nosotros»).
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

const guardado = (page: Page) => page.locator("[data-guardado]").first();
async function guardadoListo(page: Page) {
  await expect(guardado(page)).not.toHaveAttribute("data-pendiente", "1");
  await expect(guardado(page)).toContainText("Guardado");
}
const formas = (page: Page) => page.locator("[data-formas]");

let sid = "";
const TITULO = `E2E moldes ${Date.now()}`;

test("elegir la clase de historia se guarda solo; no hay giros (Spec-780)", async ({ page, request }) => {
  await page.goto("/nuevo");
  await page.getByLabel("Título").fill(TITULO);
  await page.getByLabel("¿De qué trata?").fill("Una criatura sale de la laguna porque una fábrica le mató los peces.");
  await expect(page).toHaveURL(/\/asistente\/[0-9a-f-]{36}\/direccion$/);
  await guardadoListo(page);
  sid = page.url().split("/")[4];
  // Sin elegir: se pregunta como en la de siempre.
  await expect(page.locator("[data-sin-forma]")).toContainText("Alguien rompe una regla");

  await formas(page).getByText("Un lugar que no hay que pisar").click();
  await guardadoListo(page);
  await expect(page.locator("[data-giros]")).toHaveCount(0);

  await formas(page).getByText("Otra clase de historia").click();
  await expect(page.locator("#a-form-other")).toBeVisible();
  await page.locator("#a-form-other").fill("Una muñeca que envejece con la nena.");
  await guardadoListo(page);

  await formas(page).getByText("Algo viene por nosotros").click();
  await expect(page.locator("#a-form-other")).toBeHidden();
  await guardadoListo(page);

  await page.reload();
  await expect(formas(page).getByRole("radio", { name: /Algo viene por nosotros/ })).toBeChecked();
  const d = (await (await request.get(`/api/v1/authoring/stories/${sid}`)).json()).direction;
  expect([d.form, d.form_other]).toEqual(["asedio", "Una muñeca que envejece con la nena."]);
});

test("la IA sugiere la clase de historia y dice por qué", async ({ page }) => {
  await page.goto(`/asistente/${sid}/direccion`);
  await formas(page).getByRole("button", { name: /Que la IA lo sugiera/ }).click();
  await expect(page.locator("[data-sugerencia]")).toContainText("La IA sugiere «Algo viene por nosotros»", {
    timeout: 15_000,
  });
  await expect(formas(page).locator("[data-sugerida]")).toHaveCount(1);
});

test("«Preguntas» agrupa las de toda historia y las de la forma", async ({ page }) => {
  await page.goto(`/asistente/${sid}/direccion`);
  await page.getByRole("button", { name: /Que la IA me pregunte/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/taller$`));
  const resumen = page.locator("[data-grupo]");
  await expect(resumen.filter({ hasText: "De toda historia" })).toBeVisible();
  await expect(resumen.filter({ hasText: "De «Algo viene por nosotros»" })).toContainText("Cómo se acerca");
  await expect(resumen.filter({ hasText: "Del giro" })).toHaveCount(0);
  await expect(page.getByText("Son 9 como mucho y ninguna es obligatoria.")).toBeVisible();
});

test("cambiar de clase guarda las respuestas que la nueva no usa", async ({ page }) => {
  await page.goto(`/asistente/${sid}/taller`);
  const pregunta = page.locator('[data-pregunta="asedio_acercamiento"]');
  await pregunta.getByText(/Primera opción/).click();
  await pregunta.getByRole("button", { name: "Guardar respuesta" }).click();
  await expect(page.locator('[data-pregunta="asedio_acercamiento"]').first()).toBeVisible();

  await page.goto(`/asistente/${sid}/direccion`);
  await formas(page).getByText("Alguien que llega a casa").click();
  await guardadoListo(page);
  await page.goto(`/asistente/${sid}/taller`);
  await expect(page.locator("[data-guardadas]")).toContainText("1 respuesta de otra clase de historia");
  await expect(page.locator('[data-pregunta="asedio_acercamiento"]')).toHaveCount(0);
});
