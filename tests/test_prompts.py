import unittest

from single_pass_parsing_ranker import build_prompt


class PromptTests(unittest.TestCase):
    def test_build_prompt_assembles_instruction_schema_and_document(self) -> None:
        prompt = build_prompt(
            instruction="Extract the invoice.",
            document_text="Invoice INV-0001\nTotal: 175.50",
            data_model={
                "type": "object",
                "properties": {
                    "total": {"type": "number"},
                    "invoice_number": {"type": "string"},
                },
            },
        )

        self.assertEqual(
            prompt,
            """Extract the invoice.

Data model:
{
  "properties": {
    "invoice_number": {
      "type": "string"
    },
    "total": {
      "type": "number"
    }
  },
  "type": "object"
}

Document:
Invoice INV-0001
Total: 175.50""",
        )

    def test_build_prompt_rejects_blank_instruction(self) -> None:
        with self.assertRaises(ValueError):
            build_prompt(
                instruction="  ",
                document_text="Invoice text",
                data_model={"type": "object"},
            )

    def test_build_prompt_strips_evaluation_metadata_from_schema(self) -> None:
        prompt = build_prompt(
            instruction="Extract.",
            document_text="Invoice text",
            data_model={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "evaluation": {"comparison": "fuzzy_text"},
                    }
                },
            },
        )

        self.assertIn('"address"', prompt)
        self.assertNotIn("evaluation", prompt)
        self.assertNotIn("fuzzy_text", prompt)

    def test_build_prompt_rejects_blank_document_text(self) -> None:
        with self.assertRaises(ValueError):
            build_prompt(
                instruction="Extract.",
                document_text="  ",
                data_model={"type": "object"},
            )


if __name__ == "__main__":
    unittest.main()
