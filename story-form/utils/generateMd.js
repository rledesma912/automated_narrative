/**
 * Genera el contenido del archivo .md a partir de los datos del formulario.
 * El formato respeta exactamente la estructura que espera el flujo n8n.
 */
function generateMarkdown(data) {
  const {
    genero,
    protagonistas,
    escenarios,
    sinopsis,
    reglas,
    acto1, acto2, acto3, acto4, acto5
  } = data;

  // Reglas: pueden venir como array (múltiples inputs) o string separado por saltos
  const reglasList = Array.isArray(reglas)
    ? reglas.filter(r => r.trim())
    : reglas.split('\n').filter(r => r.trim());

  const reglasFormatted = reglasList.map(r => `- ${r.trim()}`).join('\n');

  return `# Contexto del relato

**Género**: ${genero}
**Protagonistas**: ${protagonistas}
**Escenarios**: ${escenarios}
**Sinopsis**: ${sinopsis}

---

## Las reglas de la historia

${reglasFormatted}

---

**Acto 1 (Situación inicial)**
${acto1}

**Acto 2 (Conflicto inicial)**
${acto2}

**Acto 3 (Falsa calma)**
${acto3}

**Acto 4 (Crisis mayor)**
${acto4}

**Acto 5 (Clímax - Resolución final)**
${acto5}
`;
}

/**
 * Genera el nombre del archivo a partir del nombre de la historia.
 * Ejemplo: "El otro pueblo" → "el_otro_pueblo.md"
 */
function generateFilename(storyName) {
  return storyName
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '') // quita tildes
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
    + '.md';
}

module.exports = { generateMarkdown, generateFilename };