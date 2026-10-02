import express from "express";
import path from "path";
import router from "./routes";
import { createApiProxy } from "./middleware/api_proxy";
import { getEnvironment } from "./utils/environment";
import { rutas } from "./utils/rutas";
import { assetVersion } from "./utils/assets";

const app = express();

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));

// Versión de los estáticos: las vistas los piden como `/js/x.js?v=<versión>`.
// Spec-630 B17: sale de la última modificación de los estáticos (utils/assets.ts)
// y se calcula en cada request, así cambia apenas cambian (también en dev).
app.locals.assetVersion = assetVersion();

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
  res.locals.assetVersion = assetVersion();
  next();
});

app.use("/", router);

export default app;
