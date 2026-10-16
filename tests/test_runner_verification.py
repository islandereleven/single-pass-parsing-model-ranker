from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import UUID

from single_pass_parsing_ranker import (
    AttemptStatus,
    FailureReason,
    LLMCallError,
    LLMCallResult,
    LLMResponseError,
    Run,
    RunnerError,
    RunStatus,
    RunTestCase,
    StructuredOutputValidationError,
    load_corpus,
    run_evaluation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CORPUS = PROJECT_ROOT / "corpora" / "0.1.0.json"
EXAMPLE_CORPORA = PROJECT_ROOT / "corpora" / "corpora.json"
EXAMPLE_DOCUMENTS = PROJECT_ROOT / "documents"
DOCUMENT_REGISTRY = EXAMPLE_DOCUMENTS / "documents.json"
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")


class ProviderCause(Exception):
    pass


class RunnerVerificationTests(unittest.TestCase):
    def test_empty_model_output_zero_scores_but_completes_run(self) -> None:
        case_row, run_row, returned_run = _run_jsonl(lambda **kwargs: LLMCallResult(raw_output=""))

        self.assertEqual(case_row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(case_row.score, 0.0)
        self.assertEqual(case_row.failure_reason, FailureReason.EMPTY_RESPONSE)
        self.assertEqual(case_row.raw_output, "")
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)
        self.assertEqual(returned_run, run_row)

    def test_schema_invalid_json_zero_scores_but_completes_run(self) -> None:
        raw_output = json.dumps({"invoice_number": "INV-0001", "unexpected": "hallucinated"})

        case_row, run_row, _ = _run_jsonl(lambda **kwargs: LLMCallResult(raw_output=raw_output))

        self.assertEqual(case_row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(case_row.score, 0.0)
        self.assertEqual(case_row.failure_reason, FailureReason.SCHEMA_VALIDATION_ERROR)
        self.assertEqual(case_row.parsed_output, {"invoice_number": "INV-0001", "unexpected": "hallucinated"})
        self.assertIsNone(case_row.normalized_output)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)

    def test_litellm_structured_validation_error_zero_scores_but_completes_run(self) -> None:
        def fake_request(**kwargs):
            raise StructuredOutputValidationError("schema rejected by provider")

        case_row, run_row, _ = _run_jsonl(fake_request)

        self.assertEqual(case_row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(case_row.score, 0.0)
        self.assertEqual(case_row.failure_reason, FailureReason.SCHEMA_VALIDATION_ERROR)
        self.assertIsNone(case_row.raw_output)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)

    def test_missing_litellm_response_fails_case_and_run(self) -> None:
        def fake_request(**kwargs):
            raise LLMResponseError("LiteLLM response contained no choices")

        case_row, run_row, returned_run = _run_jsonl(fake_request)

        self.assertEqual(case_row.status, AttemptStatus.FAILED)
        self.assertIsNone(case_row.score)
        self.assertEqual(case_row.failure_reason, FailureReason.NO_RESPONSE)
        self.assertEqual(run_row.status, RunStatus.FAILED)
        self.assertEqual(run_row.failure_reason, FailureReason.NO_RESPONSE)
        self.assertEqual(returned_run, run_row)

    def test_provider_error_failure_reasons_fail_case_and_run(self) -> None:
        cases = {
            "auth failed": FailureReason.AUTH_ERROR,
            "rate limit exceeded": FailureReason.RATE_LIMIT,
            "request timed out": FailureReason.TIMEOUT,
            "connection reset by peer": FailureReason.NETWORK_ERROR,
            "provider sadness": FailureReason.PROVIDER_ERROR,
        }

        for message, expected_reason in cases.items():
            with self.subTest(message=message):
                def fake_request(**kwargs):
                    raise _llm_call_error_with_cause(message)

                case_row, run_row, _ = _run_jsonl(fake_request)

                self.assertEqual(case_row.status, AttemptStatus.FAILED)
                self.assertIsNone(case_row.score)
                self.assertEqual(case_row.failure_reason, expected_reason)
                self.assertEqual(run_row.status, RunStatus.FAILED)
                self.assertEqual(run_row.failure_reason, expected_reason)

    def test_invalid_ground_truth_fixture_raises_runner_error_before_provider_call(self) -> None:
        calls = []

        def fake_request(**kwargs):
            calls.append(kwargs)
            return LLMCallResult(raw_output="{}")

        with tempfile.TemporaryDirectory() as temp_dir:
            corpus_path = _copy_example_fixture(Path(temp_dir))
            rows = json.loads(corpus_path.read_text(encoding="utf-8"))
            rows[0]["ground_truth"] = {"invoice_number": "INV-0001"}
            corpus_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

            output = StringIO()
            with self.assertRaises(RunnerError):
                with redirect_stdout(output):
                    run_evaluation(
                        model="gemini/gemini-2.5-flash",
                        corpus_path=corpus_path,
                        document_registry_path=Path(temp_dir) / "documents" / "documents.json",
                        run_id=RUN_ID,
                        env_path=None,
                        output_format="jsonl",
                        structured_parse_request=fake_request,
                    )

        self.assertEqual(calls, [])
        self.assertEqual(output.getvalue(), "")

    def test_jsonl_output_is_parseable_case_row_then_run_row(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]

        case_row, run_row, _ = _run_jsonl(lambda **kwargs: LLMCallResult(raw_output=json.dumps(test_case.ground_truth)))

        self.assertEqual(case_row.status, AttemptStatus.SCORED)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertEqual(case_row.run_id, run_row.run_id)


def _run_jsonl(structured_parse_request):
    output = StringIO()
    with redirect_stdout(output):
        returned_run = run_evaluation(
            model="gemini/gemini-2.5-flash",
            corpus_path=EXAMPLE_CORPUS,
            document_registry_path=DOCUMENT_REGISTRY,
            run_id=RUN_ID,
            env_path=None,
            output_format="jsonl",
            structured_parse_request=structured_parse_request,
        )

    lines = output.getvalue().splitlines()
    if len(lines) != 2:
        raise AssertionError(f"expected 2 JSONL rows, got {len(lines)}: {lines!r}")
    return RunTestCase.model_validate_json(lines[0]), Run.model_validate_json(lines[1]), returned_run


def _llm_call_error_with_cause(message: str) -> LLMCallError:
    try:
        raise ProviderCause(message)
    except ProviderCause as exc:
        raise LLMCallError("LiteLLM call failed") from exc


def _copy_example_fixture(temp_root: Path) -> Path:
    copied_corpus = temp_root / "corpora" / "0.1.0.json"
    copied_corpus.parent.mkdir(parents=True)
    shutil.copy2(EXAMPLE_CORPUS, copied_corpus)
    shutil.copy2(EXAMPLE_CORPORA, copied_corpus.parent / "corpora.json")
    shutil.copytree(EXAMPLE_DOCUMENTS, temp_root / "documents")
    return copied_corpus


if __name__ == "__main__":
    unittest.main()
