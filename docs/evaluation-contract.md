# Evaluation Contract

This document defines how a single model attempt becomes a score, a zero, or a failed run.

The goal is to keep the first evaluator brutally simple: one document, one row-level data model, one model call, one output, one result record. No retries for now.

## Inputs

Each attempt is tied to one `TestCase` row:

- `corpus_id`
- `test_case_id`
- `document_id`
- `data_model`
- `prompt`
- `ground_truth`

All `*_id` fields are UUID strings on disk and UUID values in code.

The evaluator resolves `document_id` through the document table. It then resolves the source document into model-ready text using the run's layout-to-text strategy and OCR strategy. Plain text documents pass through unchanged, PDFs use native layout text extraction first with OCR fallback, and image documents use OCR. The evaluator sends the row-level prompt, resolved document text, and inline data model to one configured model through LiteLLM. The data model may be represented as JSON Schema in the corpus row and normalized through a Pydantic-compatible model in the evaluator.

## Normalization Policy

Both sides of the comparison must pass through the same model contract:

1. Normalize `ground_truth` through the row's data model.
2. Parse the LLM response as JSON.
3. Normalize the parsed LLM output through the same row data model.
4. Compare normalized output to normalized ground truth.

The Pydantic-compatible data model is the authority for types, required fields, nested shapes, and any allowed coercion. If the ground truth cannot normalize through its own row data model, the `TestCase` row is invalid and should be fixed before the run is trusted.

## Scoring Policy

Default policy: **field-level exact match after normalization**.

Scoring flattens the normalized model output and normalized ground truth into field paths, compares each path one-to-one, and averages those field scores. Missing or extra fields score `0`. Nested objects and lists are scored by path, such as `line_items[0].total`.

Exact comparison assigns `1` for an exact match and `0` otherwise. A field schema may opt into a different comparison with evaluator-owned metadata:

```json
{
  "type": "string",
  "evaluation": {
    "comparison": "fuzzy_text"
  }
}
```

`fuzzy_text` compares normalized strings and returns a continuous score from `0` to `1`. The `evaluation` metadata belongs to corpus scoring; it is stripped from provider-facing JSON Schema before prompt assembly, structured-output calls, and schema validation. Identifiers, dates, and numeric fields should stay exact unless a corpus explicitly says otherwise.

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
- Document text extraction failure before the model call.

The score is `null`. Failed runs are reported separately as reliability data and do not become zero-score parsing attempts.

## No-Retry Rule

The first evaluator does not retry failed runs.

Retries can be added later as a separate evaluation track, but the baseline should stay single-call and easy to reason about.

## Result Record Shape

The evaluator should emit a `runs` row for run identity/status and a `run_test_cases` row for each individual test case result. The first storage sink prints JSON rows; file-backed JSONL can use the same row shapes later.

The `runs` row owns:

- `run_id`
- `corpus_id`
- `provider`
- `model`
- `model_settings`
- `model_metadata`
- `layout_to_text_strategy`
- `ocr_strategy`
- `status`
- `failure_reason`
- `started_at`
- `ended_at`
- `created_at`

The `run_test_cases` row owns:

- `run_id`
- `test_case_id`
- `status`
- `score`
- `failure_reason`
- `raw_output`
- `raw_response_metadata`
- `parsed_output`
- `normalized_output`
- `document_text_sha256`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `reasoning_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `input_cost_usd`
- `output_cost_usd`
- `reasoning_cost_usd`
- `started_at`
- `ended_at`
- `created_at`

Token and cost fields should be populated from LiteLLM response metadata where available. Missing provider metadata should be recorded as `null`, not guessed silently.

## Reporting Handoff

The evaluator records `runs` and `run_test_cases`. It does not aggregate scores or decide cross-model rankings.

Reporting systems can read `run_test_cases` and decide how to aggregate and compare models. A first reporting policy may:

- Rank models by score on completed parsing attempts.
- Count `zero_score` attempts as `0`.
- Report `failed` attempts separately as reliability/failure-rate data.
- Display latency and cost as secondary columns.
- Do not retry, repair, or agentically improve the model response.

This keeps model parsing quality separate from infrastructure reliability while still making malformed returned output hurt the model's score. The ranking decision itself belongs outside the core evaluator.
