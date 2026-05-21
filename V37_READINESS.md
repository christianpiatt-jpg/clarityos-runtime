# V37 Readiness — Cross-cluster entity graph + ELINS network view

Status: ✅ Ready
Backend version: `3.3`
Entity graph version: `entity_graph.v37.1`
Build: `20260506900000`

---

## What v37 ships

A pure deterministic entity-graph builder over ELINS objects, hooked
into the macro-ELINS scheduler so every scheduled pass produces a fresh
graph snapshot. Entities are surfaced via four read-side endpoints
(search, neighbours, timeseries, raw export) and rendered in the web
+ phone surfaces. ESO anchors flow through directly: when the
scheduler runs in `cloud_perplexity` mode, anchors like "Federal
Reserve rate path" become first-class graph nodes; without ESO, the
graph still picks up lexical entities from the regional scaffolds.

The graph is a plain JSON dict — entities are name-keyed and edges
keyed by `"<a>||<b>"` with `a < b`, so persistence to memory or
Firestore is identical and the snapshot can be exported as-is.

---

## Files added / changed

### New
- `elins_entity_graph.py` — extraction + build + merge + neighbours +
  timeseries + search; deterministic, pure functions; 30-line lexical
  seed list with word-boundary regex matching.
- `tests/test_v37_entity_graph.py` — 37 tests.
- `web/src/components/founder/entities/EntitySearch.tsx`
- `web/src/components/founder/entities/EntityNeighborsPanel.tsx`
- `web/src/components/founder/entities/EntityTimeseriesPanel.tsx`
- `web/src/components/founder/entities/EntityGraphPanel.tsx` (orchestrator)
- `phone/app/entities.tsx`
- `phone/app/entity_detail.tsx`
- `phone/app/entity_timeseries.tsx`
- `V37_READINESS.md` (this file)

### Modified
- `ELINS/elins_project.py` — `_ENTITY_GRAPH_COLL`, `_MEM_ENTITY_GRAPH`,
  `save_entity_graph`, `load_latest_entity_graph`, `load_entity_graph_at`,
  `list_entity_graph_snapshots`; reset hook clears the new store.
- `elins_scheduler.py` — imports `elins_entity_graph`; collects all
  ELINS produced in a pass, builds the delta, merges into the existing
  graph, persists; surfaces `entity_graph_id`, `entity_count`,
  `edge_count` in the run summary.
- `app.py` — four new endpoints (`GET /elins/entities/search`,
  `GET /elins/entities/{entity}/neighbors`,
  `GET /elins/entities/{entity}/timeseries`,
  `GET /founder/elins/entity_graph/raw`); imports `elins_entity_graph`;
  backend version `3.3`; capability `elins_entities`.
- `web/src/lib/api.ts` — `V37EntitySearchHit`, `V37EntityNeighbor`,
  `V37EntitySummary`, `V37EntityAppearance`, `V37EntityGraphRaw`,
  `V37EntityGraphSnapshot` + 4 helper calls.
- `web/src/components/founder/FounderDashboard.tsx` — embed
  `EntityGraphPanel` as a full-width row.
- `web/src/components/founder/ELINSInspector.tsx` — list
  `synthesis.external_anchors` with links to the entity graph.
- `phone/lib/api.ts` — same v37 types/helpers as web.
- `phone/app/_layout.tsx` — register `entities`, `entity_detail`,
  `entity_timeseries` stack screens.
- `phone/app/founder.tsx` — link to `/entities` (v37).
- `phone/app/elins_inspector.tsx` — tap-through from any
  `synthesis.external_anchors` entry to `/entity_detail`.
- `tests/test_v28_endpoints.py` — health version `3.3`.
- `BUILD_VERSION` — `20260506900000`.

---

## Graph shape

```jsonc
{
  "entities": {
    "Iran proxy escalation": {
      "degree":   4,
      "clusters": ["MEA"],
      "domains":  {"geopolitical": 0.45, "economic": 0.20},
      "ep_stats": {"sum": 1.34, "count": 3, "mean": 0.4467},
      "appearances": [
        {"ts": 1714998000.0, "ep_mean": 0.45, "domains": {...}, "cluster": "MEA"},
        ...
      ]
    },
    ...
  },
  "edges": {
    "Iran proxy escalation||OPEC supply posture": {
      "a": "Iran proxy escalation", "b": "OPEC supply posture",
      "weight": 2.34, "co_occurrences": 2,
      "first_ts": 1714998000.0, "last_ts": 1715080800.0
    },
    ...
  },
  "version":    "entity_graph.v37.1",
  "updated_ts": 1715080800.0
}
```

Edges are undirected; the lex-sorted key keeps the dict JSON-clean.
Each appearance is a stand-alone event (no dedup) — sort by `ts` for
chronology.

---

## Entity extraction

`extract_entities(elins_obj)` returns a de-duped list of
`{name, source}` dicts. Sources, in priority order:

1. `external_signals.anchors` (regional ELINS with ESO) — `eso_anchor`
2. `external_signals.signals[].anchor` — `eso_signal`
3. `synthesis.external_anchors` (forward-compat mirror) — `synthesis_anchor`
4. `topic_hint` (raw caller-supplied topic) — `topic_hint`
5. Lexical scan over `input_phase.text` against a stable
   word-boundary-regexed seed list (United States, ECB, Iran, Senate,
   Frontier model, …) — `lexical`

Word-boundary matching is mandatory — the prior pure-substring approach
made "AI" hit "raise" and other false positives.

---

## API surface

### `GET /elins/entities/search?q=…&limit=…` (auth, v28-gated)
Substring (case-insensitive) search over entity names. Empty `q`
returns the top-degree entities. Response includes
`graph_updated_ts` so clients can show staleness.

### `GET /elins/entities/{entity}/neighbors?limit=…` (auth, v28-gated)
Returns `{entity, summary, neighbors}`:
- `summary`: `{degree, clusters, ep_mean, domains}`
- `neighbors`: list of `{name, weight, co_occurrences, first_ts,
  last_ts, top_domains}` sorted by weight desc.
- 404 when the entity isn't in the graph.

### `GET /elins/entities/{entity}/timeseries` (auth, v28-gated)
Chronological list of `{ts, ep_mean, domains, cluster}` per
appearance.

### `GET /founder/elins/entity_graph/raw` (founder-only)
Full graph dict + snapshot metadata
(`{id, ts, entity_count, edge_count, version}`). Used for export and
debug.

---

## Macro scheduler integration

`elins_scheduler._run_macro_elins_once`:

1. Run global ELINS, persist via `elins_project.save_daily_run`.
2. For each region, run regional ELINS (with optional ESO), persist.
3. Collect every produced ELINS into `pass_runs` (= 1 global + N
   regional).
4. `existing = elins_project.load_latest_entity_graph()` (or `None`).
5. `merged = elins_entity_graph.build_and_merge(existing, pass_runs)`.
6. `merged["updated_ts"] = now`; `elins_project.save_entity_graph(merged, ts=now)`.
7. Add `entity_graph_id`, `entity_count`, `edge_count` to the macro
   summary + log line.

Safe when no prior graph exists (`build_and_merge(None, runs)` returns
the delta directly). All operations are deterministic given the same
inputs — same set of ELINS in → identical graph out.

---

## UI

### Web
- `EntityGraphPanel` is a 3-column composite:
  - left: search box + result list (debounced 200 ms);
  - middle: selected entity's summary + clickable neighbour list;
  - right: SVG line chart of EP-mean per appearance + recent rows.
- `FounderDashboard` mounts the panel as a full-width row beneath the
  v36 macro panel.
- `ELINSInspector` lists each `synthesis.external_anchors` entry as a
  clickable hint that points at the entity graph URL.

### Phone
- `entities.tsx` is the search + result list (pull-to-refresh, debounced
  text input).
- `entity_detail.tsx` shows the summary + neighbours; tapping a
  neighbour drills into another entity. Includes a link to
  `entity_timeseries`.
- `entity_timeseries.tsx` renders an EP-mean bar series per appearance
  (no SVG dep).
- `elins_inspector.tsx` tap-through: every `external_anchors` entry
  routes to `/entity_detail?entity=…`.
- Founder hub gains an "Entity graph" shortcut.

---

## Tests

```
tests/test_v37_entity_graph.py — 37 tests, all pass
Full suite — 337 passed, 0 failed
```

Coverage:
- Extraction: ESO anchors, lexical word-boundary (no false positives),
  topic hint, case-insensitive dedupe.
- Build: synthetic runs, empty input, validation, determinism.
- Merge: combines edges + entities, empty-existing path, pure-input
  invariance, determinism.
- Read helpers: neighbours ordered by weight, unknown entity → empty,
  validation, chronological timeseries, substring + empty-query
  search.
- Persistence: save / load latest / load at specific ts / reject
  invalid graph.
- Scheduler integration: macro pass creates graph (with ESO) /
  remains-runnable without ESO / safe when no prior graph; second
  pass merges into existing.
- Endpoints: search no-graph, search after pass, neighbours happy +
  404, timeseries happy + 404, raw graph founder gate + payload shape +
  empty-when-no-pass.
- UI shape lockdown: search response keys + neighbours response keys.

---

## Notes / follow-ups

- The lexical seed list is intentionally conservative (~30 entries).
  Growth path is to append region-specific entity_terms each pass —
  `_LEXICAL_ENTITIES` is a tuple, easy to extend without runtime side
  effects.
- The graph keeps every appearance (no dedup) so timeseries reflect
  every event. Callers that re-merge the same delta will double-count
  — that's by design and surfaces the bug rather than silently
  papering over it.
- Pre-v37 surfaces (v28–v36) are unchanged; the new endpoints are
  additive and gated by the existing `v28_surfaces` feature flag.
- Real Perplexity (when enabled) would feed richer ESO anchors
  automatically; no entity-graph changes required to ingest them.
