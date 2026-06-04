# Tag & Version Plan — v0.3.13 (TASK 18)

## Version surfaces
| Surface | File | HEAD | v0.3.13 |
|---|---|---|---|
| Build id (cache-bust) | `BUILD_VERSION` (read by `app.py`, `runtime_http.py`) | `20260517173728` | **`20260527222355`** |
| Backend semantic | `app.py` `/health` + `/` `"version"` | `4.23` | **`4.24`** (additive: new `/operator/*`, `/auth/*`, telemetry keys) |
| Release name | git tag / branch | — | **`v0.3.13`** |

`BUILD_VERSION` is a monotonic build id (newer = cache-bust); `20260527222355`
> `20260517173728`. `4.23 → 4.24` is a minor bump (purely additive HTTP contract,
no breaking change).

## Patch
`build_version.patch` — bumps `BUILD_VERSION` + both app.py `"version"` strings.
**Verified:** applies cleanly on top of the 7-patch backend bundle.
Apply as the **final** backend step (after console commits, before deploy):
```
git apply landing_v0.3.13/build_version.patch
git add -- BUILD_VERSION app.py
git commit -m "chore(release): v0.3.13 — BUILD_VERSION + backend 4.24" \
           -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Tag
After all commits land and the suite is green:
```
git tag -a v0.3.13 -m "$(cat landing_v0.3.13/TAG_ANNOTATION.txt)"
```

### Annotation template
```
v0.3.13 — engine-cohort-operator

Operator-Intelligence Engine surfacing + auth + cross-surface Operator Console.

Backend (4.24):
  - mount Phase 7-9 operator telemetry surface (/operator/telemetry, /operator/action)
  - surface Phase 10 behavioral_forecast + Phase 11 recommendation_narrative
  - magic-link auth (/auth/enter, /auth/verify)
  - peripheral modules: harmonizer, compass_elins_bridge, orientation_contracts
  - fix: billing grace_period mapping (2 stale tests)

Console: web / desktop / phone Operator Console + 48 analysis modules/surface
  (web 49 specs, desktop 49 scaffolds, phone 48 scaffolds).

Verification: 10186 tests / 0 failed (9028 backend + 650 web + 265 desktop + 243 phone).
Build: 20260527222355.
```
(Save the body to `TAG_ANNOTATION.txt` at tag time, or inline with `-m`.)

## Notes
- Do **not** fold `build_version.patch` into a feature commit — it is a release
  chore commit, applied last.
- If the team prefers a fresh build timestamp at release time, regenerate
  `BUILD_VERSION` then; the patch value is the WIP-staged id and is safe as-is.
