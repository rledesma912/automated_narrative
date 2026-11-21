import { test, expect, type APIRequestContext } from "@playwright/test";

/**
 * Spec-760 S2: ningún campo del asistente corta en silencio. Una idea de 20 000
 * caracteres se guarda entera; una de más queda en el cuadro, avisa cuánto sobra y
 * no se guarda; un hecho de 700 caracteres (antes se cortaba a los 400) se guarda.
 */
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

const API = "/api/v1";
const IDEA = "Lucía escucha a su padre gritar desde el auto estacionado frente a la casa. ";
const idea = (n: number) => IDEA.repeat(Math.ceil(n / IDEA.length)).slice(0, n);

async function crear(request: APIRequestContext) {
  const created = await request.post(`${API}/authoring/stories`, {
    data: { title: "E2E idea larga", premise: "Lucía ve un auto negro.", protagonist_name: "Lucía" },
  });
  return (await created.json()).story_id as string;
}

async function guardado(page: import("@playwright/test").Page) {
  await expect(page.locator("[data-guardado]")).not.toHaveAttribute("data-pendiente", "1");
}

test("una idea de 20 000 se guarda entera y una de más avisa sin cortar", async ({ page, request }) => {
  const sid = await crear(request);
  await page.goto(`/asistente/${sid}/direccion`);
  const campo = page.locator("#a-premise");

  await campo.fill(idea(20000));
  await expect(page.locator("[data-tope-contador]")).toHaveText("20.000 de 20.000 letras");
  await guardado(page);
  await page.reload();
  await expect.poll(async () => (await page.locator("#a-premise").inputValue()).length).toBe(20000);

  await page.locator("#a-premise").fill(idea(20500));
  const aviso = "Sobran 500 letras: acortalo un poco para que se guarde.";
  await expect(page.locator("[data-tope-contador]")).toHaveText(aviso);
  await expect(page.locator("[data-guardado]")).toHaveAttribute("data-estado", "error");
  await expect(page.locator("[data-guardado-texto]")).toHaveText(aviso);
  // No se cortó: el texto sigue entero en el cuadro…
  expect((await page.locator("#a-premise").inputValue()).length).toBe(20500);
  // …y no se guardó.
  const state = await (await request.get(`${API}/authoring/stories/${sid}`)).json();
  expect(state.direction.premise.length).toBe(20000);
});

test("un hecho de 700 caracteres se guarda entero", async ({ page, request }) => {
  const sid = await crear(request);
  const resp = await request.post(`${API}/stories/${sid}/jobs`, { data: { kind: "plan_outline" } });
  const { job_id } = await resp.json();
  await expect
    .poll(async () => (await (await request.get(`${API}/jobs/${job_id}`)).json()).status, { timeout: 20_000 })
    .toBe("done");

  await page.goto(`/asistente/${sid}/escaleta`);
  const hecho = page.locator('[data-acto="1"] textarea[name="events"]').first();
  const largo = idea(700);
  await hecho.fill(largo);
  await guardado(page);
  await page.reload();
  await expect(page.locator('[data-acto="1"] textarea[name="events"]').first()).toHaveValue(largo.trim());
});
