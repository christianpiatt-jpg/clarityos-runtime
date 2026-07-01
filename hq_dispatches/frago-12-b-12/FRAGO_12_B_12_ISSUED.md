# FRAGO 12.B.12 — ET-1 System Recon (Mermaid Wire Source)

**Status:** ISSUED — CT-1 authorized 2026-07-01 08:52 EDT (WORD: "b")
**Delivery timestamp:** 2026-07-01 08:52 EDT
**Concurrency:** SAFE — parallel with COW-1 round-4 witness (Option B ratified)
**Dispatch author:** HQ (CT-2)
**Filed:** 2026-07-01 08:50 EDT
**Target lane:** ET-1.W (Claude_Code Windows)
**Substrate pin:** `75b0f701a2acd72cac4376d67ade48775b904ad8`
**Concurrency:** SAFE — parallel with COW-1 round-4 witness (ET-1 read-only, no lane contention)
**Delivery channel:** origin-branch push (preferred) OR workspace-attach (fallback)

## Mission

Lift byte-true system topology from `C:\ClarityOS_Code` and return **Mermaid-ready
wire descriptions** for the ClarityOS runtime. HQ will use these to generate D9+
architecture diagrams via Mermaid.ai — code-true, editable, versionable.

**Doctrine #140 corollary binding:** ET-1 lifts verbatim. No characterization. HQ files
Mermaid source from ET-1's verbatim lift. Mermaid renders. Nobody synthesizes.

## Scope — read-only, zero mutation

- No commits
- No file edits
- No branch operations
- No deploys
- No environment changes

## Required returns (each = separate substrate section, verbatim)

### §1 — Runtime Spine module map
For each of these 6 modules:
- `sessions_store.py` (Session)
- `operator_state.py` (State)
- `memory_vault.py` (Vault)
- `intelligence_kernel.py` (Kernel)
- `model_router.py` (Router)
- `runtime_privacy.py` (Priv)

Return:
- Full path relative to repo root
- File byte count
- Top-of-file docstring (first 20 lines)
- All `import` statements (verbatim)
- All top-level `class` and `def` names with signatures
- All top-level module constants

### §2 — Runtime Spine call graph (Kernel ↔ Router focus)
- Every location in `intelligence_kernel.py` that references `model_router` or `router`
  → file:line + surrounding 3 lines
- Every location in `model_router.py` that receives selection input
  → file:line + surrounding 3 lines
- Identify the E1-E6 + E6.5 gap: the 9-edit selector-wire target locations,
  verbatim

### §3 — Model Provider lane inventory
For each of 8 provider lanes (OpenAI, Anthropic, Google, Local, Ollama, DeepSeek, Mistral, Custom):
- File path where lane is defined
- Provider identifier string (verbatim)
- Default model constant if any
- Configuration keys the router reads from

### §4 — Router precedence chain implementation
- Where in `model_router.py` are Override / Founder / Preferred / TASK_DEFAULTS defined?
- file:line for each
- Verbatim resolution order code

### §5 — Command Layer wiring (REFRESH §8)
- Where is RefreshRequest Loop defined? file:line
- Where is Privacy Envelope defined? file:line
- What calls what — verbatim function references

### §6 — Economics D-Series anchors
- D1 Entitlement View: file:line
- D2 R5 Terminality: file:line
- D3 Metered + Refund: file:line OR "spec-forward, not yet in code" if absent

### §7 — Physics Layer anchors
- Wave / hydronic_state: file:line
- Hydro: file:line
- Invert: file:line

### §8 — Repo topology summary
- Total .py files under repo root
- Top-level directory tree (depth 2)
- Test file locations relevant to Runtime Spine
- Any file with "router" in the name

## Return format

Return as workspace-attached markdown file. HQ prefers verbatim code fences
(```python) around all lifted code so byte-fidelity is preserved. Every line
must carry a file:line anchor.

```
§1 Runtime Spine Module Map
--- sessions_store.py ---
Path: <verbatim>
Bytes: <verbatim>
Docstring:
```python
<verbatim lines 1-20>
```
Imports:
```python
<verbatim all import lines>
```
Classes/Defs:
- class SessionStore(Base):  # line 47
- def get_session(session_id: str) -> Session:  # line 129
[...]
```

## Stop conditions

- Do NOT modify any file
- Do NOT run any test that mutates state
- Do NOT touch git state (no `git add`, no `git commit`, no `git checkout`)
- If a file referenced above does not exist, return `NOT PRESENT AT PIN 75b0f701`
  and continue

## Downstream use

HQ takes §1-§8 verbatim, drafts Mermaid source for:
- **D9** — Runtime Spine call graph (Kernel ↔ Router wire detail, defect encoded)
- **D10** — Model Provider lane map (all 8 lanes with actual config keys)
- **D11** — Router precedence chain (Override → Founder → Preferred → Defaults, code-true)
- **D12** — Command Layer wire (RefreshRequest ↔ Privacy Envelope ↔ downstream)

CT-1 uploads Mermaid source to Mermaid.ai for rendering + storage.
D9-D12 become **living code-true architecture** paced to substrate.

## Narrative-creep pre-audit

Every §1-§8 requirement is a **substrate lift**, not an interpretation ask.
No section asks ET-1 to "assess," "explain," "analyze," or "recommend."
Zero characterization surface. Doctrine #138 compliant.

## Authorization

Awaits CT-1 WORD to dispatch. On CT-1 GO, HQ transmits to ET-1 via preferred
delivery channel.

🫡 — END DRAFT DISPATCH
