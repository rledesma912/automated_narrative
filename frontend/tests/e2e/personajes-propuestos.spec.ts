import { test, expect, type APIRequestContext } from "@playwright/test";

/**
 * Spec-730: la IA suma un personaje con un para qué (el mock: «Don Ramón», en el acto 2).
 * Entra solo a los personajes y el acto lo cuenta con una nota que se cierra con «Entendido».
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
    data: { title: "E2E personaje de la IA", premise: "José maneja de noche por la ruta.", protagonist_name: "José" },
  });
  sid = (await created.json()).story_id;
  await job(request, "consult");
  await job(request, "plan_outline");
});

test("la nota cuenta quién sumó la IA y «Entendido» la cierra para siempre", async ({ page, request }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  const acto2 = page.locator('form[data-number="2"]');
  const nota = acto2.locator("[data-propuesto]");
  await expect(nota).toContainText("La IA sumó a «Don Ramón», el sereno de la terminal");
  await expect(acto2.getByRole("checkbox", { name: /Don Ramón/ })).toBeChecked();
  await expect(page.locator('form[data-number="1"] [data-propuesto]')).toHaveCount(0);

  await nota.getByRole("button", { name: "Entendido" }).click();
  await expect(acto2.locator("[data-propuesto]")).toHaveCount(0);
  await expect(acto2.locator("[data-ignorados]")).toHaveCount(0); // no es un aviso ignorado

  await page.reload();
  await expect(page.locator("[data-propuesto]")).toHaveCount(0);
  await job(request, "verify_outline");
  await page.reload();
  await expect(page.locator("[data-propuesto]")).toHaveCount(0);
});
