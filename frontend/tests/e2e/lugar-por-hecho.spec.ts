import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

/**
 * Spec-710 S4: cada hecho con su lugar en la tarjeta del acto. El mock arma los actos con
 * «Escenario de ejemplo» en los dos hechos de cada acto.
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

const API = "/api/v1";
let sid = "";

async function job(request: APIRequestContext, kind: string) {
  const resp = await request.post(`${API}/stories/${sid}/jobs`, { data: { kind } });
  expect(resp.status()).toBe(202);
  const { job_id } = await resp.json();
  await expect
    .poll(async () => (await (await request.get(`${API}/jobs/${job_id}`)).json()).status, { timeout: 20_000 })
    .toBe("done");
}

const acto = (page: Page, n: number) => page.locator(`[data-acto="${n}"]`);
const lugares = (page: Page, n: number) => acto(page, n).locator('select[name="event_places"]');
async function guardadoListo(page: Page) {
  await expect(page.locator("[data-guardado]").first()).not.toHaveAttribute("data-pendiente", "1");
}
async function valores(page: Page, n: number) {
  return lugares(page, n).evaluateAll((els) => els.map((e) => (e as HTMLSelectElement).value));
}

test.beforeAll(async ({ request }) => {
  const created = await request.post(`${API}/authoring/stories`, {
    data: { title: "E2E lugar por hecho", premise: "José maneja de noche por la ruta.", protagonist_name: "José" },
  });
  sid = (await created.json()).story_id;
  await job(request, "plan_outline");
});

test("«+ Lugar nuevo…» desde un hecho lo suma y lo deja elegido en ese hecho", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  await expect(lugares(page, 1)).toHaveCount(2);
  await expect(acto(page, 1).locator('input[name="scenario"]')).toHaveCount(0); // sin el radio
  await lugares(page, 1).nth(1).selectOption("__nuevo__");
  await acto(page, 1).locator("[data-lugar-nombre]").fill("La calle");
  await acto(page, 1).getByRole("button", { name: "Agregar", exact: true }).click();
  await expect(lugares(page, 1).nth(1)).toHaveValue("La calle");
  await expect(acto(page, 1).locator("[data-lugares-del-acto]")).toHaveText("Escenario de ejemplo · La calle");
  // Es un lugar de la historia: aparece en los otros actos.
  await expect(lugares(page, 2).first().locator('option[value="La calle"]')).toHaveCount(1);
});

test("agregar, subir y quitar hechos lleva cada lugar con su hecho", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  const a1 = acto(page, 1);
  await a1.getByRole("button", { name: /Agregar hecho/ }).click();
  await a1.locator('textarea[name="events"]').last().fill("José frena de golpe.");
  await guardadoListo(page);
  await page.reload();
  expect(await valores(page, 1)).toEqual(["Escenario de ejemplo", "La calle", ""]);

  // Sube el último hasta arriba: su lugar («donde el anterior») va con él.
  await acto(page, 1).locator("[data-item]").last().locator("[data-subir]").click();
  await acto(page, 1).locator("[data-item]").nth(1).locator("[data-subir]").click();
  await guardadoListo(page);
  await page.reload();
  await expect(acto(page, 1).locator('textarea[name="events"]').first()).toHaveValue("José frena de golpe.");
  expect(await valores(page, 1)).toEqual(["", "Escenario de ejemplo", "La calle"]);

  await acto(page, 1).locator("[data-item]").first().locator("[data-quitar]").click();
  await guardadoListo(page);
  await page.reload();
  expect(await valores(page, 1)).toEqual(["Escenario de ejemplo", "La calle"]);
});

test("borrar un lugar dice en cuántos hechos pasa y esos hechos quedan «donde el anterior»", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  await acto(page, 1).getByRole("button", { name: "Borrar el lugar «La calle» de la historia" }).click();
  const dialogo = page.locator("#forge-confirm");
  await expect(dialogo).toContainText("hoy está en el acto 1, en 1 hecho");
  await dialogo.getByRole("button", { name: "Borrar de la historia" }).click();
  await expect(lugares(page, 1).nth(1)).toHaveValue("");
  await expect(acto(page, 1).locator("[data-lugares-del-acto]")).toHaveText("Escenario de ejemplo");
});
