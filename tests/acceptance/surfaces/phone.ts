// tests/acceptance/surfaces/phone.ts
//
// Maestro shell-out wrapper. Phone E2E flows live as YAML under
// tests/acceptance/.maestro/. Each flow is invoked here with the
// operator-specific env (handle, secret, email) injected.

import { spawn } from "node:child_process";
import * as path from "node:path";
import { AcceptanceConfig, OperatorConfig } from "../config";

interface FlowResult {
  pass: boolean;
  output: string;
  exit_code: number;
}

function runFlow(flowFile: string, env: NodeJS.ProcessEnv): Promise<FlowResult> {
  return new Promise((resolve) => {
    const proc = spawn(
      "maestro",
      ["test", path.resolve("tests/acceptance/.maestro", flowFile)],
      { env, stdio: ["ignore", "pipe", "pipe"] },
    );
    let output = "";
    proc.stdout.on("data", (b) => { output += b.toString(); });
    proc.stderr.on("data", (b) => { output += b.toString(); });
    proc.on("close", (code) => {
      resolve({ pass: code === 0, output, exit_code: code ?? 1 });
    });
    proc.on("error", (err) => {
      // Maestro binary missing — surface clearly.
      resolve({
        pass: false,
        output: `failed to spawn maestro: ${err.message}`,
        exit_code: 127,
      });
    });
  });
}

function buildEnv(
  cfg: AcceptanceConfig, op: OperatorConfig,
): NodeJS.ProcessEnv {
  return {
    ...process.env,
    BACKEND_BASE_URL: cfg.backend_base_url,
    OP_EMAIL: op.email,
    OP_HANDLE: op.handle,
    OP_SECRET: op.vault_secret,
  };
}

export async function onboardPhone(
  cfg: AcceptanceConfig, op: OperatorConfig,
): Promise<void> {
  const r = await runFlow("onboarding_phone.yaml", buildEnv(cfg, op));
  if (!r.pass) {
    throw new Error(
      `phone onboarding flow failed (exit ${r.exit_code}): ${r.output.slice(0, 600)}`,
    );
  }
}

export interface PhoneArtifactSet {
  threads: string[];
  elins: string[];
  inbound: string[];
}

export async function verifyPhoneArtifacts(
  cfg: AcceptanceConfig, op: OperatorConfig,
): Promise<PhoneArtifactSet> {
  const r = await runFlow("artifact_presence_phone.yaml", buildEnv(cfg, op));
  if (!r.pass) {
    throw new Error(
      `phone artifact-presence flow failed (exit ${r.exit_code}): ${r.output.slice(0, 600)}`,
    );
  }
  // The Maestro flow prints lines like:
  //   ELINS_KEY=elins.123_000001
  //   THREAD_ID=t-abc
  //   INBOUND=inb-xyz
  // We parse them here.
  const out: PhoneArtifactSet = { threads: [], elins: [], inbound: [] };
  for (const line of r.output.split(/\r?\n/)) {
    const m1 = /ELINS_KEY=(\S+)/.exec(line);
    if (m1) { out.elins.push(m1[1]); continue; }
    const m2 = /THREAD_ID=(\S+)/.exec(line);
    if (m2) { out.threads.push(m2[1]); continue; }
    const m3 = /INBOUND=(\S+)/.exec(line);
    if (m3) { out.inbound.push(m3[1]); continue; }
  }
  return out;
}
