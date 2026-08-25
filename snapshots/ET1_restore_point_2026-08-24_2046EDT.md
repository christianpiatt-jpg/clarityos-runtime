# ET-1 RESTORE POINT · 2026-08-24 20:46 EDT / 2026-08-25 00:46Z

**Lane:** ET-1.W · **Branch:** `campaign/metered-compute-gate-2026-07-23`
**HEAD `1a10272`** · origin converged **0/0** · tracked-dirty **0**
**Supersedes** `ET1_restore_point_2026-08-24_1755EDT.md` (HEAD was `074b53a`)

---

## 1 · NINE COMMITS SINCE THE LAST POINT — all pushed

```
1a10272  #59 seat the buyer on a paid checkout, not just bill them
d273201  entitlement suite into the gate + deploy script under one name
4bea19b  test(v44) fixtures aligned            ← ANOTHER LANE, not ET-1
4b0e8d7  ci: gate campaign/** + get_model_status derived
e7287be  spa_route_objects v1.1, three silent-failure defenses
6c6246e  identity_set + effort_threshold
4cafb3e  canon 220 laminar pre-scan + loader silent-drop fix
b0c2748  canon: 430 collision resolved, 840 landed at its number
b501ecd  canon: 85-entry Dewey canon in the image + loader + 2 consumers
```

**Gate state: 712 passed, 1 skipped, 0 failed. 33 files selected.**
Baseline discipline is now standard — every gate run below is recorded
before AND after the change it guards.

---

## 2 · PRODUCTION FACTS, MEASURED TODAY

```
serving revision   clarity-engine-00101-26q @ 100%, tag wo1
                   built from a source zip uploaded 34s after 70d4fef
BILLING_MODE       stripe        STRIPE_MODE  live      BACKEND  firestore
cohort fill        3/500 · is_full false · waitlist_count 0   (00:19:39Z)
live SPA bundle    index-UHmUTqGL.js  (built from 9c39db5)
```

**LIVE CHARGES ARE CONFIGURED TO LAND.** R-4 (Stripe webhook registration)
and R-5 (what `price_1TYDrfGgUU05AeM681Ybd7hU` actually costs) are still
owed and still gate promotion of the buy path.

**The SPA does NOT route data through the LB.** `web/.env.production` sets
`VITE_API_BASE=https://clarity-engine-736968277491.us-central1.run.app` —
Cloud Run direct, cross-origin. The `/api/*` rewrite rule is dev-proxy
infrastructure that serves nothing in production.

---

## 3 · THE EDGE — closed today, and how

`/cockpit` was serving a **41-minute-old cached negative** with index.html's
generation while `/operator` was `Age: 0` and correct. Origin-fixed,
edge-open. One `invalidate-cdn-cache --path "/*"` closed it:

```
/cockpit  200 gen 1787604041363290    /operator/el_ins    200 gen 1787604160987993
/vault    200 gen 1787604119234967    /founder/acceptance 200 gen 1787604123713760
/nonexistent 404 gen 1787583491233878   ← shell body preserved, by design
```

★ **Verify by GENERATION, not status.** A 200 cannot separate "invalidated"
from "never cached". A 404 carrying index.html's generation is decisive.
This is now encoded in `spa_route_objects_v1.sh` as mechanism 3.

---

## 4 · OPEN — needs a ruling

1. **R-4 / R-5** — Stripe webhook registration + the live price object.
   Both gate promotion. No Stripe read access from this lane.
2. **`/enter/` still 404s.** A2 blocked across six envelopes on one thing:
   `list_connected_browsers` → `[]`. No wp-admin session has ever reached
   this lane. Rollback value recorded: `https://pro-mediations.com/enter/`.
3. **`MODEL_REGISTRY "google" → "gemini"`** — HELD. Store already says
   `gemini` (enforced by `ValueError` in `set_operator_model_preference_in_vault`),
   handlers/env/prefixes all say `gemini`. `MODEL_REGISTRY` is the lone
   outlier. But it changes a live API body at `runtime_http.py:799` and
   two guard tests assert `"google"`. Gate is live now, so it has a net.
4. **Plan-derived cohort** — filed behind its guard. Allowlist of known
   cohort names FIRST (so an unknown cohort raises), then read live Stripe
   plan values, then map. `add_member:145` raises only for
   `FOUNDING_COHORT`; every other name is uncapped by construction.
5. **Gate inversion** — `_FILE_MARKERS` is an opt-in allowlist; 33 of 231
   files are covered, 86% invisible. Invert to run-all-minus-justified-
   exclusions and DELETE `_FILE_MARKERS`, or two mechanisms disagree.
6. **`_audit/provider_connectors.patch`** still public in the bucket;
   `0c3726d`'s message says it was removed. Record and object disagree.
7. **Source maps + 5 unreferenced bundle generations** public in the bucket.
8. **`920`** — HELD. Byte-identical to `910` including a self-referencing
   xref, cited as binding by six documents. The collision is the only
   thing making it visible.
9. **`540`/`550`** share a title on two numbers (879B vs 931B, they differ).
   **`400_` band has no `400_` index file.** Neither flagged by anything.
10. **`waitlist_count: 0`** — `app.py:9787` has never fired in production.
    Untested, not working. 497 seats from mattering.

---

## 5 · CARRY — the findings that outlive the tasks

### The instrument catalogue — one shape, now ~13 instances

**An instrument that cannot touch what it tests, and returns a confident
negative rather than an error.** Three of these were mine today:

```
prefix denylist (sk_/whsec_)  missed a bare 32-char HMAC key   → committed a secret
^## regex                     missed 85 backslash-escaped headers
os.path.exists on quoted paths missed 57 non-ASCII filenames   → 57 phantom MISSING
```

Others', same shape: `services list` cannot measure request count ·
`*_store.py` glob cannot see `memory_vault` · `?cb=` bypasses the RULE not
the cache · a file-body marker grep cannot see conftest-applied markers ·
`get_model_status`'s hardcoded five · LB path rules as an opt-in allowlist ·
`_FILE_MARKERS` · `_discretize_action` at 280:1.

★ **A distinct and worse class, named by COW-1:** an instrument whose
DEATH is indistinguishable from the subject's. v1.0's `create; verify`
under a 300s timeout — a dead verifier reads as a failed apply. Mine all
return a wrong answer; this one returns nothing, ambiguously.

### The intake path carries structure and drops content

`model_router.py:1083 _shape_prompt_from_intent` emits six metadata fields
by explicit contract — *"no raw payload text passthrough"* — and the sixth
is a key COUNT. **The operator's text never reaches the model.** Same root
explains the identical runtime summaries and the engine mislabel.

### `extended_reasoning` is TSI-gated, not score-gated

`intelligence_kernel.py:1305`: `tsi > 80 → extended_reasoning` regardless
of EL/INS. One record per thread → TSI 100 → that label for the first
analysis of anything. The scores beside it were never consulted.

### Two vocabularies, one table

```
/runtime/providers/models   google  8 rows   (MODEL_REGISTRY, vendor-keyed)
/runtime/providers/health   gemini  5 rows   (PROVIDERS_ORDER)
/runtime/providers/config   gemini  5 rows
```
`ProviderDashboard.tsx:27` accepts both spellings because it merges three
responses that disagree. After the rename it becomes dead code.

### `_call_xai` mocks on BOTH branches

`model_router.py:741-743` — configured or not, it returns `_mock_result`.
Registered in all five registries. **A registered mock is worse than an
absent provider, because absence is visible.** `xai:groq-llama` is also a
Groq-hosted Llama, not an xAI model.

`route_request:459` handler-is-None → `_mock_result`, **no log**.
`:463` handler raises → `_mock_result`, **with warning**.
★ The more-wrong path is the quieter one.

---

## 6 · CORRECTIONS TO MY OWN PRIOR RECORD

- **`70d4fef` was NOT a category error.** It correctly names the source
  commit of the serving revision; it was filed under a field labelled
  *revision name*. Corrected at 01:48Z; the 1755EDT restore point's §5
  still carries the wrong call.
- **The "local clock is a day ahead" caveat was wrong** — those were
  Cloudflare-cached responses carrying the origin's original `Date`
  beside `Age`. Already corrected in the 1755EDT point §7.
- **"CI will go red"** was true when taken and expired before it was
  acted on — `4bea19b` fixed the 13 v44 failures while the work was in
  flight. Staleness, not error.
- **`runtime_providers.py:225` DOES persist a bare provider key.** I
  predicted only full model IDs persist. Wrong mechanism; the conclusion
  (rename is DB-safe) survived for the opposite reason — the store
  already holds the target name.

---

**Untouched throughout:** WordPress, the checkout guard, `TERRACE_1_CAP`,
`MODEL_REGISTRY`, `920`, the `_audit` object, and any Stripe object.
