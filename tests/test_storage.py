from contextlib import redirect_stdout
from io import StringIO
import unittest
from uuid import UUID

from single_pass_parsing_ranker import (
    AttemptStatus,
    FieldComparison,
    Run,
    RunTestCase,
    append_field_comparison,
    append_run,
    append_run_test_case,
)


CORPUS_ID = UUID("3d2f2e84-7f80-4d8d-a243-3b2d273d4a04")
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")
TEST_CASE_ID = UUID("5c9c0d9b-a412-4f0a-9cc6-fdb164b2c1f5")


class StorageTests(unittest.TestCase):
    def test_append_run_prints_one_json_row(self) -> None:
        output = StringIO()
        run = Run(
            run_id=RUN_ID,
            model="openai/gpt-4o-mini",
            corpus_id=CORPUS_ID,
            provider="openai",
            model_settings={"temperature": 0},
        )

        with redirect_stdout(output):
            append_run("runs/runs.jsonl", run)

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        restored = Run.model_validate_json(lines[0])
        self.assertEqual(restored.run_id, RUN_ID)
        self.assertEqual(restored.model_settings, {"temperature": 0})

    def test_append_run_test_case_prints_json_rows(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            append_run_test_case(
                "runs/run_test_cases.jsonl",
                RunTestCase(
                    run_id=RUN_ID,
                    test_case_id=TEST_CASE_ID,
                    status=AttemptStatus.SCORED,
                    score=1.0,
                    raw_output='{"ok": true}',
                    parsed_output={"ok": True},
                    normalized_output={"ok": True},
                ),
            )
            append_run_test_case(
                "runs/run_test_cases.jsonl",
                RunTestCase(
                    run_id=RUN_ID,
                    test_case_id=TEST_CASE_ID,
                    status=AttemptStatus.ZERO_SCORE,
                    score=0.0,
                    raw_output="not json",
                ),
            )

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(RunTestCase.model_validate_json(lines[0]).status, AttemptStatus.SCORED)
        self.assertEqual(RunTestCase.model_validate_json(lines[1]).status, AttemptStatus.ZERO_SCORE)

    def test_append_field_comparison_prints_json_row(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            append_field_comparison(
                "runs/field_comparisons.jsonl",
                FieldComparison(
                    run_id=RUN_ID,
                    test_case_id=TEST_CASE_ID,
                    field_path="total",
                    expected_value=123.45,
                    actual_value=120.0,
                    matched=False,
                    score=0.0,
                ),
            )

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        restored = FieldComparison.model_validate_json(lines[0])
        self.assertEqual(restored.field_path, "total")
        self.assertFalse(restored.matched)


if __name__ == "__main__":
    unittest.main()
