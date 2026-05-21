# ELINS — Reports and Output Surfaces

## Overview

This document covers the surfaces that present ELINS results for consumption.
The ELINS analysis pipeline itself is specified in
`docs/elins/elins_deep_spec.md`.

There is no geometric "report visual" — no sphere, pentagon, rings, or
"metadata cloud". ELINS output is structured data rendered by ordinary panels
and charts.

## Dashboard

`elins_dashboard.py` (v38) builds the ELINS dashboard snapshot — see
`docs/dashboard.md` for the dashboard subsystem doc.
`get_dashboard_snapshot` returns sections for `global`, `regional`, `macro`,
`entity_graph`, and `continuity`. Its `forecast` field carries the
`multi_envelope` block produced by the forecast engine.

## Narratives

`elins_narratives.py` produces short text summaries of a run in the shape
`{headline, bullets, details}`.

## Feed

`elins_feed.py` projects ELINS results into a newsfeed-style stream; each item
carries an `info` / `warning` / `critical` severity.

## Regression summaries

Within the ELINS-regression suite, `elins_run_summary.py` and
`elins_run_summary_multi.py` aggregate stored regression runs into band and
score summary tables, and `elins_run_dashboard.py` assembles a regression-side
dashboard view over those runs. The suite itself is specified in
`docs/elins/elins_deep_spec.md`.

## Forecast charts

The web `ForecastPanel` renders the forecast-engine envelopes as SVG line
charts — plots of `ep(D + n) = ep0 · exp(-λ · n)` over the forecast horizon.
They are line charts only; there are no geometric primitives.
