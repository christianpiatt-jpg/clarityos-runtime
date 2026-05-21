# ClarityOS v32 — Public Website + Waitlist Pipeline Readiness Report

**Build:** `20260506400000`
**Backend version:** `2.8`
**Status:** Ready — public landing page + waitlist pipeline + founder console wired end-to-end.

This pass turns the existing `Home.tsx` (an authenticated operator
shortcut grid) into a real public landing page with the marketing
copy + waitlist signup, ships the public + founder API surface for the
waitlist, and integrates cohort fill into both the public CTA and the
authenticated activation flow.

All **152 tests pass** under in-memory backends + mock billing
(30 new v32 tests).

---

## 1. Public website (static front door)

### `web/src/routes/Home.tsx` (rewritten)
The home route is now the public landing page. Composed sections:

1. **Hero** — "ClarityOS — A cognitive operating system. Clarity about
   the forces shaping outcomes — not summaries, not advice. Local-first.
   Trust-centered. Yours."
2. **Founding Cohort** — bullet list of:
   - 500-member cap (live fill from `/public/cohort_status`)
   - $50/month locked for life until cancelled
   - Full price $150/month after the cohort
   - Direct founder access
   - Participation in testing and evolution
3. **Core capabilities** — Identity wrapper · Trust-centered clarity
   partner (Emotional Physics + Langbridg) · Local vault · #c cloud
   engine (metadata-only) · #G personal ELINS · Macro-ELINS (3×/week).
4. **Timeline** — Founding Cohort opens May 15; waitlist active.
5. **Trust & privacy** — Local-first; no content stored in cloud
   (metadata only); auditable via the cockpit envelope viewer.
6. **Call-to-action** — `<WaitlistForm />` flips its label between
   "Join the Founding Cohort" and "Join the Waitlist" based on
   `is_full`.

If the visitor is already authenticated (session token present), an
"Operator shortcuts" row appears at the bottom with quick links into
`/cockpit`, `/membership`, `/elins`, `/operator`.

### `web/src/components/public/WaitlistForm.tsx` (new)
Inline form: email (required) + name (optional) + "How did you hear
about this?" (select: website / linkedin / facebook / manual) +
"Anything else?" (optional 1000-char textarea, sent as `note`).

POSTs to `/waitlist/join`. On success replaces itself with a
confirmation card; **no account is created and no login is required**.
Adapts the success copy when the cohort is full.

Uses existing CSS variables (`--os-surface`, `--os-border`,
`--os-text-secondary`) so it inherits the design system.

### Design constraints respected
* Minimal, no animation (only the natural progressive disclosure
  collapse on `<details>` rows in the founder panel).
* Mobile-first: `maxWidth: 760` on the page; flex/grid containers wrap
  on narrow screens; `inputMode="email"` and `autoComplete="email"`
  for the waitlist form.
* High contrast: relies on the existing CSS-variable tokens.

---

## 2. Waitlist data model — `waitlist_store.py` (new)

Schema:
```python
{
  "id":           "wl_<token>",
  "email":        str,                 # normalized to lowercase
  "name":         str | None,
  "source":       "website|linkedin|facebook|manual",
  "created_ts":   float,
  "updated_ts":   float | None,
  "status":       "waiting|contacted|converted|dropped",
  "note":         str | None,           # ≤ 1000 chars
  "user_id":      str | None,           # required when status="converted"
  "contacted_ts": float | None,
  "converted_ts": float | None,
}
```

Public API:
```python
add_waitlist_entry(email, name=None, source=None, ts=None, note=None) -> dict
list_waitlist(*, status=None, limit=500) -> list[dict]
get_waitlist_entry(record_id) -> dict | None
find_by_email(email) -> dict | None
update_status(record_id, *, status, note=None, user_id=None) -> dict | None
mark_contacted(record_id, *, note=None) -> dict | None
mark_converted(record_id, user_id, *, note=None) -> dict | None
mark_dropped(record_id, *, note=None) -> dict | None
count_waitlist(*, status=None) -> int
normalize_email(email) -> str   # used by both store and route
```

Validation invariants pinned by tests:
* Emails are lowercased + trimmed; rejected if format invalid or > 320 chars (RFC 5321 max).
* Source must be in `VALID_SOURCES`; defaults to `"website"`.
* Note is trimmed and capped at `MAX_NOTE_LEN = 1000` chars.
* Name is trimmed and capped at `MAX_NAME_LEN = 200` chars.
* `update_status(..., status="converted", ...)` **requires** a non-empty
  `user_id`. The store enforces this so callers can't silently drop the
  link to the user record.
* `add_waitlist_entry` is **idempotent on email** for non-dropped
  records: same email → same record id. Re-signing up after a `dropped`
  status creates a fresh row.

Backends: in-memory + Firestore (collection: `waitlist`).

---

## 3. Endpoints

| Endpoint | Auth | Validation | Rate limit | Logs |
|---|---|---|---|---|
| `POST /waitlist/join` | public | email format, name/source/note normalized | 10 / 600s **per IP** (X-Forwarded-For first hop) | `waitlist_join` / `waitlist_join_rate_limited` |
| `GET  /public/cohort_status` | public | – | – | – |
| `GET  /founder/waitlist` | founder (`_require_founder`) | optional `status` filter ∈ VALID_STATUSES; `limit` 1–2000 | per-user | `founder_waitlist_list` |
| `POST /founder/waitlist/update` | founder | `id` non-empty; `status` ∈ VALID_STATUSES; `user_id` required when `status="converted"` | per-user | `founder_waitlist_update` |

The IP-based rate limit reuses `v29_hardening.check_rate_limit` with a
keyspace-prefixed key (`f"ip:{ip}"`) so the per-user buckets aren't
confused with per-IP buckets. Capacity is intentionally low (10/10min)
because the legitimate use case is one or two submissions per visitor.

`/founder/waitlist` returns a `counts` block alongside the entries:
```json
{
  "ok": true,
  "entries": [...],
  "counts": {"waiting": N, "contacted": N, "converted": N, "dropped": N, "total": N}
}
```

---

## 4. Public website → waitlist pipeline

`<WaitlistForm />` → `POST /waitlist/join` → `waitlist_store.add_waitlist_entry`.

Pipeline confirmed by `test_waitlist_join_*`:
* `test_waitlist_join_does_not_require_auth` — happy path with no session header.
* `test_waitlist_join_idempotent` — duplicate email returns the same id.
* `test_waitlist_join_lowercases_email` — case-insensitive matching.
* `test_waitlist_join_rejects_bad_email` — 400 with `error: "bad_email"`.
* `test_waitlist_join_rate_limit` — 11th call from the same IP returns 429.

---

## 5. Founder view (internal)

### `web/src/routes/FounderWaitlist.tsx` (new)
Mounted at `/founder/waitlist` (auth-required client-side; the API
server-side enforces founder-cohort gating). Stub of the larger Founder
Console — composes a single `<WaitlistPanel />` so future passes can
add panels around it.

### `web/src/components/founder/WaitlistPanel.tsx` (new)
* Lists entries (most recent first) from `GET /founder/waitlist`.
* Filter by status (All / Waiting / Contacted / Converted / Dropped) —
  shows live counts inline.
* Search across email / name / note (client-side; the list is bounded
  at 500 entries).
* Click a row → inline editor for status, note, and user_id (only
  required when converting).
* Surfaces all timestamps (created / updated / contacted / converted)
  for audit.
* Refresh button + error banner for failed loads.

Endpoints used: `/founder/waitlist`, `/founder/waitlist/update`.

---

## 6. Cohort cap integration

The public landing page calls `GET /public/cohort_status` on mount and:
* Hero subline switches between "N of 500 Founding seats remaining"
  and "Founding 500 cohort is currently full. Waitlist is open."
* CTA button switches between "Join the Founding Cohort" and
  "Join the Waitlist".
* WaitlistForm success copy adapts to the cohort state.

Server-side, `/membership/activate` already short-circuits to the
in-cohort waitlist when the cap is reached. v32 attaches a friendly
`message` field to that response so the UI has copy to render:

> "The Founding 500 cohort is full. You're on the waitlist; we'll
> reach out when a spot opens."

Existing active members are unaffected — the activation guard checks
`is_cohort_full() and not user_doc.get("membership_cancelled_ts")`,
and idempotent re-activate (already-active path) returns the
membership without touching the cohort.

Test: `test_activate_when_cohort_full_returns_friendly_message`.

---

## 7. Tests — `tests/test_v32_waitlist.py` (new)

30 tests, all green. Coverage:

* `waitlist_store` unit tests:
  * `normalize_email` happy + invalid + too-long.
  * `add_waitlist_entry` happy + idempotent + post-dropped recreation.
  * Status transitions (`waiting → contacted → converted`).
  * Converted requires `user_id`.
  * `list_waitlist` newest-first + status filter.
  * `count_waitlist` total + by status.
  * Invalid source rejected.

* `/waitlist/join` endpoint:
  * Happy path (200 + record id).
  * No auth required.
  * Bad email → 400 (`bad_email`).
  * Idempotent on duplicate email.
  * IP rate limit triggers 429 on 11th request.
  * Email is lowercased on storage.

* `/public/cohort_status`:
  * Public, no auth.
  * Reflects cap-full when `is_cohort_full()` returns true.

* `/founder/waitlist` + `/founder/waitlist/update`:
  * Non-founder → 403 on both list + update.
  * List returns entries + counts.
  * Status filter (`?status=contacted`).
  * Bad status filter → 400.
  * Status transition with note.
  * Converted without user_id → 400 (`user_id_required`).
  * Converted with user_id → 200.
  * Unknown id → 404.

* Cohort-full integration:
  * Activate when cohort is full returns `waitlisted: true` with
    a `message`.
  * Public form still works when cohort is full.

`tests/conftest.py` updated to reset `waitlist_store._MEMORY` between
tests.

`tests/test_v28_endpoints.py` updated: health version assertion bumped
from `2.7` to `2.8`.

Run: `python -m pytest tests/ -q` — **152 passed**.

---

## 8. Files touched

**New**
* `waitlist_store.py`
* `tests/test_v32_waitlist.py`
* `web/src/components/public/WaitlistForm.tsx`
* `web/src/components/founder/WaitlistPanel.tsx`
* `web/src/routes/FounderWaitlist.tsx`
* `V32_READINESS.md` (this file)

**Modified**
* `app.py` — `waitlist_store` import; new endpoints (`/waitlist/join`,
  `/public/cohort_status`, `/founder/waitlist`,
  `/founder/waitlist/update`); friendly message on cohort-full
  activation; root catalog updated; v32 What's New entry; version
  bumped to 2.8.
* `tests/conftest.py` — `waitlist_store` reset hook.
* `tests/test_v28_endpoints.py` — health version assertion bump.
* `web/src/lib/api.ts` — v32 types (`V32CohortStatus`,
  `V32WaitlistEntry`, etc.) + helpers (`publicCohortStatus`,
  `waitlistJoin`, `founderWaitlistList`, `founderWaitlistUpdate`).
* `web/src/App.tsx` — `/founder/waitlist` route registered behind
  `RequireAuth`.
* `web/src/routes/Home.tsx` — full rewrite as the public landing page.
* `BUILD_VERSION` — bumped to `20260506400000`.

`tsc --noEmit` (web) — clean (exit 0).

---

## 9. Rollback path

v32 is purely additive:
1. Revert `Home.tsx` if the marketing copy needs to come down — no
   data is bound to it.
2. The waitlist endpoints can be left untouched while reverting the UI
   (they have no upstream dependents).
3. To pause the public form entirely, add a CLARITYOS feature flag
   (e.g. `waitlist_open`) and gate `/waitlist/join` on it.

No persisted state from earlier versions was migrated.

---

## 10. Known gaps / next-pass candidates

* **Email delivery** — the waitlist captures emails but doesn't yet
  send anything (welcome, status changes, "spot opened"). v33 should
  wire SMTP / SendGrid + a renderable template surface.
* **Public site analytics** — no instrumentation; if the team wants
  conversion data, add structured impression logs + a hook into
  whatever analytics stack ships.
* **Waitlist position display** — the public form's success card says
  "we'll reach out" but doesn't surface a queue position. Adding
  `position` to the `/waitlist/join` response would let the UI show
  "you're #N on the waitlist" without leaking the entire list.
* **Founder console as proper home** — `/founder/waitlist` is a
  one-panel stub. Future passes can compose membership-cohort stats,
  payment audit logs, etc., into a real Founder Console at `/founder`.
* **Refund of activation when cohort race fills** — the v31 known gap
  still applies; v32 does not change the activation race semantics.
* **CSRF on `/waitlist/join`** — the public endpoint accepts any JSON
  POST. The IP rate limit is the only abuse mitigation; if abuse rates
  rise, add a CAPTCHA or a server-issued nonce to gate POST.
