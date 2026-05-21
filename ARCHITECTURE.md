# ClarityOS — Architectural Boundary

> Authoritative as of 2026-05-07. Supersedes any earlier instruction
> that suggested ClarityOS should load, simulate, or depend on
> external "skills".

---

## Core invariant

**ClarityOS is the orchestrator. The model is the compute layer.**

The OS provides every piece of context the model needs:

* user identity + cohort
* thread state (via `threads_vault`)
* vault state (via `memory_vault`)
* operator state (via `operator_state`)
* routing rules (via `model_router` + `intelligence_kernel`)
* project metadata

The model receives that context, returns text. Nothing else crosses
the boundary. The model is **stateless** with respect to ClarityOS;
the OS holds the state.

---

## Hard prohibitions (zero tolerance)

ClarityOS runtime code — backend (`*.py`), web (`web/src/`), phone
(`phone/app/`, `phone/lib/`), and desktop (`desktop/src/`,
`desktop/electron.js`, `desktop/preload.js`) — **must not**:

1. Load, parse, register, or look up "skill" manifests.
2. Reference Perplexity's skill system or any equivalent
   plugin-loading mechanism (Hugging Face skills, OpenAI skills,
   Anthropic skills, MCP skills as runtime dependencies, etc.).
3. Assume the presence of any external toolchain that injects
   reasoning modes into the model.
4. Implement a plugin architecture where third-party packages
   register reasoning capabilities.
5. Branch behaviour on whether a skill is "active" or "loaded".

The audit at the bottom of this document confirms the current code
satisfies all five.

---

## What "skills" means in ClarityOS conversations

When the founder or specs reference "Emotional Physics", "Clarity",
"Markov", "Physics", or "Galileo Meta", these are:

* **OS-level reasoning modes** — implemented (or to be implemented)
  inside the kernel as ordinary Python functions, prompt templates,
  or analysis passes.
* **Names for behavioural contracts** the model is expected to
  honour when the OS asks it to reason a certain way.
* **Documentation labels** that humans use to talk about how a
  problem should be approached.

They are **not**:

* Plugin packages.
* External manifests the OS loads at runtime.
* Capabilities gated behind a registry lookup.
* Model add-ons that need to be "installed".

If a future feature wants Markov-style state-machine reasoning, it
goes in the kernel as e.g. `intelligence_kernel.run_markov_analysis(
user, content)` — same shape as `summarize_thread` (v50) or
`run_thread_message` (v47). It does **not** load a manifest.

---

## What lives outside the boundary

The repo also contains **export artifacts** — material designed to
brief other LLM products (Perplexity, etc.) about how the founder's
reasoning works. These live under:

```
/skills_export/
```

Everything in there is **documentation**:

* `manifest.json` files describe behavioural contracts.
* `prompts/system_prompt.txt` files are starting points for other
  LLMs to adopt a reasoning mode.
* `schemas/` describe what input/output looks like.

ClarityOS code **never imports from `/skills_export/`** and never
reads those manifests at runtime. The directory is for humans and
for outside systems. Treat it like documentation; if you find any
ClarityOS Python or TypeScript file that touches it, that file is
broken.

---

## Why this rule exists

Three reasons, in priority order:

1. **Clarity of ownership.** The OS owns orchestration; the model
   owns compute. Mixing the two by smuggling reasoning logic into
   "skill" packages produces a system where it's unclear which
   layer is responsible when something misbehaves.
2. **No supply chain.** A plugin architecture means the OS depends
   on third-party packages that publish reasoning behaviour. That
   surface is impossible to audit and dangerous to ship.
3. **Model agnosticism.** ClarityOS already supports five model
   providers via `model_router` (v44) plus a local on-device
   runtime (v45). The router selects models per-task; it does
   **not** select skills. Skills would couple the OS to a
   particular vendor's plugin system, which is exactly what v44
   was designed to avoid.

---

## Audit (2026-05-07)

Performed before writing this document.

| Surface                                       | Hits for `\bskill\b` / `\bplugin\b` |
|-----------------------------------------------|-------------------------------------|
| Backend `*.py` (root)                          | 0                                   |
| `web/src/` (excluding `node_modules/`)         | 0                                   |
| `phone/app/` + `phone/lib/`                    | 0                                   |
| `desktop/src/`, `electron.js`, `preload.js`    | 0                                   |
| `tests/*.py`                                   | 0                                   |

Hits exist inside vendored libraries (`.venv/`, `node_modules/`,
`Archive/`, `Index_Records/`) — those are third-party packages, not
ClarityOS. They cannot leak into ClarityOS behaviour because no
ClarityOS module imports skill-related symbols from them.

This audit re-runs whenever the architectural boundary needs to be
re-verified:

```bash
grep -rlE "\bskill\b|\bplugin\b" *.py web/src phone/app phone/lib \
  desktop/src desktop/electron.js desktop/preload.js tests/*.py \
  2>/dev/null
# expected output: empty
```

---

## Pointers for future passes

* If the OS needs a new reasoning mode, add a kernel function (e.g.
  `intelligence_kernel.run_clarity(user, text)` returning a dict),
  wire it through `model_router` with a `TASK_DEFAULTS` entry, and
  expose it via an endpoint. Same pattern as v47's
  `run_thread_message` and v50's `summarize_thread`.
* If a future founder wants the bundles in `/skills_export/` to
  drive ClarityOS itself, **do not silently merge**. Surface the
  contradiction with this document; one of the two has to give and
  it's a project-level decision, not a coding decision.
* `kernel_view_for_user` is the single place where per-user runtime
  context is shaped. Anything that adds new "modes" should surface
  there alongside `preferred_model`, `last_model_used`, `vault_keys`,
  `thread_count`, etc.

---

## Kernel modules (v69)

A "kernel module" is a runtime Python module that sits alongside
`intelligence_kernel`, `threads_vault`, `memory_vault`, etc. and
exposes a deterministic surface to the rest of ClarityOS. Modules
are pure Python — they may make outbound LLM calls via `model_router`
but never load skill manifests or branch on skill presence.

* **`el_ins/`** (v69 / Units 74–75) — Reasoning-stability operator
  that scores text by EL/INS ratio. Pairs with the
  `/skills_export/el_ins/` external bundle: the kernel module reads
  the bundle's `system_prompt.md` as **plain text** (not as a Python
  import) and uses it to drive an LLM-primary analyzer with a pure
  Python deterministic fallback. This is the first kernel module to
  co-evolve with a skills_export bundle; the test
  `tests/test_el_ins_analyzer.py::TestSkillsBundleAlignment::test_no_skills_export_python_import`
  locks the no-import boundary against regression. Relationship to
  Emotional Physics / Langbridg / ELINS: EL/INS scores the stability
  of any text; the other systems consume the score to decide whether
  to stabilize, expand, or proceed normally.

---

## Version

* Architecture lock-in: 2026-05-07
* Backend version: `4.4`
* `BUILD_VERSION`: `20260507680000`
