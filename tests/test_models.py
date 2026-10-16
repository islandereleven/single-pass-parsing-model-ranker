from datetime import UTC
import unittest
from uuid import UUID

from pydantic import ValidationError

from single_pass_parsing_ranker import (
    AttemptStatus,
    DataModelSchema,
    Document,
    FieldComparison,
    FieldComparisonMethod,
    FieldEvaluation,
    FailureReason,
    LayoutToTextStrategy,
    OcrStrategy,
    Run,
    RunStatus,
    RunTestCase,
    storage_schemas,
)

CORPUS_ID = UUID("3d2f2e84-7f80-4d8d-a243-3b2d273d4a04")
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")
TEST_CASE_ID = UUID("5c9c0d9b-a412-4f0a-9cc6-fdb164b2c1f5")
DOCUMENT_ID = UUID("2dcad689-51a8-4c19-8a6e-8ed72fb2e4d9")


class ModelTests(unittest.TestCase):
    def test_run_defaults_to_litellm_settings(self) -> None:
        run = Run(
            run_id=RUN_ID,
            model="openai/gpt-4o-mini",
            corpus_id=CORPUS_ID,
        )

        self.assertEqual(run.model, "openai/gpt-4o-mini")
        self.assertIsNone(run.provider)
        self.assertEqual(run.status, RunStatus.RUNNING)
        self.assertEqual(run.model_settings, {})
        self.assertEqual(run.layout_to_text_strategy, LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT)
        self.assertEqual(run.ocr_strategy, OcrStrategy.PYTESSERACT)

    def test_run_round_trips_as_storage_json(self) -> None:
        run = Run(
            run_id=RUN_ID,
            provider="openai",
            model="openai/gpt-4o-mini",
            corpus_id=CORPUS_ID,
        )

        restored = Run.model_validate_json(run.model_dump_json())

        self.assertEqual(restored.run_id, run.run_id)
        self.assertEqual(restored.status, RunStatus.RUNNING)
        self.assertEqual(restored.created_at.tzinfo, UTC)

    def test_run_test_case_records_scored_attempt(self) -> None:
        row = RunTestCase(
            run_id=RUN_ID,
            test_case_id=TEST_CASE_ID,
            status=AttemptStatus.SCORED,
            score=1.0,
            raw_output='{"ok": true}',
            parsed_output={"ok": True},
            normalized_output={"ok": True},
            latency_ms=250,
            input_tokens=100,
            output_tokens=25,
            total_tokens=125,
            estimated_cost_usd=0.001,
            document_text_sha256="abc123",
        )

        self.assertEqual(row.status, AttemptStatus.SCORED)
        self.assertEqual(row.score, 1.0)
        self.assertIsNone(row.failure_reason)
        self.assertEqual(row.document_text_sha256, "abc123")

    def test_run_test_case_records_zero_score_attempt(self) -> None:
        row = RunTestCase(
            run_id=RUN_ID,
            test_case_id=TEST_CASE_ID,
            status=AttemptStatus.ZERO_SCORE,
            score=0.0,
            raw_output="not json",
            failure_reason=FailureReason.INVALID_JSON,
        )

        self.assertEqual(row.status, AttemptStatus.ZERO_SCORE)
        self.assertEqual(row.score, 0.0)
        self.assertEqual(row.failure_reason, FailureReason.INVALID_JSON)

    def test_field_comparison_records_field_level_outcome(self) -> None:
        row = FieldComparison(
            run_id=RUN_ID,
            test_case_id=TEST_CASE_ID,
            field_path="total",
            expected_value=123.45,
            actual_value=120.0,
            matched=False,
            score=0.5,
            comparison_method=FieldComparisonMethod.FUZZY_TEXT,
        )

        self.assertFalse(row.matched)
        self.assertEqual(row.score, 0.5)
        self.assertEqual(row.comparison_method, FieldComparisonMethod.FUZZY_TEXT)

    def test_field_evaluation_defaults_to_exact_comparison(self) -> None:
        evaluation = FieldEvaluation()

        self.assertEqual(evaluation.comparison, FieldComparisonMethod.EXACT)

    def test_document_records_source_disclosure(self) -> None:
        document = Document(
            document_id=DOCUMENT_ID,
            path="acme_invoice.txt",
            source_name="ACME Invoice Fixture",
            source_record_id="acme_invoice",
        )

        self.assertEqual(document.source_name, "ACME Invoice Fixture")
        self.assertEqual(document.source_record_id, "acme_invoice")

    def test_document_path_round_trips_as_uri(self) -> None:
        document = Document(
            document_id=DOCUMENT_ID,
            path="s3://example-bucket/documents/invoice.txt",
            source_name="Example",
        )

        restored = Document.model_validate_json(document.model_dump_json())

        self.assertEqual(str(restored.path), "s3://example-bucket/documents/invoice.txt")

    def test_data_model_schema_rejects_unknown_comparison_method(self) -> None:
        with self.assertRaises(ValidationError):
            DataModelSchema({
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "evaluation": {"comparison": "close_enough"},
                    }
                },
            })

    def test_storage_models_reject_extra_fields(self) -> None:
        with self.assertRaises(ValidationError):
            Run(
                run_id=RUN_ID,
                model="openai/gpt-4o-mini",
                corpus_id=CORPUS_ID,
                aggregate_score=1.0,
            )

    def test_storage_schemas_include_expected_tables(self) -> None:
        schemas = storage_schemas()

        self.assertEqual(set(schemas), {"runs", "run_test_cases", "field_comparisons"})
        self.assertEqual(schemas["runs"]["additionalProperties"], False)
        self.assertEqual(schemas["run_test_cases"]["additionalProperties"], False)
        self.assertEqual(schemas["field_comparisons"]["additionalProperties"], False)


if __name__ == "__main__":
    unittest.main()
