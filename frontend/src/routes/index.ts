import { Router } from "express";
import { homePage } from "../controllers/home.controller";
import { galleryPage } from "../controllers/gallery.controller";
import { debugPage } from "../controllers/debug.controller";
import { setTheme } from "../controllers/theme.controller";
import { wizardRedirect, showStep, submitStep, confirmPage, loadWizardData, autoSaveField } from "../controllers/wizard.controller";
import { submitGeneration, streamingRoomPage, getActiveStreamApi } from "../controllers/stream.controller";
import { historiaPage, generarDesdeHistoria, deleteStoryHandler, confirmDeleteModal, generateNarrativeHandler } from "../controllers/historia.controller";
import { relatosPage } from "../controllers/relatos.controller";

const router = Router();

router.get("/",            homePage);
router.get("/galeria",     galleryPage);
router.get("/debug",       debugPage);
router.post("/theme",      setTheme);

// Wizard
router.get("/generar",              wizardRedirect);
router.get("/generar/paso/:step",   showStep);
router.post("/generar/paso/:step",  submitStep);
router.patch("/generar/paso/:step/guardar", autoSaveField);
router.get("/generar/confirmar",    confirmPage);
router.get("/generar/cargar/:storyId", loadWizardData);

// Stream
router.post("/generar/submit",              submitGeneration);
router.get("/generar/stream/:storyId",      streamingRoomPage);
// Spec-221 T0: rutas Express renombradas a /internal/* para liberar /api/* al proxy del backend.
router.get("/internal/streaming/active",    getActiveStreamApi);

// Historia (ver detalle + generar desde borrador + eliminar)
router.get("/historia/:storyId",            historiaPage);
router.post("/historia/:storyId/generar",   generarDesdeHistoria);
router.post("/historia/:storyId/generar-relato", generateNarrativeHandler);
router.delete("/internal/historia/:storyId",          deleteStoryHandler);

// Modales de confirmación (HTMX)
router.get("/modales/confirmar-borrar/:storyId", confirmDeleteModal);

// Nueva ruta de relatos (Spec-235)
router.get("/historia/:storyId/relatos", relatosPage);

export default router;
