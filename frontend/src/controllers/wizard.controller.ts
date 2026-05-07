import { Request, Response } from "express";
import axios from "axios";
import { STEPS, getStep, saveStepData, getStepData, WizardData, mapStoryToWizard } from "../services/wizard.service";
import { mapWizardToCore } from "../services/mapper.service";
import { createStory, updateStory } from "../services/core_api.service";
import { renderPage } from "../utils/render";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

type WizardSession = Request["session"] & { wizard?: WizardData; wizard_story_id?: string };

export async function loadWizardData(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params as { storyId: string };
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    const session = req.session as WizardSession;
    session.wizard = mapStoryToWizard(resp.data as Record<string, unknown>);
    session.wizard_story_id = storyId;
    res.redirect("/generar/paso/1");
  } catch {
    res.redirect("/galeria?error=load_failed");
  }
}


function stepLocals(req: Request, stepNumber: number) {
  const step   = getStep(stepNumber)!;
  const saved  = getStepData(req.session as WizardSession, step.id);
  const isLast = stepNumber === STEPS.length;
  return { step, saved, steps: STEPS, isLast };
}

export function wizardRedirect(req: Request, res: Response): void {
  const session = req.session as WizardSession;
  delete session.wizard_story_id;
  res.redirect("/generar/paso/1");
}

export async function showStep(req: Request, res: Response): Promise<void> {
  const num = parseInt(req.params["step"] as string, 10);
  if (!getStep(num)) { res.redirect("/generar/paso/1"); return; }
  await renderPage(res, "wizard", {
    title: "Generar Historia",
    activePage: "generate",
    ...stepLocals(req, num),
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
        }
      }
    }
  }
  saveStepData(req.session as WizardSession, step.id, data);

  const next = num + 1;
  if (next > STEPS.length) {
    // Último paso: persistir en DB (POST si nuevo, PATCH si ya existe)
    const session = req.session as WizardSession;
    const wizard  = session.wizard ?? {};
    const coreDto = mapWizardToCore(wizard) as unknown as Record<string, unknown>;

    try {
      if (session.wizard_story_id) {
        await updateStory(session.wizard_story_id, coreDto);
      } else {
        const story = await createStory(coreDto, "save");
        session.wizard_story_id = story.id;
      }
    } catch {
      // Si la persistencia falla, igual avanzamos a confirmar
    }

    res.redirect("/generar/confirmar");
  } else {
    res.redirect(`/generar/paso/${next}`);
  }
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
    }
  } else {
    const value = String(fieldValue ?? "");
    if (value) {
      data[fieldName] = value;
    }
  }

  saveStepData(req.session as WizardSession, step.id, data);
  res.json({ success: true, saved: { fieldName, step: num } });
}
