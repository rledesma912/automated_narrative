/**
 * Spec-440 S1 — contrato wizard → API.
 * mapWizardToCore envía campos explícitos y solo IDs; mapStoryToWizard
 * rehidrata tanto IDs como el formato legado "id: Etiqueta".
 */
import { describe, it, expect } from "vitest";
import { mapWizardToCore } from "../../../src/services/mapper.service";
import { mapStoryToWizard, WizardData } from "../../../src/services/wizard.service";

const WIZARD: WizardData = {
  step_config_title: {
    title: "El galpón",
    atmosfera: "terror: Terror",
    atmosphere_subgenre: "folk_horror: Terror rural",
    atmosphere_tone: "opresivo: Opresivo",
  },
  step_config_personajes: {
    protagonista_1_name: "Rosa",
    protagonista_1_role: "peona",
    protagonista_1_traits: JSON.stringify(["valiente: Valiente", "curiosa"]),
    protagonista_2_name: "Tito",
    protagonista_2_role: "capataz",
    protagonista_2_traits: "[]",
    storyteller_id: "protagonista_2",
    voice_style: "intimista: Como un diario personal, cámara cerca",
  },
  step_config_voz: {
    perception_reliability: "poco_confiable: A veces ve bien, a veces no",
    distortion_level: "alta: Alta",
    distortion_triggers: JSON.stringify(["oscuridad: La oscuridad"]),
    paranormal_knowledge: "bajo: Poco",
    religioso_knowledge: "alto: Mucho",
    interpretation_style: "literal: Literal",
    language_register: "rural_tradicional: Del campo",
    figurative_density: "baja: Poca",
    fear_focus: JSON.stringify(["muerte: La muerte", "aislamiento: Quedar solo"]),
    attention_focus: JSON.stringify(["sonidos: Los sonidos"]),
  },
  step_world: {
    scenario_1_name: "El galpón",
    scenario_1_description: "Chapas y olor a gasoil",
    rule_1_text: "Nadie entra de noche",
    rule_1_type: "fenomeno: Sobrenatural",
    rule_2_text: "Los perros no ladran",
    rule_2_type: "indicador: Señal o indicio",
  },
  step_plot: {
    acto_1_exposicion: "Uno",
    acto_2_accion: "Dos",
    acto_3_climax: "Tres",
    acto_4_accion: "Cuatro",
    acto_5_desenlace: "Cinco",
  },
};

describe("mapWizardToCore (Spec-440 T1.1)", () => {
  const dto = mapWizardToCore(WIZARD) as unknown as Record<string, any>;

  it("envía genero/subgenero/tono y narrator_config explícitos, sin campos viejos", () => {
    expect(dto.genero).toBe("terror");
    expect(dto.subgenero).toBe("folk_horror");
    expect(dto.tono).toBe("opresivo");
    expect(dto).not.toHaveProperty("atmosfera");
    expect(dto).not.toHaveProperty("storyteller_config");
    expect(dto).not.toHaveProperty("actos");
    expect(Object.keys(dto).sort()).toEqual([
      "escenarios", "genero", "narrator_config", "personajes_full", "protagonista",
      "reglas", "relator", "sinopsis", "subgenero", "title", "tono",
    ]);
  });

  it("la config de voz lleva solo IDs", () => {
    const nc = dto.narrator_config;
    expect(nc.storyteller_id).toBe("P2");
    expect(nc.storyteller_name).toBe("Tito");
    expect(nc.voice_style).toBe("intimista");
    expect(nc.perception).toEqual({
      reliability: "poco_confiable",
      distortion: { level: "alta", triggers: ["oscuridad"] },
    });
    expect(nc.knowledge).toEqual({
      domain: { paranormal: "bajo", religioso: "alto" },
      interpretation_style: "literal",
    });
    expect(nc.language).toEqual({ register: "rural_tradicional", figurative_density: "baja" });
    expect(nc.bias).toEqual({ fear_focus: ["muerte", "aislamiento"], attention_focus: ["sonidos"] });
    expect(nc.atmosphere).toEqual({ genre: "terror", subgenre: "folk_horror", tone: "opresivo" });
  });

  it("el relator usa el ID del registro", () => {
    expect(dto.relator).toBe(
      "Primera persona en pasado. Narrador: Tito. Tono: intimista. Registro: rural_tradicional."
    );
  });

  it("reglas tipadas, rasgos, escenarios y actos", () => {
    expect(dto.narrator_config.rules).toEqual([
      { id: "R1", text: "Nadie entra de noche", type: "fenomeno" },
      { id: "R2", text: "Los perros no ladran", type: "indicador" },
    ]);
    expect(dto.reglas).toEqual(["Nadie entra de noche", "Los perros no ladran"]);
    expect(dto.personajes_full[0]).toEqual({
      id: "P1", name: "Rosa", role: "peona", traits: ["valiente", "curiosa"],
    });
    expect(dto.narrator_config.scenarios).toEqual([
      { id: "S1", order: 1, name: "El galpón", description: "Chapas y olor a gasoil" },
    ]);
    expect(dto.narrator_config.actos.act_3).toEqual({ type: "climax", text: "Tres" });
    expect(dto.sinopsis).toBe("Uno\n\nDos\n\nTres\n\nCuatro\n\nCinco");
  });
});

describe("mapStoryToWizard (Spec-440 T1.2)", () => {
  const baseStory = (config: Record<string, unknown>) => ({
    title: "t",
    personajes_full: [],
    storyteller_config: config,
  });

  const clean = {
    voice_style: "intimista",
    perception: { reliability: "poco_confiable", distortion: { level: "media", triggers: [] } },
    language: { register: "rural_tradicional", figurative_density: "media" },
    bias: { fear_focus: ["muerte"], attention_focus: [] },
    rules: [{ text: "r", type: "fenomeno" }],
  };
  const legacy = {
    voice_style: "intimista: Como un diario personal, cámara cerca",
    perception: {
      reliability: "poco_confiable: A veces ve bien, a veces no",
      distortion: { level: "media", triggers: [] },
    },
    language: { register: "rural_tradicional: Del campo", figurative_density: "media" },
    bias: { fear_focus: ["muerte: La muerte"], attention_focus: [] },
    rules: [{ text: "r", type: "paranormal" }],
  };

  it("historia con IDs y legado producen el mismo wizard", () => {
    expect(mapStoryToWizard(baseStory(legacy))).toEqual(mapStoryToWizard(baseStory(clean)));
  });

  it("lleva cada valor a la opción completa del combo", () => {
    const w = mapStoryToWizard(baseStory(legacy));
    expect(w.step_config_voz!.perception_reliability).toBe(
      "poco_confiable: A veces ve bien, a veces no"
    );
    expect(w.step_config_voz!.language_register).toBe("rural_tradicional: Del campo");
    expect(JSON.parse(w.step_config_voz!.fear_focus)).toEqual(["muerte: La muerte"]);
    expect(w.step_config_personajes!.voice_style).toBe(
      "intimista: Como un diario personal, cámara cerca"
    );
  });

  it("mapea los tipos de regla viejos a RuleType", () => {
    const types = (t: string) =>
      mapStoryToWizard(baseStory({ rules: [{ text: "r", type: t }] })).step_world!.rule_1_type;
    expect(types("paranormal")).toBe("fenomeno: Sobrenatural");
    expect(types("social")).toBe("entorno: Del lugar");
    expect(types("indicador")).toBe("indicador: Señal o indicio");
  });

  it("ida y vuelta: el wizard rehidratado produce el mismo payload", () => {
    const dto = mapWizardToCore(WIZARD) as unknown as Record<string, any>;
    const story = {
      ...dto,
      storyteller_config: dto.narrator_config,
      personajes_full: dto.personajes_full,
    };
    const again = mapWizardToCore(mapStoryToWizard(story)) as unknown as Record<string, any>;
    expect(again.narrator_config.perception).toEqual(dto.narrator_config.perception);
    expect(again.narrator_config.language).toEqual(dto.narrator_config.language);
    expect(again.narrator_config.rules).toEqual(dto.narrator_config.rules);
    expect(again.relator).toBe(dto.relator);
  });
});
