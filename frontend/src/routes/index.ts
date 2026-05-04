import { Router } from "express";
import { homePage } from "../controllers/home.controller";
import { galleryPage } from "../controllers/gallery.controller";
import { debugPage } from "../controllers/debug.controller";
import { setTheme } from "../controllers/theme.controller";
import { wizardRedirect, showStep, submitStep, confirmPage, loadWizardData } from "../controllers/wizard.controller";
import { submitGeneration, streamingRoomPage, getActiveStreamApi } from "../controllers/stream.controller";
import { historiaPage, verMarkdownHandler, downloadMarkdownHandler, generarDesdeHistoria, deleteStoryHandler, exportStoryHandler, deleteMarkdownHandler, confirmDeleteModal, confirmDeleteMarkdownModal, markdownCheckHandler, updateFilePathHandler } from "../controllers/historia.controller";

const router = Router();

router.get("/",            homePage);
router.get("/galeria",     galleryPage);
router.get("/debug",       debugPage);
router.post("/theme",      setTheme);

// Wizard
router.get("/generar",              wizardRedirect);
router.get("/generar/paso/:step",   showStep);
router.post("/generar/paso/:step",  submitStep);
router.get("/generar/confirmar",    confirmPage);
router.get("/generar/cargar/:storyId", loadWizardData);

// Stream
router.post("/generar/submit",              submitGeneration);
router.get("/generar/stream/:storyId",      streamingRoomPage);
router.get("/api/streaming/active",         getActiveStreamApi);

// Historia (ver detalle + generar desde borrador + eliminar)
router.get("/historia/:storyId",            historiaPage);
router.get("/historia/:storyId/ver-markdown", verMarkdownHandler);
router.get("/historia/:storyId/descargar-markdown", downloadMarkdownHandler);
router.post("/historia/:storyId/generar",   generarDesdeHistoria);
router.post("/historia/:storyId/exportar",  exportStoryHandler);
router.delete("/api/historia/:storyId",          deleteStoryHandler);
router.delete("/api/historia/:storyId/markdown", deleteMarkdownHandler);
router.patch("/api/historia/:storyId/file-path", updateFilePathHandler);

router.get("/api/historia/:storyId/markdown-check", markdownCheckHandler);

// Modales de confirmación (HTMX)
router.get("/modales/confirmar-borrar/:storyId", confirmDeleteModal);
router.get("/modales/confirmar-borrar-markdown/:storyId", confirmDeleteMarkdownModal);

export default router;
