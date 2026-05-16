import { Request, Response } from "express";
import { checkCoreHealth, type CoreHealthStatus } from "../services/core_api.service";
import { renderPage } from "../utils/render";

export async function debugPage(_req: Request, res: Response): Promise<void> {
  const coreHealth: CoreHealthStatus = await checkCoreHealth();

  const env = {
    PORT: process.env.PORT ?? "(no definido)",
    CORE_API_URL: process.env.CORE_API_URL ?? "(no definido)",
    NODE_ENV: process.env.NODE_ENV ?? "(no definido)",
    DATABASE_URL: process.env.DATABASE_URL ?? "(no definido)",
  };

  const llmInfo = coreHealth.reachable
    ? {
        provider: coreHealth.provider ?? "(desconocido)",
        model: coreHealth.active_profile ?? "(desconocido)",
      }
    : null;

  await renderPage(res, "debug", {
    title: "Debug",
    activePage: "debug",
    coreHealth,
    env,
    llmInfo,
  });
}
