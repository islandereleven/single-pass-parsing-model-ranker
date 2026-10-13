import unittest

from single_pass_parsing_ranker import (
    JsonParseError,
    SchemaValidationError,
    normalize_json_value,
    parse_json_output,
)


INVOICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["vendor", "total"],
    "properties": {
        "vendor": {"type": "string"},
        "total": {"type": "number"},
    },
}


class NormalizeTests(unittest.TestCase):
    def test_parse_json_output_returns_json_value(self) -> None:
        self.assertEqual(parse_json_output('{"vendor": "Acme Corp", "total": 123.45}'), {
            "vendor": "Acme Corp",
            "total": 123.45,
        })

    def test_parse_json_output_rejects_invalid_json(self) -> None:
        with self.assertRaises(JsonParseError):
            parse_json_output("not json")

    def test_normalize_json_value_validates_against_schema(self) -> None:
        value = {"vendor": "Acme Corp", "total": 123.45}

        self.assertEqual(normalize_json_value(value, INVOICE_SCHEMA), value)

    def test_normalize_json_value_ignores_evaluation_metadata(self) -> None:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["address"],
            "properties": {
                "address": {
                    "type": "string",
                    "evaluation": {"comparison": "fuzzy_text"},
                }
            },
        }

        value = {"address": "3043 Peters Lights Suite 433"}

        self.assertEqual(normalize_json_value(value, schema), value)

    def test_normalize_json_value_rejects_schema_mismatch(self) -> None:
        with self.assertRaises(SchemaValidationError):
            normalize_json_value({"vendor": "Acme Corp", "total": "123.45"}, INVOICE_SCHEMA)

    def test_same_normalizer_handles_output_and_ground_truth_values(self) -> None:
        parsed_output = parse_json_output('{"vendor": "Acme Corp", "total": 123.45}')
        ground_truth = {"vendor": "Acme Corp", "total": 123.45}

        normalized_output = normalize_json_value(parsed_output, INVOICE_SCHEMA)
        normalized_ground_truth = normalize_json_value(ground_truth, INVOICE_SCHEMA)

        self.assertEqual(normalized_output, normalized_ground_truth)

    def test_same_normalizer_rejects_invalid_ground_truth_fixture(self) -> None:
        with self.assertRaises(SchemaValidationError):
            normalize_json_value({"vendor": "Acme Corp"}, INVOICE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
