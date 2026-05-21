# Auth

## Purpose

Username/password authentication with server-side, opaque session tokens. There
is no JWT, no OAuth, and no cookie — a session is a bearer token presented in a
custom request header.

## Implementation location

`app.py` (the endpoints and the `require_session` dependency), `users_store.py`,
`sessions_store.py`, and `invites_store.py`.

## Data model

- **User record** — the `users` collection, document id = username:
  `username`, `password_hash` (bcrypt bytes), `salt` (reserved, always `""`),
  `tier`, `created_at`. The record is extended additively by other subsystems
  (`cohort`, `operator_id`, the membership fields, the billing fields, the #G
  credit fields — documented with those subsystems).
- **Session record** — the `sessions` collection, document id = the session id:
  `{user, expires_at}`. Two fields only.

## APIs / entrypoints

- `POST /login` — verifies the password with `bcrypt.checkpw`, mints
  `session_id = secrets.token_urlsafe(32)`, stores a session via
  `sessions_store.create_session` with an expiry of `now + SESSION_TTL_SECONDS`
  (`CLARITYOS_SESSION_TTL`, default `86400` s), and returns
  `{ok, session_id, expires_in, user}`. Bad credentials → 401 `bad_credentials`.
- `POST /register` — validates the username (3–64 chars, no whitespace) and
  password (≥ 8 chars), rejects a duplicate (409 `user_exists`), calls
  `_create_user`, then auto-logs-in by minting a session and returning the same
  envelope as `/login`. When `CLARITYOS_INVITE_ONLY=true` the endpoint is locked
  entirely → 403 `invite_required`.
- `_create_user(username, password)` — bcrypt-hashes the password (`bcrypt.hashpw`
  with a fresh `gensalt`) and writes the user via `users_store.create_user`.
- `require_session` — the FastAPI dependency (`Depends(require_session)`) on
  protected routes. It reads the `X-Session-ID` header: missing → 401
  `missing_session`; unknown → 401 `invalid_session`; past `expires_at` → the
  session is deleted and 401 `expired_session` is returned. On success it yields
  `{session_id, user, cohort}`.
- `_require_admin` / `_require_founder` — derived gates. Admin requires the
  session user to equal the admin user; founder requires the user's `cohort` to
  be `founder` or `founder_exception` (else 403).

## Integration points

- **`invites_store.py`** — a separate Terrace-1 onboarding path
  (`/invite/{token}/redeem`, `/finalize`). It does not gate `/register` unless
  `CLARITYOS_INVITE_ONLY` is set.
- **Admin bootstrap** — `_bootstrap_admin` runs at module import. The admin user
  is `CLARITYOS_ADMIN_USER` (default `admin`). An existing admin is not
  recreated but is force-set to `cohort=founder`; otherwise a user is created
  with `CLARITYOS_ADMIN_PASSWORD`, or with a random token printed once to stdout
  when that env var is unset.
- Every protected subsystem route depends on `require_session`.

## Invariants

- Passwords are stored only as bcrypt hashes; the salt is embedded in the hash.
- A session is valid only until `expires_at`; an expired session is deleted on
  its next use.
- The `X-Session-ID` header is the sole authentication mechanism.

## Non-goals

No JWT, no OAuth, no third-party identity providers, no cookies, no
password-reset flow, and no per-session metadata beyond `user` and `expires_at`.

## Fiction removed

None — this subsystem had no prior canon file; it is newly documented.
