"""
runtime_providers.py — v64 / Unit 65.

Thin adapter over the existing v44/v45/v58 ``model_router`` that
exposes an operator-vocabulary surface:

    get_available_providers() -> list[str]
    call_model(provider, model, prompt) -> str

The canonical model dispatch + env-key gating + mock fallback all
remain in ``model_router``. This module just maps the operator's
``(provider, model)`` tuple to a ``model_router`` ``model_id`` and
forwards the call, returning the response text.

NAMING BRIDGE
-------------
Operator vocabulary uses bare provider names (``"gemini"``) while
``model_router`` uses provider-prefixed model_ids (``"google:gemini-2.0-flash"``):

    operator provider  → model_router prefix
    "anthropic"        → "anthropic:"
    "openai"           → "openai:"
    "gemini"           → "google:"
    "xai"              → "xai:"
    "local"            → "local:"

The ``model`` argument is appended verbatim. Callers that want the
TASK_DEFAULTS-resolved id should keep using ``model_router.select_model``
directly — this module is for explicit ``(provider, model)`` callers.

ENV KEYS
--------
Same env keys as ``model_router`` (no parallel definition):

    CLARITYOS_ANTHROPIC_KEY
    CLARITYOS_OPENAI_KEY
    CLARITYOS_GEMINI_KEY
    CLARITYOS_XAI_KEY
    CLARITYOS_LOCAL_MODEL_PATH

``get_available_providers`` returns the providers whose key is set.

PUBLIC API
----------
    get_available_providers() -> list[str]
    call_model(provider: str, model: str, prompt: str) -> str
"""
from __future__ import annotations

from typing import Optional

import model_router


# Operator-vocabulary providers in stable order. The ordering matches
# the resolution preference used by ``get_default_provider``.
PROVIDERS_ORDER: tuple = ("anthropic", "openai", "gemini", "xai", "local")

# Operator-vocab → model_router provider prefix. ``"gemini"`` maps to
# the ``google:`` namespace because the v44 catalogue picked the
# canonical-vendor-prefix naming for Gemini.
_PROVIDER_TO_PREFIX: dict = {
    "anthropic": "anthropic:",
    "openai":    "openai:",
    "gemini":    "google:",
    "xai":       "xai:",
    "local":     "local:",
}

# Operator-vocab → model_router internal provider name used by
# ``_provider_configured``.
_PROVIDER_TO_ROUTER_NAME: dict = {
    "anthropic": "anthropic",
    "openai":    "openai",
    "gemini":    "gemini",  # NB: model_router uses "gemini" not "google" here
    "xai":       "xai",
    "local":     "local",
}


def get_available_providers() -> list[str]:
    """Return the providers whose env key is currently set.

    Order matches ``PROVIDERS_ORDER`` so callers can pick a sensible
    default via ``get_available_providers()[0]``.
    """
    out: list[str] = []
    for provider in PROVIDERS_ORDER:
        router_name = _PROVIDER_TO_ROUTER_NAME[provider]
        if model_router._provider_configured(router_name):
            out.append(provider)
    return out


def call_model(provider: str, model: str, prompt: str) -> str:
    """Send ``prompt`` to ``(provider, model)``; return the response text.

    On any underlying error (unknown provider, malformed model name,
    network failure inside the router), ``model_router.route_request``
    already converts to a mock payload — this wrapper just unwraps to
    the text. No retries; no streaming.

    Raises:
        ValueError: when ``provider`` is not in PROVIDERS_ORDER.
    """
    if provider not in _PROVIDER_TO_PREFIX:
        raise ValueError(
            f"provider must be one of {PROVIDERS_ORDER}, got {provider!r}"
        )
    if not isinstance(model, str) or not model:
        raise ValueError(f"model must be a non-empty string, got {model!r}")
    if not isinstance(prompt, str):
        prompt = str(prompt or "")

    model_id = _PROVIDER_TO_PREFIX[provider] + model
    # model_router.route_request expects model_id to be in
    # SUPPORTED_MODELS, but unknown ids raise ValueError. Validate
    # softly: if not supported, return a mock-shaped response with
    # the original (provider, model) preserved.
    if not model_router.is_valid_model(model_id):
        return f"[mock {provider}:{model}] {prompt[:60]}".rstrip()

    result = model_router.route_request(model_id, prompt)
    text = result.get("text") if isinstance(result, dict) else None
    return text if isinstance(text, str) else ""


def get_default_provider() -> Optional[str]:
    """Return the first available provider, or ``None`` if none.

    Useful for ``get_operator_model`` (Unit 65) when no vault
    preference is set.
    """
    available = get_available_providers()
    return available[0] if available else None


# v64 / Unit 65 — Default model id per provider when neither vault
# preference nor TASK_DEFAULTS narrows further. Picked to match the
# v44 SUPPORTED_MODELS entries so the result is always a valid
# model_router model_id.
_PROVIDER_DEFAULT_MODEL: dict = {
    "anthropic": "claude-3.7",
    "openai":    "gpt-4o",
    "gemini":    "gemini-2.0-flash",
    "xai":       "groq-llama",
    "local":     "llama3.1",
}


def get_operator_model(vault) -> tuple[str, str]:
    """Resolve the ``(provider, model)`` an operator's runtime calls
    should use.

    v64 / Unit 65 resolution chain (highest priority first):

        1. ``vault["runtime"]["model_preferences"]`` — explicit
           operator preference, set via
           ``set_operator_model_preference_in_vault``.
        2. First available real provider (env key set), in
           PROVIDERS_ORDER. Anthropic first if its key is set,
           else OpenAI, etc.
        3. ``"anthropic" + "claude-3.7"`` — final fallback when no
           keys are set. ``call_model`` will mock through it because
           the provider isn't configured.

    Returns:
        ``(provider, model)`` tuple. Both fields are always
        non-empty strings drawn from the validated sets.
    """
    # 1. Vault preference.
    if isinstance(vault, dict):
        runtime = vault.get("runtime")
        if isinstance(runtime, dict):
            prefs = runtime.get("model_preferences")
            if isinstance(prefs, dict):
                provider = prefs.get("provider")
                model = prefs.get("model")
                if (
                    isinstance(provider, str)
                    and provider in _PROVIDER_TO_PREFIX
                    and isinstance(model, str)
                    and model
                ):
                    return (provider, model)

    # 2. First available real provider.
    default_provider = get_default_provider()
    if default_provider is not None:
        return (default_provider, _PROVIDER_DEFAULT_MODEL[default_provider])

    # 3. Final fallback — anthropic/claude-3.7 (will mock through
    # model_router because no env key is set).
    return ("anthropic", _PROVIDER_DEFAULT_MODEL["anthropic"])


def set_operator_model_preference_in_vault(
    vault, provider: str, model: str,
) -> dict:
    """Return a new vault dict with ``runtime.model_preferences``
    set to ``{"provider": provider, "model": model}``.

    Does NOT mutate the input vault. The runtime caller is
    responsible for persisting the result via
    ``runtime_persistence.save_vault``. This split lets tests
    construct vault snapshots without going through I/O.

    Raises:
        ValueError: when provider isn't in PROVIDERS_ORDER, or
            model is empty/not-a-string.
    """
    if provider not in _PROVIDER_TO_PREFIX:
        raise ValueError(
            f"provider must be one of {PROVIDERS_ORDER}, got {provider!r}"
        )
    if not isinstance(model, str) or not model:
        raise ValueError(f"model must be a non-empty string, got {model!r}")

    new_vault = dict(vault) if isinstance(vault, dict) else {}
    prior_runtime = (
        dict(new_vault.get("runtime"))
        if isinstance(new_vault.get("runtime"), dict)
        else {}
    )
    prior_runtime["model_preferences"] = {"provider": provider, "model": model}
    new_vault["runtime"] = prior_runtime
    return new_vault


def model_id_for(provider: str, model: str) -> str:
    """Return the model_router-canonical model_id for
    ``(provider, model)``. Useful when injecting an override into
    Unit 38's ``operator_intent.payload.preferred_model_id``.

    Raises:
        ValueError: when provider isn't in PROVIDERS_ORDER.
    """
    if provider not in _PROVIDER_TO_PREFIX:
        raise ValueError(
            f"provider must be one of {PROVIDERS_ORDER}, got {provider!r}"
        )
    if not isinstance(model, str) or not model:
        raise ValueError(f"model must be a non-empty string, got {model!r}")
    return _PROVIDER_TO_PREFIX[provider] + model
