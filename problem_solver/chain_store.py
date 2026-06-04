"""
problem_solver/chain_store.py — V77 / regression-chain storage layer.

Defines the storage interface the kernel calls into. Two
implementations ship:

    ``InMemoryRegressionChainStore``  (default, used by kernel tests)
        Process-local dict. Orders by the persisted per-chain ``seq``
        stamped by ``start_chain``; keeps a strictly-monotonic internal
        insertion seq as a fallback so same-millisecond ``start_chain``
        calls sort deterministically newest-first.

    ``VaultBackedRegressionChainStore(user_id)``  (endpoint side)
        Reads + writes through ``memory_vault`` under the
        ``regression_chains`` namespace. User-scoped at construction —
        cross-user access is impossible because the underlying vault
        is partitioned per-user. Sorts by ``(created_at, seq, chain_id)
        DESC`` using the monotonic ``seq`` that ``start_chain`` persists
        onto each chain (the vault keeps no in-process counter).

The kernel takes ``store=None`` everywhere; when omitted it uses the
module-level default in-memory store. Endpoint handlers pass a
fresh ``VaultBackedRegressionChainStore(session_user)`` per request.

Public surface
--------------
    RegressionChainStoreProtocol               (Protocol — get/save/delete/list_all)
    InMemoryRegressionChainStore               (default — module-level instance below)
    VaultBackedRegressionChainStore(user_id)   (per-user vault adapter)
    DEFAULT_STORE                              (singleton instance — module-level)
    _reset_default_store_for_tests()
"""
from __future__ import annotations

import logging
from typing import Optional, Protocol, runtime_checkable

import memory_vault

logger = logging.getLogger("clarityos.problem_solver.chain_store")


# ---------------------------------------------------------------------------
# Key construction
# ---------------------------------------------------------------------------
VAULT_NAMESPACE: str = "regression_chains"


def _vault_key(chain_id: str) -> str:
    """Canonical key under the ``regression_chains`` namespace."""
    return f"{VAULT_NAMESPACE}.{chain_id}"


def _coerce_chain_defaults(chain: dict) -> dict:
    """Backward-compat defaults applied on read so the rest of the
    system sees a uniform shape without forcing a migration sweep.
    Pure — does not mutate the underlying object.

      * ``archived`` (V81): pre-V81 chains predate the visibility flag.
      * ``seq`` (V77.1): pre-seq chains predate the monotonic creation
        counter; default ``0`` so they sort oldest under the
        ``(created_at, seq, chain_id)`` ordering.
    """
    missing: dict = {}
    if "archived" not in chain:
        missing["archived"] = False
    if "seq" not in chain:
        missing["seq"] = 0
    if missing:
        chain = {**chain, **missing}
    return chain


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class RegressionChainStoreProtocol(Protocol):
    """Storage abstraction for ``problem_solver`` chains.

    The kernel never branches on which implementation is in use —
    it calls these four methods and trusts the store to handle
    scoping (e.g. per-user for vault backends).
    """

    def get(self, chain_id: str) -> Optional[dict]: ...
    def save(self, chain: dict) -> None: ...
    def delete(self, chain_id: str) -> None: ...
    def list_all(self) -> list[dict]: ...


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------
class InMemoryRegressionChainStore:
    """Process-local store. Used by:
      * Kernel-only tests that don't bind a user.
      * Standalone callers (e.g. notebooks) that don't want the vault.

    Orders by the persisted per-chain ``seq`` (stamped by
    ``start_chain``); a strictly-monotonic internal insertion seq is
    kept as a fallback for chains saved without one, so newest-first
    ordering stays stable even when two ``save`` calls land in the same
    millisecond.
    """

    __slots__ = ("_chains", "_seq", "_seq_counter")

    def __init__(self) -> None:
        self._chains: dict[str, dict] = {}
        self._seq: dict[str, int] = {}
        self._seq_counter: int = 0

    def get(self, chain_id: str) -> Optional[dict]:
        return self._chains.get(chain_id)

    def save(self, chain: dict) -> None:
        cid = chain["chain_id"]
        if cid not in self._seq:
            self._seq_counter += 1
            self._seq[cid] = self._seq_counter
        self._chains[cid] = chain

    def delete(self, chain_id: str) -> None:
        self._chains.pop(chain_id, None)
        self._seq.pop(chain_id, None)

    def list_all(self) -> list[dict]:
        # Order by the persisted ``seq`` (stamped by start_chain) so this
        # backend agrees with the vault store. ``self._seq`` stays as a
        # fallback for any chain saved without one (e.g. a hand-built dict
        # in a test); ``chain_id`` is the final deterministic tiebreak.
        return sorted(
            self._chains.values(),
            key=lambda c: (
                c["created_at"],
                c.get("seq", self._seq.get(c["chain_id"], 0)),
                c["chain_id"],
            ),
            reverse=True,
        )

    def reset(self) -> None:
        self._chains.clear()
        self._seq.clear()
        self._seq_counter = 0


# ---------------------------------------------------------------------------
# Vault-backed implementation (per-user)
# ---------------------------------------------------------------------------
class VaultBackedRegressionChainStore:
    """User-scoped wrapper over ``memory_vault``. Bound to a single
    ``user_id`` at construction time — cross-user reads are simply
    impossible because ``vault_get`` is partitioned per-user.

    Persists each chain under the ``regression_chains.{chain_id}``
    vault key. The companion ``regression_packets.{chain_id}``
    namespace (write-once original packets, consumed by ``/replay``
    in V82) is NOT written from this store — the V82 endpoint
    handler writes it directly so the chain-store API stays
    chain-only. Both namespaces are registered in
    ``memory_vault.ALLOWED_NAMESPACES``.

    Ordering: ``(created_at, seq, chain_id) DESC``. The vault keeps no
    in-process insertion counter (the store is reconstructed per
    request), so ordering rides on the monotonic ``seq`` that
    ``start_chain`` persists onto each chain — this resolves the common
    case of several chains sharing one coarse ms ``created_at`` (e.g.
    rapid back-to-back creates on Windows). ``chain_id`` is a final
    deterministic tiebreak; legacy pre-seq chains default to ``seq=0``
    via ``_coerce_chain_defaults``.
    """

    __slots__ = ("user_id",)

    def __init__(self, user_id: str) -> None:
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id must be a non-empty string")
        self.user_id = user_id

    def get(self, chain_id: str) -> Optional[dict]:
        value = memory_vault.vault_get(
            self.user_id, _vault_key(chain_id), default=None,
        )
        if not isinstance(value, dict):
            return None
        return _coerce_chain_defaults(value)

    def save(self, chain: dict) -> None:
        memory_vault.vault_put(
            self.user_id, _vault_key(chain["chain_id"]), chain,
        )

    def delete(self, chain_id: str) -> None:
        memory_vault.vault_delete(self.user_id, _vault_key(chain_id))

    def list_all(self) -> list[dict]:
        keys = memory_vault.vault_keys_for_user(self.user_id)
        prefix = VAULT_NAMESPACE + "."
        chains: list[dict] = []
        for key in keys:
            if not key.startswith(prefix):
                continue
            try:
                value = memory_vault.vault_get(self.user_id, key)
            except Exception as e:   # pragma: no cover (defensive)
                logger.warning(
                    "vault read failed user=%s key=%s err=%s",
                    self.user_id, key, e,
                )
                continue
            if isinstance(value, dict) and "chain_id" in value:
                chains.append(_coerce_chain_defaults(value))
        chains.sort(
            key=lambda c: (
                c.get("created_at", 0),
                c.get("seq", 0),
                c.get("chain_id", ""),
            ),
            reverse=True,
        )
        return chains


# ---------------------------------------------------------------------------
# Module-level default (used when kernel callers pass store=None)
# ---------------------------------------------------------------------------
DEFAULT_STORE: InMemoryRegressionChainStore = InMemoryRegressionChainStore()


def _reset_default_store_for_tests() -> None:
    """Wipe the module-level in-memory default store. Wired into
    ``problem_solver._reset_for_tests`` so the kernel test fixture
    pulls a clean slate.

    The vault-backed store doesn't need a side reset — it lives
    inside ``memory_vault`` which has its own ``_reset_for_tests``
    hook already wired into the global ``reset_stores`` fixture.
    """
    DEFAULT_STORE.reset()
