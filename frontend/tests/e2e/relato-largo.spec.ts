import { test, expect, type Page } from "@playwright/test";

/**
 * Spec-750 S5: la larga (5 actos, ~35 min) de punta a punta con el LLM simulado: se elige
 * en «¿Qué tan largo?», tiene los mismos actos que la media, lleva el chip y su versión
 * guarda el largo (el video la toma como larga aunque tenga 5 actos).
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

const guardado = (page: Page) => page.locator("[data-guardado]").first();
async function guardadoListo(page: Page) {
  await expect(guardado(page)).not.toHaveAttribute("data-pendiente", "1");
  await expect(guardado(page)).toContainText("Guardado");
}

let sid = "";
const TITULO = `E2E larga ${Date.now()}`;

test("«¿Qué tan largo?» ofrece los tres y una historia nueva arranca en la media", async ({ page }) => {
  await page.goto("/nuevo");
  const radios = page.locator("[data-largo-opciones] input[name='structure']");
  await expect(radios).toHaveCount(3);
  expect(await radios.evaluateAll((els) => els.map((e) => (e as HTMLInputElement).value))).toEqual([
    "corto",
    "medio",
    "largo",
  ]);
  await expect(page.getByRole("radio", { name: /Media/ })).toBeChecked();
  await expect(page.locator("[data-largo-opciones]")).toContainText("unos 35 minutos");
});

test("crear una larga, armar sus 5 actos y escribirla", async ({ page, request }) => {
  await page.goto("/nuevo");
  await page.getByText("Larga", { exact: true }).click();
  await page.getByLabel("Título").fill(TITULO);
  await page.getByLabel("¿De qué trata?").fill("Ana escucha pasos en el techo de la casa vieja.");
  await expect(page).toHaveURL(/\/asistente\/[0-9a-f-]{36}\/direccion$/);
  await guardadoListo(page);
  sid = page.url().split("/")[4];
  expect((await (await request.get(`/api/v1/authoring/stories/${sid}`)).json()).structure).toBe("largo");

  await page.getByRole("button", { name: /Que la IA me pregunte/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/taller$`));
  await page.getByRole("button", { name: /Armar los actos/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/escaleta$`));
  await expect(page.getByRole("heading", { name: "Acto 3 · El peor momento" })).toBeVisible();
  await expect(page.locator("form[data-autosave='act']")).toHaveCount(5);

  await page.locator(".asistente-barra").getByRole("button", { name: /Escribir el relato/ }).click();
  await page.locator("#forge-confirm").getByRole("button", { name: "Escribir el relato" }).click();
  await expect(page.locator("#beat-dots [id^='dot-']")).toHaveCount(5);
  await expect(page.locator("#status-line")).toHaveText("Tu relato está listo", { timeout: 30_000 });
});

test("«El relato» y «Mis historias» marcan la larga, y la versión guarda su largo", async ({ page, request }) => {
  await page.goto(`/historia/${sid}/relatos`);
  await expect(page.locator("h2 [data-larga]")).toHaveText("Larga");
  await expect(page.locator("[data-regenerar-acto]")).toHaveCount(5);
  await expect(page.locator("[data-otro-largo]")).toHaveCount(0);

  const [version] = await (await request.get(`/api/v1/story-templates/${sid}/narratives`)).json();
  expect(version.structure).toBe("largo");

  await page.goto("/galeria");
  const card = page.locator("[data-story-card]", { has: page.getByRole("heading", { name: TITULO }) });
  await expect(card.locator("[data-larga]")).toHaveText("Larga");
});
