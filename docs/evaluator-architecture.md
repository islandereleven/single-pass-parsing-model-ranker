# Evaluator Architecture

This document defines the Phase B architecture for turning one corpus and one model config into one run plus one row per test case.

The evaluator is intentionally flat:

- `runs`: one row for one model evaluated against one corpus version.
- `run_test_cases`: one row for each corpus test case attempted within that run.

The evaluator does not compute ranking rows or store aggregate scores on `runs`. Reporting, BI, or a website export layer can aggregate `run_test_cases` however it wants.

One invocation creates one run. Running multiple models, or running the same model/corpus more than once, means starting multiple independent runs outside this evaluator flow.

## Core Flow

1. Load evaluator config.
2. Resolve exactly one provider/model/settings config for this run.
3. Resolve corpus version, defaulting to latest when omitted.
4. Create one `runs` row.
5. Load the corpus and fixed document registry.
6. Create or schedule one `run_test_cases` row per test case.
7. Execute test cases sequentially at first, with a path to parallel execution later.
8. Write each test case result to `run_test_cases`.
9. Update the `runs` row with final run status.

## `runs`

The `runs` table records run identity, configuration, status, and reproducibility metadata. It does not store aggregate scoring or cost metrics.

Suggested fields:

- `run_id`
- provider
- model
- model settings, such as temperature, timeout, and token limits
- `corpus_id`
- `corpus_version`
- model/provider metadata
- config snapshot
- run status
- failure reason, when the run fails
- failure `test_case_id`, when applicable
- start timestamp
- end timestamp
- created timestamp

Run status should answer whether the run itself completed cleanly:

- `completed`: every scheduled test case finished without provider/infrastructure failure.
- `failed`: at least one provider/infrastructure failure occurred.

Returned but malformed model output is not run failure. It is a `zero_score` test case result according to [evaluation-contract.md](evaluation-contract.md).

## `run_test_cases`

The `run_test_cases` table is the durable fact table for analysis.

Each row records one model call for one corpus row:

- `run_id`
- `test_case_id`
- `document_id`
- prompt sent to the model
- data model sent to the model
- document text or document reference
- raw LLM response
- parsed output, when available
- normalized output, when available
- normalized ground truth
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

1. Read the fixed document text.
2. Build the final model call from:
   - row-level `prompt`
   - document text
   - row-level `data_model`
3. Make exactly one LiteLLM call.
4. If the provider call fails, write a failed `run_test_cases` row and set the run to `failed`.
5. If the provider call succeeds:
   - Parse the returned content as JSON.
   - Normalize the parsed output through the row data model.
   - Normalize the ground truth through the row data model.
   - Compare normalized output to normalized ground truth.
   - Write the `run_test_cases` row.

Sequential execution can stop scheduling more test cases after a provider/infrastructure failure and mark the run failed.

Parallel execution can schedule test cases independently. If one provider/infrastructure failure occurs, the run is still marked failed, but completed test case rows remain useful for debugging and reporting.

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

## Proposed Package Boundaries

```text
data.py          # existing corpus/document loading
config.py        # evaluator config and corpus selection
prompts.py       # final call assembly from row prompt, document text, data model
llm.py           # LiteLLM call boundary and response metadata extraction
outcomes.py      # scored / zero_score / failed taxonomy
normalize.py     # Pydantic-compatible data-model normalization
scoring.py       # exact-match scoring after normalization
results.py       # runs and run_test_cases persistence
```

Design boundaries:

- `data.py` does not know about LiteLLM or scoring.
- `config.py` defines one run config for one provider/model/corpus combination.
- `prompts.py` does not call models.
- `llm.py` does not score outputs.
- `scoring.py` does not know about provider responses.
- `results.py` owns persistence for `runs` and `run_test_cases`.
- Aggregation, ranking, and comparison reporting live outside the core package.

## Phase B Exit Criteria

Phase B is complete when these contracts are defined well enough to implement:

- evaluator config shape
- model config fields
- `runs` record
- `run_test_cases` record
- final prompt assembly contract
- LiteLLM call boundary
- output classification rules
- run status rules
- reporting handoff fields
