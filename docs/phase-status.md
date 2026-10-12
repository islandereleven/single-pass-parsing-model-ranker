# Phase Status

Current phase: **Phase E readiness**.

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
- `load_corpus` loads `TestCase` rows, checks registry links, confirms document existence, and detects checksum drift.
- Tests cover loading, document reading, checksum drift, and unknown document references.
- [evaluation-contract.md](evaluation-contract.md) defines scoring, normalization, zero-score runs, failed runs, and the first result record shape.

Deferred Phase A refinements:

- Define opt-in fuzzy matching metadata once the ground-truth dataset needs it.
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
- Field-level exact-match scoring is implemented.
- Sequential evaluator runner glue is implemented.
- Local `.env` loading is implemented for provider credentials, while `model_settings` rejects secret-like keys.
- Runner terminal output defaults to readable summaries, with raw JSONL available through `output_format="jsonl"`.
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

Status: **ready to start**.

Run batches in the cloud and publish rankings on islandereleven.com.

### Phase F: Evolution

Add multimodal inputs, agentic parsing tracks, domain-specific scoring, and larger public benchmark sets.
