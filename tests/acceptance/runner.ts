// tests/acceptance/runner.ts
//
// Runner entry point. Loads config, executes scenarios, writes a
// JSON + Markdown report under tests/acceptance/reports/<run_id>/.
//
// Invocation (do NOT run from this file; this is for documentation):
//   ts-node tests/acceptance/runner.ts --mode=fast --run-id=local-001
//   ts-node tests/acceptance/runner.ts --mode=full --run-id=local-002
//
// Exit codes:
//   0 — all scenarios pass
//   1 — at least one scenario fails
//   2 — fatal runner error

import * as fs from "node:fs/promises";
import * as path from "node:path";
import { loadConfig, AcceptanceConfig } from "./config";
import { selectScenarios, ScenarioEntry, ScenarioResult } from "./scenarios";

interface RunReport {
  run_id: string;
  mode: "fast" | "full";
  started_at: string;
  finished_at: string | null;
  config: AcceptanceConfig;
  scenarios: Record<string, ScenarioResult>;
  pass: boolean;
}

interface CliArgs {
  runId: string;
  mode: "fast" | "full";
}

function parseArgs(argv: string[]): CliArgs {
  let runId = `run-${Date.now()}`;
  let mode: "fast" | "full" = "full";
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--run-id" || a === "-r") {
      runId = argv[i + 1];
      i++;
    } else if (a.startsWith("--run-id=")) {
      runId = a.slice("--run-id=".length);
    } else if (a === "--mode" || a === "-m") {
      mode = argv[i + 1] as "fast" | "full";
      i++;
    } else if (a.startsWith("--mode=")) {
      mode = a.slice("--mode=".length) as "fast" | "full";
    }
  }
  if (mode !== "fast" && mode !== "full") {
    throw new Error(`unknown --mode value: ${mode} (expected fast|full)`);
  }
  return { runId, mode };
}

async function executeOne(
  entry: ScenarioEntry,
  cfg: AcceptanceConfig,
): Promise<ScenarioResult> {
  const t0 = Date.now();
  try {
    const result = await entry.fn(cfg);
    return {
      ...result,
      id: entry.id,
      name: entry.name,
      duration_ms: Date.now() - t0,
    };
  } catch (err: unknown) {
    return {
      id: entry.id,
      name: entry.name,
      pass: false,
      duration_ms: Date.now() - t0,
      details: err instanceof Error ? err.message : String(err),
      messages: [`scenario threw: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

function writeMarkdown(report: RunReport): string {
  const lines: string[] = [];
  lines.push(`# Acceptance run ${report.run_id}`);
  lines.push("");
  lines.push(`- mode: **${report.mode}**`);
  lines.push(`- started: ${report.started_at}`);
  lines.push(`- finished: ${report.finished_at ?? "(in progress)"}`);
  lines.push(`- result: **${report.pass ? "PASS" : "FAIL"}**`);
  lines.push("");
  for (const [id, r] of Object.entries(report.scenarios)) {
    lines.push(`## ${id} — ${r.pass ? "PASS" : "FAIL"} (${r.duration_ms ?? 0}ms)`);
    if (r.details) lines.push(r.details);
    if (r.messages && r.messages.length) {
      for (const m of r.messages) lines.push(`- ${m}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cfg = await loadConfig();
  const reportDir = path.resolve(
    "tests/acceptance/reports",
    args.runId,
  );
  await fs.mkdir(reportDir, { recursive: true });

  const report: RunReport = {
    run_id: args.runId,
    mode: args.mode,
    started_at: new Date().toISOString(),
    finished_at: null,
    config: cfg,
    scenarios: {},
    pass: false,
  };

  const persist = async () => {
    await fs.writeFile(
      path.join(reportDir, "report.json"),
      JSON.stringify(report, null, 2),
      "utf-8",
    );
  };

  try {
    const entries = selectScenarios(args.mode);
    for (const entry of entries) {
      // eslint-disable-next-line no-console
      console.log(`[runner] starting ${entry.id}`);
      report.scenarios[entry.id] = await executeOne(entry, cfg);
      await persist();
    }
    report.pass = Object.values(report.scenarios).every((s) => s.pass);
  } finally {
    report.finished_at = new Date().toISOString();
    await persist();
    await fs.writeFile(
      path.join(reportDir, "report.md"),
      writeMarkdown(report),
      "utf-8",
    );
  }

  process.exit(report.pass ? 0 : 1);
}

// Only run main() if invoked directly. The user instruction prohibits
// execution of the harness in this materialization step; this guard is
// the standard ts-node entry pattern.
if (require.main === module) {
  main().catch((err) => {
    // eslint-disable-next-line no-console
    console.error("[runner] fatal:", err);
    process.exit(2);
  });
}

export { main };
