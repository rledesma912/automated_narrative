import { test, expect, type Page, type Locator } from "@playwright/test";

/**
 * Spec-630 S2 (B5): las acciones de «Preguntas» y «Los actos» no recargan la
 * página: se reemplaza solo lo que cambió y la pantalla queda donde estaba.
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

let sid = "";

/** Cuenta las navegaciones de la página (una recarga es una navegación). */
function navegaciones(page: Page): () => number {
  let n = 0;
  page.on("framenavigated", (f) => {
    if (f === page.mainFrame()) n++;
  });
  return () => n;
}

const top = (el: Locator) => el.evaluate((e) => e.getBoundingClientRect().top);
const scrollTop = (page: Page) => page.locator("main").evaluate((m) => m.scrollTop);

/** Lleva el elemento a la mitad de la pantalla, con lugar arriba para scrollear. */
async function alMedio(el: Locator) {
  await el.evaluate((e) => e.scrollIntoView({ block: "center" }));
}

test.beforeAll(async ({ browser }) => {
  const page = await browser.newPage();
  await page.goto("/nuevo");
  await page.getByLabel("Título").fill("E2E sin recargar");
  await page.getByLabel("¿De qué trata?").fill("José ve a una mujer muerta en el espejo del micro.");
  await expect(page).toHaveURL(/\/asistente\/[0-9a-f-]{36}\/direccion$/);
  await expect(page.locator("[data-guardado]").first()).not.toHaveAttribute("data-pendiente", "1");
  sid = page.url().split("/")[4];
  await page.getByRole("button", { name: /Que la IA me pregunte/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/taller$`));
  await page.close();
});

test("«Preguntas»: responder no recarga, la siguiente queda en su lugar y no se pierde lo escrito", async ({ page }) => {
  await page.goto(`/asistente/${sid}/taller`);
  const navs = navegaciones(page);
  const abiertas = page.locator("article[data-pregunta]");
  const n = await abiertas.count();
  expect(n).toBeGreaterThan(2);
  const [primera, segunda, ultima] = [abiertas.nth(1), abiertas.nth(2), abiertas.nth(n - 1)];
  const criterio = await primera.getAttribute("data-pregunta");
  const siguiente = await segunda.getAttribute("data-pregunta");
  const ultimaCriterio = await ultima.getAttribute("data-pregunta");

  // Algo escrito en otra pregunta, sin mandar.
  await ultima.getByText("Escribir la mía…").click();
  await ultima.locator("[data-texto-mia]").fill("Todavía lo estoy pensando");

  await alMedio(primera);
  const antes = await top(page.locator(`article[data-pregunta="${siguiente}"]`));
  await primera.locator(".opcion-forge").first().click();
  await primera.getByRole("button", { name: "Guardar respuesta" }).click();

  await expect(page.locator(`li[data-pregunta="${criterio}"]`)).toBeVisible();
  expect(navs()).toBe(0);
  expect(Math.abs((await top(page.locator(`article[data-pregunta="${siguiente}"]`))) - antes)).toBeLessThanOrEqual(4);
  const pendiente = page.locator(`article[data-pregunta="${ultimaCriterio}"] [data-texto-mia]`);
  await expect(pendiente).toHaveValue("Todavía lo estoy pensando");
  await expect(pendiente).toBeVisible();
});

test("«Los actos»: ignorar, volver a mostrar y sumar un personaje no recargan ni mueven la tarjeta", async ({ page }) => {
  await page.goto(`/asistente/${sid}/taller`);
  await page.getByRole("button", { name: /Armar los actos/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/escaleta$`));
  await expect(page.locator("[data-acto]")).toHaveCount(5);
  const navs = navegaciones(page);

  const acto2 = page.locator('[data-acto="2"]');
  const ignorar = acto2.locator("[data-ignorar]").first();
  await alMedio(ignorar);
  const t0 = await top(acto2);
  await ignorar.click();
  await expect(acto2.locator("[data-ignorados]")).toBeVisible();
  expect(navs()).toBe(0);
  expect(Math.abs((await top(acto2)) - t0)).toBeLessThanOrEqual(4);
  await expect(acto2).toBeFocused();

  await acto2.locator("[data-ignorados] summary").click();
  const restaurar = acto2.locator("[data-restaurar]").first();
  await alMedio(restaurar);
  const t1 = await top(acto2);
  await restaurar.click();
  await expect(acto2.locator("[data-ignorados]")).toHaveCount(0);
  expect(navs()).toBe(0);
  expect(Math.abs((await top(acto2)) - t1)).toBeLessThanOrEqual(4);

  // Sumar un personaje en el acto 4: aparece en todos los actos, sin recargar.
  const acto4 = page.locator('[data-acto="4"]');
  await acto4.getByRole("button", { name: "Personaje" }).click();
  await acto4.locator("[data-p-nombre]").fill("La sereno");
  const sumar = acto4.getByRole("button", { name: "Sumar personaje" });
  await alMedio(sumar);
  const t4 = await top(acto4);
  await sumar.click();
  await expect(acto4.getByRole("checkbox", { name: /La sereno/ })).toBeChecked();
  await expect(page.locator('[data-acto="1"]').getByRole("checkbox", { name: /La sereno/ })).not.toBeChecked();
  expect(navs()).toBe(0);
  expect(Math.abs((await top(acto4)) - t4)).toBeLessThanOrEqual(4);
});

test("después de un análisis de la IA la pantalla vuelve a donde estaba", async ({ page }) => {
  await page.goto(`/asistente/${sid}/escaleta`);
  await alMedio(page.locator('[data-acto="3"]'));
  const antes = await scrollTop(page);
  expect(antes).toBeGreaterThan(300);
  await page.getByRole("button", { name: /Que la IA lo revise/ }).click();
  await expect(page.locator("#asistente-analizando")).toBeHidden({ timeout: 20_000 });
  await page.waitForLoadState("load");
  await expect.poll(() => scrollTop(page)).toBeGreaterThan(antes - 40);
  expect(Math.abs((await scrollTop(page)) - antes)).toBeLessThanOrEqual(40);
});
