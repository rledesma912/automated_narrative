import { Router } from "express";
import { maquetaPage } from "../controllers/maquetas.controller";

// Spec-530 S0: solo fuera de producción (app.ts decide si se monta).
const router = Router();

router.get("/maquetas", (_req, res) => res.redirect("/maquetas/direccion"));
router.get("/maquetas/:pagina", maquetaPage);

export default router;
