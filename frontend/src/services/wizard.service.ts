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

/** Dado un fieldName y un ID limpio ("folk_horror"), devuelve el string completo del YAML ("folk_horror: Terror Rural…"). */
export function reverseOption(fieldName: string, id: string): string {
  if (!id) return "";
  for (const step of STEPS) {
    const field = step.fields.find((f) => f.name === fieldName);
    if (field?.options) {
      const match = field.options.find((opt) => opt.split(":")[0].trim() === id);
      if (match) return match;
    }
  }
  return id;
}

/** Convierte un array de IDs limpios a un JSON string de strings completos, listo para session.wizard. */
function reverseJsonArray(fieldName: string, ids: string[]): string {
  if (!ids?.length) return "[]";
  return JSON.stringify(ids.map((id) => reverseOption(fieldName, id)));
}

/** Reconstruye el objeto session.wizard a partir de la respuesta de la API Core. */
export function mapStoryToWizard(story: Record<string, unknown>): WizardData {
  const sc = (story["storyteller_config"] as Record<string, any>) ?? {};
  const atm = sc["atmosphere"] ?? {};
  const perception = sc["perception"] ?? {};
  const distortion = perception["distortion"] ?? {};
  const knowledge = sc["knowledge"] ?? {};
  const domain = knowledge["domain"] ?? {};
  const language = sc["language"] ?? {};
  const bias = sc["bias"] ?? {};
  const actos = sc["actos"] ?? {};
  const personajes: any[] = (story["personajes_full"] as any[]) ?? [];
  const storyAtmosfera = (story["atmosfera"] as string) ?? "";

  // ── step_config_title ────────────────────────────────────────────────────
  // Fallback: si sc.atmosphere no existe (historias CLI o formato antiguo),
  // intentar leer story.atmosfera como género y como tono.
  const stepTitle: Record<string, string> = {
    title:               (story["title"] as string) ?? "",
    atmosfera:           reverseOption("atmosfera",           atm["genre"]    || storyAtmosfera),
    atmosphere_subgenre: reverseOption("atmosphere_subgenre", atm["subgenre"] ?? ""),
    atmosphere_tone:     reverseOption("atmosphere_tone",     atm["tone"]     || storyAtmosfera),
  };

  // ── step_config_personajes ───────────────────────────────────────────────
  // Usar índice en lugar de .find por id: personajes_full del Core no siempre tiene campo id.
  const stepPersonajes: Record<string, string> = {};
  for (let i = 1; i <= 5; i++) {
    const p = personajes[i - 1];
    const defaultName = (i === 1) ? ((story["protagonista"] as string) || "") : "";
    stepPersonajes[`protagonista_${i}_name`]   = p?.name ?? defaultName;
    stepPersonajes[`protagonista_${i}_role`]   = p?.role ?? "";
    stepPersonajes[`protagonista_${i}_traits`] = Array.isArray(p?.traits) && p.traits.length
      ? reverseJsonArray(`protagonista_${i}_traits`, p.traits)
      : "[]";
  }
  const storytellerPidRaw = (sc["storyteller_id"] as string) ?? "P1";
  const storytellerNumMatch = storytellerPidRaw.match(/\d+/);
  const storytellerNum = storytellerNumMatch ? storytellerNumMatch[0] : "1";
  const storytellerId = "protagonista_" + storytellerNum;

  // voice_style: el mapper guarda en sc.voice.style; también puede estar en sc.voice_style
  const voiceStyleRaw = sc["voice_style"] ?? sc["voice"]?.["style"] ?? "";
  stepPersonajes["storyteller_id"] = reverseOption("storyteller_id", storytellerId);
  stepPersonajes["voice_style"]    = reverseOption("voice_style", voiceStyleRaw);

  // ── step_config_voz ──────────────────────────────────────────────────────
  // reverseJsonArray filtra valores no reconocidos (quedan como id raw, el widget los ignora)
  const stepVoz: Record<string, string> = {
    perception_reliability: reverseOption("perception_reliability", perception["reliability"] ?? ""),
    distortion_level:       reverseOption("distortion_level",       distortion["level"]       ?? ""),
    distortion_triggers:    reverseJsonArray("distortion_triggers", distortion["triggers"]    ?? []),
    paranormal_knowledge:   reverseOption("paranormal_knowledge",   domain["paranormal"] ?? ""),
    religioso_knowledge:    reverseOption("religioso_knowledge",    domain["religioso"]  ?? ""),
    interpretation_style:   reverseOption("interpretation_style",   knowledge["interpretation_style"] ?? ""),
    language_register:      reverseOption("language_register",      language["register"]          ?? ""),
    figurative_density:     reverseOption("figurative_density",     language["figurative_density"] ?? ""),
    fear_focus:             reverseJsonArray("fear_focus",      bias["fear_focus"]      ?? []),
    attention_focus:        reverseJsonArray("attention_focus", bias["attention_focus"] ?? []),
  };

  // ── step_world ───────────────────────────────────────────────────────────
  const stepWorld: Record<string, string> = {};
  const scenarios = (sc["scenarios"] as any[]) ?? [];
  for (let i = 1; i <= 4; i++) {
    const s = scenarios[i - 1];
    stepWorld[`scenario_${i}_name`]        = s?.name        ?? "";
    stepWorld[`scenario_${i}_description`] = s?.description ?? "";
  }
  const rules = (sc["rules"] as any[]) ?? [];
  for (let i = 1; i <= 7; i++) {
    const r = rules[i - 1];
    stepWorld[`rule_${i}_text`] = r?.text ?? "";
    stepWorld[`rule_${i}_type`] = r?.type ? reverseOption("rule_1_type", r.type) : "";
  }

  // ── step_plot ────────────────────────────────────────────────────────────
  // Fallback para historias CLI: si no hay actos, poner sinopsis en el acto 1.
  const sinopsis = (story["sinopsis"] as string) ?? "";
  const stepPlot: Record<string, string> = {
    acto_1_exposicion: actos["act_1"]?.text ?? actos["acto_1_exposicion"] ?? sinopsis,
    acto_2_accion:     actos["act_2"]?.text ?? actos["acto_2_accion"]     ?? "",
    acto_3_climax:     actos["act_3"]?.text ?? actos["acto_3_climax"]     ?? "",
    acto_4_accion:     actos["act_4"]?.text ?? actos["acto_4_accion"]     ?? "",
    acto_5_desenlace:  actos["act_5"]?.text ?? actos["acto_5_desenlace"]  ?? "",
  };

  return {
    step_config_title:      stepTitle,
    step_config_personajes: stepPersonajes,
    step_config_voz:        stepVoz,
    step_world:             stepWorld,
    step_plot:              stepPlot,
  };
}
