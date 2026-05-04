import { createProxyMiddleware, type Options } from "http-proxy-middleware";
import type { RequestHandler } from "express";

/**
 * Spec-221: proxy `/api/*` → backend FastAPI.
 *
 * Express deja de exponer URLs absolutas del backend al navegador. El cliente
 * habla siempre contra el mismo origen que sirvió el HTML; este middleware
 * reenvía cualquier request bajo `/api/*` al `coreApiUrl` (server-to-server).
 *
 * Configuración SSE-friendly: sin timeout, sin self-handle (deja que el
 * middleware streamee chunks tal cual). Debe registrarse ANTES de
 * `express.json()` / `express.urlencoded()` para no consumir bodies POST/PATCH.
 */
export function createApiProxy(coreApiUrl: string): RequestHandler {
  const options: Options = {
    target: coreApiUrl,
    // pathFilter aplica el proxy solo a /api/* y preserva el prefijo en el
    // request al backend (a diferencia de app.use("/api", ...) que lo tira).
    pathFilter: "/api",
    changeOrigin: true,
    selfHandleResponse: false,
    // SSE: streams pueden vivir minutos/horas; sin límite de tiempo.
    proxyTimeout: 0,
    timeout: 0,
    // Logging acotado: errores y conexiones SSE; no logueamos cada GET de polling.
    on: {
      error: (err, _req, res) => {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(`[api-proxy] error reaching ${coreApiUrl}: ${msg}`);
        if ("writeHead" in res && !res.headersSent) {
          res.writeHead(502, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "backend_unreachable", detail: msg }));
        }
      },
    },
  };
  return createProxyMiddleware(options);
}
