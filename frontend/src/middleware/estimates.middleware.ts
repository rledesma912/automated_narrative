import type { NextFunction, Request, Response } from "express";
import { getJobEstimates, type JobEstimates } from "../services/core_api.service";
import { formatEstimate, formatShortEstimate } from "../utils/eta";

/**
 * Spec-510: deja en `res.locals.estimateLabels` cuánto tarda cada tipo de job
 * («≈ 4 min») para mostrarlo junto a los botones que lo lanzan.
 *
 * Una llamada al Core con timeout corto; si falla o tarda, `estimateLabels`
 * queda en null y la página se ve como antes. Nunca corta el request.
 */
export const ESTIMATES_TIMEOUT_MS = 1500;

export interface EstimateLabels {
  full_generation: string;
  regenerate_voz: string;
  // Spec-530: análisis del asistente.
  consult?: string;
  plan_outline?: string;
  verify_outline?: string;
}

export function createLoadEstimates(
  fetchEstimates: () => Promise<JobEstimates> = () => getJobEstimates(ESTIMATES_TIMEOUT_MS),
  timeoutMs = ESTIMATES_TIMEOUT_MS,
) {
  return async function loadEstimates(_req: Request, res: Response, next: NextFunction) {
    res.locals.estimateLabels = null;
    let timer: NodeJS.Timeout | undefined;
    try {
      const timeout = new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error("timeout")), timeoutMs);
      });
      const estimates = await Promise.race([fetchEstimates(), timeout]);
      const labels: EstimateLabels = {
        full_generation: formatEstimate(estimates?.full_generation?.seconds),
        regenerate_voz: formatEstimate(estimates?.regenerate_voz?.seconds),
        consult: formatShortEstimate(estimates?.consult?.seconds),
        plan_outline: formatShortEstimate(estimates?.plan_outline?.seconds),
        verify_outline: formatShortEstimate(estimates?.verify_outline?.seconds),
      };
      if (labels.full_generation || labels.regenerate_voz) res.locals.estimateLabels = labels;
    } catch {
      /* sin estimación: la página se ve como antes */
    } finally {
      clearTimeout(timer);
    }
    next();
  };
}

export const loadEstimates = createLoadEstimates();
