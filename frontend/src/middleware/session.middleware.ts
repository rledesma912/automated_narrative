import session from "express-session";

export const sessionMiddleware = session({
  secret: process.env.SESSION_SECRET ?? "narrativeforge-local-secret",
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 1000 * 60 * 60 * 4 }, // 4 horas
});
