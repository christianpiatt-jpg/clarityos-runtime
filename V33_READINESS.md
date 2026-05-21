# ClarityOS v33 — Founder Console + ELINS Standardization + #cmt Readiness Report

**Build:** `20260506500000`
**Backend version:** `2.9`
**Status:** Ready — canonical 10-layer ELINS pipeline + S_ELINS QC + #cmt + founder console wired end-to-end.

This pass standardizes ELINS scenario processing as a deterministic
10-layer pipeline, ships the Most Relevant Comment Generator (#cmt /
MRCG v1.0), and stands up the Founder Console (web + phone) with the
DM pipeline and manual membership operations.

All **206 tests pass** under in-memory backends + mock billing
(54 new v33 tests).

---

## 1. ELINS Standardization

### Package: `ELINS/` (existing directory; new modules)
> Note: the on-disk directory is uppercase `ELINS/` (Windows-case is
> what NTFS reports). Imports use `from ELINS import ...`.

### `ELINS/standard_elins.py` (new)
The canonical 10-layer pipeline. Pure-Python + lexical + deterministic;
no model calls, no embeddings, no network. Same input → same output.

Layers (named `LAYER_NAMES` for stability):
```
0. input_phase            normalize + scenario_id + ts
1. primitives             6 EP primitives via lexicon (raw + intensities)
2. domain_mapping         keyword-to-domain weights (8 domains)
3. ep_field_summary       stress_total, relief_total, net, dominant
4. causal_chain           pairwise primitive co-occurrence above threshold
5. stress_relief          signal: relief_dominant / stress_dominant / balanced
6. forecast_5day          deterministic 12% mean-reversion phase trajectory
7. synthesis              top-line summary (top_primitive, signal, trend)
8. qc_s_elins             inline self-check (re-extract, confirm stable)
9. output_object          flat mirror of synthesis + scenario_id + version
```

`PRIMITIVE_KEYS = ("pressure", "tension", "trust", "drift",
"contradiction", "alignment")`. `DOMAIN_HINTS = ("legal",
"institutional", "economic", "geopolitical", "social", "personal",
"technological", "ecological")`.

Public API:
```python
generate_ELINS(input_text, *, domain_hint=None, user=None) -> dict
generate_S_ELINS(elins_object) -> dict  # alignment + pass/fail + deltas
```

`generate_S_ELINS` re-extracts primitives from the original input,
recomputes the EP summary, and returns:
```python
{
  "ok": True,
  "scenario_id": ...,
  "alignment_score": float,   # 1.0 = perfect; decays linearly
  "max_delta": float,
  "deltas": {primitive -> float},
  "fresh_primitives": {...},
  "fresh_ep_summary": {...},
  "passed": bool,             # max_delta < S_ELINS_PASS_THRESHOLD
  "threshold": 0.05,
  "version": "selins.v33.1",
  "ts": float,
}
```

Tests pin determinism (same text → same output) AND failure detection
(tampered intensities → `passed: False`).

### `ELINS/elins_project.py` (new) — persistence layer
Five logical "collections" mapped onto the in-memory + Firestore
backends:
* `runs/`         per-day per-user ELINS run records
* `primitives/`   rolling primitive intensity index
* `domains/`      rolling domain history per user
* `baseline/`     per-user EP baseline averages (EWMA, alpha=0.2)
* `config/`       reserved (currently unused; future module-level config)

Helpers (the only API consumers should use):
```python
save_daily_run(user, run, *, day=None) -> str       # idempotent on day
load_previous_run(user, *, day=None) -> dict | None
update_global_primitive_index(run) -> dict
update_domain_history(user, run) -> dict
update_ep_baseline(user, run, *, alpha=0.2) -> dict
get_baseline(user) -> dict | None
get_run(run_id) -> dict | None
list_runs_for_user(user, *, limit=30) -> list[dict]
list_primitive_index(*, limit=200) -> list[dict]
list_domain_history(user, *, limit=200) -> list[dict]
```

Same-day `save_daily_run` overwrites — tested via
`test_save_daily_run_idempotent_on_same_day`.

### Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /elins/preview` | session + `v28_surfaces` | run pipeline on text, no persistence |
| `POST /elins/global` | founder | run + persist to elins_project/* |
| `POST /elins/qc` | session + `v28_surfaces` | re-run S_ELINS QC on a given ELINS object |

`/elins/g/run` (the existing v28 path) is unchanged; it remains the
embedded-vector + Dewey-neighborhood scenario engine. The
canonical pipeline complements it for surfaces that want pure
metadata/primitives without an embedding round-trip.

---

## 2. Comment Generator (#cmt)

### `comment_generator.py` (new) — MRCG v1.0

3-layer pipeline:

```
LAYER 1 — DETECTION
    attractor   ∈ {institutional_drift, trust_collapse, contradiction,
                   consensus_drift, stabilising_pressure, neutral}
    domain      ∈ DOMAIN_HINTS  (or None / hint)
    tone        ∈ {alarmed, frustrated, analytical, hopeful, neutral}

LAYER 2 — CONSTRUCTION
    structural_reframe   per-attractor x per-domain template
    domain_alignment     per-domain template
    identity_move        per-attractor "ClarityOS reads…" line
    stabilizing_close    per-tone closing line

LAYER 3 — ACTIVATION
    micro_thread_trigger   stable handle (`open_with_a_lens`)
    low_emotion            heuristic: ≤1 alarmed/frustrated hits
    noun_density           4+-char tokens minus function words / total
```

Public API:
```python
generate_comment(input_text, domain_hint=None) -> dict
generate_structural_reframe(detection) -> str
generate_domain_alignment(detection) -> str
generate_identity_move(detection) -> str
generate_stabilizing_close(detection) -> str
```

The output `comment` is the four constructed segments joined by spaces
— stable, low-emotion, high-signal. Tests pin attractor detection +
determinism + the low-emotion constraint.

### Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /cmt/generate` | session | run the MRCG pipeline |
| `POST /c/run` | session | mode-routed #c cloud engine; mode='comment' delegates to /cmt |

`/me.capabilities` now advertises `cmt`, `c_run_comment`,
`elins_preview`, `elins_qc` so clients can render the right buttons
without a second round-trip.

---

## 3. Founder Console

### Web — `/founder`
New `routes/Founder.tsx` mounts `<FounderDashboard />` which composes:

1. `CohortList`          — read-only `/public/cohort_status`
2. `MemberDetailPanel`   — username search → selects target user
3. `ManualActivateButton`— activate / cancel / adjust credits
4. `DMNotesPanel`        — DM inbox + add/append note
5. `WaitlistPanel`       — (existing v32 panel, embedded here)
6. `ELINSInspector`      — run `/elins/preview` + `/elins/qc`
7. `CommentGeneratorPanel` — `/cmt/generate`

The `/founder/waitlist` deep-link from v32 still works; the new
`/founder` route is the composed hub.

### Phone — five new screens + Founder badge

| File | Purpose |
|---|---|
| `phone/app/founder.tsx` | hub — links to the four sub-screens |
| `phone/app/member_detail.tsx` | activate / cancel / credit adjustments |
| `phone/app/elins_inspector.tsx` | `/elins/preview` + `/elins/qc` |
| `phone/app/dm_notes.tsx` | DM inbox + add + note append |
| `phone/app/comment_generator.tsx` | `/cmt/generate` |

`phone/app/settings.tsx` got a `FounderBadge` inline in the Account
card — only visible when `/me.cohort` is `founder` or
`founder_exception`. Tapping navigates to `/founder`.

---

## 4. DM pipeline — `dm_store.py` (new)

Two collections:
* `founder_dms/`        the DM record (channel + subject + snippet +
                        founder + ts + optional user/external_id)
* `founder_dm_notes/`   per-DM founder notes (body ≤ 4000 chars, plus
                        a monotonic `seq` for stable tie-break sort)

Public API:
```python
add_dm(*, founder, user=None, external_id=None,
       channel="manual", subject=None, snippet=None) -> dict
get_dm(dm_id) -> dict | None
list_dms(*, channel=None, limit=200) -> list[dict]
list_dms_for_user(user, *, limit=200) -> list[dict]
add_dm_note(dm_id, body, *, founder) -> dict | None
get_dm_notes(dm_id) -> list[dict]   # newest first
```

Endpoints (founder-only):
| Endpoint | Purpose |
|---|---|
| `POST /founder/dm/add`   | log a manual DM |
| `GET  /founder/dm/list`  | list DMs (filter by channel or user) |
| `POST /founder/dm/notes` | append a note + return the full notes list |

The phone-screen helper had a Windows clock-resolution flake; v33's
`seq` counter is the cross-version fix (mirrors v29's mesh-LRU
mitigation).

---

## 5. Manual membership operations

Three founder-only endpoints. All record a transaction with
`metadata.manual=True` so audits can distinguish them from real
PaymentIntent-driven activations.

| Endpoint | Purpose |
|---|---|
| `POST /founder/membership/activate` | manually activate user (no PaymentIntent); writes `billing_state=active` + `renewal_ts=now+30d` |
| `POST /founder/membership/cancel` | flip user to cancelled (mirror v31 cancel) |
| `POST /founder/membership/credits` | grant or revoke #G credits (delta in [-1000, 1000], non-zero, can't drive balance below 0) |

Tested:
* activate happy path → `billing_state=active`, `price=$50`.
* activate unknown user → 404.
* cancel + verify both `membership_status` and `billing_state`.
* credits grant + revoke (round trip).
* would-go-negative blocked at 400.
* zero delta blocked at 400.

---

## 6. Tests — `tests/test_v33_founder_console.py` (new)

54 tests, all green. Coverage:

* `ELINS/standard_elins`: 10-layer presence, primitive extraction,
  domain mapping, determinism, empty-input rejection, bad-domain-hint
  rejection, S_ELINS pass/fail, edited-object detection.
* `ELINS/elins_project`: save/load previous run, same-day idempotency,
  global primitive index, domain history, EP baseline EWMA smoothing.
* `comment_generator`: shape, attractor detection, domain alignment,
  low-emotion constraint, determinism, empty-input rejection, bad
  domain hint rejection.
* `dm_store`: add + filter, notes round-trip, unknown-DM returns None.
* `/elins/preview` happy + flag-gated 403.
* `/elins/global` persists + requires founder.
* `/elins/qc` pass on clean object + 400 on empty dict.
* `/cmt/generate` happy.
* `/c/run` mode='comment' routed; unknown mode → 400.
* `/me` advertises `cmt` + `elins_qc` capabilities.
* `/founder/dm/{add,list,notes}` — founder gate, round-trip, 404 on
  unknown DM.
* `/founder/membership/{activate,cancel,credits}` — happy paths,
  unknown user 404, would-go-negative 400, zero delta 400.
* Auth contract: every v33 endpoint returns 401 unauthenticated.

`tests/conftest.py` updated to reset `dm_store` + `elins_project`
between tests.

`tests/test_v28_endpoints.py` health-version assertion bumped to
`2.9`.

Run: `python -m pytest tests/ -q` — **206 passed**.

---

## 7. Files touched

**New**
* `ELINS/__init__.py`
* `ELINS/standard_elins.py`
* `ELINS/elins_project.py`
* `comment_generator.py`
* `dm_store.py`
* `tests/test_v33_founder_console.py`
* `web/src/components/founder/FounderDashboard.tsx`
* `web/src/components/founder/CohortList.tsx`
* `web/src/components/founder/MemberDetailPanel.tsx`
* `web/src/components/founder/ManualActivateButton.tsx`
* `web/src/components/founder/DMNotesPanel.tsx`
* `web/src/components/founder/ELINSInspector.tsx`
* `web/src/components/founder/CommentGeneratorPanel.tsx`
* `web/src/routes/Founder.tsx`
* `phone/app/founder.tsx`
* `phone/app/member_detail.tsx`
* `phone/app/elins_inspector.tsx`
* `phone/app/dm_notes.tsx`
* `phone/app/comment_generator.tsx`
* `V33_READINESS.md` (this file)

**Modified**
* `app.py` — v33 imports; 11 new endpoints; `/me` capabilities + What's
  New entry; root catalog; version bumped to 2.9.
* `tests/conftest.py` — reset hooks for `dm_store` + `elins_project`.
* `tests/test_v28_endpoints.py` — version assertion bump.
* `web/src/lib/api.ts` — v33 types (`V33ELINSObject`,
  `V33SELINSResult`, `V33CommentResult`, `V33DM`, `V33DMNote`) +
  helpers (elinsPreview/Global/QC, cmtGenerate, founderDM*,
  founderMembership*).
* `web/src/App.tsx` — `/founder` route under RequireAuth.
* `phone/lib/api.ts` — same v33 types + helpers as web.
* `phone/app/settings.tsx` — `FounderBadge` inline in Account card.
* `BUILD_VERSION` — bumped to `20260506500000`.

`tsc --noEmit` (web + phone) — clean (only the pre-existing
`ingest.tsx` ProviderId error remains, unrelated to v33).

---

## 8. Rollback path

v33 is purely additive. To revert:
1. Surfaces collapse cleanly: `/founder` and `/cmt/generate` stop
   returning data; existing `/elins/g/run` (v28) is unchanged.
2. `dm_store` and `elins_project` collections are independent — wiping
   them affects nothing else.
3. `/me.capabilities` is consumed only by the v33 UI; older clients
   ignore unknown keys.

No persisted state from earlier versions was migrated.

---

## 9. Known gaps / next-pass candidates

* **DM thread storage** — `add_dm_note` persists notes, but there's no
  `list_notes_for_dm` endpoint that returns them without appending. The
  current web/phone UIs call `add_dm_note` with the new body and use
  the returned list; reads-only of an existing DM's notes need an
  endpoint in v34.
* **ELINS pipeline + Dewey integration** — the new canonical pipeline
  is text-only / lexical; integrating it with the existing
  embedding-driven `/elins/g/run` (so the same pipeline produces both
  primitive metadata and Dewey neighborhood matches) is v34 work.
* **Member search** — `MemberDetailPanel` currently requires the exact
  username. A real search (prefix / cohort filter) needs a
  `/founder/users/search` endpoint and a per-cohort index.
* **Stripe integration testing** — v31's manual-confirm path is still
  untested in stripe mode; v33 doesn't change that.
* **Comment generator templates** — the four-segment templates are
  hand-tuned and bounded; a future pass may want these editable from
  the founder console (without redeploying) and cohort-versioned.
* **#cmt rate limit** — currently piggybacks on the per-user 60/min
  default. Public-facing comment generation (via /c/run when public
  surfaces consume it) would need a stricter cap.
