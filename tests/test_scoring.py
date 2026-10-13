import unittest
from uuid import UUID

from single_pass_parsing_ranker import (
    FieldComparisonMethod,
    comparison_method_for_path,
    field_comparisons,
    field_scores,
    flatten_json_value,
    fuzzy_text_score,
    score_field_comparisons,
    score_json_values,
)


RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")
TEST_CASE_ID = UUID("5c9c0d9b-a412-4f0a-9cc6-fdb164b2c1f5")


class ScoringTests(unittest.TestCase):
    def test_scores_exact_match_as_one(self) -> None:
        value = {"vendor": "Acme Corp", "total": 123.45}

        self.assertEqual(score_json_values(value, value), 1.0)

    def test_scores_average_of_field_matches(self) -> None:
        output = {"vendor": "Acme Corp", "total": 120.0, "currency": "USD"}
        ground_truth = {"vendor": "Acme Corp", "total": 123.45, "currency": "USD"}

        self.assertEqual(field_scores(output, ground_truth), {
            "currency": 1,
            "total": 0,
            "vendor": 1,
        })
        self.assertEqual(score_json_values(output, ground_truth), 2 / 3)

    def test_scores_missing_and_extra_fields_as_zero(self) -> None:
        output = {"vendor": "Acme Corp", "total": 123.45, "extra": "nope"}
        ground_truth = {"vendor": "Acme Corp", "currency": "USD"}

        self.assertEqual(field_scores(output, ground_truth), {
            "currency": 0,
            "extra": 0,
            "total": 0,
            "vendor": 1,
        })
        self.assertEqual(score_json_values(output, ground_truth), 0.25)

    def test_builds_field_comparisons_with_presence_flags(self) -> None:
        comparisons = field_comparisons(
            run_id=RUN_ID,
            test_case_id=TEST_CASE_ID,
            output={"vendor": None},
            ground_truth={"vendor": None, "total": 123.45},
        )
        by_path = {comparison.field_path: comparison for comparison in comparisons}

        self.assertTrue(by_path["vendor"].matched)
        self.assertEqual(by_path["vendor"].score, 1.0)
        self.assertTrue(by_path["vendor"].expected_present)
        self.assertTrue(by_path["vendor"].actual_present)
        self.assertIsNone(by_path["vendor"].expected_value)
        self.assertIsNone(by_path["vendor"].actual_value)

        self.assertFalse(by_path["total"].matched)
        self.assertEqual(by_path["total"].score, 0.0)
        self.assertTrue(by_path["total"].expected_present)
        self.assertFalse(by_path["total"].actual_present)
        self.assertEqual(by_path["total"].expected_value, 123.45)
        self.assertIsNone(by_path["total"].actual_value)
        self.assertEqual(score_field_comparisons(comparisons), 0.5)

    def test_fuzzy_text_comparison_scores_similar_strings(self) -> None:
        data_model = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "evaluation": {"comparison": "fuzzy_text"},
                }
            },
        }

        comparisons = field_comparisons(
            run_id=RUN_ID,
            test_case_id=TEST_CASE_ID,
            output={"address": "3043 Peters Lights Suite 433 Greerton, NV 21983"},
            ground_truth={"address": "3043 Peters Lights Suite 433\nGreerton, NV 21983"},
            data_model=data_model,
        )

        self.assertEqual(comparisons[0].comparison_method, FieldComparisonMethod.FUZZY_TEXT)
        self.assertEqual(comparisons[0].score, 1.0)
        self.assertTrue(comparisons[0].matched)

    def test_fuzzy_text_comparison_returns_partial_credit_without_threshold(self) -> None:
        score = fuzzy_text_score("Cartoon Rabbit Printed Round Carpet", "ils Cartoon Rabbit Printed Round Carpet")

        self.assertGreater(score, 0.8)
        self.assertLess(score, 1.0)

    def test_resolves_array_item_comparison_metadata(self) -> None:
        data_model = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "evaluation": {"comparison": "fuzzy_text"},
                            },
                            "sku": {"type": "string"},
                        },
                    },
                }
            },
        }

        self.assertEqual(
            comparison_method_for_path(data_model, "items[6].description"),
            FieldComparisonMethod.FUZZY_TEXT,
        )
        self.assertEqual(
            comparison_method_for_path(data_model, "items[6].sku"),
            FieldComparisonMethod.EXACT,
        )

    def test_flattens_nested_objects_and_lists_to_field_paths(self) -> None:
        value = {
            "invoice_number": "INV-0001",
            "line_items": [
                {"description": "Bolt kit", "total": 37.5},
                {"description": "Service", "total": 125.0},
            ],
        }

        self.assertEqual(flatten_json_value(value), {
            "invoice_number": "INV-0001",
            "line_items[0].description": "Bolt kit",
            "line_items[0].total": 37.5,
            "line_items[1].description": "Service",
            "line_items[1].total": 125.0,
        })

    def test_scores_empty_json_values(self) -> None:
        self.assertEqual(score_json_values({}, {}), 1.0)
        self.assertEqual(score_json_values([], []), 1.0)
        self.assertEqual(score_json_values({}, []), 0.0)


if __name__ == "__main__":
    unittest.main()
