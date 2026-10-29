import { test, expect, type APIRequestContext } from "@playwright/test";

/**
 * Spec-700 S2: si la idea cambió después de armar los actos (o de las preguntas), se avisa.
 * Armar los actos de nuevo siempre pide confirmar; «Dejarlo así» saca la nota sin la IA.
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

test.beforeAll(async ({ request }) => {
  const premise = "José ve a una mujer muerta en el espejo del micro.";
  const created = await request.post(`${API}/authoring/stories`, {
    data: { title: "E2E la idea cambió", premise, protagonist_name: "José" },
  });
  sid = (await created.json()).story_id;
  await job(request, "consult");
  await job(request, "plan_outline");
  const state = await (await request.get(`${API}/authoring/stories/${sid}`)).json();
  const resp = await request.put(`${API}/authoring/stories/${sid}/direction`, {
    data: { ...state.direction, premise: `${premise} Al final, José deja de manejar de noche.` },
  });
  expect(resp.status()).toBe(200);
});

test("«Los actos»: armar de nuevo pide confirmar y cancelar no arma nada", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  const nota = page.locator('[data-idea-cambio="actos"]');
  await expect(nota).toContainText("Cambiaste tu idea después de armar los actos.");

  await nota.getByRole("button", { name: "Armar los actos de nuevo" }).click();
  const dialogo = page.locator("#forge-confirm");
  await expect(dialogo).toContainText("¿Armar los actos de nuevo?");
  await expect(dialogo).toContainText("se reemplaza");
  await dialogo.getByRole("button", { name: "Cancelar" }).click();
  await expect(dialogo).not.toBeVisible();
  await expect(page.locator("#asistente-analizando")).toHaveCount(1);
  await expect(page.locator("#asistente-analizando")).toBeHidden();
  await expect(nota).toBeVisible();
});

test("«Dejarlo así» saca la nota y no vuelve al recargar", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  await page.locator('[data-idea-cambio="actos"]').getByRole("button", { name: "Dejarlo así" }).click();
  await expect(page.locator('[data-idea-cambio="actos"]')).toHaveCount(0);
  await page.reload();
  await expect(page.locator('[data-idea-cambio="actos"]')).toHaveCount(0);
});

test("«Preguntas»: la nota ofrece que la IA la vuelva a leer", async ({ page }) => {
  await page.goto(`/asistente/${sid}/taller`);
  const nota = page.locator('[data-idea-cambio="preguntas"]');
  await expect(nota).toContainText("Cambiaste tu idea después de estas preguntas.");
  await expect(page.locator("[data-preguntar-falta]")).toBeVisible();
  await nota.getByRole("button", { name: "Dejarlo así" }).click();
  await expect(nota).toHaveCount(0);
});
