# Waitlist

## Purpose

The waitlist is the upstream pre-signup funnel — it records interest from
people who have not yet created an account, captured from the public website or
imported manually by a founder.

## Implementation location

`waitlist_store.py` (introduced v32).

## Data model

One record per entry, keyed globally by `id`:

- `id` — `wl_<token>`.
- `email` — lowercased and format-validated; the dedupe key.
- `name` — optional.
- `source` — `website` / `linkedin` / `facebook` / `manual`.
- `status` — `waiting` / `contacted` / `converted` / `dropped`.
- `note` — short founder annotation, optional.
- `user_id` — set when the entry converts to a real account.
- `created_ts`, `updated_ts`, `contacted_ts`, `converted_ts`.

Caps: note 1000 chars, name 200, email 320.

## APIs / entrypoints

`add_waitlist_entry` (idempotent on email) · `get_waitlist_entry` ·
`find_by_email` · `list_waitlist(status=, limit=)` · `count_waitlist(status=)` ·
`update_status` · `mark_contacted` · `mark_converted` · `mark_dropped`.

## Integration points

- **Backends** — in-memory or Firestore (collection `waitlist`), selected by
  `CLARITYOS_BACKEND`.
- Distinct from the **membership** in-cohort waitlist, which tracks
  *authenticated* users who hit the cohort cap. This store is the upstream
  funnel of un-registered emails.

## Invariants

- `add_waitlist_entry` is idempotent on email: an existing non-`dropped` entry
  for the same email is returned untouched, so public-form retries do not
  duplicate.
- A transition to `converted` requires a non-empty `user_id`.
- Only the schema fields are stored — no free-form content; `note` is a short
  founder annotation.

## Non-goals

The waitlist does not create accounts, send email, or manage subscriptions — it
records funnel state only.

## Fiction removed

None — this subsystem had no prior canon file; it is newly documented.
