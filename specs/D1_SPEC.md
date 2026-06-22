# D1 Specification — Entitlement, Metered Compute, Idempotency, Refund

| Field            | Value                                                                 |
|------------------|-----------------------------------------------------------------------|
| Status           | AUTHORITATIVE                                                         |
| Version          | 1.1                                                                   |
| Authority        | CT-1                                                                  |
| Authored         | 2026-06-19 (v1.0 → v1.1 same day)                                     |
| Supersedes       | D1_SPEC.md v1.0 (2026-06-19, CT-3 promotion of CT-1 design draft)     |
| Binds            | CT-2 (verification), CT-3 (test extension), ET-1.W (execution)        |
| Implementation   | Staged bundle at `C:\Users\chris\OneDrive\Copilot\ClarityOS_command_staging\d1_patch\` — COW-1, 2026-06-18, base `main @ d8e44ba` |
| Resolves         | Blockers #1, #2 (via PRE/POST hash gate), #3, #4                      |

---

## 0. Vocabulary

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** in
this document are to be interpreted as described in RFC 2119.

Where this spec references implementation symbols (e.g.
`require_active_entitlement`, `consume_g_credit_tx`), those names are
**binding** — they refer to the as-built bundle. Other implementations are
out of scope for v1.1.

---

## 1. Scope

This specification defines four mechanisms applied to ClarityOS Cloud:

1. **Entitlement gating** of 6 Tier-1 compute routes and 7 Tier-2 write routes.
2. **Credit metering** of the 6 Tier-1 compute routes.
3. **Idempotency-key enforcement** of the 6 Tier-1 compute routes.
4. **Refund-on-failure** for the 6 Tier-1 compute routes.

Out of scope for v1.1:

- Plan tiers beyond `FOUNDER_50MO`.
- Stripe webhook handlers; subscription lifecycle events; proration.
- Admin/back-office credit grants or overrides.
- Variable per-route cost (cost is fixed at 1 in v1.1; the `cost` parameter
  exists for forward compatibility).
- Streaming compute responses (CT-1 §6 D3 ruling: no streaming exists; all
  Tier-1 routes are synchronous in v1.1).

---

## 2. Definitions

**Entitlement.** A durable record indicating that a user holds an active
subscription. Read via `entitlement_view.compute_entitlement_view(user)`,
which returns at minimum `{"active": bool, ...}`.

**Compute credit.** A non-negative integer counter on the user record under
field `g_credits`. One credit corresponds to one successful Tier-1 call.

**Tier-1 compute route.** A route gated by `Depends(metered_compute)`. The 6
Tier-1 routes are enumerated in §8.1.

**Tier-2 write route.** A route gated by `Depends(require_active_entitlement)`
with no credit accounting. The 7 Tier-2 routes are enumerated in §8.2.

**Idempotency key.** A client-supplied string in the request header
`Idempotency-Key`. Used as the document ID in the `g_debits` Firestore
collection. The bundle's idempotency model is **charge-idempotency**, not
response-idempotency — see §6.

**Debit record.** A document in `g_debits` keyed by `request_id` with shape
`{user, cost, status, request_id, ts}`. Status lifecycle: `charged` →
`refunded`. No other states exist.

**Refund-worthy failure.** Any exception raised from the wrapped handler.
The bundle uses `except Exception:` in the yield-dependency teardown.

---

## 3. Entitlement Model

### 3.1 Entitlement reader (normative)

Implementations **MUST** read entitlement state via
`entitlement_view.compute_entitlement_view(user)`. That function is the
single source of truth and **MUST** be the same projection the Stripe
webhook writes to.

Return shape **MUST** include the key `active: bool`. Implementations
**MAY** include additional fields (plan code, period bounds, balance) but
**MUST NOT** rely on them in the §3.3 check.

### 3.2 Entitlement states

| State conveyed by `active` | Tier-1 allowed? | Tier-2 allowed? |
|----------------------------|-----------------|-----------------|
| `active == true`           | Yes             | Yes             |
| `active == false`          | No              | No              |

CT-1 §6 D4 ruling (CLOSED): production **MUST** use the Firestore backend.
The bundle enforces this at import via `_assert_prod_firestore_backend()`,
which raises `RuntimeError` if `K_SERVICE` is set and `CLARITYOS_BACKEND`
is not `firestore`.

### 3.3 Entitlement check (normative)

For every Tier-1 and Tier-2 request, the service **MUST**:

1. Resolve the session per the v2.0 baseline (`require_session`).
2. Call `entitlement_view.compute_entitlement_view(session["user"])`.
3. If the returned `active` is not truthy, reject with HTTP 403 and envelope
   `{"ok": false, "error": "inactive_entitlement", "message": "Active membership required for this resource."}`.

The bundle implements this in `require_active_entitlement`. All gating
behavior **MUST** route through that function — Tier-1 and Tier-2.

---

## 4. Credit Model

### 4.1 Credit unit and cost

One compute credit corresponds to one successful Tier-1 call. v1.1 fixes
the per-call `cost` at `1`. The `consume_g_credit_tx` and `refund_g_credit_tx`
functions accept a `cost: int = 1` keyword argument for forward
compatibility; v1.1 **MUST NOT** invoke them with `cost != 1`.

### 4.2 Counter semantics

The `g_credits` field on the user record **MUST** be a non-negative integer.
Implementations **MUST NOT** allow it to go negative; the §4.3 atomic check
prevents this.

### 4.3 Atomic debit (normative)

The function `users_store.consume_g_credit_tx(user, request_id, *, cost=1)`
**MUST**:

- Be transactional against the Firestore backend (prod) and a best-effort
  non-atomic equivalent on the memory backend (dev/test only).
- Reject `request_id` falsy/empty with `ValueError("missing_request_id")`.
- Return `{"remaining": int, "replay": True}` if a debit document already
  exists with `status == "charged"` for this `request_id`. No second debit
  occurs.
- Raise `ValueError("no_credits")` if `g_credits < cost` and no prior
  charged debit exists for this `request_id`.
- Otherwise: decrement `g_credits` by `cost`, write a new debit document
  `{user, cost, status: "charged", request_id, ts}`, and return
  `{"remaining": new_balance, "replay": False}`. Both writes **MUST** occur
  within a single Firestore transaction.

The `metered_compute` dependency **MUST** translate `ValueError("no_credits")`
into HTTP 402 with envelope `{"ok": false, "error": "no_credits", "message":
"Out of compute credits. Recharge to continue."}`.

### 4.4 X-Remaining-Credits response header

On every successful entry into the wrapped handler, `metered_compute`
**MUST** set the response header `X-Remaining-Credits` to the string form
of the `remaining` field returned by `consume_g_credit_tx`.

---

## 5. Metered Compute Behavior

### 5.1 Per-request flow

For every Tier-1 compute request, the service **MUST** execute steps in
order:

1. Resolve session via `require_session` (v2.0 baseline).
2. Resolve entitlement via `require_active_entitlement`; 403 on failure
   (§3.3).
3. Validate `Idempotency-Key` header present; 400 `missing_idempotency_key`
   on missing (§6).
4. Atomic debit via `consume_g_credit_tx(user, key)`; 402 `no_credits` if
   balance insufficient (§4.3).
5. Set `X-Remaining-Credits` response header (§4.4).
6. Yield to the wrapped handler.
7. On handler return: response propagates. Debit persists.
8. On handler exception: if `replay == False`, refund via
   `refund_g_credit_tx(user, key)`. Re-raise the original exception.

Step ordering is normative. The implementation **MUST NOT** debit before
entitlement validation. The implementation **MUST NOT** refund a debit
whose `replay == True` (it was already charged by a prior call).

### 5.2 Wire pattern (binding)

The bundle uses a FastAPI yield-dependency, NOT a decorator:

```python
@app.post("/markov")
def markov(req: EngineRequest, session: dict = Depends(metered_compute)):
    ...
```

Implementations **MUST** wire all 6 Tier-1 routes by replacing
`Depends(require_session)` with `Depends(metered_compute)` in the route
signature. Handler bodies **MUST NOT** be modified for D1.

### 5.3 Response envelope

Successful and error responses **MUST** use the v2.1 mobile-safe envelope:

- Success: `{"ok": true, "engine": "...", "data": {...}, ...}` with
  `X-Remaining-Credits` header.
- Error: `{"ok": false, "error": "<code>", "message": "<human text>"}`.

---

## 6. Idempotency-Key Enforcement

### 6.1 Header (CT-1 §6 D1 ruling CLOSED)

Header name: `Idempotency-Key`. **MUST** be present on every request to a
Tier-1 route. Missing → HTTP 400 `missing_idempotency_key`.

v1.1 does not impose charset or length validation on the key. The SPA
**MUST** generate a fresh UUID per attempt (CT-1 §6 D2 ruling). Servers
**MAY** add charset/length validation in a future spec amendment (see §11).

### 6.2 Store

Backend: Firestore collection `_DEBITS_COLLECTION = "g_debits"`. Document ID
is the `request_id` (= Idempotency-Key value). No separate idempotency
table exists.

Document shape:

| Field         | Type    | Notes                                |
|---------------|---------|--------------------------------------|
| `user`        | string  | The user_id                          |
| `cost`        | integer | Always 1 in v1.1                     |
| `status`      | string  | `"charged"` or `"refunded"`          |
| `request_id`  | string  | The Idempotency-Key                  |
| `ts`          | number  | `time.time()` at write               |
| `refunded_ts` | number  | Optional; set on status flip         |

### 6.3 Charge-idempotency semantics (binding)

The bundle's model prevents **double-charge** but does NOT cache responses:

- Same key, status `charged`: `consume_g_credit_tx` returns `replay=True`;
  the handler still executes (against whatever body the new request
  carries); no second debit; on handler exception, refund is skipped
  (the original charge stands).
- Same key, status `refunded`: idempotent — no debit, no refund. The
  handler still executes. CT-1 §6 D2 ruling: a refunded failure requires
  a **new** Idempotency-Key for the client to be re-charged for a retry.
- Different key: independent transaction.

**Implication for SPA developers**: replaying with the same key and a
different body will silently re-execute the handler with the new body
without a new charge. This is a deliberate v1.1 simplification. See §11.3.

### 6.4 TTL

Debit documents are **permanent**. v1.1 does not define a TTL. Reconciliation
or pruning is out of scope.

---

## 7. Refund-on-Failure Semantics

### 7.1 Refund-worthy classification (binding)

v1.1 refunds on **any** handler exception. The bundle's `metered_compute`
teardown reads:

```python
try:
    yield session
except Exception:
    if not res["replay"]:
        users_store.refund_g_credit_tx(user, idempotency_key)
    raise
```

Distinctions between 4xx/5xx, exception subclasses, or refund-worthy lists
are NOT made in v1.1. Any exception that propagates past the handler
triggers refund (unless the debit was a replay).

### 7.2 Refund mechanism (normative)

`users_store.refund_g_credit_tx(user, request_id, *, cost=1)` **MUST**:

- Be a no-op if `request_id` is falsy.
- Be a no-op if the debit document is missing or its `status` is not
  `"charged"` (idempotent against double-refund).
- Otherwise: within a Firestore transaction, increment `g_credits` by
  `cost` and update the debit document's `status` to `"refunded"` and set
  `refunded_ts = time.time()`.

The bundle has no separate refund ledger; the status flip on the debit
document is the audit trail.

### 7.3 Refund failure path

v1.1 does not define behavior if `refund_g_credit_tx` itself fails. This
is flagged in §11.1 as a follow-on item. In practice, a Firestore txn
failure during refund will propagate as a generic 500 from the original
exception path; the orphan debit remains in `g_debits` with status
`charged` and no corresponding response was returned to the client.

---

## 8. Tier-1 vs Tier-2 Distinction

### 8.1 Tier-1 compute routes (BINDING ENUMERATION)

Six routes. All **MUST** be gated by `Depends(metered_compute)`:

| Route             | Handler             | Notes                                  |
|-------------------|---------------------|----------------------------------------|
| `/markov`         | `markov`            | v2.1 baseline + D1 dep swap            |
| `/galileo`        | `galileo`           | v2.1 baseline + D1 dep swap            |
| `/library`        | `library`           | v2.1 baseline + D1 dep swap            |
| `/tizzy`          | `tizzy`             | v2.1 baseline + D1 dep swap            |
| `/markov/chat`    | `markov_chat`       | CT-1 §6 D3: synchronous, not streaming |
| `/engine/v1/run`  | `engine_v1_run`     | umbrella Phase-1 endpoint              |

### 8.2 Tier-2 write routes (BINDING ENUMERATION)

Seven routes. All **MUST** be gated by `Depends(require_active_entitlement)`
with **no** credit accounting and **no** Idempotency-Key requirement at the
D1 layer:

| Route                    | Handler                |
|--------------------------|------------------------|
| `/vault/write`           | `vault_write`          |
| `/vault/update`          | `vault_update`         |
| `/vault/delete`          | `vault_delete`         |
| `/library/write`         | `library_user_write`   |
| `/library/update`        | `library_user_update`  |
| `/timeline/write`        | `timeline_write`       |
| `/markov/state/update`   | `markov_state_update`  |

Tier-2 missing-entitlement code is the same as Tier-1: HTTP 403
`inactive_entitlement`. The distinction is debit, not error code.

---

## 9. Canonical HTTP and Envelope Codes

| Condition                              | HTTP | `error` code              | Source                       |
|----------------------------------------|------|---------------------------|------------------------------|
| Missing `X-Session-ID`                 | 401  | `missing_session`         | v2.0 baseline                |
| Invalid / expired session              | 401  | `invalid_session` / `expired_session` | v2.0 baseline   |
| No active entitlement (Tier-1 or 2)    | 403  | `inactive_entitlement`    | `require_active_entitlement` |
| Missing `Idempotency-Key` (Tier-1)     | 400  | `missing_idempotency_key` | `metered_compute`            |
| Balance < cost (Tier-1)                | 402  | `no_credits`              | `metered_compute`            |
| Handler exception (Tier-1)             | 500  | `engine_error`            | v2.1 baseline; refund occurs |

Success responses on Tier-1 routes carry the response header
`X-Remaining-Credits: <int>`.

---

## 10. Cross-walk

### 10.1 Bundle test → spec section

The bundle's `test_d1_entitlement_credit.py` provides the §5 starter
matrix:

| Bundle test                              | Covers spec § |
|------------------------------------------|---------------|
| `test_1_inactive_membership_403`         | §3.3, §9      |
| `test_2_active_zero_credits_402`         | §4.3, §9      |
| `test_3_active_with_credits_200_and_debit` | §4.3, §4.4, §5.1 |
| `test_4_replay_same_key_no_double_charge`| §6.3          |
| `test_5_compute_failure_refunds`         | §5.1 step 8, §7 |
| `test_6_missing_idempotency_key_400`     | §6.1, §9      |
| `test_7_tier2_write_membership_only_no_debit` | §3.3, §8.2 |

### 10.2 DRAFT-SCAFFOLD contracts → status

See `drafts/d1_scaffold/test_contracts.md` (updated this turn) for the
annotated list. Contracts collapse to three categories: subsumed by the
bundle's 7 tests, follow-on tests for the Firestore emulator phase, or
N/A under v1.1's charge-idempotency model.

---

## 11. Open items (v1.1)

Three items the bundle does not close. These are not v1.1 blockers — they
are flagged for the next CT-1 review cycle:

1. **Refund-failure path.** If `refund_g_credit_tx` itself raises during
   the teardown, the orphan debit remains in `g_debits`. v1.1 does not
   define reconciliation cadence or retry policy.
2. **`Idempotency-Key` charset / length validation.** The bundle accepts
   any non-empty string. v1.1 leaves this unvalidated.
3. **Same-key-different-body silent re-execution** (§6.3). This is a
   deliberate v1.1 simplification but creates a subtle pitfall for SPA
   developers who assume idempotency keys imply response caching. The SPA
   contract documentation **MUST** call this out.

A fourth concern flagged in BUNDLE.md is verified by extending the test
matrix, not by spec amendment:

- 422 body-validation errors before the dependency resolves. Expected
  behavior: no charge occurs (the debit is in the dep, which only resolves
  if params validate). A boundary test verifying this is a follow-on per
  CT-3.

---

## 12. Change log

| Version | Date       | Author        | Change                              |
|---------|------------|---------------|-------------------------------------|
| 1.0     | 2026-06-19 | CT-3 promote  | Initial issue, ignorant of staged bundle |
| 1.1     | 2026-06-19 | CT-3 reconcile | Aligned to as-built bundle (COW-1 2026-06-18). Vocabulary swap (`inactive_entitlement` / `no_credits` / `missing_idempotency_key`); 403 for entitlement (both tiers); charge-idempotency model; route enumeration (6 Tier-1, 7 Tier-2); `X-Remaining-Credits` header; CT-1 §6 rulings D1/D2/D3/D4 codified |
