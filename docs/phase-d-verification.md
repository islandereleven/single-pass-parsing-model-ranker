# Phase D Verification

Phase D proves the prototype evaluator follows its contract. It is mostly automated tests plus one manual live-provider smoke check.

## Automated Verification

Run:

```bash
poetry run python -m unittest discover -s tests
```

The automated suite does not call live model providers. Provider behavior is faked at the LiteLLM boundary so tests stay deterministic and cheap.

Current coverage:

- Scoring math for scalar mismatches, nested missing/extra fields, list index mismatches, list length drift, list order, and scalar equality after normalization.
- Runner outcome rules for empty output, invalid JSON, schema-invalid JSON, missing provider responses, provider-side structured validation errors, provider failure classification, invalid ground-truth fixtures, and JSONL row emission.
- Schema failure cases for missing required fields, wrong field types, extra hallucinated keys, and refusal/prose output.
- Metadata capture for latency, input tokens, output tokens, reasoning tokens, total tokens, estimated cost, raw response metadata, and null behavior when provider metadata is missing.
- LiteLLM response extraction for object-style and dict-style usage metadata, including direct and nested reasoning-token shapes.
- CLI argument mapping through unit tests.

## Manual CLI QA

The CLI should be checked locally with the Gemini key in `.env`.

Readable terminal output:

```bash
poetry run single-pass-ranker run \
  --model gemini/gemini-2.5-flash \
  --provider gemini \
  --corpus corpora/0.1.0.json \
  --temperature 0
```

Raw JSONL output:

```bash
poetry run single-pass-ranker run \
  --model gemini/gemini-2.5-flash \
  --provider gemini \
  --corpus corpora/0.1.0.json \
  --temperature 0 \
  --output-format jsonl
```

Expected live-smoke result for the current example corpus:

- One test case runs.
- The test case status is `scored`.
- The score is `1.000`.
- The final run status is `completed`.
- Pretty output shows summary fields only: status, score, latency, tokens, and cost.
- Pretty output does not print the raw model JSON or raw provider metadata.

## Not Verified In Phase D

These are intentionally deferred:

- File-backed JSONL storage.
- Markdown result export.
- Larger multi-document corpora.
- Multimodal inputs.
- Ranking/report aggregation.
- Retry behavior.

The evaluator still emits enough row data for those later layers to consume.
