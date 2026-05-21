---
name: clarity-timeline-mapper
description: >
  Extract, normalize, and map timelines from documents. Use when asked to build a timeline,
  identify temporal inconsistencies, or reconstruct sequences of events from filings,
  narratives, or institutional records.
category: Timeline Construction
capabilities:
  - Extract dates, times, and temporal references from a document
  - Normalize dates to YYYY-MM-DD format and order chronologically
  - Identify gaps, impossible sequences, overlapping events, and temporal contradictions
  - Produce clean chronological timelines with inconsistency notes
limitations:
  - Does not infer dates that are not stated or strongly implied in the text
  - Does not assign causality between events; only flags missing causal links the text implies
  - Does not resolve ambiguous dates without explicit context
  - Does not produce legal or factual conclusions; output is descriptive only
input_shape: >
  Document or set of documents containing dated events (filings, emails, transcripts, narratives, institutional records).
output_shape: >
  Chronological timeline of normalized events plus a list of temporal inconsistencies (gaps, impossible sequences, conflicting dates, missing causal links) with notes on narrative or legal impact.
dependencies: []
governance_version: 1.0.0
---

# Clarity Timeline Mapper

## Purpose
Create accurate, operator-grade timelines from any document and identify temporal conflicts.

## Instructions

### 1. Extract Events
- Identify all dates, times, and temporal references.
- Capture associated actions, actors, and context.

### 2. Normalize
- Convert all dates into a consistent format (YYYY-MM-DD).
- Order events chronologically.
- Note any missing or ambiguous dates.

### 3. Analyze
Identify:
- Gaps in the timeline
- Impossible sequences
- Overlapping or conflicting events
- Missing causal steps
- Temporal contradictions

### 4. Output Format
Provide:
- A clean chronological timeline
- A list of temporal inconsistencies
- Notes on narrative or legal impact

## Example Input
"Build a timeline from this set of emails and filings."

## Example Output
- 2021-03-14 — Event A  
- 2021-03-16 — Event B  
- 2021-03-16 — Event C (conflicts with B)  
- 2021-03-20 — Event D (missing causal link from C)
