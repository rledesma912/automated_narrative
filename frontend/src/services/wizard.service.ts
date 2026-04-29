import { Session } from "express-session";
import { loadSteps } from "./form_renderer.service";

export interface WizardField {
  name: string;
  label: string;
  type: "text" | "textarea" | "select" | "radio" | "multi-select";
  required: boolean;
  placeholder?: string;
  rows?: number;
  hint?: string;
  options?: string[];
  subtitle?: string;
  note?: string;
  group?: string;
  default?: string;
}

export interface WizardStep {
  id: string;
  number: number;
  title: string;
  subtitle?: string;
  fields: WizardField[];
}

export interface WizardData {
  [stepId: string]: Record<string, string> | undefined;
}

// Cargado una sola vez al iniciar el proceso — fuente de verdad: ui_definitions.yaml
export const STEPS: WizardStep[] = loadSteps();

export function getStep(number: number): WizardStep | undefined {
  return STEPS.find((s) => s.number === number);
}

export function getStepById(id: string): WizardStep | undefined {
  return STEPS.find((s) => s.id === id);
}

export function saveStepData(
  session: Session & { wizard?: WizardData },
  stepId: string,
  data: Record<string, string>
): void {
  if (!session.wizard) session.wizard = {};
  session.wizard[stepId] = data;
}

export function getStepData(
  session: Session & { wizard?: WizardData },
  stepId: string
): Record<string, string> {
  return session.wizard?.[stepId] ?? {};
}
