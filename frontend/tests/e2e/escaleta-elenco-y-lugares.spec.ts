import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

/**
 * Spec-630 S3: personajes, lugares y avisos desde «Los actos» (B2, B6, B7), sin
 * recargar la página.
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
const dialogo = (page: Page) => page.locator("#forge-confirm");
async function guardadoListo(page: Page) {
  await expect(page.locator("[data-guardado]").first()).not.toHaveAttribute("data-pendiente", "1");
}

test.beforeAll(async ({ request }) => {
  const created = await request.post(`${API}/authoring/stories`, {
    data: { title: "E2E elenco y lugares", premise: "José ve a una mujer muerta en el espejo del micro.", protagonist_name: "José" },
  });
  sid = (await created.json()).story_id;
  await job(request, "plan_outline");
  // Alguien que está en el acto 2 pero no en el elenco: la revisión lo avisa (regla `elenco:`).
  const state = await (await request.get(`${API}/authoring/stories/${sid}`)).json();
  const a2 = state.outline.acts[1];
  await request.put(`${API}/authoring/stories/${sid}/outline/2`, {
    data: { ...a2, on_stage: [...a2.on_stage, "El sereno"] },
  });
  await job(request, "verify_outline");
});

test("«Sumarlo a los personajes» lo marca en el acto y el aviso se va (no queda ignorado)", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  const aviso = acto(page, 2).locator(".nota-forge--warning", { hasText: "«El sereno»" });
  await expect(aviso).toBeVisible();
  await aviso.getByRole("button", { name: "Sumarlo a los personajes" }).click();

  await expect(aviso).toHaveCount(0);
  await expect(acto(page, 2).getByRole("checkbox", { name: /El sereno/ })).toBeChecked();
  await expect(acto(page, 1).getByRole("checkbox", { name: /El sereno/ })).not.toBeChecked();
  const ignorados = acto(page, 2).locator("[data-ignorados]");
  if (await ignorados.count()) await expect(ignorados).not.toContainText("El sereno");
});

test("se suman varios lugares seguidos, aparecen en todos los actos y se elige otro", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  const a3 = acto(page, 3);
  await a3.getByRole("button", { name: "Lugar", exact: true }).click();
  await a3.locator("[data-lugar-nombre]").fill("El galpón");
  await a3.locator("[data-lugar-nombre]").press("Enter");

  await expect(a3.getByRole("radio", { name: "El galpón" })).toBeChecked();
  // El campo queda abierto, vacío y con el foco, para sumar otro.
  await expect(a3.locator("[data-lugar-nombre]")).toBeVisible();
  await expect(a3.locator("[data-lugar-nombre]")).toHaveValue("");
  await expect(a3.locator("[data-lugar-nombre]")).toBeFocused();
  await a3.locator("[data-lugar-nombre]").fill("La ruta vieja");
  await a3.getByRole("button", { name: "Agregar", exact: true }).click();

  await expect(a3.getByRole("radio", { name: "La ruta vieja" })).toBeChecked();
  for (const n of [1, 2, 3, 4, 5]) {
    await expect(acto(page, n).getByRole("radio", { name: "El galpón" })).toHaveCount(1);
    await expect(acto(page, n).getByRole("radio", { name: "La ruta vieja" })).toHaveCount(1);
  }

  // Elegir otro lugar de la lista se guarda (antes ganaba siempre lo escrito en el campo).
  await a3.locator("label", { hasText: "El galpón" }).click();
  await guardadoListo(page);
  await page.reload();
  await expect(acto(page, 3).getByRole("radio", { name: "El galpón" })).toBeChecked();
});

test("borrar un lugar, un personaje y una regla", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);

  await acto(page, 1).getByRole("button", { name: "Borrar el lugar «La ruta vieja»" }).click();
  await expect(dialogo(page)).toContainText("Ningún acto lo usa.");
  await dialogo(page).getByRole("button", { name: "Borrar el lugar" }).click();
  await expect(page.getByRole("radio", { name: "La ruta vieja" })).toHaveCount(0);

  await acto(page, 4).getByRole("button", { name: "Borrar el personaje «El sereno»" }).click();
  await expect(dialogo(page)).toContainText("Se quita del acto 2.");
  await dialogo(page).getByRole("button", { name: "Borrar el personaje" }).click();
  await expect(page.getByRole("checkbox", { name: /El sereno/ })).toHaveCount(0);
  // Quien narra no se puede borrar.
  await expect(page.getByRole("button", { name: "Borrar el personaje «José»" })).toHaveCount(0);

  const a1 = acto(page, 1);
  await a1.getByRole("button", { name: "Regla", exact: true }).click();
  await a1.locator('textarea[name="rules"]').last().fill("Solo de noche");
  await guardadoListo(page);
  await page.reload();
  await expect(acto(page, 1).locator('textarea[name="rules"]')).toHaveValue("Solo de noche");
  await acto(page, 1).locator('[data-lista="rules"] [data-quitar]').click();
  await guardadoListo(page);
  await page.reload();
  await expect(acto(page, 1).locator('textarea[name="rules"]')).toHaveCount(0);
});
