# Evaluator Architecture

This document defines the Phase B architecture for turning one corpus and one model/settings set into one run plus one row per test case.

The evaluator is intentionally flat:

- `runs`: one row for one model evaluated against one corpus id.
- `run_test_cases`: one row for each corpus test case attempted within that run.

The evaluator does not compute ranking rows or store aggregate scores on `runs`. Reporting, BI, or a website export layer can aggregate `run_test_cases` however it wants.

One invocation creates one run. Running multiple models, or running the same model/corpus more than once, means starting multiple independent runs outside this evaluator flow.

The Phase B models live in one file, partitioned by usage: source tables and result rows. Test cases reference documents and corpora by id, with the data model baked into the test-case row.

All `*_id` fields are UUID strings on disk and UUID values in code.

## Core Flow

1. Load or create one run.
2. Resolve exactly one provider/model/settings set for this run.
3. Resolve exactly one corpus id for the run.
4. Resolve one layout-to-text strategy and one OCR strategy for this run.
5. Create one `runs` row.
6. Load the corpus and fixed document registry.
7. Create or schedule one `run_test_cases` row per test case.
8. Execute test cases sequentially at first, with a path to parallel execution later.
9. Write each test case result to `run_test_cases`.
10. Update the `runs` row with final run status.

## `runs`

A run describes one model/corpus evaluation and its persisted status.

Minimum fields:

- provider/model identifier in the form LiteLLM expects
- corpus id
- layout-to-text strategy
- OCR strategy

Model settings should use LiteLLM defaults unless explicitly set. The first evaluator does not need a separate model registry or candidate abstraction.

Initial output storage is intentionally thin:

- print readable run progress/results to the terminal
- optionally print raw JSONL rows for `runs` and `run_test_cases`
- collect result rows for one run and write one immutable local bundle at completion

Each bundle lives under `run_id=<uuid>/` and contains `run.json`, `run_test_cases.jsonl`, and `field_comparisons.jsonl`. Detail files are written first and `run.json` is written last as the completion marker. Later, the same bundle contract can target object storage without changing result schemas.

The `runs` table records run identity, configuration, status, and reproducibility metadata. It does not store aggregate scoring or cost metrics.

Suggested fields:

- `run_id`
- provider
- model
- model settings, such as temperature, timeout, and token limits
- layout-to-text strategy
- OCR strategy
- `corpus_id`
- model/provider metadata
- run status
- failure reason, when the run fails
- start timestamp
- end timestamp
- created timestamp

Run status should answer whether the run itself completed cleanly:

- `completed`: every scheduled test case finished without provider/infrastructure failure.
- `failed`: at least one provider/infrastructure failure occurred.

Returned but malformed model output is not run failure. It is a `zero_score` test case result according to [evaluation-contract.md](evaluation-contract.md).

## `run_test_cases`

The `run_test_cases` table is the durable fact table for analysis.

Each row records one model call for one `TestCase` row:

- `run_id`
- `test_case_id`
- raw LLM response
- parsed output, when available
- normalized output, when available
- resolved document text SHA-256, when available
- score
- attempt status: `scored`, `zero_score`, or `failed`
- failure reason, when applicable
- latency
- input tokens
- output tokens
- reasoning tokens
- total tokens
- estimated cost
- start timestamp
- end timestamp

Reporting can derive all aggregates from this table:

- average score
- exact-match rate
- zero-score rate
- failure rate
- latency summaries
- token totals
- cost totals
- per-field or per-document-family breakdowns

## Per-Test-Case Execution

For each test case:

1. Resolve the fixed source document into model-ready text.
2. Build the final model call from:
   - row-level `prompt`
   - resolved document text
   - row-level `data_model`
3. Hash the resolved document text and store that hash on the result row.
4. Make exactly one LiteLLM call.
5. If document text resolution or the provider call fails, write a failed `run_test_cases` row and set the run to `failed`.
6. If the provider call succeeds:
   - Parse the returned content as JSON.
   - Normalize the parsed output through the row data model.
   - Normalize the ground truth through the row data model.
   - Compare normalized output to normalized ground truth with the row schema's field-level evaluation metadata.
   - Write the `run_test_cases` row.

Sequential execution can stop scheduling more test cases after a document-resolution or provider/infrastructure failure and mark the run failed.

Parallel execution can schedule test cases independently. If one document-resolution or provider/infrastructure failure occurs, the run is still marked failed, but completed test case rows remain useful for debugging and reporting.

## Document Text Resolution

Document text resolution is a run-level experiment variable.

The first strategy is `native_layout_to_text`. It passes `.txt` files through unchanged, extracts native PDF text with layout where available, falls back to OCR for scanned PDFs, and OCRs image inputs with PyTesseract. Every successful path records the SHA-256 of the exact text sent into the prompt.

The run also records `ocr_strategy`. The first enum value is `pytesseract`.

## Prompt Assembly

The first prompt builder should be a simple f-string.

It should include:

- row-level `prompt`
- fixed document text
- resolved data model

No system prompt split, chat-message abstraction, or prompt template framework is needed for the first prototype unless LiteLLM mechanically requires a message shape.

## LiteLLM Call

The evaluator should use a vanilla LiteLLM call with the assembled prompt and the response model/schema.

It should capture:

- returned content
- raw response metadata when available
- latency
- input tokens
- output tokens
- reasoning tokens, when available
- estimated cost, when available

No heavy wrapper or adapter layer is needed yet.

## Reporting Handoff

The evaluator writes facts. Reporting makes rankings.

Reporting may choose:

- the best valid run per model
- the only valid run per model
- the latest valid run per model
- a corpus-specific comparison
- a date-windowed comparison
- whether failed runs are excluded or shown separately

Those policies are outside the core evaluator.

## Operational Logging Boundary

The evaluator emits a small lifecycle-event vocabulary through Python's standard logging module. CLI logs go to `stderr`; readable or JSONL result rows remain on `stdout`. Logging does not change persisted result schemas.

The package owns stable event names, severity, and explicitly selected safe fields. It does not own log shipping, sampling, deployment tags, credentials, or vendor SDKs. In a cloud deployment, the container runtime should expose JSON logs to a Datadog Agent, OpenTelemetry Collector, or similar router. That deployment layer can allowlist events, enrich them with environment and release tags, and forward the selected records to Datadog.

The contract and initial forwarding policy are documented in [logging.md](logging.md).

## Implemented Package Boundaries

```text
models.py        # source and result models, sectioned by usage
data.py          # normalized source-table loading
document_text_resolution.py # document-to-model-text resolution
prompts.py       # final call assembly from row prompt, document text, data model
llm.py           # LiteLLM call boundary and response metadata extraction
normalize.py     # Pydantic-compatible data-model normalization
observability.py # human/JSON lifecycle-event formatting and package logger setup
scoring.py       # field-level comparison scoring after normalization
storage.py       # immutable per-run result bundle writes
runner.py        # sequential evaluator orchestration
cli.py           # thin argparse command wrapper
```

Design boundaries:

- `models.py` owns the shared source and result record shapes.
- `data.py` loads normalized source tables and validates references, but does not know about LiteLLM or scoring.
- `prompts.py` does not call models.
- `llm.py` does not score outputs.
- `scoring.py` does not know about provider responses.
- `storage.py` owns immutable per-run bundle writes; reading is a reporting/resume concern for later.
- `observability.py` owns the vendor-neutral log contract; deployment owns collection and forwarding.
- `runner.py` coordinates loading, prompting, calling, normalization, scoring, and result row emission.
- `cli.py` only maps command-line arguments into `run_evaluation`.
- Aggregation, ranking, and comparison reporting live outside the core package.

## Phase B Exit Criteria

Phase B is complete. These contracts are defined well enough to implement:

- run shape
- model/settings fields
- `runs` record
- `run_test_cases` record
- final prompt assembly contract
- vanilla LiteLLM call shape
- output classification rules
- run status rules
- reporting handoff fields
