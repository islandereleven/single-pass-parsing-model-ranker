# Single-Pass Parsing Model Ranker

Evaluation infrastructure for ranking how well LLMs parse documents into structured data in a single call.

This project is managed using a NASA systems-design perspective: clear mission definition, phased requirements, architecture gates, verification, and operational readiness. It is not a NASA project.

This package is being built for experiments, ranking tables, and technical content on [islandereleven.com](https://islandereleven.com). The first mission is deliberately narrow: feed each model a text representation of a fixed document plus a row-level data model, collect one JSON response, and compare that response against the row's ground truth.

## Mission

Build a repeatable evaluation system that ranks language models by their ability to perform single-pass document parsing.

The system should answer:

- Which models produce the most accurate structured output from document text?
- How much latency and cost does each model trade for that accuracy?
- Which data models, document types, and extraction tasks expose model weaknesses?
- Which results are interesting enough to publish as rankings, writeups, and experiments on islandereleven.com?

## Mission Constraints

- **Single pass first:** one LLM call per document-case/model pair.
- **Text input first:** PDFs, HTML, DOCX, OCR text, and other sources are converted into a canonical text format before evaluation.
- **Data-model-driven output:** each test case provides a JSON-compatible, Pydantic-compatible data model that defines the expected output shape.
- **Ground-truth comparison:** model output is scored against the test case's expected JSON object.
- **Accuracy primary:** parsing accuracy is the mission-critical metric.
- **Latency and price secondary:** speed and cost are tracked, reported, and used as tie-breakers.
- **Multimodal later:** direct PDF/image or agentic parsing can be added after the text-only baseline is trustworthy.

## Systems Design Lifecycle

Current phase: **Phase B entry**.

The mission concept and Phase A requirements are set. The first evaluation data contract now exists in code and fixtures, and the scoring semantics are documented. The current work is Phase B architecture for model execution, scoring, result storage, and website publishing. See [docs/phase-status.md](docs/phase-status.md) for the live phase readout.

### Pre-Phase A: Mission Concept

Define the ranking mission, target audience, and first experiment class.

Exit criteria:

- Mission objective is written down.
- Single-pass constraint is explicit.
- Initial document families and model/provider settings are named.
- Website-facing ranking output is sketched.

### Phase A: Requirements

Define the evaluation contract.

Exit criteria:

- Document case format exists.
- Expected JSON fixture format exists.
- Data model handoff is defined.
- Metrics are specified for accuracy, latency, and price.
- Failure modes are classified.

### Phase B: Architecture

Design the ranking pipeline and package boundaries.

Exit criteria:

- Converters produce canonical document text.
- Model adapters expose a common parse interface.
- Scorers compare model JSON to ground truth.
- Ranking output is serializable for the website.
- Experiment runs are reproducible.

### Phase C: Prototype and Build

Implement the first working evaluator.

Exit criteria:

- Package can load cases, run configured models, score outputs, and persist results.
- Local tests cover scoring and ranking behavior.
- Example cases demonstrate the workflow.
- Results can be exported as JSON or Markdown.

### Phase D: Verification

Validate the evaluator against known cases.

Exit criteria:

- Golden fixtures pass.
- Invalid JSON, missing fields, hallucinated fields, and type mismatches are scored predictably.
- Latency and price capture are verified.
- Ranking output is stable enough to publish.

### Phase E: Operations

Run experiments in the cloud and publish rankings.

Exit criteria:

- Cloud runner executes repeatable evaluation batches.
- Results are stored with enough metadata to reproduce runs.
- islandereleven.com can display rankings.
- New document cases can be added without code changes.

### Phase F: Evolution

Expand beyond the first single-pass text baseline.

Candidate upgrades:

- Multimodal document inputs.
- Agentic or multi-call parsing tracks.
- Domain-specific score weighting.
- Human adjudication and qualitative notes.
- Public benchmark datasets.

## First Package Shape

```text
single-pass-parsing-model-ranker/
├── README.md
├── pyproject.toml
├── docs/
│   ├── evaluator-architecture.md
│   ├── evaluation-contract.md
│   └── phase-status.md
├── documents/
│   ├── acme_invoice.txt
│   └── documents.json
├── corpora/
│   └── 0.1.0.json
├── src/
│   └── single_pass_parsing_ranker/
│       ├── __init__.py
│       └── data.py
└── tests/
    ├── .gitkeep
    └── test_corpus.py
```

## Core Concepts

- **Document registry:** the fixed set of source documents, addressed by stable document IDs and protected by document checksums.
- **Corpus table:** one versioned table of test cases over the fixed document registry.
- **TestCase:** one corpus table row with `test_case_id`, `document_id`, `prompt`, `data_model`, and `ground_truth`.
- **Model config:** provider, model, and runtime settings being evaluated.
- **ParseAttempt:** one model's single-pass output for one document case.
- **AccuracyScore:** field-level comparison between expected JSON and model JSON.
- **Run:** one model evaluated against one corpus version.
- **RunTestCase:** one model call and result for one corpus test case inside a run.

## Data Contract

Raw documents live in a fixed document registry outside the versioned corpus table. A corpus version is the whole table: if a row is added, removed, or corrected, or if any row's `prompt`, `data_model`, or `ground_truth` changes, that creates a new corpus version.

Each corpus row has this shape:

- `test_case_id`: stable ID for this evaluation row.
- `document_id`: fixed source document to parse.
- `prompt`: reusable extraction instruction for the model attempt.
- `data_model`: JSON Schema-style object defining the expected output shape.
- `ground_truth`: expected JSON object for that document and data model.

The fixed document registry is checksum-protected so source document drift is caught before evaluation. The corpus table itself is versioned as a whole, so row-level changes do not silently rewrite history.

The evaluation semantics are defined in [docs/evaluation-contract.md](docs/evaluation-contract.md). In short: ground truth and model output are normalized through the row's data model, exact match is the default scoring policy, malformed returned output earns a zero, and infrastructure failures are logged as failed runs.

Implemented contract pieces:

- `documents/documents.json` declares fixed source documents, paths, and checksums.
- `corpora/0.1.0.json` declares a versioned corpus table over that document registry.
- `src/single_pass_parsing_ranker/data.py` loads the corpus, validates registry links, and checks document SHA-256 drift.
- `tests/test_corpus.py` covers the example corpus, document reading, checksum drift, and unknown document references.

Not implemented yet:

- Model/provider settings.
- LiteLLM execution wrapper.
- Prompt assembly.
- Response JSON parsing and data-model normalization.
- Accuracy scoring implementation.
- `runs` and `run_test_cases` persistence.

## Development

Install dependencies:

```bash
poetry install
```

Run tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## Current Status

Pre-Phase A is complete. Phase A is closed for the current scope: the corpus/document contract and evaluation semantics are documented, and the corpus loader has tests.

Phase B is defining the evaluator architecture: one config creates one run for one model/corpus pair, with one `run_test_cases` row per corpus case. Aggregation and model comparisons are reporting concerns outside the core evaluator.
