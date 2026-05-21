# Command-Line Surface

## Overview

ClarityOS has **no `clarity` command-line interface**. There is no
`clarity orient`, `clarity interpret`, `clarity vault`, `clarity state`, or
`clarity drift` command, and no `argparse` / `click` / `typer` CLI. The
operator runtime is reached over HTTP (`/operator/session/*`), not a CLI.

What exists is a small set of **command-line entrypoints** — batch scripts and
launchers — for running and deploying the backend. This document records them.

## Current entrypoints

### `start.bat` — run the backend locally

At the repository root. It creates `.venv` if missing, installs
`requirements.txt`, and starts the API with
`uvicorn app:app --host 0.0.0.0 --port 8080 --reload`. The backend then serves
on `http://localhost:8080`.

### `deploy.bat` — deploy to Cloud Run

At the repository root. Requires the `gcloud` CLI and an authenticated
session. It stamps a fresh UTC timestamp into `BUILD_VERSION` (so every image
digest is unique and Cloud Run sees a new revision), then runs
`gcloud run deploy clarity-engine --source . --region us-east4 --platform managed --allow-unauthenticated --port 8080`.

### `scripts/`

- `scripts/seed_acceptance_operators.py` — seeds operator accounts for the
  acceptance harness.
- `scripts/run_acceptance.sh` — runs the acceptance suite.

## Legacy command-line surfaces

These exist in the repository but are not the current system:

- `clarity_engine/clarity_launcher.py` — "ClarityOS Launcher v2," a Python
  process launcher that opens separate console windows for a Markoff Engine, a
  Kernel, and a Dispatcher. It targets an engine layout
  (`clarity_engine/markoff_engine/`, `clarity_engine/kernel.py`,
  `clarity_engine/dispatcher/`) that does not match the current
  `clarity_engine/` contents — it is stale.
- `clarity_engine/console.bat` — launches a legacy operator console
  (`Clarity_OS_Operating_System/04_Operator/console.py`).
- `Clarity_OS_Operating_System/modules/v3_legacy/v3_*.bat` — a v3-era batch
  command set (`v3_status`, `v3_step`, `v3_diag`, `v3_help`, `v3_map`,
  `v3_health`, and others): the legacy v3 batch shell.

## What the CLI is not

The `clarity` subcommand interface in the earlier design canon —
`clarity orient`, `clarity interpret`, `clarity invert`, `clarity integrate`,
`clarity transform`, `clarity elins`, `clarity vault open`, `clarity state`,
`clarity drift`, and a `clarity help` system — was never implemented and exists
in no code.
