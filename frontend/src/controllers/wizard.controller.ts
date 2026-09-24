import { Request, Response } from "express";
import axios from "axios";
import {
  STEPS,
  getStep,
  saveStepData,
  getStepData,
  WizardData,
  WizardField,
  mapStoryToWizard,
  namedCharacters,
  dropInvalidNatures,
  entityCardsWithoutNature,
  sessionGenre,
} from "../services/wizard.service";
import { mapWizardToCore } from "../services/mapper.service";
import { createStory, updateStory } from "../services/core_api.service";
import { getGenreCatalog, naturesOf, subgenresOf } from "../services/catalog.service";
import { renderPage } from "../utils/render";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

type WizardSession = Request["session"] & { wizard?: WizardData; wizard_story_id?: string };

export async function loadWizardData(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params as { storyId: string };
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    const session = req.session as WizardSession;
    session.wizard = mapStoryToWizard(
      resp.data as Record<string, unknown>,
      (await getGenreCatalog()) ?? undefined,
    );
    session.wizard_story_id = storyId;
    res.redirect("/generar/paso/1");
  } catch {
    res.redirect("/galeria?error=load_failed");
  }
}


async function stepLocals(
  req: Request,
  stepNumber: number,
  fieldErrors: Record<string, string> = {},
) {
  const step   = getStep(stepNumber)!;
  const saved  = getStepData(req.session as WizardSession, step.id);
  const isLast = stepNumber === STEPS.length;
  // Spec-440 §2: solo se consulta el Core si el paso tiene combos del catálogo.
  const genreCatalog = step.fields.some((f) => f.source === "genre_catalog")
    ? await getGenreCatalog()
    : null;
  const characters = namedCharacters(saved);
  const entityNatures = step.fields.some((f) => f.source === "entity_natures")
    ? await allowedNatures(req.session as WizardSession)
    : null;
  return { step, saved, steps: STEPS, isLast, genreCatalog, characters, entityNatures, fieldErrors };
}

/**
 * Spec-450 §4: naturalezas de entidad del género elegido en el paso 1.
 * `null` = no se pueden ofrecer (Core caído o sin género); el combo se deshabilita.
 */
async function allowedNatures(session: WizardSession) {
  const catalog = await getGenreCatalog();
  const genre = sessionGenre(session.wizard);
  if (!catalog || !genre) return null;
  return naturesOf(catalog, genre);
}

export function wizardRedirect(req: Request, res: Response): void {
  const session = req.session as WizardSession;
  delete session.wizard_story_id;
  res.redirect("/generar/paso/1");
}

export async function showStep(req: Request, res: Response): Promise<void> {
  const num = parseInt(req.params["step"] as string, 10);
  if (!getStep(num)) { res.redirect("/generar/paso/1"); return; }
  // Con saveUninitialized: false, una sesión nueva no tiene cookie hasta que se
  // modifica. Sin esto, los primeros auto-saves (p. ej. género + subgénero al
  // mismo tiempo) creaban cada uno su propia sesión y se pisaban.
  const session = req.session as WizardSession;
  session.wizard ??= {};
  await renderPage(res, "wizard", {
    title: "Generar Historia",
    activePage: "generate",
    ...(await stepLocals(req, num)),
  });
}

export async function submitStep(req: Request, res: Response): Promise<void> {
  const num  = parseInt(req.params["step"] as string, 10);
  const step = getStep(num);
  if (!step) { res.redirect("/generar/paso/1"); return; }

  const existingData = getStepData(req.session as WizardSession, step.id);
  const data: Record<string, string> = { ...existingData };

  for (const field of step.fields) {
    if (req.body[field.name] !== undefined) {
      if (field.type === "multi-select") {
        const raw = req.body[field.name];
        const arr = Array.isArray(raw) ? raw : (raw ? [raw as string] : []);
        data[field.name] = JSON.stringify(arr);
      } else {
        const value = (req.body[field.name] ?? "").toString().trim();
        if (value) {
          data[field.name] = value;
        } else {
          // Campo vaciado (p. ej. el nombre de un personaje borrado): mismo criterio que el auto-save.
          delete data[field.name];
        }
      }
    }
  }
  await dropInvalidSubgenre(step.fields, data);
  const fieldErrors = {
    ...invalidCharacterRefs(step.fields, data),
    ...(await invalidEntityCards(step.fields, data, req.session as WizardSession)),
  };
  saveStepData(req.session as WizardSession, step.id, data);

  if (Object.keys(fieldErrors).length > 0) {
    res.status(422);
    await renderPage(res, "wizard", {
      title: "Generar Historia",
      activePage: "generate",
      ...(await stepLocals(req, num, fieldErrors)),
    });
    return;
  }

  const next = num + 1;
  // Spec-460 §2.5: el último paso ya no guarda en silencio; se guarda con el
  // botón explícito "Guardar historia" de la confirmación.
  res.redirect(next > STEPS.length ? "/generar/confirmar" : `/generar/paso/${next}`);
}

/**
 * Spec-440 §2: el subgénero sale de la sesión si quedó vacío (combo reseteado
 * o deshabilitado, que no se envía) o si no pertenece al género elegido.
 */
async function dropInvalidSubgenre(
  fields: WizardField[],
  data: Record<string, string>,
): Promise<void> {
  for (const field of fields) {
    if (field.source !== "genre_catalog" || !field.depends_on) continue;
    const value = optionValueId(data[field.name]);
    if (!value) {
      delete data[field.name];
      continue;
    }
    const catalog = await getGenreCatalog();
    const parent = optionValueId(data[field.depends_on]);
    if (catalog && !subgenresOf(catalog, parent).some((s) => s.id === value)) {
      delete data[field.name];
    }
  }
}

const MSG_NARRADOR_INVALIDO = "Elegí uno de los personajes con nombre.";

/**
 * Spec-440 §5: un campo `source: characters` debe apuntar a un personaje con
 * nombre. Si no, se descarta de la sesión y se devuelve el error del campo.
 */
function invalidCharacterRefs(
  fields: WizardField[],
  data: Record<string, string>,
): Record<string, string> {
  const errors: Record<string, string> = {};
  const valid = namedCharacters(data).map((c) => c.value);
  for (const field of fields) {
    if (field.source !== "characters") continue;
    if (!valid.includes(optionValueId(data[field.name]))) {
      delete data[field.name];
      errors[field.name] = MSG_NARRADOR_INVALIDO;
    }
  }
  return errors;
}

const msgEntitySinNaturaleza = (n: number) =>
  `Elegí qué es la entidad ${n} (o borrala con el tacho).`;

/**
 * Spec-450 §4: descarta las naturalezas que no corresponden al género y marca
 * las cards con datos pero sin naturaleza (el Core la exige).
 */
async function invalidEntityCards(
  fields: WizardField[],
  data: Record<string, string>,
  session: WizardSession,
): Promise<Record<string, string>> {
  if (!fields.some((f) => f.source === "entity_natures")) return {};
  const natures = await allowedNatures(session);
  if (natures) dropInvalidNatures(data, natures.map((n) => n.id));
  const errors: Record<string, string> = {};
  for (const n of entityCardsWithoutNature(data)) {
    errors[`entity_${n}_nature`] = msgEntitySinNaturaleza(n);
  }
  return errors;
}

/** Antes de guardar: el género pudo cambiar después del paso 4. */
async function entitySaveError(session: WizardSession): Promise<string | null> {
  const world = session.wizard?.["step_world"];
  if (!world) return null;
  const natures = await allowedNatures(session);
  if (natures) dropInvalidNatures(world, natures.map((n) => n.id));
  const missing = entityCardsWithoutNature(world);
  if (missing.length === 0) return null;
  return `La entidad ${missing.join(", ")} quedó sin «Qué es» (¿cambiaste el tipo de horror?). `
    + "Elegila en el paso «El Mundo» antes de guardar.";
}

function optionValueId(value: string | undefined): string {
  return (value ?? "").split(":")[0].trim();
}

/** Mensaje legible de un error del Core (detail string, lista de Pydantic o red). */
function coreErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { loc?: unknown[]; msg?: string }) =>
          [Array.isArray(d.loc) ? d.loc.slice(1).join(".") : "", d.msg].filter(Boolean).join(": "),
        )
        .join(" · ");
    }
    if (!err.response) return "El servidor no responde. Verificá que el Core esté levantado.";
    return `Error ${err.response.status} del servidor`;
  }
  return err instanceof Error ? err.message : String(err);
}

/**
 * "Guardar historia" (Spec-460 §2.5): POST si es nueva, PATCH si se está editando.
 * Éxito → galería con la tarjeta resaltada. Error → la confirmación lo muestra.
 */
export async function saveWizardStory(req: Request, res: Response): Promise<void> {
  const session = req.session as WizardSession;
  if (!session.wizard || Object.keys(session.wizard).length === 0) {
    res.redirect("/generar/paso/1");
    return;
  }
  const entityError = await entitySaveError(session);
  if (entityError) {
    await renderConfirm(req, res, entityError);
    return;
  }
  const coreDto = mapWizardToCore(session.wizard) as unknown as Record<string, unknown>;

  try {
    let storyId = session.wizard_story_id;
    let flash = "saved";
    if (storyId) {
      const updated = (await updateStory(storyId, coreDto)) as { status?: string };
      // Spec-440 §8: editar una historia generada no cambia lo ya narrado.
      if (updated?.status === "completed" || updated?.status === "failed") {
        flash = "saved_regenerar";
      }
    } else {
      storyId = (await createStory(coreDto, "save")).id;
      session.wizard_story_id = storyId;
    }
    res.redirect(`/galeria?success=${flash}&guardada=${encodeURIComponent(storyId)}`);
  } catch (err: unknown) {
    await renderConfirm(req, res, coreErrorMessage(err));
  }
}

async function renderConfirm(req: Request, res: Response, saveError: string): Promise<void> {
  const session = req.session as WizardSession;
  res.status(422);
  await renderPage(res, "wizard-confirm", {
    title: "Confirmar Historia",
    activePage: "generate",
    steps: STEPS,
    wizard: session.wizard,
    storyId: session.wizard_story_id ?? null,
    saveError,
    genreCatalog: await getGenreCatalog(),
  });
}

export async function confirmPage(req: Request, res: Response): Promise<void> {
  const session = req.session as WizardSession;
  const wizard  = session.wizard ?? {};
  const storyId = session.wizard_story_id ?? null;

  await renderPage(res, "wizard-confirm", {
    title: "Confirmar Historia",
    activePage: "generate",
    steps: STEPS,
    wizard,
    storyId,
    saveError: null,
    genreCatalog: await getGenreCatalog(),
  });
}

export async function autoSaveField(req: Request, res: Response): Promise<void> {
  const num = parseInt(req.params["step"] as string, 10);
  const step = getStep(num);
  if (!step) {
    res.status(400).json({ error: "Paso inválido" });
    return;
  }

  const { fieldName, fieldValue, fieldType } = req.body;
  if (!fieldName) {
    res.status(400).json({ error: "Nombre de campo requerido" });
    return;
  }

  const existingData = getStepData(req.session as WizardSession, step.id);
  const data: Record<string, string> = { ...existingData };

  if (fieldType === "multi-select") {
    const arr = Array.isArray(fieldValue) ? fieldValue : (fieldValue ? [fieldValue] : []);
    if (arr.length > 0) {
      data[fieldName] = JSON.stringify(arr);
    } else {
      // Vacío = el usuario desmarcó todo o eliminó la card → purgar de sesión.
      delete data[fieldName];
    }
  } else {
    const value = String(fieldValue ?? "");
    if (value) {
      data[fieldName] = value;
    } else {
      // Vacío = el usuario borró el campo o eliminó la card → purgar de sesión.
      delete data[fieldName];
    }
  }

  saveStepData(req.session as WizardSession, step.id, data);
  res.json({ success: true, saved: { fieldName, step: num } });
}
