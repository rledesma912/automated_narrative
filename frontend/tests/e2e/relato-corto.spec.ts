import { test, expect, type Page } from "@playwright/test";

/**
 * Spec-650 S3: el relato corto (3 actos, ~7 min) de punta a punta con el LLM simulado,
 * y el cambio de largo con su confirmación (§2.5, D9–D11).
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

const guardado = (page: Page) => page.locator("[data-guardado]").first();
async function guardadoListo(page: Page) {
  await expect(guardado(page)).not.toHaveAttribute("data-pendiente", "1");
  await expect(guardado(page)).toContainText("Guardado");
}
const dialogo = (page: Page) => page.locator("dialog[open]");

let sid = "";
// Título único: la DB del arnés sobrevive entre corridas (y con --repeat-each).
const TITULO = `E2E corto ${Date.now()}`;

test("crear un corto, armar sus 3 actos y escribirlo", async ({ page, request }) => {
  await page.goto("/nuevo");
  // El largo se elige antes de que exista la historia: viaja con el alta.
  await page.getByText("Corto", { exact: true }).click();
  await page.getByLabel("Título").fill(TITULO);
  await page.getByLabel("¿De qué trata?").fill("Ana escucha pasos en el techo de la casa vieja.");
  await expect(page).toHaveURL(/\/asistente\/[0-9a-f-]{36}\/direccion$/);
  await guardadoListo(page);
  sid = page.url().split("/")[4];
  const story = await (await request.get(`/api/v1/authoring/stories/${sid}`)).json();
  expect(story.structure).toBe("corto");

  // Lo que se guarda solo en «Tu idea» no cambia el largo (D9).
  await page.getByText("Pavor creciente").click();
  await guardadoListo(page);
  await page.reload();
  await expect(page.getByRole("radio", { name: /Corto/ })).toBeChecked();

  await page.getByRole("button", { name: /Que la IA me pregunte/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/taller$`));
  await page.getByRole("button", { name: /Armar los actos/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/escaleta$`));

  await expect(page.getByText(/Los tres actos de tu historia/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Acto 1 · Cómo empieza" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Acto 2 · Qué pasa" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Acto 3 · Cómo termina" })).toBeVisible();
  await expect(page.locator("form[data-autosave='act']")).toHaveCount(3);
  // «Se descubre en» solo ofrece actos que existen.
  await expect(page.locator("#reveal-1 option")).toHaveText(["—", "el Acto 2", "el Acto 3"]);
  await expect(page.locator("#reveal-3")).toHaveCount(0);

  await page.getByRole("link", { name: /Escribir el relato/ }).click();
  await expect(page.locator("#beat-dots [id^='dot-']")).toHaveCount(3);
  await page.getByRole("button", { name: "Escribir el relato" }).click();
  await expect(page.locator("#status-line")).toHaveText("Tu relato está listo", { timeout: 30_000 });
  const log = await page.locator("#log-container > div").allTextContents();
  expect(log.some((l) => l.includes("Escribiendo el acto 1 de 3"))).toBe(true);
  expect(log.some((l) => l.includes("de 5"))).toBe(false);
});

test("«El relato» y «Mis historias» marcan el corto", async ({ page }) => {
  await page.goto(`/historia/${sid}/relatos`);
  await expect(page.locator("h2 [data-corto]")).toHaveText("Corto");
  await expect(page.locator("[data-regenerar-acto]")).toHaveCount(3);
  await expect(page.locator("[data-otro-largo]")).toHaveCount(0);

  await page.goto("/galeria");
  const card = page.locator("[data-story-card]", { has: page.getByRole("heading", { name: TITULO }) });
  await expect(card.locator("[data-corto]")).toHaveText("Corto");
});

test("S4: corregir y armar el guion del corto usan su largo (6–8 min)", async ({ page }) => {
  await page.goto(`/historia/${sid}/relatos`);
  const narrativeId = await page.locator("[data-relato-panel].active").getAttribute("data-relato-panel");

  await page.goto(`/historia/${sid}/relatos/${narrativeId}/corregir`);
  await expect(page.locator("[data-duracion-estado]")).toContainText("(6–8 min)");

  await page.goto(`/historia/${sid}/relatos`);
  await page.locator(`[data-acciones-version="${narrativeId}"] [data-armar-guion]`).click();
  await page.locator("#forge-confirm").getByRole("button", { name: "Armar el guion" }).click();
  await page.waitForURL(new RegExp(`/relatos/${narrativeId}/video$`), { timeout: 20_000 });
  await expect(page.locator("[data-bloque]").first()).toBeVisible();
});

test("cambiar el largo pide confirmación; cancelar no cambia nada", async ({ page, request }) => {
  await page.goto(`/asistente/${sid}/direccion`);
  await page.getByText("Largo", { exact: true }).click();
  await expect(dialogo(page)).toContainText("Los actos que armaste se borran");
  await dialogo(page).getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByRole("radio", { name: /Corto/ })).toBeChecked();
  let story = await (await request.get(`/api/v1/authoring/stories/${sid}`)).json();
  expect(story.structure).toBe("corto");
  expect(story.outline.acts).toHaveLength(3);

  await page.getByText("Largo", { exact: true }).click();
  await dialogo(page).getByRole("button", { name: "Cambiar el largo" }).click();
  await guardadoListo(page);
  story = await (await request.get(`/api/v1/authoring/stories/${sid}`)).json();
  expect(story.structure).toBe("largo");
  expect(story.outline.acts).toHaveLength(0);

  // Los actos se arman de nuevo, ahora cinco.
  await page.goto(`/asistente/${sid}/escaleta`);
  await expect(page.getByText("Todavía no armaste los actos")).toBeVisible();
  await expect(page.getByText(/en cinco actos/).first()).toBeVisible();

  // La versión corta se sigue leyendo, pero no se regenera por actos (D11).
  await page.goto(`/historia/${sid}/relatos`);
  await expect(page.locator("[data-otro-largo]")).toBeVisible();
  await expect(page.locator("[data-regenerar-acto]")).toHaveCount(0);
  await expect(page.locator("h2 [data-corto]")).toHaveCount(0);
});

test("elegir «Corto» después de crear la historia (sin actos) no pide confirmación", async ({ page, request }) => {
  await page.goto("/nuevo");
  await page.getByLabel("Título").fill("E2E corto después");
  await expect(page).toHaveURL(/\/asistente\/[0-9a-f-]{36}\/direccion$/);
  await guardadoListo(page);
  const id = page.url().split("/")[4];
  expect((await (await request.get(`/api/v1/authoring/stories/${id}`)).json()).structure).toBe("largo");

  await page.getByText("Corto", { exact: true }).click();
  await guardadoListo(page);
  await expect(dialogo(page)).toHaveCount(0);
  expect((await (await request.get(`/api/v1/authoring/stories/${id}`)).json()).structure).toBe("corto");
});
