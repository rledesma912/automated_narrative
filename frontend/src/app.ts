import express from "express";
import path from "path";
import router from "./routes";
import { createApiProxy } from "./middleware/api_proxy";
import { getEnvironment } from "./utils/environment";
import { rutas } from "./utils/rutas";

const app = express();

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));

// Versión de los estáticos: las vistas los piden como `/js/x.js?v=<versión>`.
// Cambia en cada arranque (cada deploy reinicia el proceso), así el navegador no
// sigue usando el CSS/JS de la versión anterior. ASSET_VERSION la fija a mano.
app.locals.assetVersion = process.env.ASSET_VERSION ?? String(Date.now());

// Spec-630 B1: las URLs que se arman en más de una vista (editar una historia).
app.locals.rutas = rutas;

// Spec-221: proxy /api/* → backend FastAPI. Debe ir ANTES de los body parsers
// (urlencoded/json) para no consumir el cuerpo de POST/PATCH antes del reenvío.
// Se monta en raíz y filtra internamente por pathFilter="/api" para preservar
// el prefijo en el request reenviado al backend.
const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";
app.use(createApiProxy(CORE_API_URL));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, "..", "public")));

// Spec-540: ambiente (y en dev, rama y commit) en cada página. Se lee en cada
// request para que la marca muestre siempre el último commit.
app.use((_req, res, next) => {
  res.locals.environment = getEnvironment();
  next();
});

app.use("/", router);

export default app;
