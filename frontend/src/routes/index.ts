import { Router } from "express";
import { homePage } from "../controllers/home.controller";
import { galleryPage } from "../controllers/gallery.controller";
import { debugPage } from "../controllers/debug.controller";
import { wizardRedirect, showStep, submitStep, confirmPage, loadWizardData, autoSaveField, saveWizardStory } from "../controllers/wizard.controller";
import { streamingRoomPage } from "../controllers/stream.controller";
import { historiaPage, generarDesdeHistoria, deleteStoryHandler, confirmDeleteModal, generateNarrativeHandler } from "../controllers/historia.controller";
import { relatosPage, regenerarActoAction, relatoPanelFragment } from "../controllers/relatos.controller";
import { loadEstimates } from "../middleware/estimates.middleware";
import { nuevoPage, asistentePage } from "../controllers/asistente.controller";

const router = Router();

// Spec-510: `loadEstimates` (≈ N min junto a lo que lanza un job) solo en las
// páginas que lo muestran: galería, ficha, sala y relatos.

router.get("/",            homePage);
router.get("/galeria",     loadEstimates, galleryPage);
router.get("/debug",       debugPage);

// Spec-530: asistente de autoría («Nuevo relato»).
router.get("/nuevo",                          loadEstimates, nuevoPage);
router.get("/asistente/:storyId/:paso",       loadEstimates, asistentePage);

// Wizard
router.get("/generar",              wizardRedirect);
router.get("/generar/paso/:step",   showStep);
router.post("/generar/paso/:step",  submitStep);
router.patch("/generar/paso/:step/guardar", autoSaveField);
router.get("/generar/confirmar",    confirmPage);
router.get("/generar/cargar/:storyId", loadWizardData);

// Stream
router.post("/generar/guardar",             saveWizardStory);
router.get("/generar/stream/:storyId",      loadEstimates, streamingRoomPage);
// Spec-221 T0: rutas Express renombradas a /internal/* para liberar /api/* al proxy del backend.

// Historia (ver detalle + generar desde borrador + eliminar)
router.get("/historia/:storyId",            loadEstimates, historiaPage);
router.post("/historia/:storyId/generar",   generarDesdeHistoria);
router.post("/historia/:storyId/generar-relato", generateNarrativeHandler);
router.delete("/internal/historia/:storyId",          deleteStoryHandler);

// Modales de confirmación (HTMX)
router.get("/modales/confirmar-borrar/:storyId", confirmDeleteModal);

// Nueva ruta de relatos (Spec-235)
router.get("/historia/:storyId/relatos", loadEstimates, relatosPage);
router.post(
  "/historia/:storyId/relatos/:narrativeId/actos/:actoNumero/regenerar",
  loadEstimates,
  regenerarActoAction
);
router.get("/historia/:storyId/relatos/:narrativeId/panel", loadEstimates, relatoPanelFragment);

export default router;
