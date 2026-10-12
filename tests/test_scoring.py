import unittest

from single_pass_parsing_ranker import field_scores, flatten_json_value, score_json_values


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
