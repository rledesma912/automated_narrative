import { WizardData } from "./wizard.service";

export interface CoreDTO {
  title: string;
  protagonista: string;
  relator: string;
  escenarios: string;
  sinopsis: string;
  atmosfera: string;
  reglas: string[];
  actos: object;
  storyteller_config: object;
  personajes_full: object[];
}

function parseJsonArray(raw: string | undefined): string[] {
  try {
    const parsed = JSON.parse(raw ?? "[]");
    return Array.isArray(parsed) ? (parsed as string[]) : [];
  } catch {
    return raw ? [raw] : [];
  }
}

function buildAtmosphere(cfg: Record<string, string>) {
  const genre    = cfg["atmosfera"]           ?? "";
  const subgenre = cfg["atmosphere_subgenre"] ?? "";
  const tone     = cfg["atmosphere_tone"]     ?? "";
  return { genre, subgenre, tone };
}

function buildScenarios(world: Record<string, string>) {
  const scenarios: Array<{ id: string; order: number; name: string; description: string }> = [];
  for (let i = 1; i <= 4; i++) {
    const name = (world[`scenario_${i}_name`] ?? "").trim();
    if (!name) continue;
    const description = (world[`scenario_${i}_description`] ?? "").trim();
    scenarios.push({ id: `S${i}`, order: i, name, description });
  }
  return scenarios;
}

function buildActos(plot: Record<string, string>) {
  return {
    act_1: { type: "exposicion",         text: plot["acto_1_exposicion"] ?? "" },
    act_2: { type: "accion_ascendente",  text: plot["acto_2_accion"]     ?? "" },
    act_3: { type: "climax",             text: plot["acto_3_climax"]     ?? "" },
    act_4: { type: "accion_descendente", text: plot["acto_4_accion"]     ?? "" },
    act_5: { type: "desenlace",          text: plot["acto_5_desenlace"]  ?? "" },
  };
}

function buildRules(world: Record<string, string>) {
  const rules: Array<{ id: string; text: string; type: string }> = [];
  for (let i = 1; i <= 5; i++) {
    const text = (world[`rule_${i}_text`] ?? "").trim();
    if (!text) continue;
    const type = (world[`rule_${i}_type`] ?? "entorno").trim();
    rules.push({ id: `R${i}`, text, type });
  }
  return rules;
}

/** Transforma los datos granulares del Wizard en el formato que espera el Core Python. */
export function mapWizardToCore(wizard: WizardData): CoreDTO {
  const cfg   = wizard["step_config_title"]      ?? {};
  const pjs   = wizard["step_config_personajes"]  ?? {};
  const voz   = wizard["step_config_voz"]         ?? {};
  const world = wizard["step_world"]               ?? {};
  const plot  = wizard["step_plot"]                ?? {};

  // Protagonists — IDs en formato P1..P5
  const protagonists: Array<{ id: string; name: string; role: string; traits: string[] }> = [];
  for (let i = 1; i <= 5; i++) {
    const name = (pjs[`protagonista_${i}_name`] ?? "").trim();
    if (!name) continue;
    const role   = (pjs[`protagonista_${i}_role`]   ?? "").trim();
    const traits = parseJsonArray(pjs[`protagonista_${i}_traits`]);
    protagonists.push({ id: `P${i}`, name, role, traits });
  }

  // Storyteller — protagonista_1 → P1
  const storytellerWizardId = pjs["storyteller_id"] ?? "protagonista_1";
  const storytellerPid      = storytellerWizardId.replace("protagonista_", "P");
  const storyteller         = protagonists.find(p => p.id === storytellerPid) ?? protagonists[0];
  const voiceStyleRaw       = pjs["voice_style"] ?? "intimista";
  const voiceStyle          = voiceStyleRaw.split(":")[0].trim();

  // Atmosphere
  const atmosphere = buildAtmosphere(cfg);

  // Scenarios, Rules & Actos
  const scenarios = buildScenarios(world);
  const rules     = buildRules(world);
  const actos     = buildActos(plot);

  // ── Backward-compat strings para el Core ────────────────────────────────
  const protagonistaStr = protagonists.length
    ? protagonists
        .map(p => `${p.name}: ${p.role}${p.traits.length ? ` [${p.traits.join(", ")}]` : ""}`)
        .join("; ")
    : "Personaje principal";

  const langReg     = voz["language_register"] ?? "coloquial";
  const narName     = storyteller?.name ?? "narrador";
  const relator     = `Primera persona en pasado. Narrador: ${narName}. Tono: ${voiceStyle}. Registro: ${langReg}.`;

  const atmosferaStr = [
    atmosphere.genre,
    atmosphere.subgenre ? `(${atmosphere.subgenre})` : "",
    atmosphere.tone     ? `- ${atmosphere.tone}`     : "",
  ].filter(Boolean).join(" ");

  const escenariosStr = scenarios.length
    ? scenarios.map(s => s.name + (s.description ? `: ${s.description}` : "")).join("; ")
    : "";

  const reglasList = rules.map(r => r.text);

  // ── storyteller_config ───────────────────────────────────────────────────
  const storytellerConfig = {
    storyteller_id:   storytellerPid,
    storyteller_name: narName,
    voice_style:      voiceStyle,
    voice: { person: "primera", tense: "pasado", style: voiceStyle },
    atmosphere,
    scenarios,
    rules,
    perception: {
      reliability: voz["perception_reliability"] ?? "subjetiva",
      distortion: {
        level:    voz["distortion_level"]    ?? "media",
        triggers: parseJsonArray(voz["distortion_triggers"]),
      },
    },
    knowledge: {
      domain: {
        paranormal: voz["paranormal_knowledge"] ?? "medio",
        religioso:  voz["religioso_knowledge"]  ?? "medio",
      },
      interpretation_style: voz["interpretation_style"] ?? "simbolica",
    },
    language: {
      register:           langReg,
      figurative_density: voz["figurative_density"] ?? "media",
    },
    bias: {
      fear_focus:      parseJsonArray(voz["fear_focus"]),
      attention_focus: parseJsonArray(voz["attention_focus"]),
    },
  };

  // Sinopsis compuesta desde los 5 actos (backward-compat con el Core)
  const sinopsisFromActos = [
    actos.act_1.text, actos.act_2.text, actos.act_3.text,
    actos.act_4.text, actos.act_5.text,
  ].filter(Boolean).join("\n\n");

  return {
    title:             cfg["title"]     ?? "",
    atmosfera:         atmosferaStr || atmosphere.genre,
    protagonista:      protagonistaStr,
    relator,
    escenarios:        escenariosStr,
    sinopsis:          sinopsisFromActos,
    actos,
    reglas:            reglasList,
    storyteller_config: storytellerConfig,
    personajes_full:    protagonists,
  };
}
