# UP M1/M2/M3 — Pre-registration v1.3: Lawbridg PDF Conversion

**Status:** preregistered (no inferential commitments). Expands the
allowed-format envelope of v1.2 strictly for the Lawbridg References
subsystem, which is empirically PDF-only at registration time.

**Contract version anchor:** v1.0.0 § 1–9 + v1.1.0 § 6–9 + v1.2 §1–10
(this prereg inherits all three; no contract or earlier prereg is
modified).

**Registered:** 2026-05-07
**Corpus ID:** `lawbridg_pdf_v1_3`
**Pre-flight PDF count (depth ≤ 4):** 72 `.pdf` files in the Lawbridg
References root.

---

## 0. Discipline Lock

The following must NOT be modified by any task operating under this
prereg:

```
analysis/physics/alternator/UP_M123_CONTRACT_v1.0.0.md
analysis/physics/alternator/UP_M123_CONTRACT_v1.1.0.md
analysis/physics/alternator/UP_M123_PREREG_v1_2_LOCAL_LIBRARIES.md
_scratch/up_m123_summary_v52_2*.csv
_scratch/up_m123_summary_v52_2*.json
_scratch/run_up_m123_analysis.py
_scratch/run_up_m123_region_alt.py
analysis/physics/up_kernel_spec.md
analysis/schema/up_kernel_schema.json
ELINS/*.py
```

All work is additive.

---

## 1. Scope

This prereg covers ONLY the **Lawbridg References** subsystem. ELINS
Library and Narrative Architecture ingestion (governed by v1.2) are
unchanged.

Specifically:

- v1.3 adds `.pdf` to the allowed-format envelope **for Lawbridg only**.
- v1.3 introduces a PDF → text conversion layer.
- v1.3 does not change DV definitions, metric code, alternator grid,
  models, permutation parameters, or tokenization rules.

## 1.2 Allowed formats (Lawbridg-only addition)

| format | status under v1.2 | status under v1.3 (Lawbridg only) |
|---|---|---|
| `.json`, `.md`, `.txt` | included | included |
| `.pdf` | excluded | **included via lossless text extraction** |
| `.docx`, `.xlsx`, `.pptx`, `.png`, `.jpg` | excluded | excluded |

Conversion rule:

- Lossless text extraction (embedded PDF text streams), **not OCR**.
- Tool: `pdfminer.six` (`pdfminer.high_level.extract_text`) or an
  equivalent pure-text extractor.
- PDFs that contain only scanned images and yield empty extractions are
  reported and **skipped**, not OCR'd. OCR introduces inferential
  hallucination and is out of scope.

## 1.3 Provenance fields

Each row in the Lawbridg PDF metric CSV must carry these provenance
fields:

| field | value |
|---|---|
| `source_format` | `"pdf"` |
| `converted` | `true` |
| `conversion_tool` | `"pdfminer.six"` |
| `conversion_timestamp` | UTC ISO-8601 (`%Y-%m-%dT%H:%M:%SZ`) |
| `source_path` | absolute path of the original PDF |

These fields are emitted by `_scratch/pdf_to_text.py:provenance_block()`
and merged into each ingested row.

## 1.4 Output of conversion

Converted text is **passed in-memory** to the ingestion pipeline. No
intermediate `.txt` files are written to disk. This avoids creating
secondary artifacts that could drift from their PDF sources.

## 1.5 Ingestion rules (Lawbridg PDF specifics)

After extraction, each PDF row is treated as if it were a `.txt` file
under v1.2 §2.3, with the following overrides:

| field | source |
|---|---|
| `date` | PDF metadata (`/CreationDate`, `/ModDate`) → else file mtime |
| `region_label` | `"Unknown"` unless a sibling JSON metadata file supplies one (rare in this subsystem) |
| `library` | `"lawbridg"` |
| `source` | `"local_library"` |
| `source_format` | `"pdf"` |
| `path_relative` | path under `Lawbridg References` |

## 1.6 Metrics

Identical to v1.2 §3 — same five DVs, same E / r / E_over_r /
orientation_score / node_count / body_length, computed through the
unchanged ELINS metric layer (`ELINS/region_metrics.py`,
`elins_entity_graph.py`).

No new metrics are introduced.

## 1.7 Artifacts

### 1.7a Per-corpus CSV

```
_scratch/regions_named_with_scale_DVs_lawbridg_pdf.csv
```

### 1.7b Combined local-library CSV (v1.2 §4.2 superset)

```
_scratch/regions_named_with_scale_DVs_local_libraries_combined.csv
```

is updated at run time to include Lawbridg PDF rows alongside ELINS
Library and Narrative Architecture.

### 1.7c Combined all-sources CSV (v1.2 §4.3 superset, optional)

If used:

```
_scratch/regions_named_with_scale_DVs_all_sources_combined.csv
```

includes Outlook + ELINS + Narrative + Lawbridg PDF.

## 1.8 Index update

This corpus is registered in
`analysis/physics/alternator/UP_M123_CORPUS_INDEX.json` with:

```json
{
  "id": "lawbridg_pdf_v1_3",
  "type": "local_library_pdf",
  "rows": null,
  "contract_version": "v1.1.0",
  "status": "preregistered",
  "paths": ["C:/Users/chris/ClarityOS_Library/Clarity_Library/02_Subsystems/Lawbridg References"],
  "note": "PDF-only subsystem; v1.3 prereg expands allowed formats.",
  "preflight_pdf_count": 72,
  "prereg_file": "analysis/physics/alternator/UP_M123_PREREG_v1_3_LAWBRIDG_PDF_CONVERSION.md"
}
```

`rows` is `null` until ingestion runs (per v1.2 §9, no inferential
commitments are pre-made by the prereg).

---

## 2. Implementation references

| component | path | status |
|---|---|---|
| PDF → text helper | `_scratch/pdf_to_text.py` | written under v1.3 (this turn) |
| Unified ingestion script | `_scratch/ingest_local_libraries.py` | **not yet written**; v1.2 ingestion is its precondition. v1.3 adds PDF handling to that script when it exists. |
| ELINS metric layer | `ELINS/region_metrics.py` | unchanged (frozen per §0) |
| Entity graph | `elins_entity_graph.py` | unchanged (frozen per §0) |

Until `ingest_local_libraries.py` exists, this prereg defines the
contract its PDF-handling branch must satisfy; no run-time data is
produced.

---

## 3. Sanity checks (run-time, not prereg-time)

After ingestion has executed:

- [ ] `_scratch/regions_named_with_scale_DVs_lawbridg_pdf.csv` exists
- [ ] row count > 0
- [ ] all 5 DV columns populated (no all-NaN columns)
- [ ] `region_label = "Unknown"` for rows without metadata
- [ ] `source_format = "pdf"` and `converted = true` on every row
- [ ] combined local-library CSV row count rises by the number of
      successfully converted Lawbridg PDFs

If any check fails, the run is reported as such; no scope adjustment is
made under this prereg.

---

## 4. Dependencies

`pip install pdfminer.six`

The helper at `_scratch/pdf_to_text.py` lazy-imports pdfminer; importing
the module without pdfminer installed does not crash, but
`extract_text(...)` raises `PDFExtractionError` with the install hint.

---

## Anchors

- v1.0 contract: [UP_M123_CONTRACT_v1.0.0.md](UP_M123_CONTRACT_v1.0.0.md)
- v1.1 contract: [UP_M123_CONTRACT_v1.1.0.md](UP_M123_CONTRACT_v1.1.0.md)
- v1.2 prereg (parent corpus): [UP_M123_PREREG_v1_2_LOCAL_LIBRARIES.md](UP_M123_PREREG_v1_2_LOCAL_LIBRARIES.md)
- PDF helper: [_scratch/pdf_to_text.py](../../../_scratch/pdf_to_text.py)
- Corpus index: [UP_M123_CORPUS_INDEX.json](UP_M123_CORPUS_INDEX.json)
