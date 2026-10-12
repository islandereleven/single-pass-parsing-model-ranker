import unittest

from single_pass_parsing_ranker import field_scores, score_json_values


class ScoringVerificationTests(unittest.TestCase):
    def test_scores_one_wrong_scalar_field_as_partial_average(self) -> None:
        output = {
            "invoice_number": "INV-0001",
            "currency": "USD",
            "total": 175.5,
            "payment_terms": "Due on receipt",
        }
        ground_truth = {
            "invoice_number": "INV-0001",
            "currency": "USD",
            "total": 175.5,
            "payment_terms": "Net 30",
        }

        self.assertEqual(field_scores(output, ground_truth), {
            "currency": 1,
            "invoice_number": 1,
            "payment_terms": 0,
            "total": 1,
        })
        self.assertEqual(score_json_values(output, ground_truth), 0.75)

    def test_penalizes_extra_nested_fields_without_hiding_matched_fields(self) -> None:
        output = {
            "supplier": {
                "name": "ACME Widgets",
                "address": "1 Example Lane",
            },
            "total": 175.5,
        }
        ground_truth = {
            "supplier": {
                "name": "ACME Widgets",
            },
            "total": 175.5,
        }

        self.assertEqual(field_scores(output, ground_truth), {
            "supplier.address": 0,
            "supplier.name": 1,
            "total": 1,
        })
        self.assertEqual(score_json_values(output, ground_truth), 2 / 3)

    def test_penalizes_missing_nested_fields(self) -> None:
        output = {
            "supplier": {
                "name": "ACME Widgets",
            },
            "total": 175.5,
        }
        ground_truth = {
            "supplier": {
                "name": "ACME Widgets",
                "address": "1 Example Lane",
            },
            "total": 175.5,
        }

        self.assertEqual(field_scores(output, ground_truth), {
            "supplier.address": 0,
            "supplier.name": 1,
            "total": 1,
        })
        self.assertEqual(score_json_values(output, ground_truth), 2 / 3)

    def test_scores_list_item_field_mismatches_by_index(self) -> None:
        output = {
            "line_items": [
                {"description": "Stainless bolt kit", "quantity": 3, "total": 37.5},
                {"description": "Calibration service", "quantity": 2, "total": 125.0},
            ]
        }
        ground_truth = {
            "line_items": [
                {"description": "Stainless bolt kit", "quantity": 3, "total": 37.5},
                {"description": "Calibration service", "quantity": 1, "total": 125.0},
            ]
        }

        self.assertEqual(field_scores(output, ground_truth), {
            "line_items[0].description": 1,
            "line_items[0].quantity": 1,
            "line_items[0].total": 1,
            "line_items[1].description": 1,
            "line_items[1].quantity": 0,
            "line_items[1].total": 1,
        })
        self.assertEqual(score_json_values(output, ground_truth), 5 / 6)

    def test_extra_list_item_is_penalized_per_leaf_field(self) -> None:
        output = {
            "line_items": [
                {"description": "Stainless bolt kit", "total": 37.5},
                {"description": "Calibration service", "total": 125.0},
            ]
        }
        ground_truth = {
            "line_items": [
                {"description": "Stainless bolt kit", "total": 37.5},
            ]
        }

        self.assertEqual(field_scores(output, ground_truth), {
            "line_items[0].description": 1,
            "line_items[0].total": 1,
            "line_items[1].description": 0,
            "line_items[1].total": 0,
        })
        self.assertEqual(score_json_values(output, ground_truth), 0.5)

    def test_missing_list_item_is_penalized_per_leaf_field(self) -> None:
        output = {
            "line_items": [
                {"description": "Stainless bolt kit", "total": 37.5},
            ]
        }
        ground_truth = {
            "line_items": [
                {"description": "Stainless bolt kit", "total": 37.5},
                {"description": "Calibration service", "total": 125.0},
            ]
        }

        self.assertEqual(field_scores(output, ground_truth), {
            "line_items[0].description": 1,
            "line_items[0].total": 1,
            "line_items[1].description": 0,
            "line_items[1].total": 0,
        })
        self.assertEqual(score_json_values(output, ground_truth), 0.5)

    def test_list_order_matters_because_paths_are_indexed(self) -> None:
        output = {
            "line_items": [
                {"description": "Calibration service", "total": 125.0},
                {"description": "Stainless bolt kit", "total": 37.5},
            ]
        }
        ground_truth = {
            "line_items": [
                {"description": "Stainless bolt kit", "total": 37.5},
                {"description": "Calibration service", "total": 125.0},
            ]
        }

        self.assertEqual(score_json_values(output, ground_truth), 0.0)

    def test_scalar_values_are_compared_exactly_after_normalization(self) -> None:
        self.assertEqual(score_json_values({"total": 175.5}, {"total": 175.50}), 1.0)
        self.assertEqual(score_json_values({"total": "175.5"}, {"total": 175.5}), 0.0)

        # The scorer runs after schema normalization; Python equality applies here.
        self.assertEqual(score_json_values({"paid": True}, {"paid": 1}), 1.0)


if __name__ == "__main__":
    unittest.main()
