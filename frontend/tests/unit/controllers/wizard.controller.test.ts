import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../../src/services/core_api.service", () => ({
  createStory: vi.fn(),
  updateStory: vi.fn(),
}));
vi.mock("../../../src/services/catalog.service", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../src/services/catalog.service")>()),
  getGenreCatalog: vi.fn(async () => [
    { id: "folk_horror", label: "Terror Rural", subgenres: [{ id: "rural", label: "Leyendas del campo" }] },
    {
      id: "body_horror",
      label: "Horror Corporal",
      subgenres: [{ id: "contagio", label: "Contagio" }],
      entity_natures: [{ id: "contagio", label: "Contagio / organismo" }],
    },
    {
      id: "suspenso",
      label: "Suspenso",
      subgenres: [],
      entity_natures: [{ id: "humano", label: "Humano" }],
    },
  ]),
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

/** Spec-440 §2: el subgénero no sobrevive si no corresponde al género. */
describe("submitStep (paso 1: género → subgénero)", () => {
  beforeEach(() => vi.clearAllMocks());

  async function submitStep1(body: Record<string, string>, saved: Record<string, string> = {}) {
    const session: Record<string, any> = { wizard: { step_config_title: saved } };
    await submitStep({ params: { step: "1" }, body, session } as unknown as Request, makeRes());
    return session.wizard.step_config_title as Record<string, string>;
  }

  it("par válido: se guardan género y subgénero", async () => {
    const data = await submitStep1({ title: "t", atmosfera: "folk_horror", atmosphere_subgenre: "rural" });
    expect(data).toMatchObject({ atmosfera: "folk_horror", atmosphere_subgenre: "rural" });
  });

  it("subgénero de otro género: se descarta", async () => {
    const data = await submitStep1({ title: "t", atmosfera: "body_horror", atmosphere_subgenre: "rural" });
    expect(data.atmosfera).toBe("body_horror");
    expect(data).not.toHaveProperty("atmosphere_subgenre");
  });

  it("combo deshabilitado (no se envía): se borra el subgénero viejo de la sesión", async () => {
    const data = await submitStep1(
      { title: "t", atmosfera: "body_horror" },
      { atmosfera: "folk_horror", atmosphere_subgenre: "rural" },
    );
    expect(data).not.toHaveProperty("atmosphere_subgenre");
  });

  it("acepta el formato legado «id: Etiqueta»", async () => {
    const data = await submitStep1({
      title: "t",
      atmosfera: "folk_horror: Terror Rural (Leyendas de campo)",
      atmosphere_subgenre: "rural: Leyendas del campo",
    });
    expect(data.atmosphere_subgenre).toBe("rural: Leyendas del campo");
  });
});

/** Spec-440 T4.4: el narrador debe ser un personaje con nombre. */
describe("submitStep (paso 2: narrador)", () => {
  beforeEach(() => vi.clearAllMocks());

  async function submitStep2(body: Record<string, string>, saved: Record<string, string> = {}) {
    const session: Record<string, any> = { wizard: { step_config_personajes: saved } };
    const res = makeRes();
    await submitStep({ params: { step: "2" }, body, session } as unknown as Request, res);
    return { res, data: session.wizard.step_config_personajes as Record<string, string> };
  }

  it("narrador válido: avanza al paso 3", async () => {
    const { res, data } = await submitStep2({
      protagonista_1_name: "Irene",
      protagonista_1_role: "Narradora",
      storyteller_id: "protagonista_1",
    });
    expect(res.redirect).toHaveBeenCalledWith("/generar/paso/3");
    expect(data.storyteller_id).toBe("protagonista_1");
  });

  it("narrador sin nombre: re-renderiza el paso con error y lo descarta", async () => {
    const { res, data } = await submitStep2({
      protagonista_1_name: "Irene",
      storyteller_id: "protagonista_2",
    });
    expect(res.redirect).not.toHaveBeenCalled();
    expect(res.status).toHaveBeenCalledWith(422);
    expect(data).not.toHaveProperty("storyteller_id");
    expect(data.protagonista_1_name).toBe("Irene");
    const locals = render.mock.calls[0][2];
    expect(locals.fieldErrors).toEqual({ storyteller_id: "Elegí uno de los personajes con nombre." });
    expect(locals.characters).toEqual([{ value: "protagonista_1", label: "Irene" }]);
  });

  it("combo deshabilitado (no se envía) con un narrador viejo cuyo personaje se borró", async () => {
    const { res, data } = await submitStep2(
      { protagonista_1_name: "Irene", protagonista_2_name: "" },
      { protagonista_2_name: "Tito", storyteller_id: "protagonista_2" },
    );
    expect(res.status).toHaveBeenCalledWith(422);
    expect(data).not.toHaveProperty("protagonista_2_name");
    expect(data).not.toHaveProperty("storyteller_id");
  });
});

/** Spec-450 T4.2: entidades del paso 4. */
describe("submitStep (paso 4: entidades)", () => {
  beforeEach(() => vi.clearAllMocks());
  const step4 = String(STEPS.findIndex((s) => s.id === "step_world") + 1);

  async function submitStep4(body: Record<string, string>, genre = "suspenso") {
    const session: Record<string, any> = {
      wizard: { step_config_title: { atmosfera: genre }, step_world: {} },
    };
    const res = makeRes();
    await submitStep({ params: { step: step4 }, body, session } as unknown as Request, res);
    return { res, data: session.wizard.step_world as Record<string, string> };
  }

  it("entidad válida: avanza", async () => {
    const { res, data } = await submitStep4({ entity_1_name: "El vecino", entity_1_nature: "humano" });
    expect(res.redirect).toHaveBeenCalledWith(`/generar/paso/${Number(step4) + 1}`);
    expect(data.entity_1_nature).toBe("humano");
  });

  it("naturaleza de otro género: se descarta y la card queda marcada", async () => {
    const { res, data } = await submitStep4({ entity_1_name: "Algo", entity_1_nature: "demonio" });
    expect(res.status).toHaveBeenCalledWith(422);
    expect(data).not.toHaveProperty("entity_1_nature");
    expect(render.mock.calls[0][2].fieldErrors).toEqual({
      entity_1_nature: "Elegí qué es la entidad 1 (o borrala con el tacho).",
    });
  });

  it("sin cards de entidad no hay error", async () => {
    const { res } = await submitStep4({ scenario_1_name: "La casa" });
    expect(res.status).not.toHaveBeenCalled();
  });
});

describe("saveWizardStory con entidades (Spec-450)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("si el género cambió y una entidad quedó sin naturaleza, no guarda y lo explica", async () => {
    const session = {
      wizard: {
        step_config_title: { title: "t", atmosfera: "suspenso" },
        step_world: { entity_1_name: "La Mala Hora", entity_1_nature: "folklorica" },
      },
    };
    const res = makeRes();

    await saveWizardStory({ session } as unknown as Request, res);

    expect(create).not.toHaveBeenCalled();
    expect(res.status).toHaveBeenCalledWith(422);
    expect(render.mock.calls[0][2].saveError).toContain("La entidad 1 quedó sin «Qué es»");
  });
});

