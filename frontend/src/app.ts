import express from "express";
import cookieParser from "cookie-parser";
import path from "path";
import router from "./routes";
import { themeMiddleware } from "./middleware/theme.middleware";
import { sessionMiddleware } from "./middleware/session.middleware";

const app = express();

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());
app.use(sessionMiddleware);
app.use(express.static(path.join(__dirname, "..", "public")));
app.use(themeMiddleware);

app.use("/", router);

export default app;
