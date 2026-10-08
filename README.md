# Single-Pass Parsing Model Ranker

NASA-inspired evaluation infrastructure for ranking how well LLMs parse documents into structured data in a single call.

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
- **Data-model-driven output:** each test case provides a JSON-compatible data model that defines the expected output shape.
- **Ground-truth comparison:** model output is scored against the test case's expected JSON object.
- **Accuracy primary:** parsing accuracy is the mission-critical metric.
- **Latency and price secondary:** speed and cost are tracked, reported, and used as tie-breakers.
- **Multimodal later:** direct PDF/image or agentic parsing can be added after the text-only baseline is trustworthy.

## NASA-Inspired Lifecycle

Current phase: **Phase A exit / Phase B entry**.

The mission concept is set, and the first evaluation data contract now exists in code and fixtures. The current work is to stabilize that contract, then move into the architecture for model execution, scoring, result storage, and website publishing. See [docs/phase-status.md](docs/phase-status.md) for the live phase readout.

### Pre-Phase A: Mission Concept

Define the ranking mission, target audience, and first experiment class.

Exit criteria:

- Mission objective is written down.
- Single-pass constraint is explicit.
- Initial document families and model candidates are named.
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

- Package can load cases, run candidates, score outputs, and produce rankings.
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
- **TestCase:** one corpus table row with `test_case_id`, `document_id`, `data_model`, and `ground_truth`.
- **ModelCandidate:** one LLM configuration being evaluated.
- **ParseAttempt:** one model's single-pass output for one document case.
- **AccuracyScore:** field-level comparison between expected JSON and model JSON.
- **RankedResult:** scored output ready for leaderboard rendering.

## Data Contract

Raw documents live in a fixed document registry outside the versioned corpus table. A corpus version is the whole table: if a row is added, removed, or corrected, or if any row's `data_model` or `ground_truth` changes, that creates a new corpus version.

Each corpus row has this shape:

- `test_case_id`: stable ID for this evaluation row.
- `document_id`: fixed source document to parse.
- `data_model`: JSON Schema-style object defining the expected output shape.
- `ground_truth`: expected JSON object for that document and data model.

The fixed document registry is checksum-protected so source document drift is caught before evaluation. The corpus table itself is versioned as a whole, so row-level changes do not silently rewrite history.

Implemented contract pieces:

- `documents/documents.json` declares fixed source documents, paths, and checksums.
- `corpora/0.1.0.json` declares a versioned corpus table over that document registry.
- `src/single_pass_parsing_ranker/data.py` loads the corpus, validates registry links, and checks document SHA-256 drift.
- `tests/test_corpus.py` covers the example corpus, document reading, checksum drift, and unknown document references.

Not implemented yet:

- Model candidate registry.
- LiteLLM execution wrapper.
- Prompt assembly.
- Response JSON parsing and schema validation.
- Accuracy scoring.
- Result persistence and leaderboard export.

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

Pre-Phase A is complete. Phase A is at its exit gate: the corpus/document contract has a working implementation and tests, but the project still needs a short requirements pass over scoring and failure modes before the gate is fully closed.

Phase B is starting around the evaluator architecture: LiteLLM model calls, prompt construction, output validation, scoring, ranking, result storage, and export formats for islandereleven.com.
