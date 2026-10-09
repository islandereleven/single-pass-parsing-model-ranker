# Evaluation Contract

This document defines how a single model attempt becomes a score, a zero, or a failed run.

The goal is to keep the first evaluator brutally simple: one document, one row-level data model, one model call, one output, one result record. No retries for now.

## Inputs

Each attempt is tied to one corpus row:

- `test_case_id`
- `document_id`
- `prompt`
- `data_model`
- `ground_truth`

The evaluator sends the row-level prompt, fixed document text, and row-level data model to one model candidate through LiteLLM. The data model may be represented as JSON Schema in the corpus and normalized through a Pydantic-compatible model in the evaluator.

## Normalization Policy

Both sides of the comparison must pass through the same model contract:

1. Normalize `ground_truth` through the row's data model.
2. Parse the LLM response as JSON.
3. Normalize the parsed LLM output through the same row data model.
4. Compare normalized output to normalized ground truth.

The Pydantic-compatible data model is the authority for types, required fields, nested shapes, and any allowed coercion. If the ground truth cannot normalize through its own row data model, the corpus row is invalid and should be fixed before the run is trusted.

## Scoring Policy

Default policy: **exact match after normalization**.

For the first version, exact match means the normalized model output must equal the normalized ground truth for the fields being scored. Numeric, date, enum, list, and nested object behavior should come from the data-model normalization step before comparison.

Fuzzy matching is allowed later, but only as an explicit exception. The corpus should eventually be able to mark particular fields as fuzzy-matchable, but fuzzy matching is not the default rule.

## Outcome Taxonomy

Every attempt has one of three run statuses.

### `scored`

Use `scored` when:

- The provider call completes.
- The model returns output.
- The output parses as JSON.
- The output normalizes through the row data model.
- The normalized output can be compared to normalized ground truth.

The score is computed by the active scoring policy.

### `zero_score`

Use `zero_score` when the provider call completes and the model returns output, but the output is unusable for the requested extraction.

Examples:

- Invalid JSON.
- Wrong top-level shape.
- Missing required fields that prevent normalization.
- Wrong field types that prevent normalization.
- Malformed nested objects or lists.
- Refusal text or other prose instead of the requested JSON.
- Parseable JSON that does not fit the expected data model.

The score is `0`. This counts against model parsing performance.

### `failed`

Use `failed` when the run itself does not complete in a way that gives the model a usable attempt.

Examples:

- Provider/API error.
- Timeout.
- Rate limit.
- Authentication or configuration error.
- Network failure.
- No provider response.

The score is `null`. Failed runs are reported separately as reliability data and do not become zero-score parsing attempts.

## No-Retry Rule

The first evaluator does not retry failed runs.

Retries can be added later as a separate evaluation track, but the baseline should stay single-call and easy to reason about.

## Result Record Shape

The initial result record should be able to capture identity, scoring, reliability, latency, usage, and cost.

Suggested fields:

- `run_id`
- `corpus_id`
- `corpus_version`
- `test_case_id`
- `document_id`
- `model_provider`
- `model_name`
- `run_status`
- `failure_reason`
- `score`
- `raw_output`
- `parsed_output`
- `normalized_output`
- `normalized_ground_truth`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `reasoning_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `input_cost_usd`
- `output_cost_usd`
- `reasoning_cost_usd`
- `cost_source`
- `created_at`

Token and cost fields should be populated from LiteLLM response metadata where available. Missing provider metadata should be recorded as `null`, not guessed silently.

## Leaderboard Policy

First version:

- Rank models by score on completed parsing attempts.
- Count `zero_score` attempts as `0`.
- Report `failed` attempts separately as reliability/failure-rate data.
- Display latency and cost as secondary columns.
- Do not retry, repair, or agentically improve the model response.

This keeps model parsing quality separate from infrastructure reliability while still making malformed returned output hurt the model's score.
