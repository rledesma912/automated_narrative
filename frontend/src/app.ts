import express from "express";
import cookieParser from "cookie-parser";
import path from "path";
import router from "./routes";
import { themeMiddleware } from "./middleware/theme.middleware";
import { sessionMiddleware } from "./middleware/session.middleware";
import { createApiProxy } from "./middleware/api_proxy";

const app = express();

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));

// Spec-221: proxy /api/* → backend FastAPI. Debe ir ANTES de los body parsers
// (urlencoded/json) para no consumir el cuerpo de POST/PATCH antes del reenvío.
// Se monta en raíz y filtra internamente por pathFilter="/api" para preservar
// el prefijo en el request reenviado al backend.
const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";
app.use(createApiProxy(CORE_API_URL));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());
app.use(sessionMiddleware);
app.use(express.static(path.join(__dirname, "..", "public")));
app.use(themeMiddleware);

app.use("/", router);

export default app;
