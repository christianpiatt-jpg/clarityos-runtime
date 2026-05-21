// tests/acceptance/scenarios/index.ts
//
// Scenario registry. Each scenario implements `Scenario` and is keyed
// by a stable id used in reports and the runner CLI.

import { AcceptanceConfig } from "../config";

import scenario_01 from "./01_onboarding_per_surface";
import scenario_02 from "./02_cross_surface_jump";
import scenario_03 from "./03_two_operators_concurrent";
import scenario_04 from "./04_artifact_presence";
import scenario_05 from "./05_stability_window";

export interface ScenarioResult {
  id: string;
  name: string;
  pass: boolean;
  duration_ms?: number;
  details?: string;
  messages?: string[];
}

export type Scenario = (config: AcceptanceConfig) => Promise<ScenarioResult>;

export interface ScenarioEntry {
  id: string;
  name: string;
  fast: boolean;            // included in `fast` mode?
  fn: Scenario;
}

export const SCENARIOS: ScenarioEntry[] = [
  { id: "01_onboarding_per_surface",   name: "Onboarding per surface",   fast: true,  fn: scenario_01 },
  { id: "02_cross_surface_jump",       name: "Cross-surface jump",        fast: false, fn: scenario_02 },
  { id: "03_two_operators_concurrent", name: "Two operators concurrent",  fast: false, fn: scenario_03 },
  { id: "04_artifact_presence",        name: "Artifact presence",         fast: true,  fn: scenario_04 },
  { id: "05_stability_window",         name: "Stability window",          fast: false, fn: scenario_05 },
];

export function selectScenarios(mode: "fast" | "full"): ScenarioEntry[] {
  if (mode === "full") return SCENARIOS;
  return SCENARIOS.filter((s) => s.fast);
}
