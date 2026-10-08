# Single-Pass Parsing Model Ranker

NASA-inspired evaluation infrastructure for ranking how well LLMs parse documents into structured data in a single call.

This package is being built for experiments, ranking tables, and technical content on [islandereleven.com](https://islandereleven.com). The first mission is deliberately narrow: feed each model a text representation of a document plus a Pydantic schema, collect one JSON response, and compare that response against a known-good reference JSON.

## Mission

Build a repeatable evaluation system that ranks language models by their ability to perform single-pass document parsing.

The system should answer:

- Which models produce the most accurate structured output from document text?
- How much latency and cost does each model trade for that accuracy?
- Which schemas, document types, and extraction tasks expose model weaknesses?
- Which results are interesting enough to publish as rankings, writeups, and experiments on islandereleven.com?

## Mission Constraints

- **Single pass first:** one LLM call per document-case/model pair.
- **Text input first:** PDFs, HTML, DOCX, OCR text, and other sources are converted into a canonical text format before evaluation.
- **Schema-driven output:** each task provides a Pydantic model or compatible schema that defines the expected JSON shape.
- **Reference comparison:** model output is scored against a ground-truth JSON fixture.
- **Accuracy primary:** parsing accuracy is the mission-critical metric.
- **Latency and price secondary:** speed and cost are tracked, reported, and used as tie-breakers.
- **Multimodal later:** direct PDF/image or agentic parsing can be added after the text-only baseline is trustworthy.

## NASA-Inspired Lifecycle

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
- Pydantic schema handoff is defined.
- Metrics are specified for accuracy, latency, and price.
- Failure modes are classified.

### Phase B: Architecture

Design the ranking pipeline and package boundaries.

Exit criteria:

- Converters produce canonical document text.
- Model adapters expose a common parse interface.
- Scorers compare model JSON to reference JSON.
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
├── src/
│   └── single_pass_parsing_ranker/
│       ├── __init__.py
│       ├── metrics.py
│       ├── models.py
│       └── ranking.py
└── tests/
    └── test_metrics.py
```

## Core Concepts

- **DocumentCase:** one document-text input, one schema name, and one reference JSON object.
- **ModelCandidate:** one LLM configuration being evaluated.
- **ParseAttempt:** one model's single-pass output for one document case.
- **AccuracyScore:** field-level comparison between expected JSON and model JSON.
- **RankedResult:** scored output ready for leaderboard rendering.

## Development

Install the package in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

## Current Status

Pre-Phase A is underway. The first implementation focuses on the evaluator core, not provider integrations. Model adapters, document converters, cloud storage, and website publishing will come after the scoring contract is stable.
