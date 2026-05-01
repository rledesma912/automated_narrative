import fs from "fs";
import path from "path";
import yaml from "js-yaml";
import { WizardStep, WizardField } from "./wizard.service";

const YAML_PATH = path.resolve(__dirname, "../../config/ui_definitions.yaml");

interface RawField {
  name: string;
  type: "text" | "textarea" | "select" | "radio" | "multi-select";
  label: string;
  placeholder?: string;
  required?: boolean;
  rows?: number;
  hint?: string;
  options?: string[];
  subtitle?: string;
  note?: string;
  group?: string;
  default?: string;
}

interface RawStep {
  id: string;
  title: string;
  subtitle?: string;
  fields: RawField[];
}

interface RawDefinitions {
  steps: RawStep[];
}

function parseField(raw: RawField): WizardField {
  return {
    name:        raw.name,
    label:       raw.label,
    type:        raw.type ?? "text",
    required:    raw.required ?? false,
    placeholder: raw.placeholder,
    rows:        raw.rows,
    hint:        raw.hint,
    options:     raw.options,
    subtitle:    raw.subtitle,
    note:        raw.note,
    group:       raw.group,
    default:     raw.default,
  };
}

export function loadSteps(): WizardStep[] {
  const content = fs.readFileSync(YAML_PATH, "utf-8");
  const parsed  = yaml.load(content) as RawDefinitions;

  return parsed.steps.map((raw, i) => ({
    id:       raw.id,
    number:   i + 1,
    title:    raw.title,
    subtitle: raw.subtitle,
    fields:   (raw.fields ?? []).map(parseField),
  }));
}
