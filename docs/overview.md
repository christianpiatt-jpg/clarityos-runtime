# ClarityOS Overview

## Purpose

ClarityOS is a deterministic operator-grade reasoning runtime. It holds context
across phone, web, and cloud surfaces and exposes a fixed set of reasoning
subsystems through a single cockpit. The model performs computation; the OS
holds state; the contract between them does not drift.

## System Composition

ClarityOS is assembled from the following subsystems. Each has a stable
contract and a deterministic surface.

- **Geometry System** — the visual and structural primitives: nucleus,
  pentagon, polyhedron, grid rules, and glow rules.
- **Cognitive Pipeline** — five sequential reasoning layers: orientation,
  interpretation, inversion, integration, transformation.
- **Cockpit** — the primary operator workspace for real-time monitoring.
- **Vault** — the persistent memory and structural repository.
- **State Engine** — the operator-state classifier and drift monitor.
- **ELINS** — the report and intelligence subsystem.
- **Runtime UI** — the process, log, and diagnostics surface.
- **CLI** — the command interface to the cognitive pipeline and subsystems.

## Design Canon

ClarityOS is built on a fixed design canon:

- Declarative structure over narrative description.
- Deterministic transitions over heuristic behavior.
- Grid-aligned geometry; no free-floating elements.
- Cyan for active and nominal state; red for drift and error.
- Monospace for all data fields.

## Document Set

This documentation set specifies each subsystem in full. Subsystem documents
are organized under `docs/`, the cognitive layers under `docs/layers/`, and
ELINS documents under `docs/elins/`.
