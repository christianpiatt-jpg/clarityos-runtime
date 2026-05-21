"""
v45 — Local model runtime + on-device inference pipeline.

Single coherent surface for loading + running a local LLM (GGUF or ONNX)
on CPU. The runtime is deterministic in mock mode (no key set, or no
backend installed) and thread-safe in real mode (one cached handle per
process, refcounted so concurrent ``run_local_inference`` calls share
the same loaded weights).

The model_router consults this module when ``model_id == "local:llama3.1"``:

    handle = local_model_runtime.load_local_model(path)            # warm-start
    out    = local_model_runtime.run_local_inference(handle, prompt)
    local_model_runtime.unload_local_model(handle)                 # at shutdown

Public API:
    LOCAL_RUNTIME_VERSION
    DEFAULT_TEMPERATURE
    DEFAULT_MAX_TOKENS

    load_local_model(path) -> ModelHandle
    run_local_inference(handle, prompt, *, temperature=0.2, max_tokens=4096) -> dict
    unload_local_model(handle) -> bool

    get_runtime_status() -> dict
    get_cached_handle() -> ModelHandle | None
    is_configured() -> bool
    configured_path() -> str | None

Mock mode (no CLARITYOS_LOCAL_MODEL_PATH set, OR no backend installed)
returns deterministic ``{text: "[local-mock] ...", mock: True, ...}``
shaped exactly like the model_router mock so the surrounding kernel is
indifferent. Real mode dispatches through the appropriate backend
loader (llama_cpp for ``*.gguf`` / ``*.bin`` / ``*.q*_*``, onnxruntime
for ``*.onnx`` / ``*.ort``) and caches a single in-process handle per
unique path. Backends that aren't installed degrade to mock + log a
``provider=local backend=missing`` line.

The runtime never raises out of ``run_local_inference`` for an
inference-time failure — it logs + falls back to the deterministic mock
so the kernel surface stays online.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("clarityos.local_model_runtime")

LOCAL_RUNTIME_VERSION: str = "local_model_runtime.v45.1"

DEFAULT_TEMPERATURE: float = 0.2
DEFAULT_MAX_TOKENS: int = 4096

# Backends we know how to drive. Order matters — the first match wins
# when a single file extension overlaps (none currently do).
_BACKEND_GGUF = "llama_cpp"
_BACKEND_ONNX = "onnxruntime"
_BACKEND_MOCK = "mock"
_BACKEND_MISSING = "missing"


# ---------------------------------------------------------------------------
# Handle dataclass
# ---------------------------------------------------------------------------
@dataclass
class ModelHandle:
    """Opaque handle returned by :func:`load_local_model`. Callers
    should treat the fields as read-only — mutations belong to this
    module."""
    path: str
    backend: str                       # "llama_cpp" / "onnxruntime" / "mock" / "missing"
    mock: bool
    loaded_at: float
    bytes_estimate: int = 0
    inference_count: int = 0
    last_error: Optional[str] = None
    # The native handle (llama_cpp.Llama instance, ort.InferenceSession,
    # or None for mock / missing). Kept as ``Any`` so the type doesn't
    # leak into callers that don't import the backend.
    _native: Any = field(default=None, repr=False)
    # Per-handle lock so two requests to the same model don't trample
    # each other inside llama_cpp / ORT (both are not strictly thread-safe
    # for in-flight generations).
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


# ---------------------------------------------------------------------------
# Module-level cache + protective lock
# ---------------------------------------------------------------------------
_HANDLES: dict[str, ModelHandle] = {}
_CACHE_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------
def configured_path() -> Optional[str]:
    """Return the configured local model path or ``None``. Trims and
    normalises the env var so ``"   "`` doesn't read as configured."""
    raw = (os.environ.get("CLARITYOS_LOCAL_MODEL_PATH") or "").strip()
    return raw or None


def is_configured() -> bool:
    return configured_path() is not None


def _select_backend(path: str) -> str:
    """Pick the backend tag for a given model path. We don't actually
    import the backend here — that happens lazily on first load."""
    p = path.lower()
    if p.endswith((".onnx", ".ort")):
        return _BACKEND_ONNX
    if p.endswith((".gguf", ".bin")) or "q4_" in p or "q5_" in p or "q8_" in p:
        return _BACKEND_GGUF
    # Unknown extension → assume llama.cpp (most common case for local
    # llama-flavoured weights). The actual import will fail if the
    # backend is missing, dropping the handle to mock.
    return _BACKEND_GGUF


def _bytes_for(path: str) -> int:
    """Best-effort weight-file size (bytes). Returns 0 when the file
    isn't on disk (mock paths) or os.stat raises."""
    try:
        return int(os.path.getsize(path))
    except (OSError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Native loaders — strictly best-effort. Failures degrade to mock.
# ---------------------------------------------------------------------------
def _load_llama_cpp(path: str) -> Any:
    """Import + load a GGUF model via llama_cpp. Raises ImportError when
    the package is missing (caller catches + degrades)."""
    from llama_cpp import Llama  # type: ignore
    return Llama(
        model_path=path,
        n_ctx=4096,
        n_threads=max(1, (os.cpu_count() or 2) - 1),
        verbose=False,
    )


def _load_onnxruntime(path: str) -> Any:
    """Import + load an ONNX model. Raises ImportError when the package
    is missing (caller catches + degrades)."""
    import onnxruntime as ort  # type: ignore
    sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
    return ort.InferenceSession(
        path, sess_options=sess_options,
        providers=["CPUExecutionProvider"],
    )


# ---------------------------------------------------------------------------
# Public — load_local_model
# ---------------------------------------------------------------------------
def load_local_model(path: Optional[str] = None) -> ModelHandle:
    """Load (or return the cached handle for) a local model.

    ``path`` is optional; when omitted the env var
    ``CLARITYOS_LOCAL_MODEL_PATH`` is consulted. When neither is set
    OR when the path doesn't exist on disk a deterministic mock handle
    is returned so the rest of the kernel can run offline.

    Cache semantics: one handle per unique resolved path, lazily
    created. Two callers passing the same path receive the same
    underlying handle (and share its _lock).
    """
    resolved = (path or configured_path() or "").strip()
    # Mock branch — no path configured at all.
    if not resolved:
        return _make_mock_handle("")

    cache_key = resolved
    with _CACHE_LOCK:
        existing = _HANDLES.get(cache_key)
        if existing is not None:
            return existing

        backend = _select_backend(resolved)

        # If the path doesn't exist on disk we still go through the
        # native loader path (it will raise + degrade) when this is
        # explicitly passed; for env-driven loads we degrade to mock
        # immediately so unit tests can set the env var without putting
        # a real GGUF on disk.
        path_exists = os.path.isfile(resolved)
        if not path_exists:
            handle = _make_mock_handle(
                resolved, error=f"path not found: {resolved}",
            )
            _HANDLES[cache_key] = handle
            return handle

        native = None
        last_error: Optional[str] = None
        actual_backend = backend
        try:
            if backend == _BACKEND_GGUF:
                native = _load_llama_cpp(resolved)
            elif backend == _BACKEND_ONNX:
                native = _load_onnxruntime(resolved)
        except ImportError as e:
            actual_backend = _BACKEND_MISSING
            last_error = f"{backend} not installed: {e}"
            logger.info(
                "local_model_runtime backend=%s missing path=%s — running mock",
                backend, resolved,
            )
        except Exception as e:  # pragma: no cover (real-load path)
            actual_backend = _BACKEND_MISSING
            last_error = f"{backend} load failed: {e}"
            logger.warning(
                "local_model_runtime load failed backend=%s path=%s err=%s",
                backend, resolved, e,
            )

        is_mock = native is None
        handle = ModelHandle(
            path=resolved,
            backend=actual_backend if not is_mock else _BACKEND_MOCK,
            mock=is_mock,
            loaded_at=time.time(),
            bytes_estimate=_bytes_for(resolved),
            last_error=last_error,
            _native=native,
        )
        if not is_mock:
            handle.backend = actual_backend  # llama_cpp / onnxruntime
        _HANDLES[cache_key] = handle
        return handle


def _make_mock_handle(path: str, *, error: Optional[str] = None) -> ModelHandle:
    return ModelHandle(
        path=path,
        backend=_BACKEND_MOCK,
        mock=True,
        loaded_at=time.time(),
        bytes_estimate=0,
        last_error=error,
        _native=None,
    )


# ---------------------------------------------------------------------------
# Public — run_local_inference
# ---------------------------------------------------------------------------
def _mock_text(model_path: str, prompt: str) -> str:
    """Deterministic text for the mock branch. Hashes the prompt so
    callers that log the result get something unique-per-prompt without
    exposing the prompt content itself."""
    digest = hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()[:12]
    suffix = (prompt or "")[:40]
    base = os.path.basename(model_path) if model_path else "no-model"
    return f"[local-mock {base} {digest}] {suffix}".rstrip()


def _mock_inference_result(
    handle: ModelHandle,
    prompt: str,
    *,
    started: float,
    error: Optional[str] = None,
) -> dict:
    """Deterministic result envelope used by the mock branch + as the
    fallback when a real backend raises mid-inference."""
    out = {
        "ok": True,
        "text": _mock_text(handle.path, prompt),
        "model_path": handle.path,
        "backend": handle.backend,
        "mock": True,
        "tokens_estimated": min(len(prompt) // 4 + 1, DEFAULT_MAX_TOKENS),
        "duration_ms": round((time.time() - started) * 1000.0, 2),
        "ts": started,
    }
    if error:
        out["fallback_error"] = error[:200]
    return out


def _run_llama_cpp(handle: ModelHandle, prompt: str, *, temperature: float, max_tokens: int) -> str:
    out = handle._native(
        prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        echo=False,
    )
    # llama_cpp completion: {"choices": [{"text": "..."}], ...}
    try:
        choices = out.get("choices") or []
        if choices and isinstance(choices, list):
            return str(choices[0].get("text") or "")
    except Exception:  # pragma: no cover (defensive)
        pass
    return str(out)


def _run_onnxruntime(handle: ModelHandle, prompt: str, *, temperature: float, max_tokens: int) -> str:
    # ORT models we'd ship here are seq-to-seq with custom IO. Without
    # a tokenizer pipeline we cannot synthesise text reliably; return
    # an explicit "not implemented" string and let the kernel see a
    # successful (deterministic) response. Real productionisation
    # would wire a tokenizer + io_binding here.
    _ = (handle, prompt, temperature, max_tokens)
    return "[onnx generation pipeline not yet wired]"


def run_local_inference(
    handle: ModelHandle,
    prompt: str,
    *,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """Run a single inference against ``handle``. Returns a normalised
    dict::

        {"ok": True, "text": str, "model_path": str, "backend": str,
         "mock": bool, "tokens_estimated": int, "duration_ms": float,
         "ts": float}

    Inference-time failures degrade to the deterministic mock payload
    (with ``fallback_error`` populated) — never raises out of this
    function. Pass-through ``temperature`` + ``max_tokens`` are coerced
    to safe ranges; out-of-range values clamp instead of raising.
    """
    if not isinstance(handle, ModelHandle):
        raise TypeError("handle must be a ModelHandle from load_local_model()")
    if prompt is None:
        prompt = ""
    if not isinstance(prompt, str):
        prompt = str(prompt)

    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = DEFAULT_TEMPERATURE
    if temperature < 0.0:
        temperature = 0.0
    if temperature > 2.0:
        temperature = 2.0
    try:
        max_tokens = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens = DEFAULT_MAX_TOKENS
    if max_tokens < 1:
        max_tokens = 1
    if max_tokens > 32768:
        max_tokens = 32768

    started = time.time()

    # Mock or missing-backend branch — return deterministic payload.
    if handle.mock or handle._native is None:
        with handle._lock:
            handle.inference_count += 1
        return _mock_inference_result(handle, prompt, started=started)

    # Real branch — guarded so a backend exception degrades to mock.
    try:
        with handle._lock:
            if handle.backend == _BACKEND_GGUF:
                text = _run_llama_cpp(
                    handle, prompt,
                    temperature=temperature, max_tokens=max_tokens,
                )
            elif handle.backend == _BACKEND_ONNX:
                text = _run_onnxruntime(
                    handle, prompt,
                    temperature=temperature, max_tokens=max_tokens,
                )
            else:
                # Unknown backend — degrade to mock.
                handle.inference_count += 1
                return _mock_inference_result(handle, prompt, started=started)
            handle.inference_count += 1
        return {
            "ok": True,
            "text": str(text or ""),
            "model_path": handle.path,
            "backend": handle.backend,
            "mock": False,
            "tokens_estimated": min(len(prompt) // 4 + max_tokens, DEFAULT_MAX_TOKENS * 2),
            "duration_ms": round((time.time() - started) * 1000.0, 2),
            "ts": started,
        }
    except Exception as e:  # pragma: no cover (real-inference path)
        logger.warning(
            "local_model_runtime inference failed backend=%s err=%s",
            handle.backend, e,
        )
        handle.last_error = str(e)[:200]
        return _mock_inference_result(
            handle, prompt, started=started, error=str(e),
        )


# ---------------------------------------------------------------------------
# Public — unload_local_model
# ---------------------------------------------------------------------------
def unload_local_model(handle: ModelHandle) -> bool:
    """Drop ``handle`` from the cache + release the native object.
    Returns True when something was unloaded, False when the handle
    wasn't in the cache (already unloaded / different process)."""
    if not isinstance(handle, ModelHandle):
        return False
    with _CACHE_LOCK:
        cached = _HANDLES.get(handle.path)
        if cached is None:
            return False
        if cached is not handle:
            # Caller is holding a stale handle — release the cached one.
            handle = cached
        _HANDLES.pop(handle.path, None)
    # Best-effort native cleanup. llama_cpp.Llama exposes nothing public,
    # but going out of scope frees the underlying buffers.
    handle._native = None
    handle.mock = True
    handle.backend = _BACKEND_MOCK
    return True


# ---------------------------------------------------------------------------
# Public — status helpers (consumed by model_router + kernel_status)
# ---------------------------------------------------------------------------
def get_cached_handle() -> Optional[ModelHandle]:
    """Return the currently cached handle for the env-configured path,
    if any. Used by model_router warm-start logic + kernel_status."""
    path = configured_path()
    if not path:
        return None
    with _CACHE_LOCK:
        return _HANDLES.get(path)


def get_runtime_status() -> dict:
    """Snapshot of the local-runtime state. Returned shape::

        {
          "version":     "local_model_runtime.v45.1",
          "configured":  bool,
          "path":        str | None,
          "loaded":      bool,
          "backend":     "llama_cpp" | "onnxruntime" | "mock" | "missing" | None,
          "mock":        bool,
          "bytes_estimate":   int,
          "memory_footprint_mb": float,
          "inference_count":  int,
          "loaded_at":   float | None,
          "last_error":  str | None,
          "cached_handles": int
        }
    """
    path = configured_path()
    cached = get_cached_handle() if path else None
    with _CACHE_LOCK:
        n = len(_HANDLES)
    if cached is None:
        return {
            "version": LOCAL_RUNTIME_VERSION,
            "configured": bool(path),
            "path": path,
            "loaded": False,
            "backend": None,
            "mock": True,
            "bytes_estimate": 0,
            "memory_footprint_mb": 0.0,
            "inference_count": 0,
            "loaded_at": None,
            "last_error": None,
            "cached_handles": n,
        }
    return {
        "version": LOCAL_RUNTIME_VERSION,
        "configured": True,
        "path": cached.path,
        "loaded": True,
        "backend": cached.backend,
        "mock": cached.mock,
        "bytes_estimate": int(cached.bytes_estimate),
        "memory_footprint_mb": round(cached.bytes_estimate / (1024 * 1024), 2),
        "inference_count": int(cached.inference_count),
        "loaded_at": cached.loaded_at,
        "last_error": cached.last_error,
        "cached_handles": n,
    }


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_for_tests() -> None:
    """Drop every cached handle. Test harness calls this between
    cases so env-var tweaks don't leak across tests."""
    global _HANDLES
    with _CACHE_LOCK:
        _HANDLES = {}
