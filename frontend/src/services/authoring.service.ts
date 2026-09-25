import axios from "axios";

/**
 * Spec-530: lectura del estado del asistente de autoría en el Core.
 * Las escrituras las hace el navegador directo a /api (proxy), con guardado
 * automático; acá solo se lee para renderizar las páginas.
 */
const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";
const API = `${CORE_API_URL}/api/v1/authoring`;

export interface AuthoringOption {
  id: string;
  label: string;
  detail: string;
}

export interface AuthoringOptions {
  effects: AuthoringOption[];
  tellings: AuthoringOption[];
  criteria: Array<{ id: string; nombre: string; pregunta: string; por_que: string }>;
}

export interface WorkshopItem {
  criterion: string;
  nombre: string;
  por_que: string;
  status: "cumple" | "parcial" | "falta" | "intencional";
  question: string;
  options: string[];
  answer: string;
  round: number;
}

export interface Act {
  number: number;
  goal: string;
  events: string[];
  change_from: string;
  change_to: string;
  scenario: string;
  on_stage: string[];
  held_back: string;
  seeds: string[];
  payoffs: string[];
  decisions: string[];
  warnings: string[];
  rules: string[];
  needs_review: boolean;
}

export interface AuthoringState {
  story_id: string;
  status: string;
  direction: Record<string, unknown> & { title: string };
  workshop: {
    round: number;
    max_rounds: number;
    finish: { kind: string; text: string; open_questions: number };
    items: WorkshopItem[];
  };
  outline: { acts: Act[]; decisions: Array<{ id: string; nombre: string; integrada: boolean }> };
  characters: Array<{ name: string; kind: string; relation: string }>;
  scenarios: string[];
  active_job: Record<string, unknown> | null;
}

let optionsCache: AuthoringOptions | null = null;

export async function getAuthoringOptions(): Promise<AuthoringOptions> {
  if (optionsCache) return optionsCache;
  const resp = await axios.get<AuthoringOptions>(`${API}/options`, { timeout: 5000 });
  optionsCache = resp.data;
  return resp.data;
}

export async function getAuthoringState(storyId: string): Promise<AuthoringState> {
  const resp = await axios.get<AuthoringState>(`${API}/stories/${storyId}`, { timeout: 5000 });
  return resp.data;
}
