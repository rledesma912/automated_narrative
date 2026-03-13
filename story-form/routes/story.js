const express  = require('express');
const router   = express.Router();
const fs       = require('fs');
const path     = require('path');
const { body, validationResult } = require('express-validator');
const { generateMarkdown, generateFilename } = require('../utils/generateMd');

// Carpeta de destino — ajustá esta ruta a donde n8n lee los prompts
const OUTPUT_DIR = process.env.OUTPUT_DIR
  || path.join(__dirname, '..', 'output_stories');

// GET — formulario principal
router.get('/', (req, res) => {
  res.render('index', { errors: [], saved: null, preview: null });
});

// POST — previsualización (sin guardar)
router.post('/preview', (req, res) => {
  const md = generateMarkdown(req.body);
  res.json({ markdown: md });
});

// POST — guardar archivo
const validators = [
  body('story_name').trim().notEmpty().withMessage('El nombre de la historia es obligatorio.'),
  body('genero').trim().notEmpty().withMessage('El género es obligatorio.'),
  body('protagonistas').trim().notEmpty().withMessage('Describí los protagonistas.'),
  body('escenarios').trim().notEmpty().withMessage('Describí los escenarios.'),
  body('sinopsis').trim().notEmpty().withMessage('La sinopsis es obligatoria.'),
  body('acto1').trim().notEmpty().withMessage('El Acto 1 no puede estar vacío.'),
  body('acto2').trim().notEmpty().withMessage('El Acto 2 no puede estar vacío.'),
  body('acto3').trim().notEmpty().withMessage('El Acto 3 no puede estar vacío.'),
  body('acto4').trim().notEmpty().withMessage('El Acto 4 no puede estar vacío.'),
  body('acto5').trim().notEmpty().withMessage('El Acto 5 no puede estar vacío.'),
];

router.post('/save', validators, (req, res) => {
  const errors = validationResult(req);

  if (!errors.isEmpty()) {
    return res.render('index', {
      errors: errors.array(),
      saved: null,
      preview: null,
      formData: req.body
    });
  }

  // Asegurar que la carpeta de salida existe
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const filename = generateFilename(req.body.story_name);
  const filepath = path.join(OUTPUT_DIR, filename);
  const content  = generateMarkdown(req.body);

  fs.writeFileSync(filepath, content, 'utf8');

  res.render('index', {
    errors: [],
    saved: { filename, filepath },
    preview: content,
    formData: {}
  });
});

module.exports = router;