# Founding Members — System Definition + Operator Workflow

The contract for what a "Founding Member" is inside ClarityOS, how
they get there today (manual operator workflow), and the automation
path waiting to be wired up.

Scope: this doc is a **specification**, not a runbook for code
changes. There is no Pocket code change, no Engine code change, no
new endpoint, no new branch required to satisfy this card. The
purpose is alignment — so the people writing the next backend
patch, the next Pocket UI, and the next Stripe automation are all
building against the same conceptual model.

## State definition

A Founding Member has **three attributes**.

### 1. Identity

A Stripe customer who completed a successful Founding Member
checkout against the canonical Payment Link:

```
https://buy.stripe.com/fZu9ATclDb3re3cgFB0VO00
```

Wired into the Pocket landing page CTA as of commit `7f36d59`
(branch `feature/v0.3.8-pocket-stripe-cta`, live in
revision `clarityos-pocket-v0-3-00008-znx`).

### 2. Entitlement

Once recognised as a Founding Member, the account gains access to:

- Pocket SPA (`pocket.clarityos.dev` once mapped, run.app today)
- Cockpit web v0.2 (`cockpit.pro-mediations.com`)
- Engine endpoints currently behind cohort-gated paths
- Early operator tools (founder console, founder/* routes)
- The PHONE surface when it ships (Expo native app under `phone/`)

### 3. Recognition

A Founding Member is marked in the system with a stable schema:

```yaml
role:                "founding_member"
tier:                "founding"
joined_at:           <unix epoch seconds — set on first successful checkout>
stripe_customer_id:  <cus_...>
stripe_session_id:   <cs_...>
```

This is the minimal record. Anything else (e.g. display name, intro
notes, operator-granted privileges) is operator-side metadata.

## Onboarding workflow — manual today

Until automation is wired, every Founding Member is onboarded by
the operator in the Stripe Dashboard:

1. Stripe sends a `checkout.session.completed` event for the
   Founding Member checkout. (The Engine's
   `app.py:1197 /billing/webhook` already handles this event — see
   "Future automation" below — but no Founding-Member-specific
   logic exists yet.)

2. **Operator** opens **Stripe → Customers** and finds the new
   customer.

3. Add Stripe customer metadata (these are arbitrary key/value
   pairs that survive forever and can be read by webhooks):

   ```
   clarityos_role:       founding_member
   clarityos_tier:       founding
   clarityos_joined_at:  <unix epoch seconds>
   ```

4. Add a Customer Note:

   ```
   Founding Member — onboarded manually (v0.3.x)
   ```

5. Add the operator ledger entry (see below).

That's it. The customer is now a Founding Member as far as humans
are concerned. The system catches up when the recognition rule
(below) is wired.

## Engine recognition rule — to be implemented

**Not yet code.** This is the rule the Engine SHOULD apply once
Founding Member recognition is wired:

```
When the Engine handles a request from a user with
  stripe_customer_id = X

AND Stripe metadata for that customer says
  clarityos_role = "founding_member"

THEN the Engine treats the user as
  role         = "founding_member"
  tier         = "founding"
  permissions  = ["pocket", "web", "engine"]
```

Implementation hooks already present in `app.py`:

- `users_store.set_billing_state(...)` is called from
  `_handle_subscription_event` (`app.py:1347`) on every Stripe
  subscription lifecycle event. A future patch would add a
  `role` / `tier` field that gets set there too.
- `/me` (`app.py:1489`) already returns `cohort`, `tier`, and a
  `features` map — those are the fields Pocket reads. The new
  `role` could ride in the same response.

## Pocket recognition rule — to be implemented

**Not yet code.** When `/me` returns `role: "founding_member"`,
Pocket SHOULD:

- Render a Founding Member badge on `/me` and (optionally) `/landing`
- Skip any paywall surfaces (none exist yet)
- Unlock the full surface (no gated routes today)

Pocket's existing `MeResponse` type in `pocket/src/api/client.ts`
already includes `tier` and `cohort`. Adding `role` is a one-line
type extension. The UI changes belong in their own card.

## Operator ledger

Authoritative early-cohort ledger lives at... wherever the operator
chooses (a Notion page, a private google doc, a markdown file in
this repo). One row per founding member. Suggested shape:

```
Founding Members (v0.3.x)
-------------------------
1. <name>  —  <stripe_customer_id>  —  joined <UTC timestamp>
2. <name>  —  <stripe_customer_id>  —  joined <UTC timestamp>
...
```

This is the source of truth until the automation in "Future
automation" replaces it.

If you want the ledger committed to the repo (operator-only, never
read by code), the convention would be `pocket/docs/ledger.md`
with `pocket/docs/ledger.md` added to `.gitignore` so the file is
local-only — OR committed if the cohort is public. Operator's
choice.

## Lifecycle — the contract

A Founding Member, once on the books, **never loses access**:

| Event | Outcome |
|---|---|
| Subscription renews | Stays Founding Member |
| Subscription fails | Stays Founding Member; recovery is a separate operator conversation, not an automatic downgrade |
| Customer requests cancellation | Stays Founding Member as a courtesy; manual exit only |
| Tier upgrade (founding → annual / monthly) | Founding designation persists; tier field reflects current paid level |
| Operator grants extra privileges | Adds to the role; does not remove "founding_member" |

Translation: `founding_member` is a permanent designation. `tier`
is the variable. Implementation should treat the two as orthogonal.

## Future automation — the boundary

What automation will eventually do (each line is a candidate card):

| Step | Card # |
|---|---|
| Stripe webhook → Engine reads `clarityos_role` metadata from the customer object | TBD (extends `app.py:_handle_subscription_event`) |
| Engine writes `role` + `tier` + `joined_at` to the user record | TBD (extends `users_store.set_billing_state`) |
| Engine returns `role` on `/me` | TBD (extends `MeResponse`) |
| Pocket reads `role` and renders Founding Member badge / unlocks surface | TBD (extends `pocket/src/routes/me.tsx` + `pocket/src/api/client.ts`) |
| Pocket cocktail surface (PHONE / desktop) inherits same `role`-based unlock | TBD (future surface card) |

None of these are in scope today. Card 13 (this doc) is purely
definitional so the eventual automation work has a clear contract
to build against.

## Where this connects to prior cards

| Prior card | What it landed | How it relates |
|---|---|---|
| Card 12 / 12A | Canonical Stripe Payment Link wired into Pocket landing page (commit `7f36d59`) | The CTA users click to **become** a Founding Member |
| Card 10 | Backend CORS allows Pocket origin (rev `00041-9gz`) | The fetch path Pocket uses to call `/me` so the Founding Member badge can render (once the field is added) |
| Card 11 (pending) | Custom domain mapping `pocket.clarityos.dev` | The clean URL Founding Members will visit |
| Card 13 (this) | The conceptual model the above three lead toward | — |

## Success criteria (per Card 13)

- ✅ Clear definition of what a Founding Member is
- ✅ Manual onboarding workflow executable today
- ✅ Stripe metadata schema defined (`clarityos_role`, `clarityos_tier`, `clarityos_joined_at`)
- ✅ Engine recognition rule defined (not yet code)
- ✅ Pocket recognition rule defined (not yet code)
- ✅ Operator ledger format defined
- ✅ No deploys required
- ✅ No regressions possible

This doc lives at `pocket/docs/FOUNDING_MEMBERS.md` and is committed
to the repo so future automation cards (Card 14 and beyond) can
reference it directly instead of re-establishing the same contract
in commit messages or chat transcripts.
