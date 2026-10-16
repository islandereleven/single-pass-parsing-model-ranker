from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from upath import UPath

from single_pass_parsing_ranker import (
    AttemptStatus,
    DocumentTextResolutionError,
    FieldComparison,
    FailureReason,
    LayoutToTextStrategy,
    LLMCallError,
    LLMCallResult,
    OcrStrategy,
    ResolvedDocumentText,
    Run,
    RunnerError,
    RunStatus,
    RunTestCase,
    load_corpus,
    run_evaluation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CORPUS = PROJECT_ROOT / "corpora" / "0.1.0.json"
VERSION_030_CORPUS = PROJECT_ROOT / "corpora" / "0.3.0.json"
DOCUMENT_REGISTRY = PROJECT_ROOT / "documents" / "documents.json"
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")


class AuthenticationError(Exception):
    pass


class RunnerTests(unittest.TestCase):
    def test_run_evaluation_scores_case_and_completes_run(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]
        calls = []

        def fake_request(**kwargs):
            calls.append(kwargs)
            return LLMCallResult(
                raw_output=json.dumps(test_case.ground_truth),
                raw_response_metadata={"id": "response-001"},
                latency_ms=250,
                input_tokens=10,
                output_tokens=20,
                reasoning_tokens=2,
                total_tokens=32,
                estimated_cost_usd=0.0123,
            )

        output = StringIO()
        with redirect_stdout(output):
            run = run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                provider="gemini",
                model_settings={"temperature": 0, "max_tokens": 1024},
                run_id=RUN_ID,
                output_format="jsonl",
                structured_parse_request=fake_request,
            )

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 2)

        case_row = RunTestCase.model_validate_json(lines[0])
        run_row = Run.model_validate_json(lines[1])
        self.assertEqual(case_row.run_id, RUN_ID)
        self.assertEqual(case_row.test_case_id, test_case.test_case_id)
        self.assertEqual(case_row.status, AttemptStatus.SCORED)
        self.assertEqual(case_row.score, 1.0)
        self.assertEqual(case_row.normalized_output, test_case.ground_truth)
        self.assertEqual(case_row.input_tokens, 10)
        self.assertEqual(case_row.output_tokens, 20)
        self.assertEqual(case_row.reasoning_tokens, 2)
        self.assertEqual(case_row.total_tokens, 32)
        self.assertEqual(case_row.estimated_cost_usd, 0.0123)
        self.assertEqual(case_row.raw_response_metadata, {"id": "response-001"})
        acme_text = (PROJECT_ROOT / "documents" / "acme_invoice.txt").read_text(encoding="utf-8")
        self.assertEqual(case_row.document_text_sha256, sha256(acme_text.encode("utf-8")).hexdigest())

        self.assertEqual(run, run_row)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)
        self.assertEqual(run_row.model_settings, {"temperature": 0, "max_tokens": 1024})
        self.assertEqual(run_row.layout_to_text_strategy, LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT)
        self.assertEqual(run_row.ocr_strategy, OcrStrategy.PYTESSERACT)

        self.assertEqual(calls[0]["model"], "gemini/gemini-2.5-flash")
        self.assertEqual(calls[0]["data_model"], test_case.data_model)
        self.assertEqual(calls[0]["model_settings"], {"temperature": 0, "max_tokens": 1024})
        self.assertIn("Invoice INV-0001", calls[0]["prompt"])
        self.assertIn('"invoice_number"', calls[0]["prompt"])

    def test_run_evaluation_loads_env_file_without_storing_secret(self) -> None:
        previous = os.environ.pop("SINGLE_PASS_TEST_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                env_path = Path(temp_dir) / ".env"
                env_path.write_text("SINGLE_PASS_TEST_KEY=from-dotenv\n", encoding="utf-8")
                test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]

                def fake_request(**kwargs):
                    self.assertEqual(os.environ["SINGLE_PASS_TEST_KEY"], "from-dotenv")
                    return LLMCallResult(raw_output=json.dumps(test_case.ground_truth))

                output = StringIO()
                with redirect_stdout(output):
                    run_evaluation(
                        model="gemini/gemini-2.5-flash",
                        corpus_path=EXAMPLE_CORPUS,
                        document_registry_path=DOCUMENT_REGISTRY,
                        run_id=RUN_ID,
                        env_path=env_path,
                        output_format="jsonl",
                        structured_parse_request=fake_request,
                    )

                run_row = Run.model_validate_json(output.getvalue().splitlines()[1])
                self.assertNotIn("SINGLE_PASS_TEST_KEY", run_row.model_settings)
                self.assertEqual(run_row.status, RunStatus.COMPLETED)
        finally:
            os.environ.pop("SINGLE_PASS_TEST_KEY", None)
            if previous is not None:
                os.environ["SINGLE_PASS_TEST_KEY"] = previous

    def test_run_evaluation_rejects_secret_model_settings(self) -> None:
        with self.assertRaises(RunnerError):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                model_settings={"api_key": "do-not-store-this"},
                output_format="jsonl",
                structured_parse_request=lambda **kwargs: LLMCallResult(raw_output="{}"),
            )

    def test_run_evaluation_prints_pretty_terminal_output_by_default(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]

        def fake_request(**kwargs):
            return LLMCallResult(
                raw_output=json.dumps(test_case.ground_truth),
                latency_ms=321,
                input_tokens=100,
                output_tokens=50,
                reasoning_tokens=10,
                total_tokens=160,
                estimated_cost_usd=0.0012345,
            )

        output = StringIO()
        with redirect_stdout(output):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                provider="gemini",
                model_settings={"temperature": 0},
                run_id=RUN_ID,
                structured_parse_request=fake_request,
            )

        text = output.getvalue()
        self.assertIn(f"Run {RUN_ID}", text)
        self.assertIn("model: gemini/gemini-2.5-flash", text)
        self.assertIn(f"Test case 1/1: {test_case.test_case_id}", text)
        self.assertIn("status: scored", text)
        self.assertIn("score: 1.000", text)
        self.assertIn("latency: 321ms", text)
        self.assertIn("tokens: 160 (in 100, out 50, reasoning 10)", text)
        self.assertIn("cost: $0.001234", text)
        self.assertIn("mismatches: 0", text)
        self.assertIn(f"Run completed: {RUN_ID}", text)
        self.assertNotIn("raw_output", text)

    def test_run_evaluation_prints_pretty_mismatches(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]
        model_output = dict(test_case.ground_truth)
        model_output["total"] = 999.0

        def fake_request(**kwargs):
            return LLMCallResult(raw_output=json.dumps(model_output))

        output = StringIO()
        with redirect_stdout(output):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                env_path=None,
                structured_parse_request=fake_request,
            )

        text = output.getvalue()
        self.assertIn("mismatches: 1", text)
        self.assertIn("    total", text)
        self.assertIn("expected: 175.5", text)
        self.assertIn("actual: 999.0", text)

    def test_run_evaluation_prints_jsonl_mismatch_rows(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]
        model_output = dict(test_case.ground_truth)
        model_output["total"] = 999.0

        def fake_request(**kwargs):
            return LLMCallResult(raw_output=json.dumps(model_output))

        output = StringIO()
        with redirect_stdout(output):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                env_path=None,
                output_format="jsonl",
                structured_parse_request=fake_request,
            )

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 3)
        case_row = RunTestCase.model_validate_json(lines[0])
        comparison_row = FieldComparison.model_validate_json(lines[1])
        run_row = Run.model_validate_json(lines[2])

        self.assertEqual(case_row.status, AttemptStatus.SCORED)
        self.assertLess(case_row.score, 1.0)
        self.assertEqual(comparison_row.field_path, "total")
        self.assertEqual(comparison_row.expected_value, 175.5)
        self.assertEqual(comparison_row.actual_value, 999.0)
        self.assertFalse(comparison_row.matched)
        self.assertEqual(comparison_row.score, 0.0)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)

    def test_run_evaluation_records_invalid_json_as_zero_score(self) -> None:
        def fake_request(**kwargs):
            return LLMCallResult(raw_output="not json")

        output = StringIO()
        with redirect_stdout(output):
            run = run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                output_format="jsonl",
                structured_parse_request=fake_request,
            )

        lines = output.getvalue().splitlines()
        case_row = RunTestCase.model_validate_json(lines[0])
        run_row = Run.model_validate_json(lines[1])
        self.assertEqual(case_row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(case_row.score, 0.0)
        self.assertEqual(case_row.failure_reason, FailureReason.INVALID_JSON)
        self.assertEqual(run.status, RunStatus.COMPLETED)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)

    def test_run_evaluation_marks_run_failed_on_auth_error(self) -> None:
        def fake_request(**kwargs):
            raise LLMCallError("LiteLLM call failed") from AuthenticationError("auth failed")

        output = StringIO()
        with redirect_stdout(output):
            run = run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                output_format="jsonl",
                structured_parse_request=fake_request,
            )

        lines = output.getvalue().splitlines()
        case_row = RunTestCase.model_validate_json(lines[0])
        run_row = Run.model_validate_json(lines[1])
        self.assertEqual(case_row.status, AttemptStatus.FAILED)
        self.assertIsNone(case_row.score)
        self.assertEqual(case_row.failure_reason, FailureReason.AUTH_ERROR)
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(run.failure_reason, FailureReason.AUTH_ERROR)
        self.assertEqual(run_row.status, RunStatus.FAILED)
        self.assertEqual(run_row.failure_reason, FailureReason.AUTH_ERROR)

    def test_run_evaluation_fails_case_when_document_text_resolution_fails(self) -> None:
        rows = load_corpus(VERSION_030_CORPUS, document_registry_path=DOCUMENT_REGISTRY)
        calls = []

        def fake_request(**kwargs):
            calls.append(kwargs)
            return LLMCallResult(raw_output=json.dumps(rows[0].ground_truth))

        output = StringIO()
        with patch(
            "single_pass_parsing_ranker.runner.resolve_document_text",
            side_effect=[
                ResolvedDocumentText(text="ACME Widgets\n", sha256="resolved-text-sha"),
                DocumentTextResolutionError("no text"),
            ],
        ):
            with redirect_stdout(output):
                run = run_evaluation(
                    model="gemini/gemini-2.5-flash",
                    corpus_path=VERSION_030_CORPUS,
                    document_registry_path=DOCUMENT_REGISTRY,
                    run_id=RUN_ID,
                    env_path=None,
                    output_format="jsonl",
                    structured_parse_request=fake_request,
                )

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 3)
        first_case_row = RunTestCase.model_validate_json(lines[0])
        failed_case_row = RunTestCase.model_validate_json(lines[1])
        run_row = Run.model_validate_json(lines[2])

        self.assertEqual(first_case_row.status, AttemptStatus.SCORED)
        self.assertIsNotNone(first_case_row.document_text_sha256)
        self.assertEqual(failed_case_row.status, AttemptStatus.FAILED)
        self.assertEqual(failed_case_row.failure_reason, FailureReason.DOCUMENT_TEXT_EXTRACTION_ERROR)
        self.assertIsNone(failed_case_row.document_text_sha256)
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(run.failure_reason, FailureReason.DOCUMENT_TEXT_EXTRACTION_ERROR)
        self.assertEqual(run_row.failure_reason, FailureReason.DOCUMENT_TEXT_EXTRACTION_ERROR)
        self.assertEqual(len(calls), 1)

    def test_run_evaluation_persists_results_in_both_terminal_formats(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]
        model_output = dict(test_case.ground_truth)
        model_output["total"] = 999.0

        for output_format in ("pretty", "jsonl"):
            with self.subTest(output_format=output_format), tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir) / "runs"
                with redirect_stdout(StringIO()):
                    run_evaluation(
                        model="gemini/gemini-2.5-flash",
                        corpus_path=EXAMPLE_CORPUS,
                        document_registry_path=DOCUMENT_REGISTRY,
                        run_id=RUN_ID,
                        env_path=None,
                        output_format=output_format,
                        output_dir=output_dir,
                        structured_parse_request=lambda **kwargs: LLMCallResult(
                            raw_output=json.dumps(model_output)
                        ),
                    )

                run_dir = output_dir / f"run_id={RUN_ID}"
                run_row = Run.model_validate_json((run_dir / "run.json").read_text(encoding="utf-8"))
                case_rows = _read_jsonl(run_dir / "run_test_cases.jsonl", RunTestCase)
                comparison_rows = _read_jsonl(run_dir / "field_comparisons.jsonl", FieldComparison)

                self.assertEqual(run_row.status, RunStatus.COMPLETED)
                self.assertEqual(len(case_rows), 1)
                self.assertEqual(case_rows[0].status, AttemptStatus.SCORED)
                self.assertEqual(len(comparison_rows), 1)
                self.assertEqual(comparison_rows[0].field_path, "total")

    def test_run_evaluation_persists_failed_run(self) -> None:
        def fake_request(**kwargs):
            raise LLMCallError("LiteLLM call failed") from AuthenticationError("auth failed")

        with tempfile.TemporaryDirectory() as temp_dir, redirect_stdout(StringIO()):
            output_dir = Path(temp_dir) / "runs"
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                env_path=None,
                output_dir=output_dir,
                structured_parse_request=fake_request,
            )

            run_dir = output_dir / f"run_id={RUN_ID}"
            run_row = Run.model_validate_json((run_dir / "run.json").read_text(encoding="utf-8"))
            case_rows = _read_jsonl(run_dir / "run_test_cases.jsonl", RunTestCase)

        self.assertEqual(run_row.status, RunStatus.FAILED)
        self.assertEqual(run_row.failure_reason, FailureReason.AUTH_ERROR)
        self.assertEqual(case_rows[0].status, AttemptStatus.FAILED)
        self.assertEqual(case_rows[0].failure_reason, FailureReason.AUTH_ERROR)

    def test_run_evaluation_reads_and_writes_remote_filesystem(self) -> None:
        root = UPath(f"memory://sppr-runner-{uuid4()}")
        corpus_dir = root / "corpora"
        document_dir = root / "documents"
        output_dir = root / "results"
        corpus_dir.mkdir(parents=True)
        document_dir.mkdir(parents=True)
        (corpus_dir / "0.1.0.json").write_text(EXAMPLE_CORPUS.read_text(encoding="utf-8"), encoding="utf-8")
        (corpus_dir / "corpora.json").write_text(
            (PROJECT_ROOT / "corpora" / "corpora.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (document_dir / "documents.json").write_text(
            (PROJECT_ROOT / "documents" / "documents.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (document_dir / "acme_invoice.txt").write_bytes(
            (PROJECT_ROOT / "documents" / "acme_invoice.txt").read_bytes()
        )
        test_case = load_corpus(
            corpus_dir / "0.1.0.json",
            document_registry_path=document_dir / "documents.json",
        )[0]

        with redirect_stdout(StringIO()):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=corpus_dir / "0.1.0.json",
                document_registry_path=document_dir / "documents.json",
                run_id=RUN_ID,
                env_path=None,
                output_dir=output_dir,
                structured_parse_request=lambda **kwargs: LLMCallResult(
                    raw_output=json.dumps(test_case.ground_truth)
                ),
            )

        run_dir = output_dir / f"run_id={RUN_ID}"
        run_row = Run.model_validate_json((run_dir / "run.json").read_text(encoding="utf-8"))
        case_rows = [
            RunTestCase.model_validate_json(line)
            for line in (run_dir / "run_test_cases.jsonl").read_text(encoding="utf-8").splitlines()
        ]

        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertEqual(len(case_rows), 1)
        self.assertEqual(case_rows[0].score, 1.0)


def _read_jsonl(path: Path, model):
    return [model.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
