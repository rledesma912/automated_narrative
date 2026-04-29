import { Router } from "express";
import { homePage } from "../controllers/home.controller";
import { galleryPage } from "../controllers/gallery.controller";
import { debugPage } from "../controllers/debug.controller";
import { setTheme, componentsPage } from "../controllers/theme.controller";
import { wizardRedirect, showStep, submitStep, confirmPage } from "../controllers/wizard.controller";
import { submitGeneration, streamingRoomPage } from "../controllers/stream.controller";
import { historiaPage, generarDesdeHistoria } from "../controllers/historia.controller";

const router = Router();

router.get("/",            homePage);
router.get("/galeria",     galleryPage);
router.get("/debug",       debugPage);
router.get("/componentes", componentsPage);
router.post("/theme",      setTheme);

// Wizard
router.get("/generar",              wizardRedirect);
router.get("/generar/paso/:step",   showStep);
router.post("/generar/paso/:step",  submitStep);
router.get("/generar/confirmar",    confirmPage);

// Stream
router.post("/generar/submit",              submitGeneration);
router.get("/generar/stream/:storyId",      streamingRoomPage);

// Historia (ver detalle + generar desde borrador)
router.get("/historia/:storyId",            historiaPage);
router.post("/historia/:storyId/generar",   generarDesdeHistoria);

export default router;
