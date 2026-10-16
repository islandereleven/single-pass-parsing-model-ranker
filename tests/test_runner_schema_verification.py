from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import unittest
from uuid import UUID

from single_pass_parsing_ranker import (
    AttemptStatus,
    FailureReason,
    LLMCallResult,
    Run,
    RunStatus,
    RunTestCase,
    load_corpus,
    run_evaluation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CORPUS = PROJECT_ROOT / "corpora" / "0.1.0.json"
DOCUMENT_REGISTRY = PROJECT_ROOT / "documents" / "documents.json"
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")


class RunnerSchemaVerificationTests(unittest.TestCase):
    def test_missing_required_field_zero_scores_but_completes_run(self) -> None:
        output = _valid_ground_truth()
        del output["total"]

        case_row, run_row = _run_model_output(output)

        self.assertEqual(case_row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(case_row.score, 0.0)
        self.assertEqual(case_row.failure_reason, FailureReason.SCHEMA_VALIDATION_ERROR)
        self.assertEqual(case_row.parsed_output, output)
        self.assertIsNone(case_row.normalized_output)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)

    def test_wrong_field_type_zero_scores_but_completes_run(self) -> None:
        output = _valid_ground_truth()
        output["total"] = "175.50"

        case_row, run_row = _run_model_output(output)

        self.assertEqual(case_row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(case_row.score, 0.0)
        self.assertEqual(case_row.failure_reason, FailureReason.SCHEMA_VALIDATION_ERROR)
        self.assertEqual(case_row.parsed_output, output)
        self.assertIsNone(case_row.normalized_output)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)

    def test_extra_hallucinated_key_zero_scores_but_completes_run(self) -> None:
        output = _valid_ground_truth()
        output["supplier_email"] = "billing@example.invalid"

        case_row, run_row = _run_model_output(output)

        self.assertEqual(case_row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(case_row.score, 0.0)
        self.assertEqual(case_row.failure_reason, FailureReason.SCHEMA_VALIDATION_ERROR)
        self.assertEqual(case_row.parsed_output, output)
        self.assertIsNone(case_row.normalized_output)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)

    def test_refusal_or_prose_text_zero_scores_as_invalid_json(self) -> None:
        case_row, run_row = _run_raw_output("I cannot extract this document.")

        self.assertEqual(case_row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(case_row.score, 0.0)
        self.assertEqual(case_row.failure_reason, FailureReason.INVALID_JSON)
        self.assertEqual(case_row.raw_output, "I cannot extract this document.")
        self.assertIsNone(case_row.parsed_output)
        self.assertIsNone(case_row.normalized_output)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertIsNone(run_row.failure_reason)


def _valid_ground_truth() -> dict:
    return deepcopy(
        load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0].ground_truth
    )


def _run_model_output(value: dict) -> tuple[RunTestCase, Run]:
    return _run_raw_output(json.dumps(value))


def _run_raw_output(raw_output: str) -> tuple[RunTestCase, Run]:
    output = StringIO()
    with redirect_stdout(output):
        run_evaluation(
            model="gemini/gemini-2.5-flash",
            corpus_path=EXAMPLE_CORPUS,
            document_registry_path=DOCUMENT_REGISTRY,
            run_id=RUN_ID,
            env_path=None,
            output_format="jsonl",
            structured_parse_request=lambda **kwargs: LLMCallResult(raw_output=raw_output),
        )

    lines = output.getvalue().splitlines()
    if len(lines) != 2:
        raise AssertionError(f"expected 2 JSONL rows, got {len(lines)}: {lines!r}")
    return RunTestCase.model_validate_json(lines[0]), Run.model_validate_json(lines[1])


if __name__ == "__main__":
    unittest.main()
