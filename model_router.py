"""
v44 — Multi-model router + kernel-level model selection.
v45 — Local provider warm-start + on-device inference dispatch.
v57 — Unit 38: route_model_request integration layer wraps select_model
      + route_request to bridge dispatcher engine vocab → model_router.

Centralises model-id resolution + provider dispatch so every kernel
``run_*`` can ask:

    model_id = model_router.select_model(user, task=...)
    result   = model_router.route_request(model_id, prompt)

The router is deterministic with respect to its inputs + the small
amount of stored state it consults (operator_state.preferred_model and
the founder-set global default). Provider calls are guarded by env
keys (``CLARITYOS_OPENAI_KEY``, ``CLARITYOS_ANTHROPIC_KEY``,
``CLARITYOS_GEMINI_KEY``, ``CLARITYOS_XAI_KEY``,
``CLARITYOS_LOCAL_MODEL_PATH``) — without keys the matching provider
returns a deterministic mock payload so the surrounding system can
exercise routing logic offline.

v45: when ``model_id == "local:llama3.1"`` and
``CLARITYOS_LOCAL_MODEL_PATH`` is set the local handler delegates to
``local_model_runtime.run_local_inference`` — load_local_model is called
once per process (warm-start) and the cached handle is reused. Without
the path the handler still returns the deterministic mock payload.

Public API:
    SUPPORTED_MODELS                                 # tuple of model_id strings
    TASK_DEFAULTS                                    # task → fallback model_id
    AUTO                                             # sentinel "auto"

    select_model(user, *, task, override=None)       -> model_id
    route_request(model_id, prompt, *,
                  temperature=0.2, max_tokens=4096)  -> dict

    get_model_status()                               -> dict
    get_founder_default_model()                      -> str | None
    set_founder_default_model(model_id)              -> str | None
    parse_provider(model_id)                         -> "openai"|"anthropic"|...|"local"
"""
from __future__ import annotations

import logging
import os
import time
import urllib.error
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Optional

import runtime_http_config
import runtime_privacy

logger = logging.getLogger("clarityos.model_router")

ROUTER_VERSION: str = "model_router.v80"

# v45 — model id that routes through the on-device runtime.
LOCAL_MODEL_ID: str = "local:llama3.1"

# ---------------------------------------------------------------------------
# Model catalogue
#
# v66 / Unit 71 — Replaced the flat ``SUPPORTED_MODELS`` constant with a
# structured per-provider registry. ``SUPPORTED_MODELS`` is still
# exported (as a derived flat tuple) so every existing consumer
# continues to work; new code can read ``MODEL_REGISTRY`` directly to
# know which models live under which provider. The ``auto`` sentinel
# is registry-independent (it's a routing instruction, not a wire
# model) and remains a top-level entry in ``SUPPORTED_MODELS``.
# ---------------------------------------------------------------------------
MODEL_REGISTRY: dict[str, tuple[str, ...]] = {
    "openai":    ("openai:gpt-5.4", "openai:gpt-5.4-mini"),
    "anthropic": ("anthropic:claude-haiku-4-5-20251001",),
    "google":    ("google:gemini-2.5-flash",),
    "xai":       ("xai:groq-llama",),
    "local":     ("local:llama3.1",),
    # v80 — Ollama as HTTP-localhost provider. Avoids the native Windows
    # build chain (MSVC/CMake/BLAS/wheels) that llama-cpp-python requires.
    # Activated by CLARITYOS_OLLAMA_URL; falls back to mock otherwise.
    "ollama":    ("ollama:llama3.1",),
    # v80.1 — DeepSeek V4 (OpenAI wire-format) + Mistral Large 3.
    "deepseek":  ("deepseek:deepseek-v4-flash", "deepseek:deepseek-v4-pro"),
    "mistral":   ("mistral:mistral-large-2512",),
}

# Derived flat tuple. ``auto`` is appended once (routing sentinel, not
# a wire model). Kept tuple-typed so ``model_id in SUPPORTED_MODELS``
# checks throughout the codebase continue to work.
SUPPORTED_MODELS: tuple = tuple(
    model_id
    for models in MODEL_REGISTRY.values()
    for model_id in models
) + ("auto",)

AUTO: str = "auto"

# Provider → first model_id that matches. Used to map a model_id back
# to a provider name when populating logs / status.
PROVIDER_PREFIXES: tuple = (
    ("openai:",    "openai"),
    ("anthropic:", "anthropic"),
    ("google:",    "gemini"),
    ("xai:",       "xai"),
    ("local:",     "local"),
    ("ollama:",    "ollama"),
    ("deepseek:",  "deepseek"),
    ("mistral:",   "mistral"),
)

# Task → default model. OpenAI keys are wired, so the reasoning + thread
# tasks route to gpt-5.4 and the fast `c` task to gpt-5.4-mini. The tasks
# still resolve to anthropic:claude-haiku-4-5-20251001; the earlier id 404'd on a
# configured, authenticating key, so claude-haiku-4-5-20251001 now loads (not key-absence).
TASK_DEFAULTS: dict[str, str] = {
    "c":        "openai:gpt-5.4-mini",      # fast comment / lexical work
    "G":        "openai:gpt-5.4",           # heavy reasoning + neighborhoods
    "ELINS":    "openai:gpt-5.4",           # deterministic pipeline
    "regional": "anthropic:claude-haiku-4-5-20251001",
    "forecast": "anthropic:claude-haiku-4-5-20251001",
    "macro":    "anthropic:claude-haiku-4-5-20251001",
    "entity":   "anthropic:claude-haiku-4-5-20251001",
    # v47 — threaded conversations. Pick the reasoning-heavy default;
    # users can override per-thread via preferred_model.
    "thread":   "openai:gpt-5.4",
    # v50 — per-thread summaries. Cheap call (1-2 sentence output),
    # but we still route through the deterministic-reasoning model
    # so the summary tone matches the assistant turn voice.
    "thread_summary": "anthropic:claude-haiku-4-5-20251001",
    # v52 — emotional_physics structural-not-sentimental analysis.
    # Multi-layered JSON contract; correctness + coherence matter
    # more than latency, so route to the deterministic-reasoning
    # default. No vendor pinning beyond the task default — users can
    # override via operator_state.preferred_model.
    "emotional_physics": "anthropic:claude-haiku-4-5-20251001",
    # v79 — ProblemSolver.REGRESSION_FIRST canonical task. The packet
    # parser (``analyze_packet``) doesn't itself make an LLM call —
    # it consumes packets the upstream caller emitted under the
    # bundle's system_prompt.md. The task default is the model the
    # bundle prompt was written for (Claude 3.7). When V80 lands a
    # ``/me/regression_first/packet`` endpoint that drives the model
    # from raw text, this default is what ``select_model`` returns.
    "regression_first": "openai:gpt-5.4",
    # v80.1 — /markov routed via select_model so founder/user model
    # preferences apply. v81 — default flipped ollama:llama3.1 →
    # anthropic:claude-haiku-4-5-20251001: CLARITYOS_ANTHROPIC_KEY is set on the
    # live revision (00092-tep) whereas CLARITYOS_OLLAMA_URL is unset, so
    # ollama returned a deterministic mock in prod. Anthropic yields a real
    # recast; callers can still override per-request via meta["model"].
    "markov":   "anthropic:claude-haiku-4-5-20251001",
}

# Provider → env var(s) that must be set for the provider to count as
# "configured". local provider keys on a path; everything else uses an
# API-key style.
_PROVIDER_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "openai":    ("CLARITYOS_OPENAI_KEY",),
    "anthropic": ("CLARITYOS_ANTHROPIC_KEY",),
    "gemini":    ("CLARITYOS_GEMINI_KEY",),
    "xai":       ("CLARITYOS_XAI_KEY",),
    "local":     ("CLARITYOS_LOCAL_MODEL_PATH",),
    # v80 — Ollama is "configured" when the URL is set. Suggested value
    # for local Ollama installs: "http://localhost:11434".
    "ollama":    ("CLARITYOS_OLLAMA_URL",),
    "deepseek":  ("CLARITYOS_DEEPSEEK_KEY",),
    "mistral":   ("CLARITYOS_MISTRAL_KEY",),
}

# Founder global override.
#
# PASS-4 V2 — The source of truth is the vault under
# ``founder_global.default_model``; the module-level slot below is a
# write-through process-local cache so the hot ``select_model`` path
# does not pay a vault read on every request. ``_founder_default_loaded``
# is the cache state: False means we have not yet consulted the vault in
# this process, True means the cache (None or a model_id) reflects what
# we last read or wrote. Tests reset both via ``_reset_for_tests``.
_FOUNDER_GLOBAL_USER_ID: str = "__founder_global__"
_FOUNDER_DEFAULT_KEY:    str = "founder_global.default_model"

_founder_default_model:  Optional[str] = None
_founder_default_loaded: bool = False


# ---------------------------------------------------------------------------
# Validation + provider parsing
# ---------------------------------------------------------------------------
def is_valid_model(model_id: Optional[str]) -> bool:
    return isinstance(model_id, str) and model_id in SUPPORTED_MODELS


# v51 — short aliases the project layer uses (e.g. ``"claude"`` in a
# project's ``default_model`` field). Keeps the project meta schema
# friendly while still resolving to a SUPPORTED_MODELS id.
_MODEL_ALIASES: dict[str, str] = {
    # Anthropic family
    "claude":         "anthropic:claude-haiku-4-5-20251001",
    "anthropic":      "anthropic:claude-haiku-4-5-20251001",
    "claude-3.7":     "anthropic:claude-haiku-4-5-20251001",
    # OpenAI family
    "openai":         "openai:gpt-5.4",
    "gpt":            "openai:gpt-5.4",
    "gpt-4":          "openai:gpt-5.4",
    "gpt-4o":         "openai:gpt-5.4",
    "gpt-4o-mini":    "openai:gpt-5.4-mini",
    # Google family
    "gemini":           "google:gemini-2.5-flash",
    "google":           "google:gemini-2.5-flash",
    "gemini-2.0-flash": "google:gemini-2.5-flash",
    # xAI / Groq
    "xai":            "xai:groq-llama",
    "grok":           "xai:groq-llama",
    "groq":           "xai:groq-llama",
    "groq-llama":     "xai:groq-llama",
    # Local on-device
    "local":          "local:llama3.1",
    "llama":          "local:llama3.1",
    "llama3.1":       "local:llama3.1",
    # v80 — Ollama localhost HTTP provider
    "ollama":         "ollama:llama3.1",
    "ollama-llama":   "ollama:llama3.1",
    "ollama-llama3.1":"ollama:llama3.1",
    # v80.1 — DeepSeek + Mistral aliases
    "deepseek":       "deepseek:deepseek-v4-flash",
    "deepseek-flash": "deepseek:deepseek-v4-flash",
    "deepseek-pro":   "deepseek:deepseek-v4-pro",
    "v4-flash":       "deepseek:deepseek-v4-flash",
    "v4-pro":         "deepseek:deepseek-v4-pro",
    "mistral":        "mistral:mistral-large-2512",
    "mistral-large":  "mistral:mistral-large-2512",
    "large":          "mistral:mistral-large-2512",
}


def resolve_model_alias(name: Optional[str]) -> Optional[str]:
    """Coerce a friendly model name into a SUPPORTED_MODELS id.

    Returns the canonical model_id when ``name`` is recognised (either
    already a supported id, or a known alias). Returns ``None`` when
    ``name`` is empty / None / unrecognised — the caller decides
    whether to ignore or raise.
    """
    if not isinstance(name, str):
        return None
    candidate = name.strip()
    if not candidate:
        return None
    if candidate in SUPPORTED_MODELS:
        return candidate
    # Aliases are case-insensitive for friendliness; canonical IDs are
    # case-sensitive (we already returned above).
    return _MODEL_ALIASES.get(candidate.lower())


def parse_provider(model_id: str) -> str:
    """Map a model_id to its provider tag. Raises on unknown id."""
    if not isinstance(model_id, str):
        raise ValueError("model_id must be a string")
    if model_id == AUTO:
        # ``auto`` has no provider; callers that hit this typically have
        # already resolved past it, but we surface it explicitly so log
        # lines look honest.
        return "auto"
    for prefix, name in PROVIDER_PREFIXES:
        if model_id.startswith(prefix):
            return name
    raise ValueError(f"unknown model_id {model_id!r}")


def _provider_configured(provider: str) -> bool:
    keys = _PROVIDER_ENV_KEYS.get(provider) or ()
    if not keys:
        return False
    for k in keys:
        if (os.environ.get(k) or "").strip():
            return True
    return False


# ---------------------------------------------------------------------------
# Founder default model — vault-backed, process-cached
#
# PASS-4 V2 — Previously the founder default lived only in
# ``_founder_default_model`` as a module-level variable, which meant each
# process / instance held its own copy and the value silently drifted
# across Cloud Run replicas / pods. The mitigation persists the value to
# the per-user vault under a synthetic system user_id
# (``__founder_global__``) and key ``founder_global.default_model``, then
# lazy-loads it on first read in any process. Writes still flow through
# ``set_founder_default_model`` exactly as before — they are now
# additionally written to the vault so any subsequent process sees the
# same value on first call. The selection precedence in ``select_model``
# is unchanged.
# ---------------------------------------------------------------------------
def _load_founder_default_from_vault() -> Optional[str]:
    """Read ``founder_global.default_model`` from the vault.

    Returns the stored model_id when present and valid, otherwise None.
    Defensive against vault read errors (corrupt entry, missing secret
    in a partially-configured environment): a warning is logged and
    None is returned so ``select_model`` falls through to the user-pref
    / task-default chain.
    """
    try:
        import memory_vault
        stored = memory_vault.vault_get(
            _FOUNDER_GLOBAL_USER_ID, _FOUNDER_DEFAULT_KEY, default=None,
        )
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning(
            "model_router founder default vault read failed → None; err=%s", e,
        )
        return None
    if isinstance(stored, str) and stored and is_valid_model(stored):
        return stored
    return None


def get_founder_default_model() -> Optional[str]:
    """Return the founder global default model.

    On the first call in a process, the value is read from the vault
    and cached. Subsequent calls return the cached value. ``None`` is
    cached just the same as a model_id so we do not re-hit the vault
    when no founder default has ever been set.
    """
    global _founder_default_model, _founder_default_loaded
    if not _founder_default_loaded:
        _founder_default_model = _load_founder_default_from_vault()
        _founder_default_loaded = True
    return _founder_default_model


def set_founder_default_model(model_id: Optional[str]) -> Optional[str]:
    global _founder_default_model, _founder_default_loaded
    if model_id is None or model_id == "":
        try:
            import memory_vault
            memory_vault.vault_delete(
                _FOUNDER_GLOBAL_USER_ID, _FOUNDER_DEFAULT_KEY,
            )
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning(
                "model_router founder default vault delete failed; err=%s", e,
            )
        _founder_default_model = None
        _founder_default_loaded = True
        return None
    if not is_valid_model(model_id):
        raise ValueError(f"unknown model_id {model_id!r}")
    try:
        import memory_vault
        memory_vault.vault_put(
            _FOUNDER_GLOBAL_USER_ID, _FOUNDER_DEFAULT_KEY, model_id,
        )
    except Exception as e:  # pragma: no cover (defensive)
        # Persistence failure is logged but does not block the in-process
        # update — the founder console still reflects the override for
        # this request; the next process restart will lose it.
        logger.warning(
            "model_router founder default vault write failed; err=%s", e,
        )
    _founder_default_model = model_id
    _founder_default_loaded = True
    logger.info("model_router founder default → %s", model_id)
    return _founder_default_model


# ---------------------------------------------------------------------------
# select_model
# ---------------------------------------------------------------------------
def _normalise_task(task: Optional[str]) -> str:
    if not task:
        return "ELINS"
    t = str(task).strip()
    # Map kernel run kinds → task buckets.
    aliases = {
        "run_c": "c",
        "run_G": "G",
        "run_ELINS": "ELINS",
        "run_regional_ELINS": "regional",
        "run_macro_ELINS": "macro",
    }
    return aliases.get(t, t)


def select_model(
    user: Optional[str],
    *,
    task: str,
    override: Optional[str] = None,
) -> str:
    """Resolve the model_id for a kernel run.

    Precedence (deterministic):
        1. Explicit ``override`` (if a valid model_id and != "auto").
        2. Founder global default (set via /founder/models/override).
        3. ``operator_state.preferred_model`` (if set + valid + != "auto").
        4. Task-based fallback (TASK_DEFAULTS).
    """
    # 1. Explicit override.
    if isinstance(override, str) and override and override != AUTO:
        if not is_valid_model(override):
            raise ValueError(f"unknown override model_id {override!r}")
        return override

    # 2. Founder global default.
    fo = get_founder_default_model()
    if fo and fo != AUTO and is_valid_model(fo):
        return fo

    # 3. User preferred_model.
    if user:
        try:
            import operator_state
            state = operator_state.get_operator_state(user) or {}
            pref = state.get("preferred_model")
            if isinstance(pref, str) and pref and pref != AUTO and is_valid_model(pref):
                return pref
        except Exception:  # pragma: no cover (defensive)
            pass

    # 4. Task default.
    bucket = _normalise_task(task)
    return TASK_DEFAULTS.get(bucket, TASK_DEFAULTS["ELINS"])


# ---------------------------------------------------------------------------
# route_request — provider dispatch + mock fallback
# ---------------------------------------------------------------------------
def route_request(
    model_id: str,
    prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> dict:
    """Send a prompt to the chosen provider. Returns a normalised dict::

        {"ok": True, "model_id": str, "provider": str,
         "text": str, "mock": bool, "ts": float}

    Real provider calls are gated behind env keys; without keys we
    return a deterministic mock payload so the surrounding kernel can
    exercise routing without hitting the network.
    """
    if not is_valid_model(model_id):
        raise ValueError(f"unknown model_id {model_id!r}")
    if model_id == AUTO:
        # Caller should have resolved before reaching us; default safe.
        model_id = TASK_DEFAULTS["ELINS"]
    provider = parse_provider(model_id)
    if not isinstance(prompt, str):
        prompt = str(prompt or "")

    handler = _PROVIDER_HANDLERS.get(provider)
    started = time.time()
    if handler is None:
        return _mock_result(model_id, provider, prompt, started)
    try:
        return handler(model_id, prompt, temperature=temperature, max_tokens=max_tokens)
    except Exception as e:  # pragma: no cover (real-network path)
        logger.warning(
            "model_router provider %s call failed → mock; err=%s",
            provider, e,
        )
        return _mock_result(model_id, provider, prompt, started, error=str(e))


def _mock_result(
    model_id: str,
    provider: str,
    prompt: str,
    started: float,
    *,
    error: Optional[str] = None,
) -> dict:
    """Deterministic mock — same prompt → same text. We don't echo the
    full prompt to keep logs free of operator content; instead we
    surface a hash-lite preview that callers can correlate with.

    PASS-4 FIX-P5 — the preview is now produced by
    ``runtime_privacy.prompt_preview`` so every place that emits a
    redacted prompt fragment (this mock path, the dispatcher's
    ``route_model_request`` preview, future log lines) shares the
    same cap and None-safety semantics."""
    preview = runtime_privacy.prompt_preview(prompt)
    out = {
        "ok": True,
        "model_id": model_id,
        "provider": provider,
        "text": f"[mock {model_id}] {preview}".rstrip(),
        "mock": True,
        "ts": started,
    }
    if error:
        out["fallback_error"] = error[:200]
    return out


# ---------------------------------------------------------------------------
# Provider handlers
# ---------------------------------------------------------------------------
# v64 / Unit 65 — Real HTTP implementations using stdlib urllib so no
# new dependency lands. Minimal feature set: single non-streaming
# request, basic-auth-style headers per provider, response-text
# extraction. Any exception (timeout, auth failure, parse error)
# falls back to ``_mock_result`` so callers always get the normalised
# router contract back. The fallback path stamps ``fallback_error``
# on the result for the v65 history-entry ``provider_error`` field.

# Network timeout used by `_http_post_json` for any call that does not
# wrap itself in a `_request_timeout(...)` context. Sourced from
# ``runtime_http_config`` so production code, tests, and future tuning
# all consult one place.
#
# PASS-4 FIX-H6 — Previously a plain module-level mutable float, which
# was racy under any concurrency (two coroutines / threads calling
# ``_request_timeout`` would clobber each other's prior value, and a
# health-check probe could leak its 3-second timeout into a mid-flight
# call-path request). The effective value now lives in a ContextVar so
# overrides scope to the current asyncio task / thread; concurrent
# requests in other contexts continue to observe the prior effective
# timeout. The legacy ``_PROVIDER_HTTP_TIMEOUT`` read API is preserved
# via the module-level ``__getattr__`` below — external callers and
# tests that read ``mr._PROVIDER_HTTP_TIMEOUT`` keep working unchanged.
_PROVIDER_HTTP_TIMEOUT_DEFAULT: float = runtime_http_config.DEFAULT_CALL_TIMEOUT

_PROVIDER_HTTP_TIMEOUT_VAR: ContextVar[float] = ContextVar(
    "PROVIDER_HTTP_TIMEOUT",
    default=_PROVIDER_HTTP_TIMEOUT_DEFAULT,
)


def __getattr__(name: str):
    """Module-level ``__getattr__`` (PEP 562) — preserves the pre-FIX-H6
    read API for ``_PROVIDER_HTTP_TIMEOUT``.

    External code and the runtime_http_config test suite read
    ``model_router._PROVIDER_HTTP_TIMEOUT`` expecting a float. We
    resolve it dynamically from the ContextVar so callers observe the
    current context's effective timeout (per-task / per-thread) without
    any code change at their side. The module no longer binds the name
    in its globals, which is what triggers this dispatch.
    """
    if name == "_PROVIDER_HTTP_TIMEOUT":
        return _PROVIDER_HTTP_TIMEOUT_VAR.get()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@contextmanager
def _request_timeout(seconds: float):
    """Temporarily override the effective provider HTTP timeout for the
    body of the block.

    v66 / Unit 71 — Used by the per-provider call paths and by the
    health-check helper so each request applies its own timeout
    without having to plumb a new kwarg through ``_http_post_json``
    (which would break the test mocks scattered across the suite).

    PASS-4 FIX-H6 — Now concurrency-safe via ``contextvars``. The
    override is scoped to the current asyncio task / thread, and LIFO
    restoration is preserved through ``ContextVar.reset``. Concurrent
    requests in other contexts continue to see the prior effective
    timeout, never the mid-flight one set here.
    """
    token = _PROVIDER_HTTP_TIMEOUT_VAR.set(float(seconds))
    try:
        yield
    finally:
        _PROVIDER_HTTP_TIMEOUT_VAR.reset(token)


def _http_post_json(url: str, *, headers: dict, body: dict) -> dict:
    """Single-shot JSON POST over stdlib urllib.

    Raises on transport/parse failure; the provider handlers catch
    and downgrade to mock. Kept module-level (and signature locked)
    so tests can monkey-patch it at one site rather than per-provider.
    Per-call timeout is read from ``_PROVIDER_HTTP_TIMEOUT_VAR`` (the
    ContextVar that backs ``_PROVIDER_HTTP_TIMEOUT``), which callers
    may temporarily override via ``_request_timeout(...)``.
    """
    import json as _json
    import urllib.request as _urlreq
    data = _json.dumps(body).encode("utf-8")
    req = _urlreq.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    with _urlreq.urlopen(
        req, timeout=_PROVIDER_HTTP_TIMEOUT_VAR.get(),
    ) as resp:
        raw = resp.read()
    decoded = _json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("provider returned non-object JSON")
    return decoded


def _call_openai(model_id: str, prompt: str, *, temperature: float, max_tokens: int) -> dict:
    started = time.time()
    if not _provider_configured("openai"):
        return _mock_result(model_id, "openai", prompt, started)
    key = (os.environ.get("CLARITYOS_OPENAI_KEY") or "").strip()
    # model_id is "openai:gpt-5.4"; strip the prefix for the wire model.
    wire_model = model_id.split(":", 1)[1] if ":" in model_id else model_id
    try:
        body = {
            "model": wire_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        with _request_timeout(runtime_http_config.get_call_timeout("openai")):
            out = _http_post_json(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                },
                body=body,
            )
        # Chat completions shape: {choices: [{message: {content: str}}, ...]}
        text = out.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(text, str):
            raise ValueError("openai response missing choices[0].message.content")
        return {
            "ok": True, "model_id": model_id, "provider": "openai",
            "text": text, "mock": False, "ts": started,
        }
    except Exception as e:  # pragma: no cover (real-network path)
        if isinstance(e, urllib.error.HTTPError):
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = "<body unreadable>"
            logger.warning("openai http error status=%s body=%s", e.code, body)
        else:
            logger.warning("openai non-http error: %s", str(e))
        return _mock_result(model_id, "openai", prompt, started, error=str(e))


def _call_anthropic(model_id: str, prompt: str, *, temperature: float, max_tokens: int) -> dict:
    started = time.time()
    if not _provider_configured("anthropic"):
        return _mock_result(model_id, "anthropic", prompt, started)
    key = (os.environ.get("CLARITYOS_ANTHROPIC_KEY") or "").strip()
    wire_model = model_id.split(":", 1)[1] if ":" in model_id else model_id
    try:
        body = {
            "model": wire_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        with _request_timeout(runtime_http_config.get_call_timeout("anthropic")):
            out = _http_post_json(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type":      "application/json",
                },
                body=body,
            )
        # Messages shape: {content: [{type: "text", text: str}, ...]}
        blocks = out.get("content") or []
        text_parts = [
            b.get("text", "") for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        text = "".join(text_parts)
        if not text:
            raise ValueError("anthropic response had no text blocks")
        return {
            "ok": True, "model_id": model_id, "provider": "anthropic",
            "text": text, "mock": False, "ts": started,
        }
    except Exception as e:  # pragma: no cover
        if isinstance(e, urllib.error.HTTPError):
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = "<body unreadable>"
            logger.warning("anthropic http error status=%s body=%s", e.code, body)
        else:
            logger.warning("anthropic non-http error: %s", str(e))
        return _mock_result(model_id, "anthropic", prompt, started, error=str(e))


def _call_gemini(model_id: str, prompt: str, *, temperature: float, max_tokens: int) -> dict:
    started = time.time()
    if not _provider_configured("gemini"):
        return _mock_result(model_id, "gemini", prompt, started)
    key = (os.environ.get("CLARITYOS_GEMINI_KEY") or "").strip()
    # model_id is "google:gemini-2.5-flash"; strip prefix for wire.
    wire_model = model_id.split(":", 1)[1] if ":" in model_id else model_id
    try:
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        with _request_timeout(runtime_http_config.get_call_timeout("gemini")):
            out = _http_post_json(
                f"https://generativelanguage.googleapis.com/v1beta/models/{wire_model}:generateContent?key={key}",
                headers={"Content-Type": "application/json"},
                body=body,
            )
        # Gemini shape: {candidates: [{content: {parts: [{text: str}, ...]}}, ...]}
        candidates = out.get("candidates") or []
        if not candidates:
            raise ValueError("gemini response had no candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        if not text:
            raise ValueError("gemini response had no text parts")
        return {
            "ok": True, "model_id": model_id, "provider": "gemini",
            "text": text, "mock": False, "ts": started,
        }
    except Exception as e:  # pragma: no cover
        if isinstance(e, urllib.error.HTTPError):
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = "<body unreadable>"
            logger.warning("gemini http error status=%s body=%s", e.code, body)
        else:
            logger.warning("gemini non-http error: %s", str(e))
        return _mock_result(model_id, "gemini", prompt, started, error=str(e))


def _call_xai(model_id: str, prompt: str, *, temperature: float, max_tokens: int) -> dict:
    # xAI / Groq still mock — Christian's v65 spec only listed Anthropic
    # + OpenAI + Gemini for the real-call wiring. xAI handler kept at
    # mock so v44/v45 test expectations are preserved.
    if not _provider_configured("xai"):
        return _mock_result(model_id, "xai", prompt, time.time())
    return _mock_result(model_id, "xai", prompt, time.time())


def _call_local(model_id: str, prompt: str, *, temperature: float, max_tokens: int) -> dict:
    """v45 — delegate to local_model_runtime for on-device inference.

    When ``CLARITYOS_LOCAL_MODEL_PATH`` is unset (or local_model_runtime
    is unavailable for any reason) we fall back to the deterministic
    router mock so the rest of the system is indifferent to whether a
    real model is loaded. The runtime itself also degrades to its own
    deterministic mock when the path is set but the file/backend isn't
    actually there — both paths converge on a ``mock=True`` payload.
    """
    started = time.time()
    if not _provider_configured("local"):
        return _mock_result(model_id, "local", prompt, started)

    # Lazy import keeps the model_router test surface (and the rest of
    # the kernel) decoupled from the runtime when local is unused.
    try:
        import local_model_runtime
    except Exception as e:  # pragma: no cover (import failure path)
        logger.warning("local_model_runtime import failed err=%s", e)
        return _mock_result(model_id, "local", prompt, started, error=str(e))

    handle = _warm_local_handle(local_model_runtime)
    if handle is None:
        return _mock_result(model_id, "local", prompt, started)
    try:
        out = local_model_runtime.run_local_inference(
            handle, prompt,
            temperature=temperature, max_tokens=max_tokens,
        )
    except Exception as e:  # pragma: no cover (runtime returns dict, doesn't raise)
        logger.warning("local_model_runtime.run_local_inference failed err=%s", e)
        return _mock_result(model_id, "local", prompt, started, error=str(e))

    # Normalise into the router contract (text/model_id/provider/mock/ts).
    return {
        "ok": bool(out.get("ok", True)),
        "model_id": model_id,
        "provider": "local",
        "text": str(out.get("text") or ""),
        "mock": bool(out.get("mock", True)),
        "ts": float(out.get("ts") or started),
        "backend": out.get("backend"),
        "duration_ms": out.get("duration_ms"),
        "tokens_estimated": out.get("tokens_estimated"),
        "model_path": out.get("model_path"),
        **({"fallback_error": out["fallback_error"]}
           if out.get("fallback_error") else {}),
    }


# v45 — module-level cached handle. ``load_local_model`` itself caches
# per-path inside the runtime; this guard avoids the dictionary lookup
# on every router call.
_LOCAL_HANDLE_CACHE: Optional[Any] = None
_LOCAL_HANDLE_PATH: Optional[str] = None


def _warm_local_handle(runtime_module: Any) -> Optional[Any]:
    """Return the cached local handle, loading it on first use. Called
    from ``_call_local``. Returns None when the module can't produce a
    handle (path missing, etc.) — caller falls back to mock."""
    global _LOCAL_HANDLE_CACHE, _LOCAL_HANDLE_PATH
    path = runtime_module.configured_path()
    if not path:
        # Path was unset between call to _provider_configured and now;
        # drop any stale handle we'd cached.
        _LOCAL_HANDLE_CACHE = None
        _LOCAL_HANDLE_PATH = None
        return None
    if _LOCAL_HANDLE_CACHE is not None and _LOCAL_HANDLE_PATH == path:
        return _LOCAL_HANDLE_CACHE
    try:
        handle = runtime_module.load_local_model(path)
    except Exception as e:  # pragma: no cover (load failure path)
        logger.warning("local_model_runtime.load_local_model failed err=%s", e)
        return None
    _LOCAL_HANDLE_CACHE = handle
    _LOCAL_HANDLE_PATH = path
    return handle


def get_local_runtime_status() -> dict:
    """v45 — proxy ``local_model_runtime.get_runtime_status`` so callers
    that already import the router don't also need to import the
    runtime. Returns a stable dict even when the runtime isn't
    importable (defensive — should never fail in normal deploys)."""
    try:
        import local_model_runtime
    except Exception as e:  # pragma: no cover
        return {
            "configured": _provider_configured("local"),
            "path": (os.environ.get("CLARITYOS_LOCAL_MODEL_PATH") or "").strip() or None,
            "loaded": False,
            "backend": None,
            "mock": True,
            "memory_footprint_mb": 0.0,
            "inference_count": 0,
            "loaded_at": None,
            "last_error": f"runtime import failed: {e}",
        }
    return local_model_runtime.get_runtime_status()


def _call_ollama(model_id: str, prompt: str, *, temperature: float, max_tokens: int) -> dict:
    """v80 — Ollama HTTP provider. POSTs to ``{CLARITYOS_OLLAMA_URL}/api/generate``
    on the local Ollama daemon (default Ollama install listens on
    ``http://localhost:11434``). No API key — Ollama is local.

    Activated by ``CLARITYOS_OLLAMA_URL``. When unset, returns the
    deterministic mock so the surrounding system is indifferent. When
    set but the daemon is unreachable (not running, wrong port,
    firewall), the HTTP exception is caught and we still fall back to
    mock with ``fallback_error`` stamped for diagnostics. This mirrors
    the OpenAI / Anthropic / Gemini handler pattern.

    Wire model is the suffix after ``ollama:`` — ``"ollama:llama3.1"``
    posts with ``"model": "llama3.1"``, so any model pulled via
    ``ollama pull <name>`` is reachable by registering it as
    ``"ollama:<name>"`` in MODEL_REGISTRY.
    """
    started = time.time()
    if not _provider_configured("ollama"):
        return _mock_result(model_id, "ollama", prompt, started)
    base_url = (os.environ.get("CLARITYOS_OLLAMA_URL") or "").strip().rstrip("/")
    wire_model = model_id.split(":", 1)[1] if ":" in model_id else model_id
    try:
        body = {
            "model": wire_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        # Local Ollama can take a few seconds warm, much longer cold
        # (first request loads the model). 120s ceiling matches the
        # cold-load worst case for ~8B models on consumer hardware.
        # If runtime_http_config gains an "ollama" entry later, switch
        # to runtime_http_config.get_call_timeout("ollama").
        with _request_timeout(120.0):
            out = _http_post_json(
                f"{base_url}/api/generate",
                headers={"Content-Type": "application/json"},
                body=body,
            )
        # Ollama generate shape (stream=False):
        # {"model": str, "response": str, "done": bool, ...}
        text = out.get("response")
        if not isinstance(text, str):
            raise ValueError("ollama response missing 'response' field")
        return {
            "ok": True, "model_id": model_id, "provider": "ollama",
            "text": text, "mock": False, "ts": started,
        }
    except Exception as e:  # pragma: no cover (real-network path)
        logger.warning("ollama call failed → mock; err=%s", e)
        return _mock_result(model_id, "ollama", prompt, started, error=str(e))


def _call_deepseek(model_id: str, prompt: str, *, temperature: float, max_tokens: int) -> dict:
    """v80.1 — DeepSeek V4 provider (OpenAI wire-format). POSTs to
    ``api.deepseek.com/v1/chat/completions``. Activated by
    ``CLARITYOS_DEEPSEEK_KEY``; mock-on-unset mirrors the other handlers."""
    started = time.time()
    if not _provider_configured("deepseek"):
        return _mock_result(model_id, "deepseek", prompt, started)
    key = (os.environ.get("CLARITYOS_DEEPSEEK_KEY") or "").strip()
    wire_model = model_id.split(":", 1)[1] if ":" in model_id else model_id
    try:
        body = {
            "model": wire_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with _request_timeout(runtime_http_config.get_call_timeout("deepseek")):
            out = _http_post_json(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                },
                body=body,
            )
        text = out.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(text, str):
            raise ValueError("deepseek response missing choices[0].message.content")
        return {
            "ok": True, "model_id": model_id, "provider": "deepseek",
            "text": text, "mock": False, "ts": started,
        }
    except Exception as e:  # pragma: no cover (real-network path)
        if isinstance(e, urllib.error.HTTPError):
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = "<body unreadable>"
            logger.warning("deepseek http error status=%s body=%s", e.code, body)
        else:
            logger.warning("deepseek non-http error: %s", str(e))
        return _mock_result(model_id, "deepseek", prompt, started, error=str(e))


def _call_mistral(model_id: str, prompt: str, *, temperature: float, max_tokens: int) -> dict:
    """v80.1 — Mistral Large 3 provider (OpenAI wire-format). POSTs to
    ``api.mistral.ai/v1/chat/completions``. Activated by
    ``CLARITYOS_MISTRAL_KEY``; mock-on-unset mirrors the other handlers."""
    started = time.time()
    if not _provider_configured("mistral"):
        return _mock_result(model_id, "mistral", prompt, started)
    key = (os.environ.get("CLARITYOS_MISTRAL_KEY") or "").strip()
    wire_model = model_id.split(":", 1)[1] if ":" in model_id else model_id
    try:
        body = {
            "model": wire_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with _request_timeout(runtime_http_config.get_call_timeout("mistral")):
            out = _http_post_json(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                },
                body=body,
            )
        text = out.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(text, str):
            raise ValueError("mistral response missing choices[0].message.content")
        return {
            "ok": True, "model_id": model_id, "provider": "mistral",
            "text": text, "mock": False, "ts": started,
        }
    except Exception as e:  # pragma: no cover (real-network path)
        if isinstance(e, urllib.error.HTTPError):
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = "<body unreadable>"
            logger.warning("mistral http error status=%s body=%s", e.code, body)
        else:
            logger.warning("mistral non-http error: %s", str(e))
        return _mock_result(model_id, "mistral", prompt, started, error=str(e))


_PROVIDER_HANDLERS: dict[str, Any] = {
    "openai":    _call_openai,
    "anthropic": _call_anthropic,
    "gemini":    _call_gemini,
    "xai":       _call_xai,
    "local":     _call_local,
    "ollama":    _call_ollama,
    "deepseek":  _call_deepseek,
    "mistral":   _call_mistral,
}


# ---------------------------------------------------------------------------
# get_model_status — surfaced via /founder/models/status + kernel_status
# ---------------------------------------------------------------------------
def get_model_status() -> dict:
    """Per-provider configuration snapshot for the founder console.

    v45: ``local`` carries an extra ``path`` field (the configured
    ``CLARITYOS_LOCAL_MODEL_PATH`` or ``None``) so the founder UI can
    display where the on-device model would load from without a second
    round-trip to ``get_local_runtime_status``.
    """
    out: dict[str, dict] = {}
    for provider in ("openai", "anthropic", "gemini", "xai", "local"):
        out[provider] = {"configured": _provider_configured(provider)}
    local_path = (os.environ.get("CLARITYOS_LOCAL_MODEL_PATH") or "").strip()
    out["local"]["path"] = local_path or None
    return out


def get_router_status() -> dict:
    """Bundle the provider snapshot + supported models + founder default
    so /founder/intelligence/kernel/status can embed it in one call.

    v45: includes a ``local_runtime`` block so the founder console can
    show the on-device model's loaded/unloaded state, footprint, and
    inference count alongside the per-provider config flags.
    """
    return {
        "version": ROUTER_VERSION,
        "supported_models": list(SUPPORTED_MODELS),
        "task_defaults": dict(TASK_DEFAULTS),
        "founder_default_model": get_founder_default_model(),
        "providers": get_model_status(),
        "local_runtime": get_local_runtime_status(),
    }


# ---------------------------------------------------------------------------
# v57 / Unit 38 — Model Router Integration
#
# Additive integration layer that bridges runtime_dispatcher's logical
# engine vocabulary ({copilot, claude, gemini, grok, local}) to the
# existing v44/v45 router surface (select_model + route_request).
#
# This wraps; it does NOT replace. select_model, route_request,
# TASK_DEFAULTS, SUPPORTED_MODELS, _PROVIDER_HANDLERS, and
# intelligence_kernel._resolve_model are all left untouched. Adding
# Unit 38 to the router preserves a single point of model dispatch
# instead of splitting the surface across two modules.
# ---------------------------------------------------------------------------

# Hard-pin: engines where the OS must use a specific model regardless
# of user preferred_model / founder default. Diagnostic intents (the
# only path that maps to "local" today) are an OS policy — they stay
# on-device.
_ENGINE_HARD_PIN: dict[str, str] = {
    "local": LOCAL_MODEL_ID,
}

# Soft-mapped: engines that resolve through select_model so user
# preferred_model + founder default + override all still apply. The
# task bucket determines the TASK_DEFAULTS fallback when no override
# wins.
_ENGINE_TO_TASK: dict[str, str] = {
    "claude":  "G",      # plan / reasoning
    "copilot": "c",      # query / fast lexical
    "gemini":  "ELINS",  # action / deterministic pipeline
    "grok":    "c",      # alias for fast lane
}

# Full vocabulary — the union of both maps. Used for validation.
_VALID_ENGINES: tuple = tuple(
    sorted(set(_ENGINE_HARD_PIN) | set(_ENGINE_TO_TASK))
)


def _shape_prompt_from_intent(operator_intent: dict) -> str:
    """Compress an operator intent into a model-facing prompt.

    Deterministic, length-capped, no raw payload text passthrough. The
    dispatcher (Unit 36) has already validated structure; we just emit
    a structured summary so the model can see what kind of operator
    step is being evaluated. Real provider calls today still return
    mock payloads — this prompt becomes load-bearing once live
    providers replace the mock handlers."""
    if not isinstance(operator_intent, dict):
        operator_intent = {}
    intent_type = str(operator_intent.get("intent_type") or "unknown")
    session_id = str(operator_intent.get("session_id") or "")
    operator_id = str(operator_intent.get("operator_id") or "")
    payload = operator_intent.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    runtime_mode = str(payload.get("runtime_mode") or "normal")
    override = payload.get("override") or {}
    if not isinstance(override, dict):
        override = {}
    override_decision = str(override.get("override_decision") or "-")
    elins_inputs = payload.get("elins_inputs") or {}
    n_keys = len(elins_inputs) if isinstance(elins_inputs, dict) else 0
    return (
        f"[ClarityOS operator step] "
        f"intent={intent_type} session={session_id[:8]} "
        f"operator={operator_id[:8]} runtime_mode={runtime_mode} "
        f"override={override_decision} elins_inputs_keys={n_keys}"
    )


def _resolve_model_id_for_engine(engine: str, user) -> tuple[str, str]:
    """Map dispatcher engine → (model_id, task_label).

    For hard-pinned engines (currently just ``local``) the model_id is
    forced — user preference does not apply because this is an OS
    policy. For soft-mapped engines we delegate to select_model so the
    full preference chain (override > founder default >
    operator_state.preferred_model > task default) still works.
    """
    if engine in _ENGINE_HARD_PIN:
        return _ENGINE_HARD_PIN[engine], "(pinned)"
    if engine in _ENGINE_TO_TASK:
        task = _ENGINE_TO_TASK[engine]
        return select_model(user, task=task), task
    raise ValueError(f"unknown engine {engine!r}")


def route_model_request(operator_intent: dict, model_route: dict) -> dict:
    """v57 / Unit 38 — bridge runtime_dispatcher's ``{engine, reason}``
    to the existing v44/v45 router.

    Resolves the dispatcher's logical engine to a concrete model_id
    (hard-pin for ``local``, ``select_model`` otherwise), shapes a
    deterministic prompt from the operator intent, calls
    ``route_request``, and returns a normalised dispatch result.

    Args:
        operator_intent: locked-shape intent (per Unit 35 contract).
        model_route:     ``{engine, reason}`` emitted by Unit 36.

    Returns:
        ::

            {
              "engine":  str,            # echo of the dispatcher's choice
              "request": {
                "model_id":       str,
                "task":           str,   # task bucket or "(pinned)"
                "prompt_preview": str,   # first 60 chars of the shaped prompt
              },
              "response": <raw route_request output>,
              "metadata": {
                "provider": str,
                "mock":     bool,
                "ts":       float,
              },
            }

    Raises:
        ValueError on a malformed model_route or unknown engine.
    """
    if not isinstance(operator_intent, dict):
        raise ValueError(
            f"operator_intent must be a dict, "
            f"got {type(operator_intent).__name__}"
        )
    if not isinstance(model_route, dict):
        raise ValueError(
            f"model_route must be a dict, got {type(model_route).__name__}"
        )
    engine = model_route.get("engine")
    if not isinstance(engine, str) or not engine:
        raise ValueError(
            f"model_route['engine'] must be a non-empty string, "
            f"got {engine!r}"
        )
    if engine not in _VALID_ENGINES:
        raise ValueError(
            f"model_route['engine'] must be one of {_VALID_ENGINES}, "
            f"got {engine!r}"
        )

    user = operator_intent.get("operator_id")
    if user is not None and not isinstance(user, str):
        user = None  # defensive — select_model only consults strings

    # v64 / Unit 65 — vault-stored preferred_model_id wins over the
    # engine-based resolution when present. This is the integration
    # point for ``runtime_providers.get_operator_model`` — session_loop
    # reads the operator's vault, resolves a (provider, model), maps
    # to a model_id via ``runtime_providers.model_id_for``, and
    # injects under ``payload.preferred_model_id``. Additive optional
    # field; absent → falls through to existing engine resolution.
    preferred_model_id: Optional[str] = None
    payload = operator_intent.get("payload")
    if isinstance(payload, dict):
        candidate = payload.get("preferred_model_id")
        if (
            isinstance(candidate, str)
            and candidate
            and is_valid_model(candidate)
        ):
            preferred_model_id = candidate

    if preferred_model_id is not None:
        model_id = preferred_model_id
        task = "(vault-preferred)"
    else:
        model_id, task = _resolve_model_id_for_engine(engine, user)
    prompt = _shape_prompt_from_intent(operator_intent)
    response = route_request(model_id, prompt)

    return {
        "engine": engine,
        "request": {
            "model_id":       model_id,
            "task":           task,
            "prompt_preview": runtime_privacy.prompt_preview(prompt),
        },
        "response": response,
        "metadata": {
            "provider": response.get("provider", parse_provider(model_id)),
            "mock":     bool(response.get("mock", True)),
            "ts":       float(response.get("ts", time.time())),
        },
    }


# ---------------------------------------------------------------------------
# v79 — Task helper: regression_first
#
# Thin facade that resolves ``model_id`` via ``TASK_DEFAULTS`` (or an
# explicit override) and dispatches to
# ``intelligence_kernel.run_regression_first``. The model_id is
# threaded through to the kernel for telemetry — V79's kernel
# function doesn't itself drive an LLM call (packets are already
# emitted upstream under the bundle prompt). V80's
# ``/me/regression_first/packet`` endpoint can either call this
# helper directly or go through the kernel; both paths resolve the
# same model_id from TASK_DEFAULTS["regression_first"].
# ---------------------------------------------------------------------------
def call_regression_first(
    packet,
    *,
    user: Optional[str] = None,
    model_id: Optional[str] = None,
    store=None,
) -> dict:
    """Dispatch a packet through the regression_first task pipeline.

    ``model_id`` is resolved via the standard precedence (explicit
    override → founder default → user preferred_model →
    ``TASK_DEFAULTS["regression_first"]``). The resolved id is passed
    through to ``intelligence_kernel.run_regression_first`` for
    telemetry on ``operator_state.last_model_used``.

    Parallel signature to ``route_request`` / ``call_dispatcher``.
    Returns whatever the kernel returns (the CognitivePacket dict,
    with the persisted chain under ``chain`` when applicable).
    """
    resolved = select_model(
        user, task="regression_first", override=model_id,
    )
    # Lazy import — intelligence_kernel imports model_router at top
    # level, so we can't import it eagerly here without a cycle.
    import intelligence_kernel
    return intelligence_kernel.run_regression_first(
        packet,
        user_id=user,
        model_id=resolved,
        store=store,
    )


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_for_tests() -> None:
    global _founder_default_model, _founder_default_loaded
    global _LOCAL_HANDLE_CACHE, _LOCAL_HANDLE_PATH
    _founder_default_model = None
    # PASS-4 V2 — drop the loaded flag so the next get_founder_default_model
    # re-consults the vault. The conftest also resets memory_vault so the
    # vault entry is gone too; the persistence test below pokes only the
    # cache (not the vault) to simulate a fresh-process restart.
    _founder_default_loaded = False
    _LOCAL_HANDLE_CACHE = None
    _LOCAL_HANDLE_PATH = None
    # Drop runtime cache too so env-var tweaks don't leak across tests.
    try:
        import local_model_runtime
        local_model_runtime._reset_for_tests()
    except Exception:  # pragma: no cover
        pass
