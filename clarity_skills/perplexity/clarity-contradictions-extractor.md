---
name: clarity-contradictions-extractor
description: >
  Extract contradictions from any document, including legal filings, agency decisions,
  narratives, or institutional communications. Use when asked to identify inconsistencies,
  conflicts, or mismatches between claims, facts, timelines, or behaviors.
category: Evidence Extraction
capabilities:
  - Identify and classify contradictions in any document
  - Distinguish six contradiction types (internal, external, temporal, causal, identity, institutional)
  - Quote or summarize conflicting statements with type labels and impact notes
  - Produce numbered lists of contradictions with summaries of the most leverageable items
limitations:
  - Does not verify external facts; works only on internal text consistency
  - Does not produce legal conclusions or doctrinal analysis
  - Does not classify contradictions beyond the six predefined types
  - Does not extract claims that are not in textual conflict with another claim in the document
input_shape: >
  Any document with claims, facts, assertions, or institutional statements (legal filings, agency decisions, narratives, communications).
output_shape: >
  Numbered list of contradictions, each labeled by type (internal, external, temporal, causal, identity, institutional) with a one-to-two-sentence explanation and an impact note.
dependencies: []
governance_version: 1.0.0
---

# Clarity Contradictions Extractor

## Purpose
Identify and classify contradictions in any document using a structured, repeatable method.

## Instructions

### 1. Read the Document
- Parse the full text.
- Identify all claims, facts, and assertions.

### 2. Identify Contradiction Types
Classify contradictions into:
- Internal contradictions
- External contradictions
- Temporal contradictions
- Causal contradictions
- Identity contradictions
- Institutional contradictions

### 3. Extract and Format
For each contradiction:
- Quote or summarize the conflicting statements
- Label the contradiction type
- Explain the conflict in 1–2 sentences
- Note the potential legal or narrative impact

### 4. Output Format
Produce:
- A numbered list of contradictions
- A short explanation for each
- A summary of the most leverageable contradictions

## Example Input
"Identify contradictions in this agency decision."

## Example Output
1. **Internal contradiction** — Section II claims X, but Section IV asserts Y.  
2. **Timeline contradiction** — Event A is dated after Event B, but depends on B.  
3. **Institutional contradiction** — Agency claims consistent policy, but cites exceptions.  
