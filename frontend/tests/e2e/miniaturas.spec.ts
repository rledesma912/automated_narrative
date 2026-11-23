import { test, expect } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Spec-790 §10.7 (T5.6): la sección «Miniaturas» sin usar la GPU: el menú, la lista, el
 * formulario que se guarda solo, subir un boceto con su vista previa, el color que esconde
 * el tono y «Armar las 4» que avisa lo que falta. Arnés con DB descartable.
 */
let STORY_ID = "";
test.beforeAll(async ({ request }) => {
  STORY_ID = await storyIdByTitle(request, "El monte prohibido");
});

test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Sube bocetos: solo contra el arnés con DB descartable");

// Un PNG de 1 × 1.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

test("«Miniaturas» en el menú lleva a la lista y a la historia", async ({ page }) => {
  await page.goto("/");
  await page.locator('aside a[href="/miniaturas"]').click();
  await page.waitForURL(/\/miniaturas$/);
  await page.locator(`[data-miniatura-historia="${STORY_ID}"]`).first().click();
  await page.waitForURL(new RegExp(`/miniaturas/${STORY_ID}$`));
  await expect(page.locator("[data-miniatura]")).toBeVisible();
  await expect(page.locator("h3")).toContainText(["¿Quién va", "El personaje", "El escenario", "El color", "Las 4"]);
});

test("el formulario se guarda solo y el boceto se ve después de subirlo", async ({ page, request }) => {
  await page.goto(`/miniaturas/${STORY_ID}`);
  await page.locator("#m-figura").fill("Una criatura altísima y flaca, con los ojos blancos que brillan.");
  await page.locator('[data-boceto="personaje"] [data-subir-boceto]').setInputFiles({
    name: "personaje.png", mimeType: "image/png", buffer: PNG,
  });
  await expect(page.locator('[data-boceto="personaje"] [data-boceto-img]')).toBeVisible();
  await expect(page.locator("#m-figura")).toHaveValue(/criatura altísima/);
  const vista = await (await request.get(`/api/v1/stories/${STORY_ID}/thumbnail`)).json();
  expect(vista.input.character_sketch).toBe("bocetos/personaje.png");
});

test("blanco y negro esconde el tono", async ({ page }) => {
  await page.goto(`/miniaturas/${STORY_ID}`);
  await expect(page.locator("[data-tono]")).toBeVisible();
  await page.locator('label:has(input[name="color"][value="byn"])').click();
  await expect(page.locator("[data-tono]")).toBeHidden();
  await page.reload();
  await expect(page.locator('input[name="color"][value="byn"]')).toBeChecked();
});

test("«Armar las 4» sin el boceto del escenario avisa lo que falta", async ({ page }) => {
  await page.goto(`/miniaturas/${STORY_ID}`);
  let jobs = 0;
  page.on("request", (r) => r.method() === "POST" && r.url().includes("/jobs") && jobs++);
  await page.locator("[data-armar]").click();
  await page.locator("#forge-confirm").getByRole("button", { name: "Armar" }).click();
  await expect(page.locator("[data-armar-error]")).toContainText("Falta el boceto del escenario");
  expect(jobs).toBe(1);
});
