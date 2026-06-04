# Integrated Suite Report (TASK 9)

**Stack:** HEAD `2651c78` + `phase7_mount` + `billing_fix` (×2 tests) + `auth_magiclink_landing`
+ 3 peripheral patches + `phase10_11_surface`. Applied to a clean detached worktree;
`CLARITYOS_BACKEND=memory`, `pytest tests/ -p no:cacheprovider`.

## Result
| Metric | Value |
|---|---|
| **Passed** | **9028** |
| **Failed** | **0** |
| Duration | 14m13s |
| Regressions | **none** |
| Verdict | **GREEN** ✅ |

## Reconciliation (deterministic)
| | total | passed | failed |
|---|---|---|---|
| Baseline (clean HEAD) | 8948 | 8901 | 47 |
| + 80 new tests (auth 42 / peripheral 33 / surface 5) | 9028 | — | — |
| − 47 fixed (45 phase via mount + 2 billing) | — | +47 | −47 |
| **Integrated** | **9028** | **9028** | **0** |

The +80 and −47 account for every delta exactly: `9028 = 8948 + 80`, and all 47
baseline reds resolved (45 Phase 7–11 endpoint 404s by the mount, 2 stale
grace_period tests by `billing_fix`).

## Nondeterminism
None observed. Across four independent full/partial runs the failure sets were
identical and stable: baseline 47-fail (twice, same set), mount-only 483-pass,
integrated 0-fail. Pytest collection is deterministic (no `-p randomly`, no
wall-clock in the engines — action timestamps are caller-supplied).

## Notes
- The single warning is a benign `PendingDeprecationWarning` from
  starlette/multipart (third-party), not repo code.
- This run covers **backend (pytest)** only. Console (vitest) verification is
  TASK 14.
