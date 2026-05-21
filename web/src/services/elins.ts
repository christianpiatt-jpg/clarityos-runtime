// services/elins.ts — #G personal engine + daily distribution.
// The #G engine NEVER persists scenario text; only Dewey membership metadata.

import {
  elinsDailyFeed,
  elinsDailyQueue,
  gElinsRun,
  type ElinsDeliveredReport,
  type GElinsAnalysis,
} from "../lib/api";

export type { ElinsDeliveredReport, GElinsAnalysis };

export async function runPersonalElins(scenarioText: string): Promise<GElinsAnalysis> {
  if (!scenarioText.trim()) throw new Error("empty_scenario");
  const r = await gElinsRun(scenarioText.trim());
  return r.analysis;
}

export interface QueueDailyOptions {
  scenario_text: string;
  deliver_email?: boolean;
  deliver_feed?: boolean;
  local_hour?: number;
  local_minute?: number;
}

export async function queueDailyReport(opts: QueueDailyOptions): Promise<{
  report_id: string;
  scheduled_for_ts: number;
}> {
  const r = await elinsDailyQueue(opts);
  return { report_id: r.report_id, scheduled_for_ts: r.scheduled_for_ts };
}

export async function fetchDailyFeed(limit = 50): Promise<ElinsDeliveredReport[]> {
  const r = await elinsDailyFeed(limit);
  return r.delivered;
}

/** Determine whether an analysis envelope is a successful #G result. */
export function isSuccessfulAnalysis(
  a: GElinsAnalysis | { error: string; message: string },
): a is GElinsAnalysis {
  return Object.prototype.hasOwnProperty.call(a, "neighborhoods");
}
