# Phase Status

Current phase: **Phase C entry**.

The project has moved beyond mission concept, requirements capture, and architecture definition. The document/corpus contract exists as files, code, and tests, the evaluation semantics are documented in [evaluation-contract.md](evaluation-contract.md), and the evaluator architecture is defined in [evaluator-architecture.md](evaluator-architecture.md). Phase C now starts the first runnable evaluator.

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

## Active Work

### Phase C: Prototype and Build

Status: **ready to start**.

Phase C should build the first runnable evaluator over the existing example corpus.

Phase C exit criteria:

- Package can load cases, run configured models, score outputs, and persist results.
- Local tests cover scoring and ranking behavior.
- Example cases demonstrate the workflow.
- Results can be exported as JSON or Markdown.

Initial Phase C work:

- Implement prompt assembly.
- Implement LiteLLM call boundary.
- Implement response JSON parsing.
- Implement data-model normalization.
- Implement exact-match scoring.
- Implement JSONL persistence for `runs` and `run_test_cases`.

## Later Phases

### Phase D: Verification

Validate scoring and failure handling against golden fixtures.

### Phase E: Operations

Run batches in the cloud and publish rankings on islandereleven.com.

### Phase F: Evolution

Add multimodal inputs, agentic parsing tracks, domain-specific scoring, and larger public benchmark sets.
