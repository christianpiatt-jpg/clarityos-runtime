# Batch 10 — Documentation Manifest

The single authoritative index for the Batch 10 documentation pipeline. It
holds two registers:

- the **naming ledger** — one canonical line per documented subsystem;
- the **change manifest** — what each sub-batch added, the fiction it removed,
  and any notes.

Sub-batches record here. Ledger and manifest entries are never appended to
individual subsystem docs — each doc carries only its own `Fiction removed`
section.

## Naming ledger

| Term | Sub-batch | Resolution |
|------|-----------|------------|
| Billing | 10c | Stripe-integrated economic layer — PaymentIntent activation/renewal, #G credit purchases, five-state billing machine, 24h renewal scheduler, webhooks; mock mode by default; no card data stored in ClarityOS. |
| Membership | 10c | Founding 500 cohort layer — single `founding_500` tier (500-cap), activation via PaymentIntent, in-cohort waitlist, #G credits, entitlement projection, invite-based onboarding; no monthly/annual variants. |
| Model Router | 10d | Deterministic model-id resolver + provider dispatch; mock-on-failure; no sandboxing. |
| Schedulers | 10d | Three independent cadence engines (ELINS macro scheduler, intelligence scheduler, renewal scheduler); no shared framework; no DLQ. |
| Perplexity ESO | 10d | External Signal Object contract + oracle fetcher; single provider; not a search orchestrator. |
| DEWEY | 10e | Conceptual-neighborhood indexing — embedding-space neighborhoods, basin membership, multi-origin curvature, and trajectory forecasting; opaque random IDs; not economic membership, not search, not billing. |
| DEWEY Memberships Store | 10e | Object-to-neighborhood membership rows for DEWEY; a DEWEY-neighborhood concept, unrelated to the economic Membership layer; no billing or entitlements. |
| Markov | 10f | Per-session temporal state subsystem — ordered state history, QC + predictive envelopes, and the deterministic 4/3-1 chat runtime (Observer → Interpreter → Regulator → Projector → -1 Subtractive); state persisted via the markov_states store; not a scheduler, not DEWEY. |
| Continuity | 10g | Runtime reentry subsystem — pure deterministic reconstruction of ELINS long-arc continuity from vault_state; implemented and tested but currently unwired (no production caller); not `/continuity/snapshot`, not operator-state continuity, not memory, not identity. |
| Dashboard | 10h | Read-only ELINS aggregation layer — composes global, regional, macro, entity-graph, and continuity sections into one deterministic snapshot for the cockpit; no model calls, no writes, no autonomous logic. |
| Intelligence Kernel | 10i | Central orchestration hub for intelligence operations — dispatches #c, #G, the ELINS pipelines, threads, and task modes; resolves external-signal mode; attaches S_ELINS QC; coordinates operator_state and persistence; orchestrates, does not compute. |
| Runtime Execution Layer | 10j | Operator-session execution stack — deterministic kernel / dispatcher core plus session loop, stateless HTTP, persistence, and provider bridge; bounded non-determinism only at session and timestamp boundaries; distinct from the Intelligence Kernel. |
| Operator State | 10k | Per-user metadata spine for `operator_state.py` — recorder of preferences, ELINS/#G history, signal mode, model selections, and EL/INS per-turn flag over the Memory Vault; not an intelligence engine, not a runtime kernel, not a scheduler, not a generic settings store. |
| Memory Vault | 10l | Per-user encrypted key/value substrate for `memory_vault.py` — stdlib PBKDF2 + HMAC-CTR + HMAC-SHA256 envelope, 4 backends (mock / fs / sqlite / firestore), 11-namespace whitelist, no cross-user reads, no schema enforcement; not a database, not a distributed KV, not transactional across keys, not a search/scan engine, not a vault engine. |
| Vault Store | 10m | Per-user notes / sessions / ELINS-raw Firestore document store for `vault_store.py` — unencrypted, `v_`-prefixed urlsafe-token IDs, 2 backends (memory / firestore), schema and ownership enforced at the route layer (not in the module); not encrypted, not a Memory Vault replacement, not a security boundary, not a search engine. |
| ELINS | 10o | Long-arc evaluation and forecasting pipeline — 11-layer ELINS core (`ELINS/standard_elins.py`), S-ELINS QC, forecast engine with per-primitive λ decay, regional/macro aggregation, and a separate regression-runs analytics suite (`elins_run_*.py`); uses its own `elins_project` persistence; not Memory Vault, not a state engine, not DEWEY, not Markov, not the per-turn `el_ins/` analyzer. |
| Emotional Reality Alignment (ERA) | 10p | Deterministic emotional-reframing engine in `emotional_alignment_engine.py` + `emotional_alignment_schemas.py` — pure Python, no I/O, no LLM, no network, no randomness; 3 public functions, frozen-dataclass schemas with structural privacy contract (test-enforced no-text / no-identity), 10 spec-locked invariants, advisory-only output consumed by Azimuth Transition + FEA Integration; not an HTTP service, not a state store, not the Sovereignty Gate. |
| Regression-First Protocol | 10r | Operator-facing chain-of-findings protocol in `problem_solver/` (3 modules + `__init__` re-export, V76 / V77 / V79–V82) — deterministic chain lifecycle (start / step / close / tag / delete_tag / archive / replay), two-namespace vault persistence (`regression_chains` + `regression_packets`), `analyze_packet` as a deterministic JSON parser for LLM-emitted unified packets generated upstream under the `skills_export/regression_first/` bundle prompt, pure-lexicon auto-trigger; the subsystem itself invokes no model; not a state machine, not autonomous, not coupled to the ELINS-regression analytics suite (10o). |

## Change manifest

### Sub-batch 10a — Core

**Status: unrecoverable.** This sub-batch predates the Batch 10 manifest. No
surviving batch markers, no VCS history, and no code-verifiable evidence
remain. Added / Removed entries cannot be reconstructed without invention.
Recorded as unrecoverable per the Batch 10 methodology
(`docs/BATCH_10_methodology.md`).

### Sub-batch 10b — Surfaces

**Status: unrecoverable.** This sub-batch predates the Batch 10 manifest. No
surviving batch markers, no VCS history, and no code-verifiable evidence
remain. Added / Removed entries cannot be reconstructed without invention.
Recorded as unrecoverable per the Batch 10 methodology
(`docs/BATCH_10_methodology.md`).

### Sub-batch 10c — Billing + Membership

- **Added:** `docs/billing.md`, `docs/membership.md`
- **Fiction removed:** none. The 10c instruction flagged "billing tiers", the
  "#G credit system", and billing/membership "status levels" as possibly
  fictional; each was verified real against code and documented. Nothing was
  removed.
- **Notes:** Billing runs in mock mode by default and stores no card data.
  Membership has exactly one tier (`founding_500`); a cohort slot is consumed
  only on a successful payment webhook.
- **Provenance:** recorded retroactively — this manifest was created during
  Sub-batch 10d.

### Sub-batch 10d — Model Router / Schedulers / Perplexity ESO

- **Added:** `docs/model_router.md`, `docs/schedulers.md`,
  `docs/perplexity_eso.md`
- **Fiction removed:**
  - `docs/model_router.md` — sandboxing, rate limiting, abuse prevention,
    cross-surface isolation, heuristic/adaptive routing.
  - `docs/schedulers.md` — a unified scheduler framework, dead-letter queue,
    event-driven pipeline, backoff strategy, priority queues, and
    scheduler-owned log-rotation / cache-invalidation / entitlement-refresh
    jobs.
  - `docs/perplexity_eso.md` — ESO as a search orchestrator, a provider
    registry, provider-selection logic, query aggregation, result and semantic
    ranking, multi-provider ensembles.
- **Notes:**
  - The schedulers remain three independent loops with no shared framework.
  - Perplexity ESO is a single-provider External Signal Object, not a search
    orchestrator.
  - The model router remains deterministic, with mock fallback only.

### Sub-batch 10e — DEWEY

- **Added:** `docs/dewey.md`
- **Fiction removed:**
  - The 10e instruction named `dewey_neighbors.py` and `dewey_index.py`;
    neither exists. The real DEWEY backend is `dewey_neighborhoods_store.py`,
    `dewey_memberships_store.py`, `dewey_worker.py`, and `dewey_pipeline.py`.
  - DEWEY is not a user-membership system, a billing-tier system, a search
    engine, a recommendation engine, or a graph-theory engine.
  - Neighborhood / membership IDs are opaque random tokens, not "deterministic
    region IDs"; there is no semantic ranking of external content.
- **Notes:**
  - `dewey_memberships_store.py` is DEWEY-neighborhood membership, not the
    economic Membership layer — no namespace bleed into `docs/membership.md`.
  - `dewey_pipeline.py` is a shared math core; its ELINS-envelope and
    Markov-predictive helpers belong to those subsystems' docs.
  - The DEWEY worker runs synchronously in-request; it is not a scheduler.
  - `embeddings_cache_store.py` and `trajectories_store.py` are referenced as
    integration points, not documented here — candidates for the storage
    sub-batch.
  - *(Clarified in 10f: `embeddings_cache_store.py` and `trajectories_store.py`
    are already documented in `docs/storage_stores.md`; the earlier 10e
    "candidate for storage sub-batch" wording above is retained for
    provenance.)*

### Sub-batch 10f — Markov

- **Added:** `docs/markov.md`
- **Fiction removed:** none. The 10f instruction flagged the Markov chat
  runtime, the 4/3-1 architecture, the predictive envelope, and the
  Observer / Interpreter / Regulator / Projector processors as possibly
  fictional; all four are implemented (`POST /markov/chat`, the labelled 4/3-1
  processor pipeline, Markov v3's predictive envelope, and the named processor
  stages) and are documented. Nothing was removed.
- **Notes:**
  - Markov is cross-cutting but is not a scheduler — state advances only on an
    explicit request.
  - The `markov_states` store is documented in `docs/storage_stores.md`;
    `docs/markov.md` covers the behavior layered over it.
  - The Markov-predictive helpers in `dewey_pipeline.py` are documented in
    `docs/markov.md` only for their Markov role, not their DEWEY role.
  - The legacy `POST /markov` engine endpoint is a stub adapter; the v4 chat
    generator is deterministic with no model call.

### Sub-batch 10g — Continuity

- **Added:** `docs/continuity.md`
- **Fiction removed:** the 10g instruction's suspected-fiction constructs are
  all genuinely absent — `runtime_continuity.py` is not a "continuity vault as
  LLM memory", not a "cross-session agent identity" system, and not an
  "autonomous continuity engine"; it carries no scheduler, DEWEY, or Markov
  semantics. The instruction also named `session_loop.py` and
  `elins_session_integrator.py` as call sites; they are not — they share the
  `vault_state` data contract but do not call `runtime_continuity`.
- **Notes:**
  - Continuity (`runtime_continuity.py`, Unit 37) is implemented and fully
    tested but **not yet wired** — no production code path calls
    `resume_runtime_session`; it is designed to seed the runtime kernel
    (Unit 35).
  - `/continuity/snapshot` (a v28 cockpit surface) and `operator_state.py`'s
    `continuity_section` / `continuity_context` are separate, unrelated
    "continuity" surfaces — not covered by `docs/continuity.md`.
  - No scheduler, no DEWEY, no Markov, no memory engine.

### Sub-batch 10h — Dashboard

- **Added:** `docs/dashboard.md`
- **Fiction removed:** an "autonomous dashboard", a "Dashboard AI", and a
  "predictive dashboard engine" do not exist — `elins_dashboard.py` is a
  deterministic read-only aggregator (no network, no model). The cockpit-era
  "State Engine panel" / "Drift indicator" / "Layer pipeline panel" are absent
  here too. There is no backend `/dashboard` route — `/dashboard` is the web
  route; the backend endpoints are `/elins/dashboard`, `/elins/dashboard/{date}`,
  and `/founder/elins/dashboard/overview`.
- **Notes:**
  - Dashboard is the backend read-only aggregation subsystem; the Cockpit is
    frontend-only and already documented in `docs/cockpit/cockpit_spec.md`
    (not recorded as a Batch 10 sub-batch).
  - The dashboard surfaces forecasts but does not compute them —
    `ELINS.forecast_engine` does; the dashboard recomputes via it only as a
    fallback for pre-v34 persisted records.
  - `elins_timeline_dashboard.py`, `elins_run_dashboard.py`, and
    `acceptance_dashboard.py` are separate dashboards, not part of this
    subsystem.

### Sub-batch 10i — Intelligence Kernel

- **Added:** `docs/intelligence_kernel.md`
- **Fiction removed:** there is no "TermResolution" subsystem (a prompt-era
  10-series label with no module in code). The kernel is not an "Intelligence
  Engine", an "autonomous kernel", or a "self-directing intelligence layer" —
  it is request-driven orchestration with no background loop. It owns no
  forecasting, DEWEY, or Markov logic, and it is not the runtime kernel /
  dispatcher.
- **Notes:**
  - The kernel is the central orchestrator; its spokes (model router, ESO,
    ELINS, DEWEY, Markov, schedulers, operator_state) own computation.
  - `run_macro_ELINS` runs a full macro pass with no cadence gating —
    `elins_scheduler` decides when.
  - The module docstring lists only the v40 surface; the live public API is
    larger (v47 threads, v50 summary, v52 emotional_physics, v53 elins_v2,
    v54 ingestion, v71 reasoning_mode, v79 regression_first).

### Sub-batch 10j — Runtime Execution Layer

- **Added:** `docs/runtime.md`
- **Fiction removed:** an "autonomous runtime loop", a "self-healing
  dispatcher", and an "execution AI" / "runtime engine" do not exist — the
  runtime is a pure-functional kernel / dispatcher / runner chain wrapped in
  a stateless HTTP surface plus a persistence layer; the dispatcher is a
  rule-based deterministic stub. "TermResolution" (retired in 10i) is not
  part of this layer. Two candidate modules with adjacent `runtime_*` /
  `operator_*` naming were excluded — `runtime_intelligence_wiring.py` (a
  read-only intelligence-wiring surface, Phase 3 Unit 1) and
  `operator_mode.py` (a descriptive posture derivation, Phase 11) — see the
  doc's Non-goals.
- **Notes:**
  - Runtime execution (10j) is distinct from the Intelligence Kernel (10i)
    and `operator_state` (the future 10k target).
  - `runtime_continuity.py` (Unit 37) is the dormant reentry module
    documented in `docs/continuity.md` (10g); excluded here.
  - The cluster covers Phase-1 Units 35 / 36 / 39 / 40 / 41 / 42 plus the
    later Units 65 (provider bridge) and 71 (config leaf), unified as a
    single architectural layer.

### Sub-batch 10k — Operator State

- **Added:** `docs/operator_state.md`
- **Fiction removed:** prompt-era notions of an "Operator State Engine",
  an autonomous operator-state updater, an operator-memory AI / ML model,
  a self-healing posture system, distributed operator state, and any
  background daemon or reconciliation loop; fabricated fields
  (`last_run_type`, `last_mode`, `last_qc`, `last_elins_run`,
  `last_g_run`, `last_c_run`, `operator_intent`, `session_context`, a
  single combined `history` list); fabricated functions (`record_c_run`,
  `record_elins_run`, `record_external_signal_mode`, `record_qc`,
  `record_operator_intent`, `record_session_context`, a public
  `prune_history`, and any `read_user_state` / `write_user_state`
  wrappers); and misremembered integrations where runtime or QC writes
  directly to operator state or ELINS pipelines bypass the kernel.
- **Notes:**
  - Replaces and removes `docs/state_engine.md` (pre-Batch-10,
    non-house-style) as the documentation for `operator_state.py`;
    `docs/operator_state.md` is now the canonical Operator State doc.
  - Operator State's `continuity_section` / `continuity_context` provide
    the operator-state continuity slice — distinct from the Batch 10g
    continuity doc (`docs/continuity.md`) and from any
    `/continuity/snapshot` endpoint.
  - Operator State never persists prompt text; `_strip_forbidden` removes
    `("text", "scenario_text", "input_text", "raw_text")` from stored
    contexts before persistence.
  - All persistence is delegated to the Memory Vault; the detailed vault
    substrate is the target of Sub-batch 10l (Memory Vault).

### Sub-batch 10l — Memory Vault

- **Added:** `docs/memory_vault.md`
- **Fiction removed:** prompt-era notions of a "Vault Engine", an
  autonomous vault, a "vault AI" / ML model, a distributed vault, a
  multi-key transactional vault, vault watchers / events / observers /
  pub-sub, vault TTL / auto-expiry / GC, vault background compaction,
  vault indexing beyond namespace prefix, a vault query language,
  vault-side schema enforcement, and vault-side migrations; fabricated
  APIs (`vault_scan`, `vault_search`, `vault_query`, `vault_put_many`,
  `vault_batch`, async / callback variants, "team vault" / shared-key
  reads, `read_user_state` / `write_user_state` wrappers); fabricated
  crypto framings ("encryption handled below the API" — it is inline
  stdlib Python: PBKDF2 + HMAC-CTR + HMAC-SHA256; Fernet is noted only
  as a future swap target; no external cryptography library
  dependency); and fabricated configuration (a default master secret —
  there is none, missing `CLARITYOS_VAULT_SECRET` is a hard error;
  automatic key rotation; vault-managed user provisioning beyond the
  idempotent `vault_init` scaffold).
- **Notes:**
  - Supersedes `docs/vault/vault_spec.md` and
    `docs/vault/vault_deep_structure.md` as the canonical Memory Vault
    documentation; both files are retained with legacy banners to
    preserve `vault_store.py` coverage and historical context (separate
    module, not in scope for 10l).
  - `docs/threads.md` cross-reference updated from
    `docs/vault/vault_spec.md` to `docs/memory_vault.md`.
  - Public API is 11 functions, not 4 — earlier prompt-era summaries
    omitted `vault_get`, `vault_clear`, `vault_keys_for_user`,
    `vault_count_for_user`, `vault_known_users`, `vault_status`, and
    `namespace_of`. The doc lists all 11 explicitly.
  - Encryption is inline Python (PBKDF2-HMAC-SHA256 key derivation,
    HMAC-CTR stream cipher, HMAC-SHA256 encrypt-then-MAC, scheme-byte
    envelope), not delegated to a library; the construction is fully
    stdlib so the runtime gains no new dependency.
  - Four backends are documented (`mock`, `fs`, `sqlite`, `firestore`);
    `firestore` is the production backend, durable across Cloud Run
    cold starts.
  - All retention / pruning policy is the caller's responsibility (see
    e.g. `operator_state._prune_history`, documented in
    `docs/operator_state.md`); the vault itself has no TTL, GC, or
    background work.
  - `vault_store.py` is a separate, unencrypted Firestore notes /
    sessions store; it is **not** documented by this sub-batch and
    remains covered by the retained `vault_spec.md` until a future
    sub-batch targets it directly.

### Sub-batch 10m — Vault Store

- **Added:** `docs/vault_store.md`
- **Fiction removed:** prompt-era notions of a "Vault Store engine",
  an autonomous vault store, a "vault store AI" / ML model, a
  distributed `vault_store`, multi-region replication, vault watchers
  / events / triggers / pub-sub, auto-pruning / TTL / GC / size
  quotas, vault-side background compaction, and a vault-store query
  language; fabricated APIs (`find`, `search`, `query`,
  `update_partial`, `patch`, `merge`, `count_for_user`, `list_all`,
  `bulk_write`, `batch_create`, pagination cursors, async / callback
  variants); fabricated security framings (schema enforcement, type
  validation, or ownership enforcement happening in `vault_store` —
  all three live in `app.py` at the route layer; encryption at rest —
  `vault_store` is plaintext in both backends; per-user backend
  selection — `_backend()` is global); and fabricated configuration
  (`CLARITYOS_VAULT_*` env vars, which belong to Memory Vault —
  `vault_store` uses only `CLARITYOS_BACKEND`).
- **Notes:**
  - Removes `docs/vault/vault_spec.md` and
    `docs/vault/vault_deep_structure.md` (and the now-empty
    `docs/vault/` directory). Both files were retained with legacy
    banners in 10l stating they were preserved "only for
    `vault_store.py` coverage and historical combined context"; with
    Vault Store now canonical at `docs/vault_store.md`, both are
    fully superseded.
  - Cross-references to the deleted `docs/vault/` directory updated:
    `docs/overview.md` Document Set paragraph dropped the dedicated
    "vault documents under `docs/vault/`" clause (vault docs now live
    at the docs/ root like other subsystem docs); `docs/operator_handbook.md`
    Vault entry now points to `docs/memory_vault.md` and
    `docs/vault_store.md`. The 10l manifest entry's references to
    `docs/vault/vault_spec.md` and `docs/vault/vault_deep_structure.md`
    are retained as provenance per the Batch 10 methodology — no
    silent edits to past entries.
  - Provenance / 10k cleanup gap: discovered during 10m closeout that
    `docs/operator_handbook.md` also references the deleted
    `docs/state_engine.md` (which was removed by 10k). The
    surrounding text describes "state classification and drift,"
    which does not cleanly map to `docs/operator_state.md`'s actual
    scope (per-user metadata recorder, not a state engine). Flagged
    here for a separate corrective sub-batch — not patched in 10m.
  - The persistence stack is now fully canonical at the docs root:
    Operator State (10k), Memory Vault (10l), and Vault Store (10m)
    each have one house-style root-level doc with no competing
    sources of truth.
  - The module docstring lists 8 fields for the document shape; the
    actual `app.py`-persisted shape is **11 fields** — adds `title`,
    `object_vector` (Dewey embedding), and `updated_at`. The doc
    reflects the persisted shape, not the stale docstring.
  - Type whitelist `ALLOWED_VAULT_TYPES = ("note", "session",
    "elins_raw")` is defined and enforced in `app.py`, not in
    `vault_store`. The module accepts any string in the `type` field.
  - `vault_store` is **plaintext** (no encryption); for sensitive
    per-user data use Memory Vault (`docs/memory_vault.md`).
  - `dewey_worker.py` is a writer (backfills `object_vector` on
    legacy docs); aside from `app.py` it is the only direct caller.
  - HTTP endpoints live at `/vault/*` (root), distinct from Memory
    Vault's `/me/vault/*`.

### Sub-batch 10n — Operator Handbook Alignment

- **Updated:** `docs/operator_handbook.md`
- **Fiction removed:**
  - "State Engine" entry referencing deleted `docs/state_engine.md`
    (file removed in 10k; the "State Engine" concept does not map
    to `docs/operator_state.md`, which is a per-user metadata
    recorder, not a state engine — see the 10k Fiction Removed
    list).
  - "Five Layers" entry referencing the non-existent `docs/layers/`
    directory; the conceptual content (orientation, interpretation,
    inversion, integration, transformation) is already covered by
    `docs/cognitive_pipeline.md` (entry 3), making the entry
    redundant even if the directory existed.
  - "Operator Protocols", "Invariants", and "Glossary" entries
    referencing no existing docs anywhere in the corpus — purely
    aspirational sections of vapor.
- **Notes:**
  - 10n is **not a subsystem-doc sub-batch** — `operator_handbook.md`
    is an index / reading-order doc, so house-style §8 is
    deliberately not applied and no naming-ledger row is added.
  - Surviving entries renumbered 1–7: Introduction, Geometry System,
    Cognitive Pipeline, Cockpit, Vault, ELINS, Runtime.
  - "Reading Order" paragraph updated: was *"Sections 2 through 9
    specify subsystems. Sections 10 through 12 specify the rules
    and vocabulary that span them"* → now *"Sections 2 through 7
    specify subsystems. General rules and vocabulary are documented
    within those subsystem docs and in the methodology/meta docs."*
  - Entry 6 (ELINS) still points to the legacy `docs/elins/`
    directory; ELINS has no Batch 10 canonical doc yet (similar to
    where Vault was before 10l/10m). A future ELINS sub-batch
    should canonicalize that directory at the docs root and update
    this entry, following the 10l/10m pattern.
  - Future Operator Protocols / Invariants / Glossary content
    should be added as real docs first, then referenced here.

### Sub-batch 10o — ELINS Alignment

- **Updated:** `docs/elins/elins_deep_spec.md`,
  `docs/elins/elins_report_visual.md`, `docs/operator_handbook.md`
- **Fiction removed:** clarified that the `el_ins/` package
  (`el_ins_analyzer`, `el_ins_store`, `el_ins_export`) is a distinct
  per-turn analyzer gated by `operator_state.el_ins_per_turn` and is
  not part of the ELINS-canonical long-arc pipeline. The pre-existing
  ELINS "What ELINS is not" section already retired the prompt-era
  visual myths ("sphere / pentagon / rings", "metadata cloud"), the
  five-stage `Input → Processing → Curvature → Drift → Output`
  architecture, and the `Detect → Classify → Generate → Validate →
  Propagate` loop; those rejections are reinforced by 10o's formal
  recognition of the existing docs as canonical.
- **Notes:**
  - 10o is an **alignment + canonical-recognition** sub-batch, not a
    rewrite. The existing `docs/elins/elins_deep_spec.md` and
    `docs/elins/elins_report_visual.md` are substantive, code-true,
    and pre-dated the formal Batch 10 sub-batch process; 10o formally
    recognizes them as the canonical ELINS docs.
  - The `docs/elins/` subdirectory is **retained** — ELINS legitimately
    has two complementary docs (pipeline spec + report surfaces), and
    splitting them across the docs root would obscure that pairing.
    This differs from the 10l/10m vault treatment (which split
    `docs/vault/` because the two files there documented two distinct
    subsystems).
  - Cross-references added inside `docs/elins/elins_deep_spec.md`:
    Memory Vault (`docs/memory_vault.md`, to clarify ELINS does not
    use it), Intelligence Kernel (`docs/intelligence_kernel.md`, at
    the `run_ELINS` entry point), Operator State
    (`docs/operator_state.md`, where ELINS interactions are recorded
    as analysis-derived metadata).
  - Cross-reference added inside `docs/elins/elins_report_visual.md`:
    Dashboard (`docs/dashboard.md`, at the ELINS dashboard surface).
  - `docs/operator_handbook.md` entry 6 updated to point directly at
    the two canonical ELINS docs (was: directory `docs/elins/`).
  - Scope context: ELINS spans ~70 Python files across three groups
    (ELINS/ canonical pipeline, `elins_*` root-level analytics suite,
    and the separate `el_ins/` per-turn analyzer). The existing docs
    cover this scope at the right level of abstraction — module-level
    enumeration would be a non-goal per Batch 10 methodology §3.

### Sub-batch 10p — Emotional Reality Alignment (ERA)

- **Added:** `docs/era.md`
- **Fiction removed:** prompt-era notions of an "ERA engine AI", an
  autonomous reframer, a "reframing ML model", a learning loop,
  cross-user reframe sharing or training, a multi-step LLM reasoning
  chain, a background reframe scheduler, and a batch reframe
  processor; fabricated APIs (`apply_reframe`, `commit_plan`,
  `send_reframe`, async / streaming variants, `from_text` raw-text
  entry, multi-plan / batch generation, plan diff, plan merge);
  fabricated security framings ("ERA stores user emotional history" —
  stateless; "ERA logs to a moderation pipeline" — no logging;
  identity / PII handling — structurally precluded); fabricated
  integrations (direct HTTP endpoint, direct Operator State / Memory
  Vault / Intelligence Kernel writes — ERA is consumed only by
  `azimuth_transition.py` and `fea_integration_engine.py`); and
  fabricated naming bridges (ERA is not the v52 `emotional_physics`
  kernel reasoning mode despite the namespace overlap on "emotional"
  — different inputs, different determinism, different invariants).
- **Notes:**
  - ERA is anchored to the external spec
    `SPEC_EMOTIONAL_REALITY_ALIGNMENT.md` (kept at the repo root,
    not in `docs/`). `docs/era.md` cross-references it as the
    source-of-truth behavioral spec.
  - ERA reuses `PressureLevel`, `IntensityLevel`, `Valence` from
    `azimuth` and `ExpressionPrimitive` from `language_schemas`;
    these upstream modules are **not yet documented as Batch 10
    subsystems** and are candidates for future sub-batches. ERA
    treats them as opaque inputs.
  - The engine is pure Python — no I/O, no LLM, no network, no
    randomness — and is structurally prevented from carrying
    `text`, `raw`, `user`, `id`, `name`, `email`, `session`, or 7
    further forbidden fields through any output type. Three
    module-load runtime guards (`assert_era_privacy_contract`,
    `assert_era_field_sets_canonical`,
    `assert_reframe_types_canonical`) fail import on schema drift.
  - The downstream wiring is real and live:
    `azimuth_transition.compute_aligned_expression()` calls
    `align_expression()` (around `azimuth_transition.py:1091-1145`),
    and `fea_integration_engine.integrate_alignment()` consumes the
    `AlignedExpression` to compute a halt level and surface
    directives. The SPEC's "Phase Plan" listed both as pending; both
    are now done.
  - ERA does **not** appear in `docs/operator_handbook.md`. The
    handbook is an index of operator-facing reading sections; ERA
    is a library-internal subsystem and not part of the operator
    reading order.
  - Distinct from v52 `emotional_physics` — that is a reasoning
    mode inside `intelligence_kernel.py` that calls an LLM with a
    specific prompt and operates on raw user text. ERA is pure
    deterministic Python over structural inputs. The two share a
    namespace word but are different concerns.

### Sub-batch 10q — Intelligence Kernel post-v40 surface expansion

- **Updated:** `docs/intelligence_kernel.md`
- **Fiction removed:** the "homogeneous kernel reasoning modes" frame — the
  post-v40 surface (v52, v53, v54, v71, v79) is **not** a uniform cluster.
  Only `run_emotional_physics` (v52) is an LLM-mediated reasoning mode.
  `run_elins_v2` (v53) is a deterministic Path-C view adapter with no LLM.
  The v54 ingestion functions (`run_manual_ingestion`, `run_feed_ingestion`,
  `run_ingestion_cycle`) are orchestrators that delegate to v53.
  `select_reasoning_mode` (v71) is a pure deterministic classifier.
  `run_regression_first` (v79) is a deterministic packet analyzer whose
  model_id resolution is telemetry only — the kernel docstring (lines
  1239-1243) explicitly states the kernel does NOT drive an LLM there.
  Also corrected: the prior "Its one HTTP endpoint" framing in
  Implementation location (the kernel actually exposes 7 HTTP endpoints).
- **Notes:**
  - 10q is an **expansion sub-batch** for the existing 10i Intelligence
    Kernel doc, not a new doc. No ledger row is added (Intelligence Kernel
    already has its 10i ledger row); precedent = 10n handbook patch.
  - The existing 10i doc already named all 5 post-v40 functions in
    APIs / entrypoints. 10q enriches those mentions with per-function
    task / prompt / output-contract details for v52, explicit Path-C
    framing for v53, orchestrator-vs-reasoning-mode distinction for v54,
    classifier label set and threshold constants for v71, and the
    upstream-LLM / telemetry-only framing for v79.
  - HTTP endpoints added to Implementation location:
    `POST /me/emotional_physics/analyze`, `POST /elins/v2/run`,
    `POST /ingest/manual`, `POST /ingest/feeds/run`,
    `POST /me/regression_first/{start, packet}` (in addition to the
    existing `GET /founder/intelligence/kernel/status`).
  - Two invariants added: (1) `run_emotional_physics`'s 4-key output
    contract is structurally locked via `_emotional_physics_skeleton()`
    with graceful degrade; (2) not every kernel run dispatches a model —
    most of the post-v40 surface is deterministic, and v79's model
    resolution is telemetry only.
  - **Out of scope:** the `intelligence_kernel.py` module-level docstring
    still describes only the v40 surface; updating it is a code change
    (not a docs change) and is flagged here for a future code-cleanup
    task rather than a Batch 10 sub-batch.

### Sub-batch 10r — Regression-First Protocol

- **Added:** `docs/regression_first.md`
- **Fiction removed:** prompt-era notions of an LLM-mediated
  `analyze_packet` (the function is pure deterministic JSON parser +
  validator; LLM mediation happens UPSTREAM, in the caller that
  constructs the unified packet under the bundle prompt); a state
  machine that advances chains automatically (operators drive layer
  creation; the kernel never advances a chain); `reopen` / `unclose`
  / `unarchive` surfaces (closing and archiving are both one-way); a
  kernel-driven LLM call inside `run_regression_first`
  (intelligence_kernel.py:1239-1242 explicitly states otherwise;
  model resolution is telemetry-only); a skill-manifest Python
  import path (the `skills_export/regression_first/` bundle is read
  as plain text via `Path.read_text`, never imported); LLM calls
  inside the auto-trigger layer (pure-lexicon detection only);
  cross-user chain access (structurally precluded by per-user vault
  partitioning); a canonical pre-populated layer scaffold (the
  packet's `regression_chain` skeleton is informational, not
  seeded); background reconciliation / scheduler / worker (every
  operation is request-driven); tag query / filter / bulk-replace
  surface (only `tag_chain` merge and `delete_tag` single-key
  removal exist); `find_by_*` or chain query language (`list_chains`
  returns all newest-first); fabricated endpoint paths (the earlier
  `/record`, `/get`, `/list` paths do not exist; real paths are
  `/step`, `/{chain_id}`, `/`); coupling to the ELINS-regression
  analytics suite (separate subsystem, documented in
  `docs/elins/elins_deep_spec.md` per 10o); and `CognitivePacket`
  persistence as a TypedDict shape (the stored
  `regression_packets.{chain_id}` entries are the original raw
  packet dicts, not parsed views).
- **Notes:**
  - 10r is a **new canonical subsystem doc** for the
    `problem_solver/` package (V76 / V77 introducing pluggable
    storage; V79 kernel task; V80 packet endpoint; V81 archive +
    delete_tag; V82 replay).
  - The protocol persists under **two** vault namespaces of
    `memory_vault.ALLOWED_NAMESPACES`: `regression_chains` (chain
    documents) and `regression_packets` (write-once original
    packets, consumed by v82 replay). Both were registered in 10l.
  - `intelligence_kernel.run_regression_first` resolves a
    `model_id` via `_resolve_model(task="regression_first")` for
    **telemetry only**; it never invokes a model. The kernel
    docstring at intelligence_kernel.py:1239-1242 makes this
    explicit. The cross-reference is in `docs/intelligence_kernel.md`
    (10q expansion).
  - **`model_router.TASK_DEFAULTS` comment/entry mismatch flagged,
    not normalized.** The entry
    `"regression_first": "openai:gpt-4o"` (model_router.py:131)
    does not match its preceding comment referencing Claude 3.7
    (the model the bundle prompt was originally written for).
    `docs/regression_first.md` records the code-truth and
    explicitly documents the discrepancy in §5 for future review.
  - The `skills_export/regression_first/` external bundle (3 files:
    `system_prompt.md`, `schema.json`, `README.md`) is read as plain
    text via `Path.read_text`, never imported as Python. This
    preserves the no-skills-import architecture boundary in
    `ARCHITECTURE.md`.
  - **Distinct from the ELINS-regression analytics suite**
    (`elins_regression_single_party`, `elins_regression_economic_coercion`,
    `elins_regression_compare`), already documented in
    `docs/elins/elins_deep_spec.md` (10o). The shared word
    "regression" is a naming collision, not an architectural link.
  - No update to `docs/operator_handbook.md` — Regression-First is
    a kernel-internal protocol, not a front-of-house operator
    workflow. Same precedent as ERA in 10p.
  - The behavioural contract is locked by ~152 tests across 6 test
    files; verified during PASS-3D.
