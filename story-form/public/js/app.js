/* ═══════════════════════════════════════════════════════
   STORY FORM — CLIENT SIDE
═══════════════════════════════════════════════════════ */

const TOTAL_STEPS = 5;
let currentStep = 1;

// ─── UTILIDADES ──────────────────────────────────────

function wordCount(str) {
  return str.trim().split(/\s+/).filter(Boolean).length;
}

function slugify(str) {
  return str
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '');
}

// ─── WIZARD NAVIGATION ────────────────────────────────

function goToStep(n) {
  document.querySelectorAll('.step-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.step-btn').forEach(b => b.classList.remove('active'));

  const panel = document.querySelector(`.step-panel[data-panel="${n}"]`);
  const btn   = document.querySelector(`.step-btn[data-step="${n}"]`);

  if (panel) panel.classList.add('active');
  if (btn)   btn.classList.add('active');

  // Mark completed steps
  for (let i = 1; i < n; i++) {
    const b = document.querySelector(`.step-btn[data-step="${i}"]`);
    if (b) b.classList.add('completed');
  }

  // Progress bar
  const fill  = document.getElementById('progressFill');
  const label = document.getElementById('progressLabel');
  if (fill)  fill.style.width = `${(n / TOTAL_STEPS) * 100}%`;
  if (label) label.textContent = `Paso ${n} de ${TOTAL_STEPS}`;

  currentStep = n;

  // Auto-load preview on step 5
  if (n === 5) loadPreview();

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Next / Prev buttons
document.querySelectorAll('.next-btn').forEach(btn => {
  btn.addEventListener('click', () => goToStep(parseInt(btn.dataset.next)));
});

document.querySelectorAll('.prev-btn').forEach(btn => {
  btn.addEventListener('click', () => goToStep(parseInt(btn.dataset.prev)));
});

// Sidebar step buttons
document.querySelectorAll('.step-btn').forEach(btn => {
  btn.addEventListener('click', () => goToStep(parseInt(btn.dataset.step)));
});

// ─── FILENAME PREVIEW ─────────────────────────────────

const storyNameInput = document.getElementById('story_name');
const filenamePreview = document.getElementById('filenamePreview');

if (storyNameInput && filenamePreview) {
  storyNameInput.addEventListener('input', () => {
    const slug = slugify(storyNameInput.value);
    filenamePreview.textContent = slug ? `→ ${slug}.md` : '';
  });
}

// ─── GENRE CHIPS ──────────────────────────────────────

document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const target = document.getElementById(chip.dataset.target);
    if (!target) return;
    target.value = chip.dataset.val;
    target.focus();
  });
});

// ─── WORD COUNTERS ────────────────────────────────────

function attachCounter(textareaId, counterId) {
  const ta = document.getElementById(textareaId);
  const ct = document.getElementById(counterId);
  if (!ta || !ct) return;
  const update = () => ct.textContent = wordCount(ta.value);
  ta.addEventListener('input', update);
  update();
}

attachCounter('protagonistas', 'cc-protagonistas');
attachCounter('escenarios',    'cc-escenarios');
attachCounter('sinopsis',      'cc-sinopsis');

// Word counters for act textareas
document.querySelectorAll('.act-block').forEach(block => {
  const ta = block.querySelector('.act-textarea');
  const ct = block.querySelector('.cc-act');
  if (!ta || !ct) return;
  const update = () => ct.textContent = wordCount(ta.value);
  ta.addEventListener('input', update);
  update();
});

// ─── ACT ACCORDION ────────────────────────────────────

document.querySelectorAll('.act-header').forEach(header => {
  header.addEventListener('click', () => {
    const block = header.closest('.act-block');
    const body  = block.querySelector('.act-body');
    const arrow = header.querySelector('.act-arrow');
    const isOpen = body.classList.contains('open');

    body.classList.toggle('open', !isOpen);
    arrow.style.transform = isOpen ? '' : 'rotate(180deg)';
  });
});

// ─── DYNAMIC RULES ────────────────────────────────────

let ruleCount = 4;

document.getElementById('addRuleBtn')?.addEventListener('click', () => {
  ruleCount++;
  const container = document.getElementById('rulesContainer');
  const row = document.createElement('div');
  row.className = 'rule-row';
  row.innerHTML = `
    <span class="rule-num">${ruleCount}</span>
    <input type="text" name="reglas" class="field-input rule-input" placeholder="Nueva regla..." value="">
    <button type="button" class="rule-remove" title="Eliminar">×</button>
  `;
  container.appendChild(row);

  // Bind remove on the new row
  row.querySelector('.rule-remove').addEventListener('click', () => {
    row.remove();
    renumberRules();
  });

  row.querySelector('.rule-input').focus();
});

// Remove buttons on initial rows
document.querySelectorAll('.rule-remove').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.closest('.rule-row').remove();
    renumberRules();
  });
});

function renumberRules() {
  document.querySelectorAll('.rule-row').forEach((row, i) => {
    const num = row.querySelector('.rule-num');
    if (num) num.textContent = i + 1;
  });
  ruleCount = document.querySelectorAll('.rule-row').length;
}

// ─── MARKDOWN PREVIEW ─────────────────────────────────

async function loadPreview() {
  const form = document.getElementById('storyForm');
  if (!form) return;

  const formData = new FormData(form);
  const body = {};
  formData.forEach((val, key) => {
    if (body[key]) {
      if (!Array.isArray(body[key])) body[key] = [body[key]];
      body[key].push(val);
    } else {
      body[key] = val;
    }
  });

  const previewEl = document.getElementById('mdPreview');
  if (!previewEl) return;

  previewEl.textContent = 'Generando vista previa...';

  try {
    const res = await fetch('/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    previewEl.textContent = data.markdown || 'No hay contenido aún.';
  } catch (e) {
    previewEl.textContent = 'Error al generar la vista previa.';
  }
}

document.getElementById('refreshPreview')?.addEventListener('click', loadPreview);

// ─── INIT ──────────────────────────────────────────────

goToStep(1);