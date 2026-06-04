# ClarityOS — Envelope / Data-Management Audit

**OPORD response · read-only · no code modified.** Evidence is `file:line` in the
current tree (verified live, not from memory).

---

## Executive finding (reads against the OPORD's premise)

The OPORD assumes a **single canonical "envelope"** that all data is wrapped in as it
moves through primitives → runtime → vault → UI. **The codebase does not work that
way, and pretending it does would be inaccurate.** Two true statements:

1. **"Envelope" is the single most overloaded word in the repo — ~10 unrelated
   meanings.** Only one of them is a data-management record wrapper.
2. **There is no universal record envelope.** A real, consistent, enforced
   user-content record envelope exists in **exactly three stores** (`vault`,
   `library`, `timeline`). Every persistence layer added from v46 onward (everything
   built on `memory_vault`) and the ELINS/EL-INS run stores **intentionally use a
   different pattern**.

So the honest audit conclusion is: **two intentional storage patterns + one badly
overloaded term**, not one envelope with violations. The risk to "payment / login /
runtime entry" is **not** that they'll "bypass the envelope" (most features already
don't use it, by design) — it's that the **name "envelope" means 10 things**, which
makes generic reasoning about records error-prone. The highest-value, in-scope fix is
**disambiguation + documentation**, not restructuring.

---

## Section 1 — Envelope definition(s)

### 1a. The canonical user-content record envelope — `vault` / `library` / `timeline`

Hand-declared (not shared) in three modules with a common core:

| Field | vault | library | timeline | type | meaning |
|---|---|---|---|---|---|
| `id` | ✅ `v_*` | ✅ `l_*` | ✅ `t_*` | str | record id (store-prefixed) |
| `user` | ✅ | ✅ | ✅ | str | **owner** (enforced at route layer) |
| `type` / `kind` | `type` | — | `kind` | str | record/event class |
| `title` | — | ✅ (required) | — | str | heading |
| `content` | ✅ | ✅ | — | str | body text |
| `tags` | ✅ | ✅ | — | list[str] | labels |
| `metadata` / `data` | `metadata` | `metadata` | `data` | dict | passthrough |
| `ref` | — | — | ✅ | str? | points at source record id |
| `summary` | — | — | ✅ | str | human event description |
| `object_vector` | ✅ | ✅ | ✅ | list[float] | DEWEY embedding (counts toward size) |
| `size_bytes` | ✅ | ✅ | ✅ | int | serialized JSON size (quota) |
| `created_at` | ✅ | ✅ | ✅ | float (s) | server write time |
| `updated_at` | — | ✅ | — | float (s) | last modification |
| `ts` | — | — | ✅ | float (s) | event time (caller-supplied) |

Definitions: `vault_store.py:8`, `library_store.py:7`, `timeline_store.py:5`. **No
shared constructor/validator** — each store re-declares the shape; the write bodies in
`app.py` build the dict inline (`app.py:2041`, `:2187`, `:2294`).

**The word "envelope" in this layer = a per-object BYTE-SIZE CAP**, not the wrapper:
`app.py:1916 _envelope_check(payload_bytes, max_bytes, kind)` → `413 envelope_exceeded`;
`VAULT_ENVELOPE_BYTES = 256*1024`, `LIBRARY = 128*1024`, `TIMELINE = 32*1024`
(`app.py:304-306`). Plus a per-user cohort **quota** (`_assert_quota` `app.py:1927`;
founder-like → 1 GB else 500 MB; `413 quota_exceeded`).

**Example instance** (a vault note):
```json
{ "id":"v_x8…","user":"alice","type":"note","content":"…","tags":["idea"],
  "metadata":{},"object_vector":[0.01,…],"size_bytes":742,"created_at":1.748e9 }
```

### 1b. The *second* pattern (intentional) — `memory_vault` namespaced encrypted KV (v46+)

`memory_vault.py` stores each value as a bare encrypted entry `{"v": ciphertext_b64,
"ts": float}` under `namespace.key` (`vault_put` `memory_vault.py:678`). **No per-record
`id` / `type` / `owner` / `created_at` / `version`** — `owner` collapses into the vault
partition, and version lives on the *module* (`VAULT_VERSION="memory_vault.v46.1"`
`:65`; `STATE_VERSION`, `THREADS_VAULT_VERSION`, …). Here "envelope" = the **encryption
container** (`scheme_byte‖nonce‖ciphertext‖mac`, `_encrypt_value` `memory_vault.py:331`).
Stores built on it: `operator_state`, `threads_vault`, `projects_vault`,
`problem_solver/chain_store` (the latter explicitly: *"no envelope/header, the chain
dict itself is the value"* `memory_vault.py:88`).

### 1c. The other "envelope" meanings (glossary — so they aren't conflated)
| # | Meaning | Anchor |
|---|---|---|
| 1 | storage record wrapper | `vault_store.py:8` |
| 2 | ELINS forecast **math** `ep(D+n)=ep0·e^(−λn)` | `ELINS/forecast_engine.py:152` |
| 3 | per-user ELINS **accumulator doc** ("Envelope Base Layer") | `envelopes_store.py`, `app.py:5495 _evolve_envelope` |
| 4 | Markov **`qc_envelope`** (4 QC metrics) | `markov_states_store.py:11`, `app.py:2686` |
| 5 | HTTP **response wrapper** `{ok,…}` | `app.py:539`, `error_response :528` |
| 6 | **byte-size cap** | `app.py:1916`, `VAULT_ENVELOPE_BYTES :304` |
| 7 | **encryption container** | `memory_vault.py:331` |
| 8 | Azimuth **privacy boundary** (holds `raw_text`) | `azimuth_envelope.py:1` |
| 9 | ELINS-run **persistence wrapper** `{metadata,result}` | `elins_persistence_sqlite.py:118` |
| 10 | ingestion-bus **packet** (`ENVELOPE_TYPE=…`) | `daily_personal_elins.py:498` |

---

## Section 2 — Data flow overview

Constructed **inline per write endpoint** (vault/library bodies are near-duplicates),
sharing only the finalize helpers: `_serialized_size` → `_envelope_check` (size) →
`_assert_quota` (quota) → `embed_object` → `_emit_timeline` (auto-emit).

```
A. Vault note:
 web/src/routes/Vault.tsx (vaultWrite, api.ts:274)
  → POST /vault/write app.py:2033  [build app.py:2041 · embed :2050 · _envelope_check :2052 · _assert_quota :2053]
  → vault_store.create vault_store.py:71  [+ usage_store.add_bytes app.py:2058]
  → AUTO-EMIT _emit_timeline("vault.write") app.py:2063 → timeline_store.create timeline_store.py:70
  → GET /vault/list app.py:2152 → vault_store.list_for_user :100
  → web/src/routes/Vault.tsx renders ServerVaultItem (api.ts:234) + UsageEnvelope (api.ts:229)

B. Library entry:  Library.tsx → POST /library/write app.py:2178 → library_store.create :74
                   → AUTO-EMIT library.write app.py:2209 → GET /library/list → Library.tsx

C. Timeline (append-only; it *is* the timeline, no auto-emit):
   POST /timeline/write app.py:2285 → timeline_store.create :70 → GET /timeline/list app.py:2319
   (Python-side kind/since/until filter timeline_store.py:123) → Timeline.tsx (ServerTimelineEvent api.ts:259)
```
Auto-emit is **best-effort** (`_emit_timeline` `app.py:1984` swallows all exceptions
`:2029`) so a timeline failure never fails the primary write. The same pipeline is
reused by ELINS ingest (`app.py:2449`, `:2488`) and the v29 demo seed (`app.py:9110`).

---

## Section 3 — Deviations

> Distinguish **intentional** (a design choice) from **accidental** (a real
> inconsistency). Most of what looks like a "violation" is the intentional second
> pattern (§1b); the genuinely accidental items are flagged ⚠️.

### 3a. Term overload — the #1 consistency problem
"envelope" = **10 unrelated things** (table in §1c). ⚠️ Two of them collide **inside a
single frontend file**: `web/src/state/cockpitStore.ts:36-37` declares both
`RuntimeEnvelope` (meaning #3) and `SessionEnvelope` (meaning #4) as co-existing
"envelope" slices.

### 3b. Field-name drift across modules
- **timestamp:** `created_at` (vault/library/timeline/users/invites) vs `ts`
  (timeline/dm/membership/memory_vault entry) vs `updated_at`; ⚠️ `incident_store.py`
  uses **epoch ms**, everything else **seconds**.
- **owner:** `user` (vault/library/timeline/usage/dm/sessions) vs `operator_id`
  (`el_ins_store`) vs `founder` (`dm_store`) vs `system_user` (scheduler) vs **absent**
  (memory_vault-backed). The literal token `owner` is used **nowhere**.
- ⚠️ **`type` vs `kind` are swapped for the same role.** Storage uses `type` for
  record-class (`app.py:2043`) but `kind` for event-class (`timeline_store.py:11`);
  billing uses `kind` for intent-class (`app.py:9426`) and `type` for tx-class
  (`app.py:8506`). Highest-risk drift for anyone reasoning about records generically.
- **content vs body** (dm_note uses `body`); **payload** = "the whole record"
  (`vault_store.py:71`) vs "a side-channel dict" (`payload_meta`); **summary** has 3
  meanings (timeline event vs kernel digest vs ingestion section).

### 3c. Raw / non-record paths (mostly **intentional** = the §1b pattern)
`/me/vault/notes` stores a **bare string** (`app.py:11517`; GET defensively handles
str-or-dict `:11511`); `/me/vault/embeddings` a **bare list[float]** (`app.py:11568`);
`operator_state` history dicts (`operator_state.py:407`); `threads_vault.ThreadMeta`
(`:222`), `projects_vault.ProjectMeta` (`:244`), regression chains (`chain_store.py:190`),
`el_ins_store.ElInsRecord` (`:51`), ELINS-run `{metadata,result}`
(`elins_persistence_sqlite.py:326`). **These are the second pattern, not bugs** — but
they are **undocumented as a deliberate exception**, which is what makes them read as
violations.

### 3d. Frontend ⚠️ accidental
`ServerVaultItem.type` is typed `"note" | "session"` (`api.ts:237`) but the backend
also accepts `"elins_raw"` (`ALLOWED_VAULT_TYPES` `app.py:310`) — a type-completeness
gap.

---

## Section 4 — Minimal fixes (surgical; no redesign, no renames of existing fields)

The system is **consistent within each pattern**; the defect is **naming +
documentation**, not structure. So the fixes are mostly docs + two tiny code touches.
**None applied — recommendations only.**

1. **Commit a glossary** (`docs/envelope_glossary.md`) = the §1c table. One page; ends
   the 10-way ambiguity for every future reader. *(doc only)*
2. **Document the two storage patterns as intentional** — one paragraph in
   `memory_vault.py`'s module docstring (it already half-says this `:88`): "record
   envelope (vault/library/timeline) for user *content*; namespaced encrypted KV
   (owner = partition, version = module) for operator *state*." Closes §3c as a
   documented exception. *(doc only)*
3. **Adopt a naming convention for NEW code** (do **not** rename existing fields — out
   of scope): owner→`user`, write-time→`created_at` (seconds), record-class→`type`,
   event-class→`kind`. A short CONTRIBUTING note. *(doc only)*
4. ⚠️ **`api.ts:237`** — add `"elins_raw"` to `ServerVaultItem.type` (1 line; fixes a
   real type gap).
5. ⚠️ **`cockpitStore.ts:36-37`** — rename the two TS *aliases* to
   `RuntimeAccumulator` / `MarkovQc` (frontend-only type aliases, no behavior/wire
   change) to stop the in-file "envelope" collision. *(optional; touches 1 file)*
6. *(optional)* Extract the inline vault/library/timeline record build into one
   `_build_record(...)` helper in `app.py` — removes the near-duplicate write bodies so
   the shape can't drift. Small, but it **is** a code change; flagged for a later OPORD.

### Commander's-intent verdict
- **Real / consistent / enforced?** ✅ for the `vault`/`library`/`timeline` record
  envelope (size cap + quota + auto-emit, §1a/§2). ✅ for the memory_vault KV pattern,
  *within itself*.
- **Universal / "nothing bypasses it"?** ❌ — and that's by design. Payment, login
  (`sessions_store`: `{user, expires_at}`), and runtime (`envelopes_store` /
  `qc_envelope`) each use their own shapes; they don't and shouldn't route through the
  content record envelope. The thing to lock down before wiring those features is the
  **glossary + two-pattern doc** (items 1–2) so no one assumes a unified envelope that
  doesn't exist.

*No primitives, envelope models, core renames, or refactors introduced. No files
modified by this audit.*
