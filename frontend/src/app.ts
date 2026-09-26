import express from "express";
import path from "path";
import router from "./routes";
import { createApiProxy } from "./middleware/api_proxy";

const app = express();

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));

// Versión de los estáticos: las vistas los piden como `/js/x.js?v=<versión>`.
// Cambia en cada arranque (cada deploy reinicia el proceso), así el navegador no
// sigue usando el CSS/JS de la versión anterior. ASSET_VERSION la fija a mano.
app.locals.assetVersion = process.env.ASSET_VERSION ?? String(Date.now());

// Spec-221: proxy /api/* → backend FastAPI. Debe ir ANTES de los body parsers
// (urlencoded/json) para no consumir el cuerpo de POST/PATCH antes del reenvío.
// Se monta en raíz y filtra internamente por pathFilter="/api" para preservar
// el prefijo en el request reenviado al backend.
const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";
app.use(createApiProxy(CORE_API_URL));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, "..", "public")));

app.use("/", router);

export default app;
