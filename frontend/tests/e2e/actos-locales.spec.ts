import { test, expect, type APIRequestContext } from "@playwright/test";

/**
 * Spec-720 D7: si la IA de la nube no responde, los actos los arma la de la compu y
 * «Los actos» lo dicen. El arnés simula la nube caída con «NUBE CAÍDA» en la idea.
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
  const created = await request.post(`${API}/authoring/stories`, {
    data: { title: "E2E nube caída", premise: "José maneja de noche. NUBE CAÍDA.", protagonist_name: "José" },
  });
  sid = (await created.json()).story_id;
  await job(request, "consult");
  await job(request, "plan_outline");
});

test("«Los actos» dicen que los armó la IA de la compu y «Dejarlo así» lo saca", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  const nota = page.locator('[data-hecho-local="actos"]');
  await expect(nota).toContainText("Estos actos los armó la IA de tu compu");

  await nota.getByRole("button", { name: "Armar los actos de nuevo" }).click();
  const dialogo = page.locator("#forge-confirm");
  await expect(dialogo).toContainText("¿Armar los actos de nuevo?");
  await dialogo.getByRole("button", { name: "Cancelar" }).click();

  await nota.getByRole("button", { name: "Dejarlo así" }).click();
  await expect(page.locator("[data-hecho-local]")).toHaveCount(0);
  await page.reload();
  await expect(page.locator("[data-hecho-local]")).toHaveCount(0);
});
