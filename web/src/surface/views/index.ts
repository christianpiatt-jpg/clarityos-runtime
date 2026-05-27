/**
 * Web Surface v0.2.0 — view-registration barrel.
 *
 * Production bootstrap (``server/main.ts``) imports this module
 * exactly once. Each ``import`` below triggers the corresponding
 * view module's module-level ``registerView`` side effect,
 * populating the registry that ``classifier.ts`` reads at request
 * time.
 *
 * Without this barrel, the prod registry is empty and every
 * resolved view name returns ``undefined`` from ``getView``,
 * producing the symptom: ``"View 'index' not found."``
 *
 * Tests do NOT import this file. They call
 * ``_clearViewRegistryForTests`` and register only the views they
 * need, keeping each test case deterministic.
 *
 * Imports are alphabetical. ``home`` is imported by name (not just
 * for side effect) so it can also be aliased under ``"index"``
 * below — see ``viewResolution.ts`` for why ``"/"`` resolves to
 * the view name ``"index"`` rather than ``"home"``.
 */
import { homeView } from "./home";
import "./errors";
import "./formDemo";
import "./formWizard";
import "./perplexityDemo";
import "./redirect";
import "./streamDemo";
import "./streamSseDemo";
import "./uploadDemo";

import { registerView } from "../viewRegistry";


// ``viewResolution.resolveView`` maps the root path ``"/"`` to the
// view name ``"index"`` (last-non-empty-segment-or-fallback rule).
// No view module registers itself under that name, so we alias
// ``homeView`` under it here. Last-writer-wins semantics in
// ``registerView`` mean this is safe and order-independent.
registerView("index", homeView);
