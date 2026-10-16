from contextlib import redirect_stdout
from io import StringIO
import json
import logging
from pathlib import Path
import unittest
from uuid import UUID

from single_pass_parsing_ranker import LLMCallError, LLMCallResult, load_corpus, run_evaluation
from single_pass_parsing_ranker.observability import PACKAGE_LOGGER_NAME, configure_logging


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CORPUS = PROJECT_ROOT / "corpora" / "0.1.0.json"
DOCUMENT_REGISTRY = PROJECT_ROOT / "documents" / "documents.json"
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")


class AuthenticationError(Exception):
    pass


class RunnerLoggingTests(unittest.TestCase):
    def tearDown(self) -> None:
        package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
        for handler in tuple(package_logger.handlers):
            if getattr(handler, "_sppr_managed", False):
                package_logger.removeHandler(handler)
                handler.close()
        package_logger.setLevel(logging.NOTSET)
        package_logger.propagate = True

    def test_successful_run_emits_expected_events_without_polluting_stdout(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]
        logs = StringIO()
        stdout = StringIO()
        configure_logging(level="INFO", log_format="json", stream=logs)

        with redirect_stdout(stdout):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                provider="gemini",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                env_path=None,
                output_format="jsonl",
                structured_parse_request=lambda **kwargs: LLMCallResult(
                    raw_output=json.dumps(test_case.ground_truth),
                    latency_ms=25,
                    total_tokens=42,
                    estimated_cost_usd=0.001,
                ),
            )

        records = _records(logs)
        self.assertEqual(
            [record["event"] for record in records],
            [
                "run.started",
                "case.started",
                "stage.started",
                "stage.started",
                "case.finished",
                "run.finished",
            ],
        )
        self.assertEqual(
            [record["stage"] for record in records if record["event"] == "stage.started"],
            ["document_resolution", "llm_request"],
        )
        for record in records:
            self.assertEqual(record["run_id"], str(RUN_ID))
            self.assertEqual(record["model"], "gemini/gemini-2.5-flash")
            self.assertEqual(record["provider"], "gemini")
            self.assertEqual(record["corpus_id"], str(test_case.corpus_id))

        document_stage = next(
            record
            for record in records
            if record.get("stage") == "document_resolution"
        )
        self.assertEqual(document_stage["layout_to_text_strategy"], "native_layout_to_text")
        self.assertEqual(document_stage["ocr_strategy"], "pytesseract")

        case_finished = records[-2]
        self.assertEqual(case_finished["level"], "INFO")
        self.assertEqual(case_finished["outcome"], "scored")
        self.assertEqual(case_finished["model"], "gemini/gemini-2.5-flash")
        self.assertEqual(case_finished["provider"], "gemini")
        self.assertEqual(case_finished["latency_ms"], 25)
        self.assertEqual(case_finished["total_tokens"], 42)
        self.assertEqual(case_finished["mismatch_count"], 0)
        self.assertEqual(records[-1]["attempted"], 1)
        self.assertEqual(records[-1]["scored"], 1)
        self.assertEqual(records[-1]["failed"], 0)
        self.assertNotIn("INV-0001", logs.getvalue())

        result_lines = stdout.getvalue().splitlines()
        self.assertEqual(len(result_lines), 2)
        self.assertNotIn("run.started", stdout.getvalue())

    def test_zero_score_is_info_without_logging_raw_response(self) -> None:
        sensitive_response = "sensitive malformed provider response"
        logs = StringIO()
        configure_logging(level="INFO", log_format="json", stream=logs)

        with redirect_stdout(StringIO()):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                env_path=None,
                output_format="jsonl",
                structured_parse_request=lambda **kwargs: LLMCallResult(
                    raw_output=sensitive_response
                ),
            )

        records = _records(logs)
        case_finished = next(record for record in records if record["event"] == "case.finished")
        run_finished = records[-1]
        self.assertEqual(case_finished["level"], "INFO")
        self.assertEqual(case_finished["outcome"], "zero_score")
        self.assertEqual(case_finished["failure_reason"], "invalid_json")
        self.assertEqual(run_finished["level"], "INFO")
        self.assertEqual(run_finished["zero_score"], 1)
        self.assertNotIn(sensitive_response, logs.getvalue())

    def test_provider_failure_is_error_without_logging_exception_text(self) -> None:
        sensitive_error = "auth failed with sensitive credential"
        logs = StringIO()
        configure_logging(level="INFO", log_format="json", stream=logs)

        def failing_request(**kwargs):
            raise LLMCallError("provider call failed") from AuthenticationError(sensitive_error)

        with redirect_stdout(StringIO()):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                env_path=None,
                output_format="jsonl",
                structured_parse_request=failing_request,
            )

        records = _records(logs)
        case_finished = next(record for record in records if record["event"] == "case.finished")
        run_finished = records[-1]
        self.assertEqual(case_finished["level"], "ERROR")
        self.assertEqual(case_finished["outcome"], "failed")
        self.assertEqual(case_finished["failure_reason"], "auth_error")
        self.assertEqual(run_finished["level"], "ERROR")
        self.assertEqual(run_finished["outcome"], "failed")
        self.assertEqual(run_finished["failed"], 1)
        self.assertNotIn(sensitive_error, logs.getvalue())
        self.assertNotIn("provider call failed", logs.getvalue())


def _records(output: StringIO) -> list[dict]:
    return [json.loads(line) for line in output.getvalue().splitlines()]


if __name__ == "__main__":
    unittest.main()
