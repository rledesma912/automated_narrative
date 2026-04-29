import { Request, Response } from "express";
import { STEPS, getStep, saveStepData, getStepData, WizardData } from "../services/wizard.service";
import { renderPage } from "../utils/render";

type WizardSession = Request["session"] & { wizard?: WizardData };

function stepLocals(req: Request, stepNumber: number) {
  const step   = getStep(stepNumber)!;
  const saved  = getStepData(req.session as WizardSession, step.id);
  const isLast = stepNumber === STEPS.length;
  return { step, saved, steps: STEPS, isLast };
}

export function wizardRedirect(_req: Request, res: Response): void {
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

  const data: Record<string, string> = {};
  for (const field of step.fields) {
    if (field.type === "multi-select") {
      const raw = req.body[field.name];
      const arr = Array.isArray(raw) ? raw : (raw ? [raw as string] : []);
      data[field.name] = JSON.stringify(arr);
    } else {
      data[field.name] = (req.body[field.name] ?? "").toString().trim();
    }
  }
  saveStepData(req.session as WizardSession, step.id, data);

  const next = num + 1;
  if (next > STEPS.length) {
    res.redirect("/generar/confirmar");
  } else {
    res.redirect(`/generar/paso/${next}`);
  }
}

export async function confirmPage(req: Request, res: Response): Promise<void> {
  const wizard = (req.session as WizardSession).wizard ?? {};
  await renderPage(res, "wizard-confirm", {
    title: "Confirmar Historia",
    activePage: "generate",
    steps: STEPS,
    wizard,
  });
}
