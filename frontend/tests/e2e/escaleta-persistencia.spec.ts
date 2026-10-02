import { test, expect, type APIRequestContext } from "@playwright/test";

/**
 * Spec-630 B11 (T6.4): todo lo que se edita en un acto de «Los actos» se guarda.
 * Se edita cada campo, se recarga la página y se comprueba cada valor.
 */
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

const API = "/api/v1";
let sid = "";

async function job(request: APIRequestContext, kind: string) {
  const resp = await request.post(`${API}/stories/${sid}/jobs`, { data: { kind } });
  const { job_id } = await resp.json();
  await expect
    .poll(async () => (await (await request.get(`${API}/jobs/${job_id}`)).json()).status, { timeout: 20_000 })
    .toBe("done");
}

test.beforeAll(async ({ request }) => {
  const created = await request.post(`${API}/authoring/stories`, {
    data: { title: "E2E persistencia", premise: "José ve a una mujer muerta en el espejo del micro.", protagonist_name: "José" },
  });
  sid = (await created.json()).story_id;
  await job(request, "plan_outline");
  await request.post(`${API}/authoring/stories/${sid}/characters`, { data: { name: "Marta", kind: "persona" } });
  await request.post(`${API}/authoring/stories/${sid}/scenarios`, { data: { name: "La terminal" } });
});

test("cada campo del acto se guarda y vuelve igual al recargar", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  const a2 = page.locator('[data-acto="2"]');
  const valores = {
    bridge: "Pasó una semana sin volver a mirar el espejo.",
    goal: "José quiere cambiar de recorrido.",
    change_from: "con miedo",
    change_to: "decidido a mirar",
    held_back: "La mujer es su hermana.",
  };
  for (const [name, value] of Object.entries(valores)) await a2.locator(`[name="${name}"]`).fill(value);
  await a2.getByRole("button", { name: /Agregar hecho/ }).click();
  await a2.locator('textarea[name="events"]').last().fill("José pide el cambio en la oficina.");
  await a2.getByRole("button", { name: "Regla", exact: true }).click();
  await a2.locator('textarea[name="rules"]').last().fill("Ella solo aparece en el espejo.");
  await a2.locator('[name="reveal_act"]').selectOption("4");
  await a2.locator("label", { hasText: "La terminal" }).click();
  await a2.locator("label", { hasText: "Marta" }).click();
  await expect(page.locator("[data-guardado]").first()).not.toHaveAttribute("data-pendiente", "1");

  await page.reload();
  const r2 = page.locator('[data-acto="2"]');
  for (const [name, value] of Object.entries(valores)) await expect(r2.locator(`[name="${name}"]`)).toHaveValue(value);
  await expect(r2.locator('textarea[name="events"]').last()).toHaveValue("José pide el cambio en la oficina.");
  await expect(r2.locator('textarea[name="rules"]').last()).toHaveValue("Ella solo aparece en el espejo.");
  await expect(r2.locator('[name="reveal_act"]')).toHaveValue("4");
  await expect(r2.getByRole("radio", { name: "La terminal" })).toBeChecked();
  await expect(r2.getByRole("checkbox", { name: /Marta/ })).toBeChecked();
  // Y no se tocó otro acto.
  await expect(page.locator('[data-acto="3"] [name="goal"]')).not.toHaveValue(valores.goal);
});
