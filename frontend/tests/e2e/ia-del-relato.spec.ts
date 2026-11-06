import { test, expect } from "@playwright/test";

import { storyIdByTitle } from "./support/stories";

/** Spec-740 C2: cada versión dice qué IA la escribió; las viejas, nada. */
test.skip(!!process.env.BASE_URL, "Escribe un relato: solo contra el arnés con DB descartable");

test("un relato nuevo dice qué IA lo escribió y uno viejo no dice nada", async ({ page, request }) => {
  const storyId = await storyIdByTitle(request, "El monte prohibido");
  const antes = (await (await request.get(`/api/v1/story-templates/${storyId}/narratives`)).json()) as Array<{ id: string }>;

  const resp = await request.post(`/api/v1/stories/${storyId}/jobs`, { data: { kind: "full_generation" } });
  expect(resp.status()).toBe(202);
  const jobId = (await resp.json()).job_id;
  await expect
    .poll(async () => (await (await request.get(`/api/v1/jobs/${jobId}`)).json()).status, { timeout: 60_000 })
    .toBe("done");
  const nuevo = (await (await request.get(`/api/v1/jobs/${jobId}`)).json()).narrative_id;

  await page.goto(`/historia/${storyId}/relatos`);
  await page.locator(`[data-relato-tab="${nuevo}"]`).click();
  const panelNuevo = page.locator(`[data-relato-panel="${nuevo}"]`);
  await expect(panelNuevo.locator("[data-ia-relato]")).toContainText("Lo escribió IA de prueba.");
  await panelNuevo.locator("[data-ia-detalle] summary").click();
  await expect(panelNuevo.locator("[data-ia-detalle]")).toContainText("La memoria de cada acto: IA de prueba");

  // Una versión sin registro (de la siembra; otros E2E ya escriben con registro): nada.
  let viejo: { id: string } | undefined;
  for (const r of antes) {
    const ia = await (await request.get(`/api/v1/generated-narratives/${r.id}/ia`)).json();
    if (!ia.modelos.length) {
      viejo = r;
      break;
    }
  }
  if (viejo) {
    await page.locator(`[data-relato-tab="${viejo.id}"]`).click();
    await expect(page.locator(`[data-relato-panel="${viejo.id}"] [data-ia-relato]`)).toHaveCount(0);
  }
});
