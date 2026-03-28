const express  = require('express');
const router   = express.Router();
const fs       = require('fs');
const path     = require('path');
const { body, validationResult } = require('express-validator');
const { generateMarkdown, generateFilename } = require('../utils/generateMd');
const Story = require('../models/story');

// Carpeta de destino — ajustá esta ruta a donde n8n lee los prompts
const OUTPUT_DIR = process.env.OUTPUT_DIR
  || path.join(__dirname, '..', 'output_stories');

// GET — formulario principal (nueva historia)
router.get('/', (req, res) => {
  res.render('index', { errors: [], saved: null, preview: null, formData: {} });
});

// GET — listado de historias
router.get('/list', async (req, res) => {
  try {
    const stories = await Story.findAll();
    res.render('stories', { stories });
  } catch (err) {
    console.error('Error fetching stories:', err);
    res.render('stories', { stories: [] });
  }
});

// GET — cargar historia para editar
router.get('/stories/:id/edit', async (req, res) => {
  try {
    const story = await Story.findById(req.params.id);
    if (!story) {
      return res.status(404).render('index', {
        errors: [{ msg: 'Historia no encontrada' }],
        saved: null,
        preview: null,
        formData: {}
      });
    }

    // Formatear datos para el formulario
    const formData = {
      story_id: story.id,
      story_name: story.story_name,
      protagonistas: story.protagonistas,
      relator: story.relator,
      sinopsis: story.sinopsis,
      escenarios: story.escenarios,
      reglas: story.reglas.map(r => r.texto),
      acto1: story.actos.find(a => a.numero === 1)?.contenido || '',
      acto2: story.actos.find(a => a.numero === 2)?.contenido || '',
      acto3: story.actos.find(a => a.numero === 3)?.contenido || '',
      acto4: story.actos.find(a => a.numero === 4)?.contenido || '',
      acto5: story.actos.find(a => a.numero === 5)?.contenido || ''
    };

    res.render('index', {
      errors: [],
      saved: null,
      preview: null,
      formData: formData,
      isEditing: true
    });
  } catch (err) {
    console.error('Error loading story:', err);
    res.render('index', {
      errors: [{ msg: 'Error al cargar la historia' }],
      saved: null,
      preview: null,
      formData: {}
    });
  }
});

// POST — previsualización (sin guardar)
router.post('/preview', (req, res) => {
  const md = generateMarkdown(req.body);
  res.json({ markdown: md });
});

// POST — guardar archivo
const validators = [
  body('story_name').trim().notEmpty().withMessage('El nombre de la historia es obligatorio.'),
  body('protagonistas').trim().notEmpty().withMessage('Describí los protagonistas.'),
  body('relator').trim().notEmpty().withMessage('Describí el relator.'),
  body('sinopsis').trim().notEmpty().withMessage('La sinopsis es obligatoria.'),
  body('escenarios').trim().notEmpty().withMessage('Describí los escenarios.'),
  body('acto1').trim().notEmpty().withMessage('El Acto 1 no puede estar vacío.'),
  body('acto2').trim().notEmpty().withMessage('El Acto 2 no puede estar vacío.'),
  body('acto3').trim().notEmpty().withMessage('El Acto 3 no puede estar vacío.'),
  body('acto4').trim().notEmpty().withMessage('El Acto 4 no puede estar vacío.'),
  body('acto5').trim().notEmpty().withMessage('El Acto 5 no puede estar vacío.'),
];

router.post('/save', validators, async (req, res) => {
  const errors = validationResult(req);

  if (!errors.isEmpty()) {
    return res.render('index', {
      errors: errors.array(),
      saved: null,
      preview: null,
      formData: req.body,
      isEditing: !!req.body.story_id
    });
  }

  try {
    // Asegurar que la carpeta de salida existe
    if (!fs.existsSync(OUTPUT_DIR)) {
      fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    // Guardar primero en base de datos (para obtener el ID)
    let savedStory;
    try {
      if (req.body.story_id) {
        // Actualizar historia existente
        savedStory = await Story.update(req.body.story_id, req.body);
      } else {
        // Crear nueva historia
        savedStory = await Story.create(req.body);
      }
    } catch (dbErr) {
      console.error('Database error:', dbErr);
      
      let errorMsg = 'Error al guardar la historia en la base de datos';
      if (dbErr.message && dbErr.message.includes('UNIQUE')) {
        errorMsg = 'Ya existe una historia con ese nombre. Por favor, utiliza un nombre diferente.';
      }
      
      return res.render('index', {
        errors: [{ msg: errorMsg }],
        saved: null,
        preview: null,
        formData: req.body,
        isEditing: !!req.body.story_id
      });
    }

    // Ahora guardar el archivo markdown con nombre único (story_id + nombre)
    const baseFilename = generateFilename(req.body.story_name);
    const filename = `${savedStory.id}_${baseFilename}`;
    const filepath = path.join(OUTPUT_DIR, filename);
    const content = generateMarkdown(req.body);

    // Guardar archivo markdown
    try {
      fs.writeFileSync(filepath, content, 'utf8');
    } catch (fileErr) {
      console.error('File write error:', fileErr);
      // Log the error but don't fail - the important part (DB save) succeeded
      return res.render('index', {
        errors: [{ msg: 'Historia guardada en BD pero hubo un error al generar el archivo markdown. Intenta con permisos correctos.' }],
        saved: null,
        preview: null,
        formData: req.body,
        isEditing: !!req.body.story_id
      });
    }

    res.render('index', {
      errors: [],
      saved: { filename, filepath, id: savedStory.id },
      preview: content,
      formData: {}
    });
  } catch (err) {
    console.error('Error in /save route:', err);
    res.render('index', {
      errors: [{ msg: 'Error inesperado: ' + (err.message || 'Error desconocido') }],
      saved: null,
      preview: null,
      formData: req.body,
      isEditing: !!req.body.story_id
    });
  }
});

// POST — eliminar historia
router.post('/stories/:id/delete', async (req, res) => {
  try {
    await Story.delete(req.params.id);
    // Redirigir a listado de historias
    res.redirect('/list');
  } catch (err) {
    console.error('Error deleting story:', err);
    res.redirect('/list');
  }
});

module.exports = router;