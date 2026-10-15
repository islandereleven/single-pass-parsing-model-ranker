# Logging

The evaluator emits a small set of vendor-neutral lifecycle events through Python's standard logging module. The CLI writes logs to `stderr`, leaving readable or JSONL result output on `stdout` unchanged.

Local defaults are `INFO` and `human`. Cloud deployments should normally select JSON:

```bash
SPPR_LOG_LEVEL=INFO SPPR_LOG_FORMAT=json \
  poetry run single-pass-ranker run \
  --model gemini/gemini-2.5-flash \
  --provider gemini \
  --corpus corpora/0.1.0.json
```

The equivalent CLI options are `--log-level` and `--log-format`. Supported levels are `DEBUG`, `INFO`, `WARNING`, and `ERROR`; supported formats are `human` and `json`.

Library use is quiet by default. An embedding application can configure the `single_pass_parsing_ranker` logger itself or call `configure_logging` from `single_pass_parsing_ranker.observability`.

## JSON Contract

Every JSON event has these common fields:

- `timestamp`: UTC RFC 3339 timestamp.
- `level`: `DEBUG`, `INFO`, `WARNING`, or `ERROR`.
- `service`: `single-pass-parsing-model-ranker`.
- `event`: stable machine-readable event name.
- `message`: short human-readable description.

Every evaluator lifecycle event also carries `run_id`, `model`, `corpus_id`, and `provider` when a provider label was supplied. This makes individual records independently filterable without joining them to `run.started`. Available event-specific fields are added at the top level, and fields with no value are omitted.

```json
{"timestamp":"2026-10-15T12:34:56.123Z","level":"INFO","service":"single-pass-parsing-model-ranker","event":"case.finished","message":"Evaluation case completed","run_id":"72b60a7f-2a08-4d18-91f6-cb524ec777a0","provider":"gemini","model":"gemini/gemini-2.5-flash","corpus_id":"...","test_case_id":"...","document_id":"...","outcome":"scored","duration_ms":842,"score":1.0,"mismatch_count":0}
```

`level` is log severity. `outcome` is the evaluation result, avoiding an overloaded `status` field.

## Events and Levels

| Event | Normal level | Purpose |
| --- | --- | --- |
| `run.started` | `INFO` | Records the run identity, configuration labels, and case count. |
| `case.started` | `INFO` | Identifies the current test case. |
| `stage.started` | `INFO` | Marks entry into `document_resolution` or `llm_request`; document resolution also identifies the layout and OCR strategies. |
| `case.finished` | varies | Records the terminal case outcome and available measurements. |
| `run.finished` | varies | Records the terminal run outcome, counters, and duration. |

`case.finished` is `INFO` for both `scored` and `zero_score`, because both are valid evaluation outcomes. It is `ERROR` for an operationally `failed` case. `run.finished` is `ERROR` for a failed run and `INFO` otherwise. `WARNING` is reserved for future degraded-but-recoverable operational conditions rather than model quality.

Only deliberately selected operational fields are logged. Prompts, document contents, ground truth, raw model responses, full model settings, raw provider metadata, and exception messages are excluded.

## Deployment Router Boundary

The package does not include a Datadog or OpenTelemetry SDK. A container runtime collects `stderr`; a deployment-level Datadog Agent, OpenTelemetry Collector, or other log router parses the JSON and decides what to forward.

A useful initial forwarding policy is:

```text
forward when level is WARNING or ERROR
or event is run.started
or event is case.finished
or event is run.finished
```

This keeps routine `case.started` and `stage.started` breadcrumbs in local/container logs without paying to ingest them into Datadog. The router can later add sampling or rate limits without a package release.

The deployment layer should enrich forwarded records with low-cardinality tags such as `env`, `service`, `version`, `region`, `cluster`, and `team`. Package fields such as `provider`, `model`, `corpus_id`, and `outcome` are suitable for filtering and aggregation. Keep `run_id`, `test_case_id`, and `document_id` as searchable attributes rather than metric tags because they are high-cardinality.

For Datadog, configure a status remapper from `level` if the chosen ingestion path does not already recognize it. Authentication, endpoints, forwarding rules, and Datadog-specific metadata remain deployment concerns.
