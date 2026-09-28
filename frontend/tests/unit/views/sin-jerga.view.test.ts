import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * Spec-580 §2.2: el sitio no le habla a quien escribe con términos de oficio ni
 * técnicos. Se revisa solo lo que se lee: el texto entre etiquetas, los atributos
 * que se muestran (title, placeholder, aria-label, data-titulo…) y los textos de
 * los bloques EJS y del JS (strings con espacios o con mayúscula). Los ids, las
 * URLs y los comentarios pueden seguir diciendo «escaleta» o «taller».
 */
const ROOT = path.resolve(__dirname, "../../..");
const VIEWS = ["src/views/asistente"];
const SCRIPTS = ["public/js/asistente.js"];

const JERGA: RegExp[] = [
  /\bescaletas?\b/i,
  /\btaller\b/i,
  /\brondas?\b/i,
  /\bsiembra[ns]?\b/i,
  /\bretoma\b/i,
  /\belenco\b/i,
  /\bbeats?\b/i,
  /\bcl[ií]max\b/i,
  /\bexposici[oó]n\b/i,
  /\bdesenlace\b/i,
  /\bacci[oó]n (ascendente|descendente)\b/i,
  /\bcriterios?\b/i,
  /\bDirecci[oó]n\b/,
  /\bVoz\b/,
  /\bAnalizar\b/i,
];

const ATTRS = /\b(?:title|placeholder|aria-label|data-titulo|data-detalle|data-confirmar(?:-titulo|-label)?)="([^"]*)"/g;
const STRINGS = /(["'`])((?:(?!\1)[^\\\n]|\\.)*)\1/g;

function files(dir: string): string[] {
  return fs.readdirSync(path.join(ROOT, dir), { withFileTypes: true }).flatMap((e) => {
    const rel = path.join(dir, e.name);
    return e.isDirectory() ? files(rel) : e.name.endsWith(".ejs") ? [rel] : [];
  });
}

/** Textos que puede ver una persona en una vista EJS. */
export function visibleTexts(ejs: string): string[] {
  const src = ejs.replace(/<%\/\*[\s\S]*?\*\/%>/g, "").replace(/<!--[\s\S]*?-->/g, "");
  const out: string[] = [];
  // Textos dentro de los bloques EJS (etiquetas de objetos, ternarios…).
  for (const block of src.matchAll(/<%[=-]?([\s\S]*?)%>/g)) out.push(...codeTexts(block[1]));
  const html = src.replace(/<%[\s\S]*?%>/g, " ");
  for (const m of html.matchAll(ATTRS)) out.push(m[1]);
  for (const m of html.matchAll(/>([^<]+)</g)) if (m[1].trim()) out.push(m[1].trim());
  return out;
}

/** Strings de código que parecen texto para leer (tienen un espacio o arrancan en mayúscula). */
function codeTexts(code: string): string[] {
  const sinComentarios = code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  return [...sinComentarios.matchAll(STRINGS)]
    .map((m) => m[2])
    .filter((s) => / /.test(s.replace(/\$\{[^}]*\}/g, "")) || /^[A-ZÁÉÍÓÚ¿¡]/.test(s))
    .filter((s) => !/^[\w-]+(?: [\w-]+)*$/.test(s) || /^[A-ZÁÉÍÓÚ¿¡]/.test(s))
    .filter((s) => !s.startsWith("/") && !/[<>]/.test(s));
}

function jerga(texts: string[], file: string): string[] {
  return texts.flatMap((t) => JERGA.filter((re) => re.test(t)).map((re) => `${file}: «${t}» (${re.source})`));
}

describe("el sitio habla sin jerga (Spec-580)", () => {
  it("las vistas del asistente no usan términos de oficio", () => {
    const bad = VIEWS.flatMap(files).flatMap((f) => jerga(visibleTexts(fs.readFileSync(path.join(ROOT, f), "utf-8")), f));
    expect(bad).toEqual([]);
  });

  it("los mensajes del JS del asistente tampoco", () => {
    const bad = SCRIPTS.flatMap((f) => jerga(codeTexts(fs.readFileSync(path.join(ROOT, f), "utf-8")), f));
    expect(bad).toEqual([]);
  });

  it("detecta la jerga en texto, atributos y bloques EJS, pero no en ids ni URLs", () => {
    const ejs = `<%/* Escaleta: comentario */%><a href="/asistente/1/escaleta" data-destino="escaleta" title="Revisar la escaleta">Taller</a>
      <% const N = { 1: 'Clímax' }; %><span><%= x ? 'Ronda 2' : '' %></span>`;
    const found = jerga(visibleTexts(ejs), "x");
    expect(found.map((s) => s.split("«")[1].split("»")[0]).sort()).toEqual(["Clímax", "Revisar la escaleta", "Ronda 2", "Taller"]);
  });
});
