import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../../src/services/core_api.service", () => ({
  createStory: vi.fn(),
  updateStory: vi.fn(),
}));
vi.mock("../../../src/utils/render", () => ({
  renderPage: vi.fn(async () => undefined),
}));

import { createStory, updateStory } from "../../../src/services/core_api.service";
import { renderPage } from "../../../src/utils/render";
import { saveWizardStory, submitStep } from "../../../src/controllers/wizard.controller";
import { STEPS } from "../../../src/services/wizard.service";
import type { Request, Response } from "express";

const create = createStory as unknown as ReturnType<typeof vi.fn>;
const update = updateStory as unknown as ReturnType<typeof vi.fn>;
const render = renderPage as unknown as ReturnType<typeof vi.fn>;

const WIZARD = { step_config_title: { title: "La pena del colectivo" } };

function makeRes() {
  const res = { redirect: vi.fn(), status: vi.fn() } as unknown as Response & {
    redirect: ReturnType<typeof vi.fn>;
    status: ReturnType<typeof vi.fn>;
  };
  (res.status as ReturnType<typeof vi.fn>).mockReturnValue(res);
  return res;
}

function axiosError(status: number | null, detail?: unknown) {
  return Object.assign(new Error("axios"), {
    isAxiosError: true,
    response: status === null ? undefined : { status, data: { detail } },
  });
}

/** Spec-460 §2.5: el wizard termina en "Guardar historia"; se genera desde la galería. */
describe("saveWizardStory", () => {
  beforeEach(() => vi.clearAllMocks());

  it("historia nueva: la crea como borrador y vuelve a la galería resaltándola", async () => {
    create.mockResolvedValue({ id: "s-1" });
    const session: Record<string, unknown> = { wizard: WIZARD };
    const res = makeRes();

    await saveWizardStory({ session } as unknown as Request, res);

    expect(create).toHaveBeenCalledWith(expect.objectContaining({ title: "La pena del colectivo" }), "save");
    expect(update).not.toHaveBeenCalled();
    expect(session.wizard_story_id).toBe("s-1");
    expect(res.redirect).toHaveBeenCalledWith("/galeria?success=saved&guardada=s-1");
  });

  it("edición: actualiza la historia existente (PATCH), no crea otra", async () => {
    update.mockResolvedValue({ id: "s-9" });
    const res = makeRes();

    await saveWizardStory(
      { session: { wizard: WIZARD, wizard_story_id: "s-9" } } as unknown as Request,
      res,
    );

    expect(update).toHaveBeenCalledWith("s-9", expect.any(Object));
    expect(create).not.toHaveBeenCalled();
    expect(res.redirect).toHaveBeenCalledWith("/galeria?success=saved&guardada=s-9");
  });

  it("editar una historia ya generada avisa que hay que regenerar", async () => {
    update.mockResolvedValue({ id: "s-9", status: "completed" });
    const res = makeRes();

    await saveWizardStory(
      { session: { wizard: WIZARD, wizard_story_id: "s-9" } } as unknown as Request,
      res,
    );

    expect(res.redirect).toHaveBeenCalledWith("/galeria?success=saved_regenerar&guardada=s-9");
  });

  it("con una generación en curso (409) muestra el aviso del Core", async () => {
    update.mockRejectedValue(
      axiosError(409, "Hay una generación en curso; esperá a que termine para editar"),
    );
    const res = makeRes();

    await saveWizardStory(
      { session: { wizard: WIZARD, wizard_story_id: "s-9" } } as unknown as Request,
      res,
    );

    expect(render.mock.calls[0]![2].saveError).toMatch(/generación en curso/);
  });

  it("error de validación del Core: se muestra en la confirmación (no se oculta)", async () => {
    create.mockRejectedValue(
      axiosError(422, [
        { loc: ["body", "title"], msg: "Field required" },
        { loc: ["body", "sinopsis"], msg: "String too short" },
      ]),
    );
    const res = makeRes();

    await saveWizardStory({ session: { wizard: WIZARD } } as unknown as Request, res);

    expect(res.redirect).not.toHaveBeenCalled();
    expect(res.status).toHaveBeenCalledWith(422);
    const [, view, locals] = render.mock.calls[0]!;
    expect(view).toBe("wizard-confirm");
    expect(locals.saveError).toBe("title: Field required · sinopsis: String too short");
  });

  it("error con detail de texto: se muestra tal cual", async () => {
    update.mockRejectedValue(axiosError(422, "Solo se pueden editar historias en estado draft"));
    const res = makeRes();

    await saveWizardStory(
      { session: { wizard: WIZARD, wizard_story_id: "s-9" } } as unknown as Request,
      res,
    );

    expect(render.mock.calls[0]![2].saveError).toBe(
      "Solo se pueden editar historias en estado draft",
    );
  });

  it("Core caído: mensaje claro", async () => {
    create.mockRejectedValue(axiosError(null));
    const res = makeRes();

    await saveWizardStory({ session: { wizard: WIZARD } } as unknown as Request, res);

    expect(render.mock.calls[0]![2].saveError).toMatch(/servidor no responde/);
  });

  it("sin datos en la sesión vuelve al paso 1", async () => {
    const res = makeRes();

    await saveWizardStory({ session: {} } as unknown as Request, res);

    expect(res.redirect).toHaveBeenCalledWith("/generar/paso/1");
    expect(create).not.toHaveBeenCalled();
  });
});

describe("submitStep (último paso)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("ya no guarda en silencio: solo avanza a la confirmación", async () => {
    const last = STEPS.length;
    const res = makeRes();

    await submitStep(
      { params: { step: String(last) }, body: {}, session: { wizard: WIZARD } } as unknown as Request,
      res,
    );

    expect(res.redirect).toHaveBeenCalledWith("/generar/confirmar");
    expect(create).not.toHaveBeenCalled();
    expect(update).not.toHaveBeenCalled();
  });
});
