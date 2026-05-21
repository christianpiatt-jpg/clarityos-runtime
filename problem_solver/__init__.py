"""
ClarityOS ProblemSolver kernel module — V76 / ProblemSolver.REGRESSION_FIRST.

Operator-protocol module. Each chain is an operator log of findings
(one per chain layer) plus free-form key/value tags and a title +
optional notes. Chains stay open until ``close_chain`` is called.

Pairs with the ``skills_export/regression_first/`` external bundle:
the kernel reads the bundle's ``system_prompt.md`` as **plain text**
(not as a Python import) and uses it to drive an LLM-primary
analyzer for the auto-trigger path. Same boundary discipline as v69
``el_ins``.

Public surface re-exported here so callers can do:

    from problem_solver import (
        start_chain, record_finding, close_chain, tag_chain,
        get_chain, list_chains, analyze_packet,
        RegressionChain, RegressionLayer, CognitivePacket,
        should_auto_trigger, extract_problem, CUE_WORDS, CUE_PHRASES,
    )
"""
from __future__ import annotations

from .regression_first import (
    start_chain,
    record_finding,
    close_chain,
    tag_chain,
    delete_tag,
    archive_chain,
    get_chain,
    list_chains,
    analyze_packet,
    RegressionChain,
    RegressionLayer,
    CognitivePacket,
    LAYER_STATUSES,
    CLASSIFICATIONS,
    SYSTEM_PROMPT_PATH,
    PROTOCOL_NAME,
    TITLE_MAX,
    NOTES_MAX,
    LAYER_NOTES_MAX,
    TAG_KEY_MAX,
    TAG_VALUE_MAX,
    TAGS_PER_CHAIN_MAX,
    _extract_packet_dict,
    _make_chain_id,
    _now_ms,
    _reset_prompt_cache,
    _reset_for_tests,
)
from .chain_store import (
    DEFAULT_STORE,
    InMemoryRegressionChainStore,
    RegressionChainStoreProtocol,
    VaultBackedRegressionChainStore,
    VAULT_NAMESPACE,
    _reset_default_store_for_tests,
)
from .auto_trigger import (
    should_auto_trigger,
    extract_problem,
    CUE_WORDS,
    CUE_PHRASES,
    _has_cue,
)


__all__ = [
    # chain lifecycle
    "start_chain",
    "record_finding",
    "close_chain",
    "tag_chain",
    "delete_tag",      # v81
    "archive_chain",   # v81
    "get_chain",
    "list_chains",
    # unified-packet pipeline
    "analyze_packet",
    # types
    "RegressionChain",
    "RegressionLayer",
    "CognitivePacket",
    # storage layer (V77)
    "RegressionChainStoreProtocol",
    "InMemoryRegressionChainStore",
    "VaultBackedRegressionChainStore",
    "DEFAULT_STORE",
    "VAULT_NAMESPACE",
    # enums + constants
    "LAYER_STATUSES",
    "CLASSIFICATIONS",
    "PROTOCOL_NAME",
    "SYSTEM_PROMPT_PATH",
    # caps
    "TITLE_MAX",
    "NOTES_MAX",
    "LAYER_NOTES_MAX",
    "TAG_KEY_MAX",
    "TAG_VALUE_MAX",
    "TAGS_PER_CHAIN_MAX",
    # auto-trigger
    "should_auto_trigger",
    "extract_problem",
    "CUE_WORDS",
    "CUE_PHRASES",
    # test hooks
    "_reset_for_tests",
]
