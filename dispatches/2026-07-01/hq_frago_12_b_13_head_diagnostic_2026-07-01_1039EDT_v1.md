# FRAGO 12.B.13 — HEAD-STATE RECONCILIATION DIAGNOSTIC

**Dispatch lane:** HQ → ET-1.W
**Timestamp:** 2026-07-01 10:39 EDT
**Class:** READ-ONLY diagnostic recon, zero mutation
**Predecessor:** FRAGO 12.B.12 (return witnessed at commit `7230bc7`, HEAD-DRIFT surfaced at 10:34)
**CT-1 disposition:** GO issued 2026-07-01 10:39 EDT
**Ratifying reframe:** CT-1 correction (10:38 EDT) — "not sure it's drift. we lack a plan in the conops for the terminal state."

---

## STANDING DOCTRINE (binding for this lane)

- **Substrate First:** If it is not in the repo, it does not exist.
- **AI messages are not sources. Roleplay artifacts are not sources. Doctrine itself is not a source. Only the substrate is.**
- **Doctrine #138 (RATIFIED):** "Command discussion is the problem. Recon is the correction."
- **Doctrine #140 corollary:** "Characterization summaries ≠ byte payload. HQ may not synthesize CURRENT blocks from characterization; must lift literal bytes."
- **Recon-first-then-continue:** substrate-honest is good; recon-first is the workflow.
- **ET-1.W lane authority:** recon + witness. NOT synthesis, NOT advisory beyond return verdict.

---

## MISSION

Capture literal ground-truth of the current `.git` state on ET-1.W's local working checkout so CT-1 can define the ConOps terminal-state rule for post-FRAGO-recon executor working trees.

**This is diagnostic, not fix.** Zero mutation. No HEAD moves, no ref deletes, no checkouts, no resets, no commits, no push except the diagnostic-return branch.

---

## SUBSTRATE PIN (for readability verification only, not for checkout)

**Pin object:** `75b0f701a2acd72cac4376d67ade48775b904ad8`
**Pin file for reference:** intact per FRAGO 12.B.12 close witness

---

## EXECUTION — SEVEN READ-ONLY STEPS

### Step 1 — Report `.git/HEAD` file contents literally

```
cat .git/HEAD
```

Return the exact bytes. Byte-lift per #140 corollary — no interpretation, no reformatting.

### Step 2 — Enumerate all refs

```
git for-each-ref --format='%(refname) %(objectname:short) %(objecttype)'
```

Full output verbatim.

### Step 3 — Enumerate all branches (local + remote)

```
git branch -a
git branch -vv
```

Both outputs verbatim.

### Step 4 — Report the reflog for HEAD

```
git reflog HEAD -n 30
```

Full output verbatim. This surfaces the transition history that produced the current state.

### Step 5 — Confirm pin object still resolves

```
git cat-file -t 75b0f701
git rev-parse 75b0f701
```

Confirm readability without checking out.

### Step 6 — Working tree state

```
git status --short --branch
```

Surface any uncommitted, staged, or untracked state.

### Step 7 — Origin state check

```
git ls-remote origin refs/heads/hq/frago-12-b-12 refs/heads/hq/fr refs/heads/main refs/heads/hq/frago-12-b-13-diagnostic
```

Confirm what actually exists on origin. Include all four refs; note which resolve and which don't.

---

## RETURN FORMAT

Verbatim output from each step, no interpretation. Wrap each step's output in a fenced block labeled `### Step N output`. Byte-lift per #140 corollary.

Include at top of return:
- Timestamp of execution (local clock, ET)
- Executor identity: ET-1.W
- Confirmation that ZERO mutation occurred
- Confirmation that pin `75b0f701` remains readable

---

## RETURN PATH

**Primary:** origin-branch push to new branch `hq/frago-12-b-13-diagnostic`.

- Create the branch from the current unresolvable state without moving HEAD.
- If `git branch hq/frago-12-b-13-diagnostic` from current position is not possible due to the unresolvable ref, fall back to Method B below.

**Method B (fallback if primary blocked):** paste return inline in chat.

**Method C (fallback if push fails but branch creates):** report the local commit hash, HQ will pull via `gh api`.

---

## HARD PROHIBITIONS (zero-tolerance under this FRAGO)

- ❌ Do NOT run `git checkout <anything>`
- ❌ Do NOT run `git reset` (any mode)
- ❌ Do NOT run `git branch -d` or `git branch -D`
- ❌ Do NOT run `git update-ref` on HEAD or any live ref
- ❌ Do NOT commit anything
- ❌ Do NOT delete anything from `.git/`
- ❌ Do NOT edit `.git/HEAD` directly
- ❌ Do NOT run `git gc`, `git prune`, or `git repack`

If any of Steps 1-7 return an error, capture the error verbatim and continue to the next step. Do not attempt to fix.

---

## SUCCESS CRITERIA

- All seven steps executed
- Verbatim outputs returned
- Zero mutation confirmed
- Pin `75b0f701` readability confirmed
- Return delivered via one of the three defined paths

---

## POST-RETURN

HQ will:
1. File the return as substrate witness.
2. Surface the findings to CT-1.
3. Present ConOps terminal-state options (α/β/γ/δ per 10:38 EDT dispatch preamble) with substrate-informed recommendation.
4. Await CT-1 ratification of the terminal-state rule before any HEAD mutation.

---

**Dispatch class:** READ-ONLY diagnostic
**Ratification:** CT-1 GO 2026-07-01 10:39 EDT
**Doctrine compliance:** Substrate First, #138, #140 corollary, recon-first
**End of FRAGO 12.B.13.**
