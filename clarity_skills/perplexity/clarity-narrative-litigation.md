---
name: clarity-narrative-litigation
description: >
  Analyze legal motions, briefs, agency decisions, or institutional documents using a
  narrative-architecture approach. Use when asked to analyze, oppose, or respond to a
  motion, brief, or government filing. Applies contradictions, timelines, identity threads,
  and institutional behavior patterns to surface structural weaknesses and disputed facts.
category: Narrative Analysis
capabilities:
  - Analyze legal motions, briefs, and agency decisions for structural readings
  - Apply narrative-architecture analysis (contradictions, timelines, identity threads, institutional behavior patterns)
  - Surface disputed material facts, framing tricks, and gaps in the record
  - Produce structural summaries and proposed opposition outlines with suggested headings
  - Prioritize attack points by impact on requested relief and applicable standard of review
limitations:
  - Does not draft full briefs or replace legal counsel
  - Does not verify or cite-check legal authorities
  - Does not perform jurisdiction-specific procedural analysis
  - Does not apply outside-the-document evidence; analysis is bound to the input text
input_shape: >
  Legal motion, brief, agency decision, or institutional document containing assertions, framing, and supporting material.
output_shape: >
  Structural reading of the document — section summary, list of contradictions and disputes, proposed opposition outline with suggested headings, and prioritized attack-point notes.
dependencies: []
governance_version: 1.0.0
---

# Clarity Narrative Litigation

## Purpose
Provide a structured, repeatable method for analyzing legal or institutional documents
and producing operator-grade outputs for litigation strategy and drafting.

## Instructions

### 1. Ingest the Document
- Read the entire text.
- Identify the relief requested.
- Identify the legal standards invoked.
- Identify the core narrative and framing.

### 2. Extract Structure
Identify and list:
- Issues
- Arguments
- Asserted facts
- Standards of review
- Requested relief
- Section structure (e.g., Introduction, Facts, Argument, Conclusion)

### 3. Apply Narrative Architecture
Analyze the document using:
- Contradictions (internal and external)
- Timeline inconsistencies
- Missing causal steps
- Identity-thread conflicts (roles claimed vs. roles acted)
- Institutional behavior patterns (what the institution does vs. what it says)

### 4. Surface Leverage Points
Identify:
- Disputed material facts
- Misstatements or overstatements of law
- Gaps in the record
- Framing tricks (e.g., selective timelines, omitted context)

Prioritize by:
- Impact on the requested relief
- Vulnerability under the applicable standard (e.g., Rule 56)

### 5. Produce Outputs
Provide:
- A concise structural summary
- A list of contradictions and disputes
- A proposed outline for an opposition or response
- Suggested headings and subheadings
- Operator-grade language and structure

## Example Input
"Analyze this motion for summary judgment and identify contradictions, disputed facts,
and the best structure for an opposition."

## Example Output
1. Structural summary of the motion  
2. List of contradictions and disputed facts  
3. Proposed outline for the opposition  
4. Notes on the most promising attack points  
