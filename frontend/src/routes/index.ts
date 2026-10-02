import { Router } from "express";
import { homePage } from "../controllers/home.controller";
import { galleryPage } from "../controllers/gallery.controller";
import { debugPage } from "../controllers/debug.controller";
import { streamingRoomPage } from "../controllers/stream.controller";
import { historiaRedirect, generarDesdeHistoria, deleteStoryHandler, confirmDeleteModal } from "../controllers/historia.controller";
import { relatosPage, regenerarActoAction, relatoPanelFragment, corregirRelatoPage, videoPage } from "../controllers/relatos.controller";
import { loadEstimates } from "../middleware/estimates.middleware";
import { nuevoPage, asistentePage } from "../controllers/asistente.controller";
import { editarHref } from "../utils/rutas";

const router = Router();

// Spec-510: `loadEstimates` (≈ N min junto a lo que lanza un job) solo en las
// páginas que lo muestran: asistente, sala y relatos (la galería ya no lanza jobs).

router.get("/",            homePage);
router.get("/galeria",     galleryPage);
router.get("/debug",       debugPage);

// Spec-530: asistente de autoría («Nuevo relato»).
router.get("/nuevo",                          loadEstimates, nuevoPage);
router.get("/asistente/:storyId/:paso",       loadEstimates, asistentePage);

// Spec-530 S7: el wizard se retiró; las rutas viejas llevan al asistente.
router.get("/generar",                     (_req, res) => res.redirect(301, "/nuevo"));
// Spec-630 B1: editar abre siempre «Los actos».
router.get("/generar/cargar/:storyId",     (req, res) => res.redirect(301, editarHref(String(req.params["storyId"]))));

// Stream
router.get("/generar/stream/:storyId",      loadEstimates, streamingRoomPage);
// Spec-221 T0: rutas Express renombradas a /internal/* para liberar /api/* al proxy del backend.

// Historia: la ficha se fue (Spec-630 B12); quedan generar (desde la sala) y eliminar.
router.get("/historia/:storyId",            historiaRedirect);
router.post("/historia/:storyId/generar",   generarDesdeHistoria);
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
// Spec-610: corregir el relato en la web.
router.get("/historia/:storyId/relatos/:narrativeId/corregir", loadEstimates, corregirRelatoPage);
router.get("/historia/:storyId/relatos/:narrativeId/video", loadEstimates, videoPage);

export default router;
