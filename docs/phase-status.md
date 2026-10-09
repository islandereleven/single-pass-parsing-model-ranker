# Phase Status

Current phase: **Phase B entry**.

The project has moved beyond mission concept and requirements capture. The document/corpus contract exists as files, code, and tests, and the evaluation semantics are documented in [evaluation-contract.md](evaluation-contract.md). The next step is to design the model-running and ranking pipeline around that contract.

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

Status: **starting**.

Phase B should design the evaluator pipeline around the existing corpus contract:

1. Load corpus version.
2. Load fixed document text by `test_case_id`.
3. Build the model call from the row-level `prompt`, document text, and row-level `data_model`.
4. Run one model call through LiteLLM.
5. Parse model output as JSON.
6. Normalize model output and ground truth through the row data model.
7. Score normalized output against normalized ground truth.
8. Record latency, token usage, estimated cost, raw response metadata, run status, and failure reason.
9. Export rankings for website display.

Phase B exit criteria:

- Model candidate representation is defined.
- Prompt contract is defined.
- LiteLLM call boundary is defined.
- Attempt/result schema is defined.
- Scoring interface is defined.
- Ranking output format is defined.
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
