from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from uuid import UUID

from single_pass_parsing_ranker import (
    AttemptStatus,
    FailureReason,
    LLMCallError,
    LLMCallResult,
    Run,
    RunnerError,
    RunStatus,
    RunTestCase,
    load_corpus,
    run_evaluation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CORPUS = PROJECT_ROOT / "corpora" / "0.1.0.json"
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")


class AuthenticationError(Exception):
    pass


class RunnerTests(unittest.TestCase):
    def test_run_evaluation_scores_case_and_completes_run(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS)[0]
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

        self.assertEqual(run, run_row)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)
        self.assertEqual(run_row.model_settings, {"temperature": 0, "max_tokens": 1024})

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
                test_case = load_corpus(EXAMPLE_CORPUS)[0]

                def fake_request(**kwargs):
                    self.assertEqual(os.environ["SINGLE_PASS_TEST_KEY"], "from-dotenv")
                    return LLMCallResult(raw_output=json.dumps(test_case.ground_truth))

                output = StringIO()
                with redirect_stdout(output):
                    run_evaluation(
                        model="gemini/gemini-2.5-flash",
                        corpus_path=EXAMPLE_CORPUS,
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
                run_id=RUN_ID,
                model_settings={"api_key": "do-not-store-this"},
                output_format="jsonl",
                structured_parse_request=lambda **kwargs: LLMCallResult(raw_output="{}"),
            )

    def test_run_evaluation_prints_pretty_terminal_output_by_default(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS)[0]

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
        self.assertIn(f"Run completed: {RUN_ID}", text)
        self.assertNotIn("raw_output", text)

    def test_run_evaluation_records_invalid_json_as_zero_score(self) -> None:
        def fake_request(**kwargs):
            return LLMCallResult(raw_output="not json")

        output = StringIO()
        with redirect_stdout(output):
            run = run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
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


if __name__ == "__main__":
    unittest.main()
