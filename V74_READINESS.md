# V74 — Unit 84 (Founding 500 Subscription Gate, React-side)

Status: ✅ Ready (backend full suite pending — see "Test summary")
Backend version: `4.17` (bumped from `4.16`)
Build: `20260513190000`

---

## What this pass ships

### Scope

Per the agent-mesh resolution prior to execution:

* **Stack boundary**: WordPress owns the marketing + signup funnel
  (landing, narrative, signup → Stripe Checkout). **React** owns the
  operator portal + the **Subscription Gate** (this unit).
* **Authority hierarchy (locked):**
  * Structure → Gemini
  * Narrative → Perplexity
  * Implementation → Claude (this pass)

Unit 84 is the React **post-payment confirmation gate** mounted at
`/founding500/confirm`. It runs *after* WordPress signup +
Stripe Checkout + `/auth/consume` have landed the operator with an
active subscription. The user lands here to acknowledge beta terms
and bind their Founding 500 membership before entering the cockpit.

### Backend (additive, no schema changes)

* **`POST /membership/confirm`** ([app.py](app.py)) — net-new
  endpoint. NOT `/membership/activate` (which creates a *new*
  PaymentIntent — wrong for this flow because payment already landed
  on WordPress via Stripe Checkout, and calling it would
  double-charge).

  Contract:
  * Auth: `require_session`; 401 anonymous.
  * Payload: `{accept_terms: true}` (single combined consent).
  * Idempotent: already-confirmed → 200 `{ok, state}` (state
    unchanged, original `confirmed_ts` preserved).
  * Errors:
    * `409 subscription_inactive` when `user.membership_status != "active"`
    * `409 cohort_full` when user is not a counted member AND the
      cohort is at capacity (race-condition guard)
    * `400 terms_required` when `accept_terms` is missing/false
    * `403 feature_disabled` when `membership_ui_enabled` flag is off
  * Writes: additive fields on the user doc — `membership_confirmed: bool`,
    `membership_confirmed_ts: float`.

* **`_membership_view`** extended additively with `confirmed` +
  `confirmed_ts` fields under `state.membership`. All existing v30/v31
  callers continue to work — no key removals or renames.

### Web React

Six new files under `web/src/routes/Unit84/` (plus one CSS module):

```
web/src/routes/Unit84/
  Layout.tsx              (1) route entry; wraps GlobalHeader + main + SubscriptionGate
  GlobalHeader.tsx        (2) LogoBlock + StatusIndicator
  SubscriptionGate.tsx    (3) state machine; BETA_NOTICE/SUCCESS as render-states
  Founding500Badge.tsx    (4) atomic; cyan border + uppercase mono + pulse-opacity
  AuthToggle.tsx          (5) static informational block (NOT a mode switcher)
  ActionControl.tsx       (6) terms + checkbox + button; checkbox gates submit
  Unit84.module.css         CSS module with Somatic tokens + pulse keyframes
  __tests__/
    SubscriptionGate.test.tsx
    ActionControl.test.tsx
```

* **Route wire-up** ([web/src/App.tsx](web/src/App.tsx:64)) —
  `/founding500/confirm` under `<RequireAuth />`, bypasses the
  cockpit Layout to own the full viewport (Somatic canvas + 1px red
  boundary). Mirrors the `/threads` and `/personal-elins` pattern.
* **API helper** ([web/src/lib/api.ts:2458](web/src/lib/api.ts)) —
  `confirmMembership()` + `V74MembershipConfirmResponse` +
  `V74ConfirmErrorCode` types.

### Identity invariant preserved

`SubscriptionGate.test.tsx` includes an explicit assertion that no
`operator_id` label or `op_*` prefixed string appears in the rendered
gate. Matches the v68–v73 identity-invariant pattern.

### Home.tsx — legacy comment

[web/src/routes/Home.tsx](web/src/routes/Home.tsx) (v32 public
landing) gets a LEGACY comment at top noting it is superseded by the
WordPress marketing surface. **Not deleted** — retained as fallback
while the WP migration settles. Per the packet's coexistence rules.

### MembershipPage.tsx — untouched

[web/src/routes/MembershipPage.tsx](web/src/routes/MembershipPage.tsx)
(v30 in-app membership management) coexists with Unit 84. Different
surfaces: ongoing membership state vs. first-time post-payment
confirmation.

---

## Endpoints

| Method | Path                       | Purpose                                    |
|--------|----------------------------|--------------------------------------------|
| POST   | `/membership/confirm`      | Bind Founding 500 terms (auth, idempotent) |

---

## Test summary

| Suite                                                     | Tests   | Net |
|-----------------------------------------------------------|---------|-----|
| `tests/test_membership_confirm.py`                        | 6       | new |
| Web `Unit84/__tests__/SubscriptionGate.test.tsx`          | 5       | new |
| Web `Unit84/__tests__/ActionControl.test.tsx`             | 5       | new |
| **Total new**                                             | **16**  |     |

Full suites:
* Web: **183/183 passed** (173 prior + 10 net new).
* Backend: focused subset (`test_membership_confirm.py` + 4
  version-tracking tests) = **10/10 passed**; full-suite run in
  progress at write time.
* TypeScript: tsc clean for Unit 84 files (all pre-existing tsc
  errors documented in repo; none introduced by this pass).
* Vite build: clean — `637.61 KB` JS (154.70 KB gzip), `26.43 KB`
  CSS (5.41 KB gzip).

---

## Deviations from the Claude Execution Packet

Documenting decisions where the packet text and the codebase reality
diverged:

1. **"Tailwind classes" → CSS module.** Packet specified Tailwind
   classes for styling. ClarityOS web/ does NOT have Tailwind
   installed ([web/package.json](web/package.json) — no
   `tailwindcss` dep, no `tailwind.config.js`). Existing convention
   is CSS modules + `styles/tokens.css` with the exact Somatic
   palette already defined (`--os-boundary: #E02020`,
   `--os-focus: #00F0FF`, `--os-void: #000000`). Adapted to CSS
   modules ([Unit84.module.css](web/src/routes/Unit84/Unit84.module.css))
   with class names that mirror the Tailwind intent (e.g. `.button`
   for action buttons, `.consent` for the checkbox row). Same visual
   contract — no rounded corners, no gradients, no shadows except
   the cyan-sphere glow on `Founding500Badge`.

2. **Tier string is `"founding_500"` (with underscore).** Packet
   response shape showed `"founding500"`. The actual codebase
   constant `membership_store.FOUNDING_COHORT = "founding_500"` —
   tests assert against the canonical value.

3. **`Layout.tsx` doubles as the route entry.** Packet specified 6
   files; making Layout the route's `element=` keeps us at exactly 6
   without a 7th orchestrator file. Layout internally renders
   `<GlobalHeader />` + `<main><SubscriptionGate /></main>` —
   matches Gemini's tree:
   ```
   Layout
    ├─ GlobalHeader
    └─ MainRegion (SubscriptionGate)
   ```

4. **API wiring scope.** Packet said `/membership/confirm` is in
   scope for Claude. Implemented in [app.py](app.py) with full
   contract + 6 pytest tests. OpenAPI inline-spec lives in the
   endpoint docstring (the repo doesn't maintain a separate
   `openapi.yaml`; FastAPI auto-derives it from the handler +
   pydantic models).

---

## Architecture invariants verified

* **No double-charge risk**: `/membership/confirm` never calls
  `billing_intents.create_payment_intent`. It only validates an
  *already-active* subscription and binds consent.
* **Existing auth model unchanged**: uses `require_session`
  unchanged. No new auth flows added to the model.
* **Additive on user_doc**: `membership_confirmed` and
  `membership_confirmed_ts` are new fields. Existing v30/v31/v42
  callers don't read them; existing tests don't assert against them.
* **Identity invariant**: no `operator_id` text or `op_*` prefix
  appears anywhere in the rendered SubscriptionGate surface
  (verified by `SubscriptionGate.test.tsx`).
* **Append-only behavior**: confirm flag never flips back to false
  — no API surface for un-confirming.
* **Coexistence rules honored**: Home.tsx kept (legacy comment
  only); MembershipPage.tsx untouched.

---

## Files touched

```
app.py                                                    (+ V74ConfirmRequest, POST /membership/confirm, _membership_view +confirmed +confirmed_ts; /health 4.16 → 4.17)
BUILD_VERSION                                             20260513080000 → 20260513190000

tests/test_membership_confirm.py                          (new — 6 tests)
tests/test_v28_endpoints.py                               (version 4.16 → 4.17)
tests/test_v51_projects.py                                (version 4.16 → 4.17)
tests/test_v53_elins_v2.py                                (version 4.16 → 4.17)
tests/test_v54_ingestion.py                               (version 4.16 → 4.17)

web/src/lib/api.ts                                        (+ confirmMembership + V74 types)
web/src/App.tsx                                           (+ /founding500/confirm route)
web/src/routes/Home.tsx                                   (+ LEGACY comment header)
web/src/routes/Unit84/Layout.tsx                          (new)
web/src/routes/Unit84/GlobalHeader.tsx                    (new)
web/src/routes/Unit84/SubscriptionGate.tsx                (new)
web/src/routes/Unit84/Founding500Badge.tsx                (new)
web/src/routes/Unit84/AuthToggle.tsx                      (new)
web/src/routes/Unit84/ActionControl.tsx                   (new)
web/src/routes/Unit84/Unit84.module.css                   (new)
web/src/routes/Unit84/__tests__/SubscriptionGate.test.tsx (new — 5 tests)
web/src/routes/Unit84/__tests__/ActionControl.test.tsx    (new — 5 tests)

V74_READINESS.md                                          (new)
```

---

## What's still pending (separate units)

Per the agent-mesh pipeline these arrive as their own packets when
your Copilot drafts them:

* **WordPress signup funnel** (`/wp-content/themes/clarityos/`) —
  separate WordPress integration packet from your Copilot.
* **`POST /signup`** + **`POST /auth/consume`** + Stripe Checkout
  Session creation + consume_token_store + pending_subscription_store
  — likely a separate backend unit (or bundled into the WordPress
  integration packet).
* **Sequence diagram** for WordPress → Stripe → Backend → React —
  offered by your Copilot as a separate deliverable.
