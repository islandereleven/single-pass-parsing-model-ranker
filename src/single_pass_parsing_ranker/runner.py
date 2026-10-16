"""Sequential evaluator runner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from uuid import UUID, uuid4

from upath import UPath

from single_pass_parsing_ranker.data import load_corpus, load_documents
from single_pass_parsing_ranker.document_text_resolution import (
    DocumentTextResolutionError,
    resolve_document_text,
)
from single_pass_parsing_ranker.llm import (
    LLMCallError,
    LLMResponseError,
    StructuredOutputValidationError,
    request_structured_parse,
)
from single_pass_parsing_ranker.models import (
    AttemptStatus,
    Document,
    FieldComparison,
    FailureReason,
    JsonObject,
    LayoutToTextStrategy,
    LLMCallResult,
    OcrStrategy,
    Run,
    RunStatus,
    RunTestCase,
    TestCase,
)
from single_pass_parsing_ranker.normalize import (
    JsonParseError,
    SchemaValidationError,
    normalize_json_value,
    parse_json_output,
)
from single_pass_parsing_ranker.observability import log_event
from single_pass_parsing_ranker.prompts import build_prompt
from single_pass_parsing_ranker.scoring import (
    field_comparisons,
    score_field_comparisons,
)
from single_pass_parsing_ranker.storage import write_run_bundle


class RunnerError(RuntimeError):
    pass


OutputFormat = Literal["pretty", "jsonl"]

_LOGGER = logging.getLogger(__name__)


_SECRET_SETTING_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer_token",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "refresh_token",
    "secret",
    "access_token",
    "id_token",
}


@dataclass(frozen=True)
class _RunTestCaseResult:
    row: RunTestCase
    field_comparisons: tuple[FieldComparison, ...] = ()


def run_evaluation(
    *,
    model: str,
    corpus_path: str | Path,
    document_registry_path: str | Path,
    output_dir: str | Path | None = None,
    provider: str | None = None,
    model_settings: JsonObject | None = None,
    layout_to_text_strategy: LayoutToTextStrategy | str = LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT,
    ocr_strategy: OcrStrategy | str = OcrStrategy.PYTESSERACT,
    run_id: UUID | None = None,
    corpus_table_path: str | Path | None = None,
    env_path: str | Path | None = ".env",
    output_format: OutputFormat = "pretty",
    structured_parse_request: Callable[..., LLMCallResult] = request_structured_parse,
) -> Run:
    _load_env_file(env_path)
    settings = dict(model_settings or {})
    _reject_secret_model_settings(settings)
    _validate_output_format(output_format)
    resolved_output_dir = UPath(output_dir) if output_dir is not None else None
    resolved_corpus_path = UPath(corpus_path)
    resolved_layout_strategy = LayoutToTextStrategy(layout_to_text_strategy)
    resolved_ocr_strategy = OcrStrategy(ocr_strategy)

    rows = load_corpus(
        resolved_corpus_path,
        corpus_table_path=corpus_table_path,
        document_registry_path=document_registry_path,
    )
    if not rows:
        raise RunnerError(f"Corpus has no test cases: {resolved_corpus_path}")

    corpus_id = _single_corpus_id(rows)
    documents = load_documents(document_registry_path)
    run = Run(
        run_id=run_id or uuid4(),
        model=model,
        provider=provider,
        corpus_id=corpus_id,
        model_settings=settings,
        layout_to_text_strategy=resolved_layout_strategy,
        ocr_strategy=resolved_ocr_strategy,
    )
    run_started = perf_counter()
    attempted = 0
    scored = 0
    zero_score = 0
    failed = 0
    result_rows: list[RunTestCase] = []
    comparison_rows: list[FieldComparison] = []

    _log_run_started(run, total_cases=len(rows))
    _emit_run_start(run, output_format)

    run_status = RunStatus.COMPLETED
    run_failure_reason: FailureReason | None = None
    for index, test_case in enumerate(rows, start=1):
        case_started = perf_counter()
        attempted += 1
        _log_case_started(
            run,
            test_case,
            document=documents[test_case.document_id],
            index=index,
            total=len(rows),
        )
        result = _run_test_case(
            run=run,
            test_case=test_case,
            document=documents[test_case.document_id],
            request_structured_parse=structured_parse_request,
        )
        result_rows.append(result.row)
        comparison_rows.extend(comparison for comparison in result.field_comparisons if not comparison.matched)
        _emit_run_test_case(
            result.row,
            result.field_comparisons,
            output_format,
            index=index,
            total=len(rows),
        )
        _log_case_finished(
            run,
            test_case,
            document=documents[test_case.document_id],
            result=result,
            index=index,
            total=len(rows),
            duration_ms=_elapsed_ms(case_started),
        )

        if result.row.status == AttemptStatus.SCORED:
            scored += 1
        elif result.row.status == AttemptStatus.ZERO_SCORE:
            zero_score += 1
        else:
            failed += 1
            run_status = RunStatus.FAILED
            run_failure_reason = result.row.failure_reason
            break

    final_run = run.model_copy(
        update={
            "status": run_status,
            "failure_reason": run_failure_reason,
            "ended_at": _utc_now(),
        }
    )
    if resolved_output_dir is not None:
        write_run_bundle(resolved_output_dir, final_run, result_rows, comparison_rows)
    _emit_run(final_run, output_format)
    _log_run_finished(
        final_run,
        attempted=attempted,
        scored=scored,
        zero_score=zero_score,
        failed=failed,
        skipped=len(rows) - attempted,
        duration_ms=_elapsed_ms(run_started),
    )
    return final_run


def _run_test_case(
    *,
    run: Run,
    test_case: TestCase,
    document: Document,
    request_structured_parse: Callable[..., LLMCallResult],
) -> _RunTestCaseResult:
    started_at = _utc_now()
    _log_stage_started(run, test_case, document, stage="document_resolution")
    try:
        resolved_document_text = resolve_document_text(
            document,
            layout_to_text_strategy=run.layout_to_text_strategy,
            ocr_strategy=run.ocr_strategy,
        )
    except DocumentTextResolutionError:
        return _RunTestCaseResult(
            _result_row(
                run=run,
                test_case=test_case,
                status=AttemptStatus.FAILED,
                failure_reason=FailureReason.DOCUMENT_TEXT_EXTRACTION_ERROR,
                started_at=started_at,
            )
        )

    try:
        normalized_ground_truth = normalize_json_value(test_case.ground_truth, test_case.data_model)
    except SchemaValidationError as exc:
        raise RunnerError(f"Invalid ground_truth for test_case_id: {test_case.test_case_id}") from exc

    prompt = build_prompt(
        instruction=test_case.prompt,
        document_text=resolved_document_text.text,
        data_model=test_case.data_model,
    )

    _log_stage_started(run, test_case, document, stage="llm_request")
    try:
        llm_result = request_structured_parse(
            model=run.model,
            prompt=prompt,
            data_model=test_case.data_model,
            model_settings=run.model_settings,
        )
    except StructuredOutputValidationError:
        return _RunTestCaseResult(
            _result_row(
                run=run,
                test_case=test_case,
                status=AttemptStatus.ZERO_SCORE,
                score=0.0,
                failure_reason=FailureReason.SCHEMA_VALIDATION_ERROR,
                document_text_sha256=resolved_document_text.sha256,
                started_at=started_at,
            )
        )
    except LLMResponseError:
        return _RunTestCaseResult(
            _result_row(
                run=run,
                test_case=test_case,
                status=AttemptStatus.FAILED,
                failure_reason=FailureReason.NO_RESPONSE,
                document_text_sha256=resolved_document_text.sha256,
                started_at=started_at,
            )
        )
    except LLMCallError as exc:
        return _RunTestCaseResult(
            _result_row(
                run=run,
                test_case=test_case,
                status=AttemptStatus.FAILED,
                failure_reason=_failure_reason_for_llm_error(exc),
                document_text_sha256=resolved_document_text.sha256,
                started_at=started_at,
            )
        )

    try:
        parsed_output = parse_json_output(llm_result.raw_output)
    except JsonParseError:
        reason = FailureReason.EMPTY_RESPONSE if not llm_result.raw_output.strip() else FailureReason.INVALID_JSON
        return _RunTestCaseResult(
            _result_row(
                run=run,
                test_case=test_case,
                llm_result=llm_result,
                status=AttemptStatus.ZERO_SCORE,
                score=0.0,
                failure_reason=reason,
                document_text_sha256=resolved_document_text.sha256,
                started_at=started_at,
            )
        )

    try:
        normalized_output = normalize_json_value(parsed_output, test_case.data_model)
    except SchemaValidationError:
        return _RunTestCaseResult(
            _result_row(
                run=run,
                test_case=test_case,
                llm_result=llm_result,
                status=AttemptStatus.ZERO_SCORE,
                score=0.0,
                failure_reason=FailureReason.SCHEMA_VALIDATION_ERROR,
                parsed_output=parsed_output,
                document_text_sha256=resolved_document_text.sha256,
                started_at=started_at,
            )
        )

    comparisons = field_comparisons(
        run_id=run.run_id,
        test_case_id=test_case.test_case_id,
        output=normalized_output,
        ground_truth=normalized_ground_truth,
        data_model=test_case.data_model,
    )
    return _RunTestCaseResult(
        _result_row(
            run=run,
            test_case=test_case,
            llm_result=llm_result,
            status=AttemptStatus.SCORED,
            score=score_field_comparisons(comparisons),
            parsed_output=parsed_output,
            normalized_output=normalized_output,
            document_text_sha256=resolved_document_text.sha256,
            started_at=started_at,
        ),
        comparisons,
    )


def _result_row(
    *,
    run: Run,
    test_case: TestCase,
    status: AttemptStatus,
    started_at: datetime,
    llm_result: LLMCallResult | None = None,
    score: float | None = None,
    failure_reason: FailureReason | None = None,
    parsed_output: Any = None,
    normalized_output: Any = None,
    document_text_sha256: str | None = None,
) -> RunTestCase:
    return RunTestCase(
        run_id=run.run_id,
        test_case_id=test_case.test_case_id,
        status=status,
        score=score,
        failure_reason=failure_reason,
        raw_output=llm_result.raw_output if llm_result else None,
        raw_response_metadata=llm_result.raw_response_metadata if llm_result else {},
        parsed_output=parsed_output,
        normalized_output=normalized_output,
        document_text_sha256=document_text_sha256,
        latency_ms=llm_result.latency_ms if llm_result else None,
        input_tokens=llm_result.input_tokens if llm_result else None,
        output_tokens=llm_result.output_tokens if llm_result else None,
        reasoning_tokens=llm_result.reasoning_tokens if llm_result else None,
        total_tokens=llm_result.total_tokens if llm_result else None,
        estimated_cost_usd=llm_result.estimated_cost_usd if llm_result else None,
        started_at=started_at,
        ended_at=_utc_now(),
    )


def _single_corpus_id(rows: tuple[TestCase, ...]) -> UUID:
    corpus_ids = {row.corpus_id for row in rows}
    if len(corpus_ids) != 1:
        raise RunnerError("A run must target exactly one corpus_id")
    return next(iter(corpus_ids))


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _run_log_context(run: Run) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "provider": run.provider,
        "model": run.model,
        "corpus_id": run.corpus_id,
    }


def _log_run_started(run: Run, *, total_cases: int) -> None:
    log_event(
        _LOGGER,
        logging.INFO,
        "run.started",
        "Evaluation run started",
        **_run_log_context(run),
        total_cases=total_cases,
        layout_to_text_strategy=run.layout_to_text_strategy,
        ocr_strategy=run.ocr_strategy,
    )


def _log_case_started(
    run: Run,
    test_case: TestCase,
    *,
    document: Document,
    index: int,
    total: int,
) -> None:
    log_event(
        _LOGGER,
        logging.INFO,
        "case.started",
        "Evaluation case started",
        **_run_log_context(run),
        test_case_id=test_case.test_case_id,
        document_id=document.document_id,
        case_index=index,
        total_cases=total,
    )


def _log_stage_started(
    run: Run,
    test_case: TestCase,
    document: Document,
    *,
    stage: str,
) -> None:
    stage_context = {}
    if stage == "document_resolution":
        stage_context = {
            "layout_to_text_strategy": run.layout_to_text_strategy,
            "ocr_strategy": run.ocr_strategy,
        }

    log_event(
        _LOGGER,
        logging.INFO,
        "stage.started",
        "Evaluation stage started",
        **_run_log_context(run),
        test_case_id=test_case.test_case_id,
        document_id=document.document_id,
        stage=stage,
        **stage_context,
    )


def _log_case_finished(
    run: Run,
    test_case: TestCase,
    *,
    document: Document,
    result: _RunTestCaseResult,
    index: int,
    total: int,
    duration_ms: int,
) -> None:
    row = result.row
    level = {
        AttemptStatus.SCORED: logging.INFO,
        AttemptStatus.ZERO_SCORE: logging.INFO,
        AttemptStatus.FAILED: logging.ERROR,
    }[row.status]
    mismatch_count = sum(not comparison.matched for comparison in result.field_comparisons)
    log_event(
        _LOGGER,
        level,
        "case.finished",
        "Evaluation case completed",
        **_run_log_context(run),
        test_case_id=test_case.test_case_id,
        document_id=document.document_id,
        case_index=index,
        total_cases=total,
        outcome=row.status,
        failure_reason=row.failure_reason,
        score=row.score,
        duration_ms=duration_ms,
        latency_ms=row.latency_ms,
        total_tokens=row.total_tokens,
        estimated_cost_usd=row.estimated_cost_usd,
        mismatch_count=mismatch_count,
    )


def _log_run_finished(
    run: Run,
    *,
    attempted: int,
    scored: int,
    zero_score: int,
    failed: int,
    skipped: int,
    duration_ms: int,
) -> None:
    level = logging.ERROR if run.status == RunStatus.FAILED else logging.INFO
    log_event(
        _LOGGER,
        level,
        "run.finished",
        "Evaluation run completed",
        **_run_log_context(run),
        outcome=run.status,
        failure_reason=run.failure_reason,
        attempted=attempted,
        scored=scored,
        zero_score=zero_score,
        failed=failed,
        skipped=skipped,
        duration_ms=duration_ms,
    )


def _validate_output_format(output_format: str) -> None:
    if output_format not in ("pretty", "jsonl"):
        raise RunnerError(f"Unknown output_format: {output_format}")


def _emit_run_start(run: Run, output_format: OutputFormat) -> None:
    if output_format == "jsonl":
        return

    print(f"Run {run.run_id}")
    print(f"  model: {run.model}")
    if run.provider:
        print(f"  provider: {run.provider}")
    print(f"  corpus: {run.corpus_id}")
    print(f"  layout_to_text_strategy: {run.layout_to_text_strategy.value}")
    print(f"  ocr_strategy: {run.ocr_strategy.value}")
    if run.model_settings:
        settings = json.dumps(run.model_settings, sort_keys=True)
        print(f"  settings: {settings}")


def _emit_run_test_case(
    row: RunTestCase,
    comparisons: tuple[FieldComparison, ...],
    output_format: OutputFormat,
    *,
    index: int,
    total: int,
) -> None:
    mismatches = tuple(comparison for comparison in comparisons if not comparison.matched)
    if output_format == "jsonl":
        print(row.model_dump_json())
        for mismatch in mismatches:
            print(mismatch.model_dump_json())
        return

    print("")
    print(f"Test case {index}/{total}: {row.test_case_id}")
    print(f"  status: {row.status.value}")
    print(f"  score: {_format_score(row.score)}")
    if row.failure_reason:
        print(f"  failure: {row.failure_reason.value}")
    print(f"  latency: {_format_ms(row.latency_ms)}")
    print(f"  tokens: {_format_tokens(row)}")
    print(f"  cost: {_format_money(row.estimated_cost_usd)}")
    if row.status == AttemptStatus.SCORED:
        print(f"  mismatches: {len(mismatches)}")
        for mismatch in mismatches:
            print(f"    {mismatch.field_path}")
            print(f"      comparison: {mismatch.comparison_method.value}")
            print(f"      comparison_score: {_format_score(mismatch.score)}")
            print(f"      expected: {_format_json_value(mismatch.expected_value, mismatch.expected_present)}")
            print(f"      actual: {_format_json_value(mismatch.actual_value, mismatch.actual_present)}")


def _emit_run(run: Run, output_format: OutputFormat) -> None:
    if output_format == "jsonl":
        print(run.model_dump_json())
        return

    print("")
    print(f"Run {run.status.value}: {run.run_id}")
    if run.failure_reason:
        print(f"  failure: {run.failure_reason.value}")
    if run.ended_at:
        elapsed = (run.ended_at - run.started_at).total_seconds()
        print(f"  elapsed: {elapsed:.2f}s")


def _format_score(score: float | None) -> str:
    if score is None:
        return "n/a"
    return f"{score:.3f}"


def _format_ms(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value}ms"


def _format_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.6f}"


def _format_tokens(row: RunTestCase) -> str:
    if row.total_tokens is None:
        return "n/a"

    parts = [str(row.total_tokens)]
    details = []
    if row.input_tokens is not None:
        details.append(f"in {row.input_tokens}")
    if row.output_tokens is not None:
        details.append(f"out {row.output_tokens}")
    if row.reasoning_tokens is not None:
        details.append(f"reasoning {row.reasoning_tokens}")
    if details:
        parts.append(f"({', '.join(details)})")
    return " ".join(parts)


def _format_json_value(value: Any, present: bool) -> str:
    if not present:
        return "<missing>"
    return json.dumps(value, sort_keys=True)


def _load_env_file(env_path: str | Path | None) -> None:
    if env_path is None:
        return

    path = Path(env_path)
    if not path.is_file():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = _unquote_env_value(value.strip())


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _reject_secret_model_settings(settings: JsonObject) -> None:
    for path, value in _walk_mapping(settings):
        if value is None:
            continue
        key = path.rsplit(".", 1)[-1].lower().replace("-", "_")
        if _is_secret_setting_key(key):
            raise RunnerError(f"model_settings must not contain secret-like key: {path}")


def _walk_mapping(value: Any, path: str = "") -> tuple[tuple[str, Any], ...]:
    if not isinstance(value, dict):
        return ()

    items: list[tuple[str, Any]] = []
    for key, child in value.items():
        child_path = str(key) if not path else f"{path}.{key}"
        items.append((child_path, child))
        items.extend(_walk_mapping(child, child_path))
    return tuple(items)


def _is_secret_setting_key(key: str) -> bool:
    return (
        key in _SECRET_SETTING_KEYS
        or key.endswith("_api_key")
        or key.endswith("_secret")
        or key.endswith("_password")
        or key.endswith("_token")
    )


def _failure_reason_for_llm_error(exc: LLMCallError) -> FailureReason:
    text = _exception_chain_text(exc)
    if "auth" in text or "permission" in text or "unauthorized" in text:
        return FailureReason.AUTH_ERROR
    if "rate_limit" in text or "ratelimit" in text or "rate limit" in text:
        return FailureReason.RATE_LIMIT
    if "timeout" in text or "timed out" in text:
        return FailureReason.TIMEOUT
    if "network" in text or "connection" in text or "dns" in text:
        return FailureReason.NETWORK_ERROR
    return FailureReason.PROVIDER_ERROR


def _exception_chain_text(exc: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        parts.append(type(current).__name__)
        parts.append(str(current))
        current = current.__cause__ or current.__context__
    return " ".join(parts).lower()
