from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from upath import UPath

from single_pass_parsing_ranker import (
    AttemptStatus,
    FieldComparison,
    Run,
    RunStatus,
    RunTestCase,
    write_run_bundle,
)


CORPUS_ID = UUID("3d2f2e84-7f80-4d8d-a243-3b2d273d4a04")
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")
TEST_CASE_ID = UUID("5c9c0d9b-a412-4f0a-9cc6-fdb164b2c1f5")


class StorageTests(unittest.TestCase):
    def test_write_run_bundle_writes_complete_result_files(self) -> None:
        run = Run(
            run_id=RUN_ID,
            model="openai/gpt-4o-mini",
            corpus_id=CORPUS_ID,
            provider="openai",
            model_settings={"temperature": 0},
            status=RunStatus.COMPLETED,
        )
        test_cases = (
            RunTestCase(
                run_id=RUN_ID,
                test_case_id=TEST_CASE_ID,
                status=AttemptStatus.SCORED,
                score=1.0,
                raw_output='{"ok": true}',
                parsed_output={"ok": True},
                normalized_output={"ok": True},
            ),
            RunTestCase(
                run_id=RUN_ID,
                test_case_id=TEST_CASE_ID,
                status=AttemptStatus.ZERO_SCORE,
                score=0.0,
                raw_output="not json",
            ),
        )
        comparisons = (
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

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "nested"
            run_dir = write_run_bundle(output_dir, run, test_cases, comparisons)

            restored_run = Run.model_validate_json((run_dir / "run.json").read_text(encoding="utf-8"))
            restored_cases = [
                RunTestCase.model_validate_json(line)
                for line in (run_dir / "run_test_cases.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            restored_comparisons = [
                FieldComparison.model_validate_json(line)
                for line in (run_dir / "field_comparisons.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(run_dir, output_dir / f"run_id={RUN_ID}")
        self.assertEqual(restored_run.run_id, RUN_ID)
        self.assertEqual(restored_run.model_settings, {"temperature": 0})
        self.assertEqual([row.status for row in restored_cases], [AttemptStatus.SCORED, AttemptStatus.ZERO_SCORE])
        self.assertEqual(len(restored_comparisons), 1)
        self.assertEqual(restored_comparisons[0].field_path, "total")

    def test_write_run_bundle_writes_empty_comparison_file(self) -> None:
        run = Run(run_id=RUN_ID, model="model", corpus_id=CORPUS_ID, status=RunStatus.COMPLETED)

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = write_run_bundle(temp_dir, run, (), ())
            comparison_payload = (run_dir / "field_comparisons.jsonl").read_text(encoding="utf-8")

        self.assertEqual(comparison_payload, "")

    def test_write_run_bundle_does_not_overwrite_existing_run(self) -> None:
        run = Run(run_id=RUN_ID, model="model", corpus_id=CORPUS_ID, status=RunStatus.COMPLETED)

        with tempfile.TemporaryDirectory() as temp_dir:
            write_run_bundle(temp_dir, run, (), ())
            with self.assertRaises(FileExistsError):
                write_run_bundle(temp_dir, run, (), ())

    def test_write_run_bundle_supports_remote_filesystem(self) -> None:
        run = Run(run_id=RUN_ID, model="model", corpus_id=CORPUS_ID, status=RunStatus.COMPLETED)
        output_dir = UPath(f"memory://sppr-storage-{uuid4()}")

        run_dir = write_run_bundle(output_dir, run, (), ())

        self.assertEqual(Run.model_validate_json((run_dir / "run.json").read_text()).run_id, RUN_ID)
        self.assertEqual((run_dir / "run_test_cases.jsonl").read_text(), "")
        self.assertEqual((run_dir / "field_comparisons.jsonl").read_text(), "")

    def test_write_failure_does_not_create_completion_marker(self) -> None:
        run = Run(run_id=RUN_ID, model="model", corpus_id=CORPUS_ID, status=RunStatus.COMPLETED)
        output_dir = UPath(f"memory://sppr-storage-{uuid4()}")
        path_type = type(output_dir)
        write_text = path_type.write_text

        def fail_on_comparisons(path, data, *args, **kwargs):
            if path.name == "field_comparisons.jsonl":
                raise OSError("simulated write failure")
            return write_text(path, data, *args, **kwargs)

        with patch.object(path_type, "write_text", fail_on_comparisons):
            with self.assertRaisesRegex(OSError, "simulated write failure"):
                write_run_bundle(output_dir, run, (), ())

        run_dir = output_dir / f"run_id={RUN_ID}"
        self.assertTrue((run_dir / "run_test_cases.jsonl").exists())
        self.assertFalse((run_dir / "run.json").exists())


if __name__ == "__main__":
    unittest.main()
