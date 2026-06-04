# ClarityOS — Internal Architecture Audit

**OPORD response · read-only · no code modified.** Input for Perplexity Computer's
integration plan. Evidence is `file:line` in the current tree (verified live).
Companion: [`ENVELOPE_AUDIT.md`](ENVELOPE_AUDIT.md) (the storage-envelope deep dive).

---

## 0. Method
Five inputs: the prior envelope audit + three read-only sub-agent sweeps (account/
return-loop, engine integration, runtime entry) + a direct backend domain/URL sweep.
No primitives, schemas, renames, or migrations introduced. No files changed by this
audit (only this `.md` and `ENVELOPE_AUDIT.md` were written).

---

## 1. Envelope patterns (summary — full detail in `ENVELOPE_AUDIT.md`)
**Two intentional storage patterns, not one universal envelope.** The word "envelope"
denotes ~10 unrelated concepts.
- **Content-record envelope** — `vault_store`/`library_store`/`timeline_store`:
  `{id, user, type|kind, title?, content, tags, metadata, object_vector, size_bytes,
  created_at}`; enforced by a per-object **byte cap** (`VAULT_ENVELOPE_BYTES`=256 KB,
  `app.py:304`), a per-user **quota** (`_assert_quota` `app.py:1927`), and **auto-emit**
  timeline (`_emit_timeline` `app.py:1984`). Built **inline per endpoint**, no shared factory.
- **System/runtime KV** — `memory_vault` (encrypted per-user KV; `vault_put`
  `memory_vault.py:678`) fronted by `operator_state`/`threads_vault`/`projects_vault`/
  regression chains. No per-record `id/type/owner/version`; **owner = vault partition,
  version = module** (`STATE_VERSION`, `THREADS_VAULT_VERSION`, …).

---

## 2. Engine integration map
The engine (`intelligence_kernel.py` + `ELINS/*` + markov + `dewey_pipeline.py` +
azimuth) touches **both** patterns; the **live markov-chat path consumes state/
accumulator records, not the content records.**

- **Consumes:** `operator_state` (ESO mode + model precedence, `intelligence_kernel.py:93,196`;
  el_ins opt-in `:1005`), `threads_vault`/`projects_vault` (`:878,928,765`), `elins_project`
  (`:511,661`), `envelopes_store` accumulator (`app.py:5512,7633`), `markov qc_envelope`
  history (`app.py:7969`), dewey neighborhoods (`app.py:7986`).
- **Produces:** `operator_state.record_*` kernel logging (`intelligence_kernel.py:330,439,534`);
  `kernel_logging.log_kernel_run` on every run; `elins_project` persistence (`:414,525,643`);
  `threads_vault.append_message` (`:898,981`); `envelopes_store._evolve_envelope` mutates
  `brief.object_vector` then persists (`app.py:5495→7509`); markov `qc_envelope` persist
  (`app.py:2736`); dewey `object_vector` stamped on **every** vault/library/timeline write
  (`dewey_pipeline.embed_object`, `app.py:2050,2196,2303`).
- ⚠️ **Validation gap:** unit-norm validation lives only at the content/client boundary
  (`_validate_unit_norm` `app.py:2689`; `/envelope/update` `:8158`). **Engine-produced
  vectors are persisted without re-validation**, and the client-supplied `qc_envelope` is
  accepted as a **free-form `dict={}` with no schema check** (`app.py:2686,2742`).
- ⚠️ **Cross-pattern coupling is field-name-level, not a data leak:** `dewey_pipeline._object_text`
  (`:221-258`) is one dispatcher keyed on `kind`/`type`/`title`/`content`/`summary` across
  all three content stores. `user` (content family) vs `user_id` (`operator_state`/
  `memory_vault`/`threads_vault`) straddle the boundary.
- ⚠️ **Opposite raw-text policies between the two runtime stores:** `operator_state`/
  `memory_vault` strip raw text (`_strip_forbidden` `operator_state.py:142`); but
  `elins_project.save_daily_run` persists the full ELINS payload **incl. scenario text**
  (`elins_project.py:129`, with a misleading "don't store raw text" comment). Matters only
  if anything ever copies an `elins_project` run into `operator_state`/vault.

---

## 3. Account system map
**The username IS the primary key** for both `users_store` and `sessions_store` — there
is no separate user id.

| Path | Where | Returns | Auth carrier |
|---|---|---|---|
| `POST /login` (password) | `app.py:853` | `{ok, session_id, expires_in, user}` | session_id in **body** → SPA sends `X-Session-ID` |
| Magic-link `/auth/enter`→`/auth/verify` | `app.py:986,1002` / `auth_magiclink.py:392,459` | sets **HttpOnly cookie** `clarityos_session` + 303 to allowlisted path | ⚠️ **cookie only** (see §5) |
| `POST /invite/{token}/finalize` | `app.py:1327` | Stripe-verified → create user → `{ok, session_id, …, cohort, operator_id, plan}` | session_id in **body** |

- **Session record:** `{user, expires_at}` (`sessions_store.py:89`). **Validator:**
  `require_session(X-Session-ID)` (`app.py:552`) — 401 on missing/invalid/expired (lazy
  expiry, no sweeper), then **augments** to `{session_id, user, cohort}` which every
  endpoint receives. TTL `CLARITYOS_SESSION_TTL` = 86400 (`app.py:284`).
- **Identity enters the engine at:** `operator_state.get_operator_state(user_id)`
  (`operator_state.py:192`) → `memory_vault.vault_list(user_id)` (username = encryption +
  partition key) → `intelligence_kernel.kernel_view_for_user(user_id)`
  (`intelligence_kernel.py:2044`) → assembled into `GET /me` (`app.py:1691`). The first
  `/me` after user creation lazily materializes the vault scaffolding (`operator_state.py:202`).
- Privileged side-channel: `Authorization: Operator <token>` constant-time vs
  `CLARITYOS_OPERATOR_TOKEN` (`app.py:584`) — not session-based.

---

## 4. Runtime entry points + return loop
**Frontend boot:** `main.tsx` → `App.tsx` → `RequireAuth.tsx` (`:20` gates on
`auth.session` from localStorage; unauth → `/login` carrying `from`). **API base
resolution** (`config.ts resolveBase`, last non-empty wins): `localStorage
clarityos_api_base` > `window.CLARITYOS_API_BASE` (WordPress embed) > `VITE_API_BASE`
> `DEFAULT_API_BASE`.

**Return loop** (`auth → engine → memory_vault → UI`):
```
X-Session-ID header
 → require_session (app.py:552; validates sessions_store, attaches cohort)
 → users_store.get_user(session["user"])  (app.py:1697)
 → operator_state.get_operator_state(user)  (operator_state.py:192)   ← identity enters engine
 → memory_vault (memory_vault.py:660+; username = encryption/partition key)
 → kernel_view_for_user (intelligence_kernel.py:2044)
 → GET /me JSON (app.py:1733)
 → web refreshProfile cache (api.ts:184) → invalidateAndNotify (auth.ts:31)
 → useSyncExternalStore re-render (Layout.tsx)
```
**Post-login hydration order:** `/login` → `/me` (`syncProfile`) → `/config` →
`/continuity/snapshot` → `/v29/flags`; default landing route **`/operator`**
(`Login.tsx:14`). Each secondary call independently re-enters via `require_session`.

---

## 5. Deviations (consolidated; ⚠️ = accidental, ◾ = intentional-but-undocumented)
- ⚠️ **`type` vs `kind` swapped for the same role** across storage vs billing vs timeline; **`user` vs `user_id`** across the two patterns (§2). Highest-risk drift for generic record reasoning.
- ⚠️ **Timestamp drift:** `created_at`/`ts`/`updated_at`; `incident_store` uses **ms**, others **seconds**.
- ⚠️ **Validation gap:** engine vectors + client `qc_envelope` persisted unvalidated (`app.py:2686`).
- ⚠️ **Cookie/header gap (integration-critical):** magic-link sets a cookie; `require_session` reads only `X-Session-ID` (`app.py:552`). The cookie alone does **not** authorize SPA XHR after the `/auth/verify → /app` redirect.
- ⚠️ **Three backend API URLs** disagree (`config.ts:23` default vs `.env.production` vs `.env.local`; §6).
- ⚠️ **`INVITE_BASE_URL` = `clarityos.app` placeholder** (`app.py:293`), not `clarity.pro-mediations.com` (the post-purchase redirect gap; success page added in `fix/invite-success-page`).
- ⚠️ **Frontend type gap:** `ServerVaultItem.type` `"note"|"session"` misses backend `"elins_raw"` (`api.ts:237` vs `app.py:310`).
- ◾ memory_vault-backed stores omit the content record envelope (owner=partition, version=module) — a deliberate pattern, just undocumented as such.

---

## 6. Constraints for runtime-URL selection (the integration-critical output)
**Domain map (verified):**
| Role | Host | Source |
|---|---|---|
| Web SPA front-end (the "OS") | **`clarity.pro-mediations.com`** | CORS `app.py:346`; serves the `web/` build |
| Magic-link auth base | **`clarity.pro-mediations.com`** | `CLARITYOS_AUTH_BASE_URL` default `auth_magiclink.py:107` |
| WordPress shell (enter form) | `pro-mediations.com/enter/` | `CLARITYOS_SHELL_ENTER_URL` `auth_magiclink.py:113` |
| Cockpit surface | **`cockpit.pro-mediations.com`** | `app.py:335` (Node v0.2) |
| Invite/checkout base | ⚠️ `clarityos.app` **placeholder** | `INVITE_BASE_URL` `app.py:293` — **must be `clarity.pro-mediations.com`** |
| Backend API | ⚠️ **3 conflicting Cloud Run URLs** | `config.ts:23` / `.env.production` / `.env.local` |

**Required invariants for integration:**
1. **Pin ONE canonical backend API URL** and ensure it is in CORS `allow_origins`
   (`app.py:344-349`). Today the SPA can resolve to any of three Cloud Run hosts.
2. **`INVITE_BASE_URL` must equal the SPA host** (`clarity.pro-mediations.com`) so Stripe's
   `success_url` (`/invite/{token}/success?plan=&session_id=`, `app.py:1308`) lands on the
   new success page rather than the 404'ing placeholder.
3. **Magic-link redirects are allowlisted** to `{/app, /app/transformation, /onboarding,
   /account}` (`NEXT_KEYS` `auth_magiclink.py:80`); the SPA **must serve `/app`** and the
   default `/operator` landing must be reconciled with the magic-link `/app` target.
4. **Resolve the cookie↔header split:** either the SPA reads `clarityos_session` at `/app`
   entry and promotes it into `X-Session-ID`/localStorage, or `require_session` is taught to
   accept the cookie. Without this, magic-link sign-in does not hydrate the SPA session.
5. **Identity key = username** end-to-end (no separate user id); it enters the engine at
   `operator_state.get_operator_state(username)`. Any external identity (Perplexity) must
   map to a stable username.
6. **`X-Session-ID` is the sole API auth carrier** for the SPA — any embedding host
   (WordPress, Perplexity Computer) must surface it on every request.

---

## 7. Minimal corrections (surgical; recommendations only — none applied)
1. **`app.py:293`** — set `INVITE_BASE_URL` default to `https://clarity.pro-mediations.com`
   (or require the env var), removing the `clarityos.app` placeholder. *(1 line / config)*
2. **Cookie↔header** — smallest fix: at SPA `/app` boot, read `clarityos_session` and call
   `setSession(...)` so XHR authenticates. *(frontend, localized)* — or document that magic-link
   currently requires a follow-up to populate `X-Session-ID`.
3. **`api.ts:237`** — add `"elins_raw"` to `ServerVaultItem.type`. *(1 line)*
4. **Pin the backend URL** — make `config.ts:23` `DEFAULT_API_BASE` and `.env.production`
   agree on one host. *(config only)*
5. **Doc** — commit the envelope glossary + two-pattern note (`ENVELOPE_AUDIT.md` §4) so the
   intentional bifurcation and the `user`/`user_id`, `type`/`kind` conventions are explicit.

*No structural changes, schema unification, or migrations proposed. Holding for the next
OPORD before any code change.*
