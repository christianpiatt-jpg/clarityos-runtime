# PATCH PROPOSAL — `require_active_entitlement` (close D1 / D-recon-G-1)
*COW-1 · 2026-06-18 · READ-ONLY proposal for ET-1.W to apply under CT-1 authorship · repo `clarityos-runtime`*

**What it does.** Adds one surgical FastAPI dependency that composes `require_session` + the
existing entitlement contract, and fails closed (403) for non-entitled sessions. Reuses
`entitlement_view.compute_entitlement_view` (already imported; used at `app.py:13433/13448`) —
no new entitlement logic, no new state, no handler-body changes.

**Why it's safe/small.** `compute_entitlement_view(user)` reads `billing_state` /
`membership_status` from `users_store` — the *same store the webhook writes* via
`set_billing_state` (`app.py:1665/1696/1728/…`). Its `active` flag already encodes the v31
grace rules (`active`, `past_due`, `grace_period` keep access; `cancelled`/`failed` revoke;
`billing_state is None` → tracks `membership_status == "active"`). We gate on that flag.

---

## 1. The helper (insert after `require_session`, ~`app.py:580`)

```python
def require_active_entitlement(session: dict = Depends(require_session)) -> dict:
    """Gate value routes on active entitlement (D1 / D-recon-G-1).

    Composes require_session (session validity first), then consumes the
    canonical entitlement projection and FAILS CLOSED for non-entitled users.
    Returns the same session dict require_session does — handler bodies are
    unchanged (they keep using session["user"]).
    """
    view = entitlement_view.compute_entitlement_view(session["user"])
    if not view.get("active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response(
                "inactive_entitlement",
                "Active membership required for this resource.",
            ),
        )
    return session
```

Dependencies used are all already in scope: `Depends`, `HTTPException`, `status`,
`error_response`, `entitlement_view` (confirm the `import entitlement_view` line is present —
it is exercised at `app.py:13433`).

---

## 2. Wire it into the value routes — swap the dependency

For each handler below, change its `Depends(require_session)` → `Depends(require_active_entitlement)`.
Because the helper itself depends on `require_session`, session validation is preserved.

### Tier 1 — paid compute (gate; this is the revenue leak — do these)

| Route | Function @ line | Change |
|-------|-----------------|--------|
| `/markov` | `markov` @ `8365` | `def markov(req: EngineRequest, session: dict = Depends(require_active_entitlement)):` |
| `/galileo` | `galileo` @ `8374` | `def galileo(req: EngineRequest, session: dict = Depends(require_active_entitlement)):` |
| `/library` | `library` @ `8383` | `def library(req: EngineRequest, session: dict = Depends(require_active_entitlement)):` |
| `/tizzy` | `tizzy` @ `8392` | `def tizzy(req: EngineRequest, session: dict = Depends(require_active_entitlement)):` |
| `/markov/chat` | `markov_chat` @ `8029` | in its signature, `session: dict = Depends(require_active_entitlement),` (line ~`8031`) |
| `/engine/v1/run` | `engine_v1_run` @ `11540` | in its signature, `session: dict = Depends(require_active_entitlement),` (line ~`11542`) |

The four single-line engine signatures have unique function names → safe exact replace.
`markov_chat` and `engine_v1_run` are multi-line → change the `Depends(require_session)` **within
that function's signature only** (the substring repeats elsewhere; scope by function).

### Tier 2 — user-data writes (POLICY CHOICE — see caveat before applying)

| Route | Function @ line |
|-------|-----------------|
| `/library/write` | `library_user_write` @ `2264` |
| `/library/update` | `library_user_update` @ `2302` |
| `/vault/write` | `vault_write` @ `2119` |
| `/vault/update` | `vault_update` @ `2156` |
| `/vault/delete` | `vault_delete` @ `2211` |
| `/timeline/write` | `timeline_write` @ `2371` |
| `/markov/state/update` | `markov_state_update` @ `2835` |

> **Advisor caveat (Condition-1 discipline).** Tier 1 is an unambiguous fix — paid compute must
> be entitled. Tier 2 is a **product decision**, not a mechanical one: gating *all* writes fails
> closed on free-tier / onboarding users (anyone with `billing_state is None` and
> `membership_status != "active"` → `active == False` → blocked). If free tier is allowed to
> read/write basic data, do **not** blanket-apply Tier 2 — gate only the metered subset. The
> helper makes this a one-line toggle per route, so the decision stays explicit and reversible.

---

## 3. Optional — free-tier-aware variant (if some routes allow free)

If you want a single helper that distinguishes "logged in" from "entitled" without duplicating:

```python
def require_entitlement(allow_free: bool = False):
    def _dep(session: dict = Depends(require_session)) -> dict:
        if allow_free:
            return session
        view = entitlement_view.compute_entitlement_view(session["user"])
        if not view.get("active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_response("inactive_entitlement",
                                      "Active membership required for this resource."),
            )
        return session
    return _dep
# usage: Depends(require_entitlement())            # gate
#        Depends(require_entitlement(allow_free=True))  # free-tier route
```

Pick one of §1 or §3 — not both. §1 is the smaller, recommended start (Tier 1 only).

---

## 4. Fail-closed behaviour (what the client sees)

Non-entitled session → **HTTP 403** with the mobile-safe envelope
`{ok:false, error:"inactive_entitlement", message:"Active membership required…"}`. These are
API/JSON endpoints, so **return 403, do not server-side redirect** — the SPA maps
`inactive_entitlement` to its paywall/upgrade route (the redirect belongs on the client, same
pattern as `RequireAuth`).

## 5. Apply / verify (ET-1.W, under CT-1 authorship)

1. Insert §1 helper after `require_session`.
2. Apply Tier 1 swaps (6 routes). Decide Tier 2 per the §2 caveat.
3. `python -c "import app"` (import-clean) + run the route tests.
4. Suggested test: a session whose user has `billing_state` unset / `cancelled` → `POST /markov`
   expects **403 inactive_entitlement**; an `active` user → **200**.
5. Scoped commit, signed, on the working branch → **STOP** before push (separate CT-1 gate).

**Scope discipline:** this is the D1 fix only. No instrumentation/console work rides along.
