# PATCH PROPOSAL v2 — Membership gate + transactional credit debit
*COW-1 · 2026-06-18 · READ-ONLY proposal for ET-1.W (apply under CT-1 authorship) · supersedes v1*
*Scope per CT-1 brief: 1B + 2i + 3a, Tier 2 = entitlement-only.*

**What v2 adds over v1.** v1 wired membership-gating only. v2 adds the **metered credit debit**
on the six compute routes, made **transactional + idempotent + refund-on-failure**, using the
credit primitives already in `users_store` (`g_credits`, `consume_g_credit`, `add_g_credits`).
Two-layer entitlement: **membership = access (403)**, **credits = compute (402)**.

Grounded loci: store internals `users_store.py:41/58/83/89/131`; credit helpers `:166/175/193`;
`EngineRequest` `app.py:808-810`; webhook idempotency precedent `app.py:1498` / `billing_config.seen_event`.

---

## 1. New store functions — atomic, idempotent (the real work)

The existing `consume_g_credit` (`users_store.py:193`) is a non-atomic read-modify-write → it
**double-spends under Cloud Run concurrency** and **double-charges on retry**. Leave it in place
(other callers), add transactional siblings:

```python
# users_store.py — new. Requires CLARITYOS_BACKEND=firestore in prod.
_DEBITS_COLLECTION = "g_debits"
_MEMORY_DEBITS: dict = {}   # dev/test only

def consume_g_credit_tx(user: str, request_id: str, *, cost: int = 1) -> dict:
    """Atomic, idempotent debit keyed by request_id.
    Returns {"remaining": int, "replay": bool}. Raises ValueError("no_credits")
    if balance < cost (and not a replay of an already-charged request)."""
    if not request_id:
        raise ValueError("missing_request_id")

    if _backend() != "firestore":            # dev/test fallback — NOT concurrency-safe
        rec = _MEMORY_DEBITS.get(request_id)
        if rec and rec["status"] == "charged":
            return {"remaining": get_g_credit_balance(user), "replay": True}
        bal = get_g_credit_balance(user)
        if bal < cost: raise ValueError("no_credits")
        update_user(user, {"g_credits": bal - cost})
        _MEMORY_DEBITS[request_id] = {"user": user, "cost": cost, "status": "charged"}
        return {"remaining": bal - cost, "replay": False}

    from google.cloud import firestore
    client    = _get_firestore()
    user_ref  = _coll().document(user)
    debit_ref = client.collection(_DEBITS_COLLECTION).document(request_id)

    @firestore.transactional
    def _txn(txn):
        debit = debit_ref.get(transaction=txn)         # all reads before writes
        usr   = user_ref.get(transaction=txn)
        bal   = int((usr.to_dict() or {}).get("g_credits") or 0)
        if debit.exists and debit.to_dict().get("status") == "charged":
            return {"remaining": bal, "replay": True}   # idempotent no-op
        if bal < cost:
            raise ValueError("no_credits")
        txn.update(user_ref, {"g_credits": bal - cost})
        txn.set(debit_ref, {"user": user, "cost": cost, "status": "charged",
                            "request_id": request_id, "ts": time.time()})
        return {"remaining": bal - cost, "replay": False}

    return _txn(client.transaction())

def refund_g_credit_tx(user: str, request_id: str, *, cost: int = 1) -> None:
    """Void a prior debit after compute failure. Idempotent: only a 'charged'
    debit is refunded, then flipped to 'refunded' so it cannot refund twice."""
    if _backend() != "firestore":
        rec = _MEMORY_DEBITS.get(request_id)
        if rec and rec["status"] == "charged":
            update_user(user, {"g_credits": get_g_credit_balance(user) + cost})
            rec["status"] = "refunded"
        return
    from google.cloud import firestore
    client = _get_firestore(); user_ref = _coll().document(user)
    debit_ref = client.collection(_DEBITS_COLLECTION).document(request_id)
    @firestore.transactional
    def _txn(txn):
        debit = debit_ref.get(transaction=txn); usr = user_ref.get(transaction=txn)
        if not debit.exists or debit.to_dict().get("status") != "charged":
            return
        bal = int((usr.to_dict() or {}).get("g_credits") or 0)
        txn.update(user_ref, {"g_credits": bal + cost})
        txn.update(debit_ref, {"status": "refunded", "refunded_ts": time.time()})
    _txn(client.transaction())
```

---

## 2. App-layer helpers (`app.py`, near `require_session`)

```python
import contextlib, uuid

def require_credit_balance(session: dict = Depends(require_active_entitlement)) -> dict:
    """Cheap pre-check: fail fast with 402 if the user is obviously out of credits.
    (The authoritative charge is the transaction in `credit_charge`.)"""
    if users_store.get_g_credit_balance(session["user"]) <= 0:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
            detail=error_response("no_credits", "Out of compute credits. Recharge to continue."))
    return session

@contextlib.contextmanager
def credit_charge(user: str, request_id: str):
    """Atomic debit on enter; refund on exception from the wrapped compute."""
    try:
        res = users_store.consume_g_credit_tx(user, request_id)
    except ValueError as e:
        if str(e) == "no_credits":
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                detail=error_response("no_credits", "Out of compute credits. Recharge to continue."))
        raise
    charged = not res["replay"]
    try:
        yield res
    except Exception:
        if charged:
            users_store.refund_g_credit_tx(user, request_id)
        raise
```

Note: `require_active_entitlement` is the v1 helper (membership → 403); `require_credit_balance`
composes it, so a compute route depending on `require_credit_balance` enforces **both** layers.

---

## 3. The six compute routes — pattern (shown for `/markov`)

```python
@app.post("/markov")
def markov(req: EngineRequest,
           session: dict = Depends(require_credit_balance),
           idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    request_id = idempotency_key or (req.meta or {}).get("request_id")
    if not request_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            detail=error_response("missing_idempotency_key",
                "Idempotency-Key header (or meta.request_id) required for compute calls."))
    _log_call("markov", session)
    with credit_charge(session["user"], request_id) as charge:
        out = _timed("markov", markov_adapter, req.text, req.meta, session["user"])
    return ok_response("markov", out, remaining_credits=charge["remaining"])
```

Apply the same shape to: `markov` `8365`, `galileo` `8374`, `library` `8383`, `tizzy` `8392`,
`markov_chat` `8029`, `engine_v1_run` `11540`. (`ok_response` may need a small change to pass
`remaining_credits` into the envelope `data`/meta — see §5 cloud contract.)

**Tier 2 writes (entitlement-only, no debit)** — swap `Depends(require_session)` →
`Depends(require_active_entitlement)` on `library_user_write` `2264`, `library_user_update` `2302`,
`vault_write` `2119`, `vault_update` `2156`, `vault_delete` `2211`, `timeline_write` `2371`,
`markov_state_update` `2835`. No credit logic — local OS state per CT-1 ruling.

---

## 4. Cloud-contract response (CT-1 spec)

Compute responses surface `remaining_credits`; the app maps status codes:
`403 inactive_entitlement` (no membership) · `402 no_credits` (no balance) · `200` (ran).
`ok_response(...)` gains an optional `remaining_credits` folded into the envelope `data`.
`entitled`/`credit_ok` are implicit in the HTTP status (403/402/200) — no separate booleans needed
on success; the SPA branches on status.

---

## 5. Tests (ET-1.W)

1. **Inactive membership** → `POST /markov` ⇒ **403 inactive_entitlement**.
2. **Active, 0 credits** → **402 no_credits**; balance unchanged.
3. **Active, N credits** → **200**, balance N-1, `remaining_credits=N-1`, `g_debits/{request_id}` = charged.
4. **Replay same Idempotency-Key** → **200**, balance unchanged (no double-charge).
5. **Compute raises** (force adapter error) → balance restored (refund), debit flipped `refunded`.
6. **Concurrency** (two parallel calls, balance=1, distinct keys) → exactly one 200, one 402; never negative.
7. **Missing key** → **400 missing_idempotency_key**.

---

## 6. Decisions / edge cases for CT-1 (flagged, not assumed)

- **Client must send `Idempotency-Key`.** Per your "every request carries a request_id." This is
  an **API contract change** — the SPA/clients must send it (server-generated keys are not
  retry-safe). Confirm the SPA gets updated alongside.
- **Prod must be `CLARITYOS_BACKEND=firestore`.** The memory fallback is non-atomic (dev/test
  only). Atomicity guarantee = Firestore transactions; flagging so this never runs metered on memory.
- **Refund + retry:** a failed call is refunded and flipped `refunded`; a genuine retry should use
  a **new** Idempotency-Key (fresh charge). Reusing a `charged` key = idempotent no-op (no work,
  no charge). Confirm client retry policy matches.
- **`/markov/chat` streaming (if any):** if it streams, "compute failure after first token" makes
  refund semantics fuzzy — confirm whether chat is non-streaming here before wrapping identically.

---

## 7. Apply (ET-1.W, under CT-1 authorship)
1. Add §1 store functions + §2 app helpers. 2. Apply §3 route changes (6 compute + 7 Tier-2).
3. `python -c "import app"` clean. 4. Run §5 tests (add Firestore-emulator or memory-mode cases).
5. Scoped signed commit on the working branch → **STOP** before push (separate CT-1 gate).

**Scope discipline:** D1 + credit-debit only. No instrumentation/console work rides along.
