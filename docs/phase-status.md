# Phase Status

Current phase: **Phase E operations**.

The project has moved beyond mission concept, requirements capture, architecture definition, the first working prototype, and core evaluator verification. The document/corpus contract exists as files, code, and tests, the evaluation semantics are documented in [evaluation-contract.md](evaluation-contract.md), the evaluator architecture is defined in [evaluator-architecture.md](evaluator-architecture.md), the Phase C prototype runs end to end against Gemini, and Phase D verifies the core scoring/failure contract.

## Completed Gates

### Pre-Phase A: Mission Concept

Status: **complete**.

Completed evidence:

- Mission objective is defined: rank LLMs on single-pass document-to-JSON parsing.
- First operating constraint is defined: one LLM call per document-case/model pair.
- Input strategy is defined: canonical text first, multimodal later.
- Primary metric is defined: parsing accuracy.
- Secondary metrics are defined: latency and price.
- Publishing target is defined: rankings and experiment content for islandereleven.com.

### Phase A: Requirements

Status: **complete for current scope**.

Completed evidence:

- `documents/documents.json` defines the fixed source document registry.
- `corpora/corpora.json` defines the corpus table.
- `corpora/0.1.0.json` defines the first versioned test-case table.
- Test-case rows include `corpus_id`, `test_case_id`, `document_id`, `data_model`, `prompt`, and `ground_truth`.
- All `*_id` fields are UUIDs.
- Document files are protected by SHA-256 checksums.
- `load_corpus` accepts explicit corpus and document-registry locations, loads them from local paths or object-storage URIs, and checks registry links without assuming a shared directory layout.
- Document resolution reads the selected source once and validates its checksum before the model call.
- Tests cover local and remote loading, document reading, checksum drift, and unknown document references.
- [evaluation-contract.md](evaluation-contract.md) defines scoring, normalization, zero-score runs, failed runs, and the first result record shape.

Deferred Phase A refinements:

- Expand opt-in comparison metadata as the ground-truth dataset needs it.
- Decide how strongly latency and price affect final ranking versus being displayed as secondary columns after the first results exist.
- Decide whether `data_model` remains JSON Schema only or whether authored Pydantic models become a first-class source format. Phase B keeps inline JSON Schema as the corpus source format and validates that contract in code.

### Phase B: Architecture

Status: **complete**.

Completed evidence:

- Evaluator flow is defined around one run for one model/corpus pair.
- Model/provider settings live on the `Run` row.
- `Corpus`, `TestCase`, `Document`, `Run`, and `RunTestCase` have code-level models in one file.
- All source and result ids are UUIDs.
- Prompt assembly contract is defined.
- Vanilla LiteLLM call shape is defined.
- Attempt/result schema is defined.
- `runs` storage format is defined.
- `run_test_cases` storage format is defined.
- Reporting handoff fields are defined.
- Reproducibility metadata is limited to explicit run/model fields.
- Returned but malformed output is classified as `zero_score`, not run failure.
- Provider/infrastructure failure marks the run failed.
- Reporting aggregates and compares `run_test_cases` outside the core evaluator.

### Phase C: Prototype and Build

Status: **complete for current scope**.

Phase C built the first runnable evaluator over the existing example corpus.

Phase C exit criteria:

- Package can load cases, run configured models, score outputs, and emit result rows.
- Local tests cover scoring and ranking behavior.
- Example cases demonstrate the workflow.
- Results can be exported as raw JSONL through the CLI output mode.

Phase C progress:

- Prompt assembly is implemented.
- Print-backed JSON row emission for `runs` and `run_test_cases` is implemented.
- LiteLLM structured-output call boundary is implemented.
- Response JSON parsing is implemented.
- Shared JSON Schema normalization for output and ground truth is implemented.
- Field-level exact-match scoring is implemented, with schema-owned fuzzy text comparison for noisy text fields.
- Sequential evaluator runner glue is implemented.
- Local `.env` loading is implemented for provider credentials, while `model_settings` rejects secret-like keys.
- Runner terminal output defaults to readable summaries, with raw JSONL available through `output_format="jsonl"` and result output suppression through `output_format="quiet"`.
- CLI entry point is implemented as `single-pass-ranker run`.
- Live Gemini smoke test over `corpora/0.1.0.json` completed with a scored result.

Deferred hardening:

- File-backed JSONL storage for runs and run test cases.
- Markdown export for publishable summaries.

### Phase D: Verification

Status: **complete for current scope**.

Validate scoring and failure handling against golden fixtures. See [phase-d-verification.md](phase-d-verification.md) for the verification checklist and manual CLI smoke commands.

Phase D progress:

- Scoring verification tests cover scalar mismatches, nested missing/extra fields, list index mismatches, list length drift, list order, and scalar equality after normalization.
- Runner verification tests cover empty output, schema-invalid output, provider-side structured validation errors, missing provider responses, provider failure classification, invalid ground-truth fixtures, and parseable JSONL row emission.
- Schema verification tests cover missing required fields, wrong field types, extra hallucinated keys, and refusal/prose output classification.
- Metadata verification tests cover LiteLLM usage/cost extraction shapes, direct and nested reasoning-token fields, runner metadata copying, null behavior when provider metadata is missing, and pretty output summaries without raw response leakage.
- Local CLI QA covers help output, invalid output-format rejection, and one live Gemini pretty-output smoke run over `corpora/0.1.0.json`.

Deferred verification hardening:

- Larger multi-document corpora.
- Published ranking/report output validation.
- File-backed storage/resume validation.

## Active Work

### Phase E: Operations

Status: **in progress**.

Run larger batches and prepare the evaluator for repeatable operations.

Phase E checklist:

- [x] 1. Corpus growth: add a larger local corpus and register its fixed documents.
- [x] 2. Conversion path for non-text document rows.
- [x] 3. Structural data-source disclosure for public, generated, and hand-authored corpora.
- [x] 4. File-backed run storage for repeatable local batches.
- [ ] 5. Batch execution ergonomics for larger local runs.

Phase E progress:

- Added `0.2.0.json`, a 21-row corpus.
- Added `0.3.0.json`, a 2-row mini corpus for document text resolution smoke checks.
- Included the existing ACME text case in `0.2.0`.
- Registered 20 source invoice images in `documents/documents.json` with checksums.
- Kept generated OCR text files out of the corpus and document registry.
- Added run-level `layout_to_text_strategy` and `ocr_strategy` tracking.
- Added document text resolution for `.txt`, native-text PDFs, scanned PDFs, and image files.
- Added per-attempt `document_text_sha256` for the exact text sent to the model.
- Added `FieldComparison` rows for field-level scoring evidence.
- Added schema-owned `evaluation.comparison` metadata with `fuzzy_text` for noisy text fields.
- Added document-level source names and [../DATA_NOTICE.md](../DATA_NOTICE.md) for provenance and license disclosure.
- Added immutable local or S3 run bundles containing the final run, test-case results, and field-comparison evidence.

Local smoke examples on `corpora/0.3.0.json`:

| Model | Image-case score | Image-case mismatches | Image-case latency | Image-case cost | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemini/gemini-2.5-flash` | `0.714` | `10` | `6464ms` | `$0.004245` | Picked net-worth line totals before the prompt/schema fix clarified numeric amount fields. |
| `gemini/gemini-3.5-flash` | `0.743` | `9` | `37505ms` | `$0.031306` | Same net-worth pattern as 2.5, with one fewer text mismatch. |
| `gemini/gemini-3.1-pro-preview` | `0.886` | `4` | `24161ms` | `$0.050600` | Resolved the gross-worth line totals; remaining misses were address whitespace/text noise and OCR's `GB04`/`GBO4` confusion. |

These are local smoke examples, not ranking exports. The text-field scores will change after `fuzzy_text` metadata because address whitespace and near-match descriptions now receive partial or full field credit.

Current boundary:

- PyTesseract OCR requires the `tesseract` system binary.
- Multimodal model-native image/PDF input remains future work.

### Phase F: Evolution

Add multimodal inputs, agentic parsing tracks, domain-specific scoring, and larger public benchmark sets.
