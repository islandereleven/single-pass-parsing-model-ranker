# Phase Status

Current phase: **Phase B closeout**.

The project has moved beyond mission concept and requirements capture. The document/corpus contract exists as files, code, and tests, the evaluation semantics are documented in [evaluation-contract.md](evaluation-contract.md), and the evaluator architecture is being defined in [evaluator-architecture.md](evaluator-architecture.md).

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
- `corpora/0.1.0.json` defines the first versioned corpus table.
- Corpus rows include `test_case_id`, `document_id`, `prompt`, `data_model`, and `ground_truth`.
- Document files are protected by SHA-256 checksums.
- `load_corpus` loads corpus rows, checks registry links, confirms document existence, and detects checksum drift.
- Tests cover loading, document reading, checksum drift, and unknown document references.
- [evaluation-contract.md](evaluation-contract.md) defines scoring, normalization, zero-score runs, failed runs, and the first result record shape.

Deferred Phase A refinements:

- Define opt-in fuzzy matching metadata once the ground-truth dataset needs it.
- Decide how strongly latency and price affect final ranking versus being displayed as secondary columns after the first results exist.
- Decide whether `data_model` remains JSON Schema only or whether Pydantic models become a first-class source format.

## Active Work

### Phase B: Architecture

Status: **near closeout**.

Phase B should design the evaluator pipeline around the existing corpus contract:

1. Load evaluator config.
2. Resolve one provider/model/settings config for the run.
3. Resolve corpus version, defaulting to latest when omitted.
4. Create one `runs` row.
5. Execute or schedule one `run_test_cases` row per corpus test case.
6. Treat returned but malformed output as `zero_score`, not run failure.
7. Mark the run failed if any provider/infrastructure failure occurs.
8. Let reporting aggregate and compare `run_test_cases` outside the core evaluator. Multiple models are just multiple independent runs.

Phase B exit criteria:

- Model/provider settings are defined.
- Evaluator config representation is defined.
- Prompt contract is defined.
- Vanilla LiteLLM call shape is defined.
- Attempt/result schema is defined.
- `runs` storage format is defined.
- `run_test_cases` storage format is defined.
- Reporting handoff fields are defined.
- Reproducibility metadata is defined.

## Later Phases

### Phase C: Prototype and Build

Build the first runnable evaluator over the existing example corpus.

### Phase D: Verification

Validate scoring and failure handling against golden fixtures.

### Phase E: Operations

Run batches in the cloud and publish rankings on islandereleven.com.

### Phase F: Evolution

Add multimodal inputs, agentic parsing tracks, domain-specific scoring, and larger public benchmark sets.
