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

Current phase: **Phase E operations**.

The mission concept, Phase A requirements, Phase B architecture, Phase C prototype, and Phase D core verification are set. The current work is Phase E: larger corpora, batch readiness, and operational plumbing. See [docs/phase-status.md](docs/phase-status.md) for the live phase readout.

Each document records its source name in `documents/documents.json`; [DATA_NOTICE.md](DATA_NOTICE.md) provides the corresponding provenance and license disclosure.

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
│   ├── logging.md
│   ├── phase-d-verification.md
│   └── phase-status.md
├── documents/
│   ├── acme_invoice.txt
│   ├── documents.json
│   └── invoice-batch-1-sample-20-v0.1/
├── corpora/
│   ├── 0.1.0.json
│   ├── 0.2.0.json
│   ├── 0.3.0.json
│   └── corpora.json
├── src/
│   └── single_pass_parsing_ranker/
│       ├── __init__.py
│       ├── cli.py
│       ├── data.py
│       ├── llm.py
│       ├── models.py
│       ├── normalize.py
│       ├── observability.py
│       ├── prompts.py
│       ├── runner.py
│       ├── scoring.py
│       └── storage.py
└── tests/
    ├── .gitkeep
    ├── test_corpus.py
    └── test_models.py
```

## Core Concepts

- **Document registry:** a flat list of source documents, addressed by stable UUIDs and protected by checksums.
- **Corpus table:** a flat list of corpus UUIDs and versions.
- **TestCase:** one corpus row with `corpus_id`, `test_case_id`, `document_id`, `data_model`, `prompt`, and `ground_truth`.
- **Run:** one model/corpus evaluation, including provider settings, document text strategy, status, and reproducibility metadata.
- **ParseAttempt:** one model's single-pass output for one document case.
- **FieldComparison:** field-level comparison between expected JSON and model JSON, using exact matching by default and schema-owned fuzzy text comparison where the corpus opts in.
- **RunTestCase:** one model call and result for one corpus test case inside a run.

## Data Contract

Raw documents and corpus metadata live in separate flat tables. The data model is baked into each versioned test-case row, so a corpus file is self-contained apart from the fixed document registry. If a row is added, removed, or corrected, or if any row's `prompt`, `data_model`, or `ground_truth` changes, that creates a new corpus version.

Each `TestCase` row has this shape:

- `test_case_id`: stable UUID for this evaluation row.
- `corpus_id`: corpus UUID this row belongs to.
- `document_id`: fixed source document UUID to parse.
- `data_model`: row-level extraction schema.
- `prompt`: reusable extraction instruction for the model attempt.
- `ground_truth`: expected JSON object for that document and data model.

The fixed document registry is checksum-protected so source document drift is caught before evaluation. Test cases reference corpora and documents by id, while the data model stays inside the corpus row.

The evaluation semantics are defined in [docs/evaluation-contract.md](docs/evaluation-contract.md). In short: ground truth and model output are normalized through the row's data model, field-level exact match is the default scoring policy, schema-owned fuzzy text comparison can opt in noisy text fields, malformed returned output earns a zero, and infrastructure failures are logged as failed runs.

Implemented contract pieces:

- `documents/documents.json` is a flat list of fixed source documents, paths, and checksums.
- `corpora/corpora.json` is a flat corpus table.
- `corpora/0.1.0.json` is a flat test-case table with inline data models.
- `corpora/0.2.0.json` is a 21-row corpus: the existing ACME text case plus 20 source-image invoice cases.
- `corpora/0.3.0.json` is a 2-row mini corpus for resolver smoke checks: ACME text plus one source-image invoice case.
- `documents/invoice-batch-1-sample-20-v0.1/` keeps the 20 source `.jpg` invoice images.
- `src/single_pass_parsing_ranker/data.py` loads the normalized tables, validates references, checks registry links, and detects document SHA-256 drift.
- `src/single_pass_parsing_ranker/models.py` defines `Corpus`, `Document`, `TestCase`, run row, run-test-case row, layout/OCR strategy enums, status enums, failure taxonomy, and storage schemas.
- `src/single_pass_parsing_ranker/document_text_resolution.py` resolves fixed documents into model-ready text and hashes the exact text sent to the prompt.
- `tests/test_corpus.py` covers the example corpus, document reading, data-model validation, checksum drift, and unknown document references.
- `tests/test_models.py` covers the run/result storage models and generated storage schemas.

Phase C is complete for the current scope. Pieces now in place:

- Prompt assembly.
- Readable terminal output, raw JSONL terminal output, and append-only local result storage.
- LiteLLM structured-output call wrapper.
- Response JSON parsing plus shared JSON Schema normalization for output and ground truth.
- Field-level exact-match scoring with opt-in fuzzy text comparison.
- Sequential evaluator runner glue.
- CLI entry point.
- Live Gemini smoke test over `corpora/0.1.0.json`.

Deferred hardening:

- File-backed JSONL storage for runs and run test cases.
- Markdown export for publishable summaries.

The current runner resolves documents into model-ready UTF-8 text. Plain `.txt` files pass through unchanged, PDFs use native text extraction first with OCR fallback, and image files use PyTesseract OCR.

## Local Credentials

Copy `.env.example` to `.env` and fill in local provider credentials. The real `.env` file is gitignored.

For Gemini/LiteLLM runs:

```bash
GEMINI_API_KEY=...
```

The runner loads `.env` into the process environment when present, but does not store API keys in result rows. Provider credentials should not be passed through `model_settings`.

Run the example corpus with readable terminal output:

```bash
poetry run single-pass-ranker run \
  --model gemini/gemini-2.5-flash \
  --provider gemini \
  --corpus corpora/0.1.0.json \
  --temperature 0
```

The runner defaults to `--layout-to-text-strategy native_layout_to_text` and `--ocr-strategy pytesseract`. PyTesseract requires the `tesseract` system binary to be installed locally.

Every CLI run appends results to `runs/runs.jsonl`, `runs/run_test_cases.jsonl`, and `runs/field_comparisons.jsonl`. Use `--output-dir PATH` to store them elsewhere. The `runs/` directory is ignored by Git.

## Logging

The CLI writes operational logs to `stderr`, independently of result output on `stdout`. Logs default to human-readable `INFO` output. Cloud deployments can emit one JSON object per line:

```bash
SPPR_LOG_FORMAT=json SPPR_LOG_LEVEL=INFO \
  poetry run single-pass-ranker run \
  --model gemini/gemini-2.5-flash \
  --provider gemini \
  --corpus corpora/0.1.0.json
```

The package remains vendor-neutral. A deployment-level Datadog Agent, OpenTelemetry Collector, or other router can filter and enrich these events before forwarding them. See [docs/logging.md](docs/logging.md) for the event contract, safe-field policy, and recommended forwarding allowlist.

Print raw JSON rows instead:

```bash
poetry run single-pass-ranker run \
  --model gemini/gemini-2.5-flash \
  --provider gemini \
  --corpus corpora/0.1.0.json \
  --temperature 0 \
  --output-format jsonl
```

## Development

Install dependencies:

```bash
poetry install
```

Run `poetry install` again after script entry-point changes so `poetry run single-pass-ranker` is installed cleanly.

Install the local OCR binary for image/scanned-PDF document resolution:

```bash
brew install tesseract
```

Run tests:

```bash
poetry run python -m unittest discover -s tests
```

Phase D verification details live in [docs/phase-d-verification.md](docs/phase-d-verification.md). The automated suite does not call live model providers; live smoke checks are manual CLI runs.

## Current Status

Pre-Phase A, Phase A, and Phase B are complete for the current scope: the corpus/document contract, evaluation semantics, and evaluator architecture are documented and represented in code.

Phase C completed the first runnable evaluator: one run describes one model/corpus pair, with one `run_test_cases` row per corpus case. Phase D verified the core scoring, metadata, CLI, and failure-mode behavior. Phase E has added larger corpora plus OCR/native document text resolution; storage, batch operations, and model-native multimodal handling are next.
