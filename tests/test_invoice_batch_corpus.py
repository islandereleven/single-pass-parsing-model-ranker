from pathlib import Path
import json
import unittest
from uuid import UUID

from single_pass_parsing_ranker import (
    load_corpora,
    load_corpus,
    load_documents,
    normalize_json_value,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = PROJECT_ROOT / "corpora" / "0.2.0.json"
MINI_CORPUS_PATH = PROJECT_ROOT / "corpora" / "0.3.0.json"
CORPORA_PATH = PROJECT_ROOT / "corpora" / "corpora.json"
DOCUMENTS_PATH = PROJECT_ROOT / "documents" / "documents.json"
DOCUMENT_DIR = PROJECT_ROOT / "documents" / "invoice-batch-1-sample-20-v0.1"
CORPUS_ID = UUID("3b0d1e43-a649-5e66-a3b0-1a03960970e3")
MINI_CORPUS_ID = UUID("e714c86b-f654-5357-823c-cb51fe8602af")
ACME_DOCUMENT_ID = UUID("2dcad689-51a8-4c19-8a6e-8ed72fb2e4d9")
ACME_SOURCE_NAME = "ACME Invoice Fixture"
KAGGLE_SOURCE_NAME = "High-Quality Invoice Images for OCR"


class Version020CorpusTests(unittest.TestCase):
    def test_loads_version_020_corpus(self) -> None:
        rows = load_corpus(CORPUS_PATH)
        corpora = load_corpora(CORPORA_PATH)

        self.assertIn(CORPUS_ID, corpora)
        self.assertEqual(corpora[CORPUS_ID].version, "0.2.0")
        self.assertEqual(len(rows), 21)
        self.assertEqual({row.corpus_id for row in rows}, {CORPUS_ID})
        self.assertEqual(len({row.test_case_id for row in rows}), 21)
        self.assertEqual(len({row.document_id for row in rows}), 21)
        self.assertEqual(sum(row.document_id == ACME_DOCUMENT_ID for row in rows), 1)
        self.assertEqual(sum(row.data_model["title"] == "InvoiceExtraction" for row in rows), 20)
        self.assertEqual(sum(row.data_model["title"] == "Invoice" for row in rows), 1)
        self.assertTrue(all("Return exactly one JSON object" in row.prompt for row in rows))

    def test_version_020_uses_acme_text_and_source_jpegs_only(self) -> None:
        rows = load_corpus(CORPUS_PATH)
        documents = load_documents(DOCUMENTS_PATH)
        files = sorted(DOCUMENT_DIR.iterdir())
        jpg_files = sorted(path for path in files if path.suffix == ".jpg")
        txt_files = sorted(path for path in files if path.suffix == ".txt")
        corpus_document_paths = [documents[row.document_id].path for row in rows]

        self.assertEqual(len(files), 20)
        self.assertEqual(len(jpg_files), 20)
        self.assertEqual(len(txt_files), 0)
        self.assertEqual(sum(path.suffix == ".jpg" for path in corpus_document_paths), 20)
        self.assertEqual(sum(path.name == "acme_invoice.txt" for path in corpus_document_paths), 1)
        self.assertEqual(documents[ACME_DOCUMENT_ID].source_name, ACME_SOURCE_NAME)
        self.assertEqual(sum(documents[row.document_id].source_name == ACME_SOURCE_NAME for row in rows), 1)
        self.assertEqual(sum(documents[row.document_id].source_name == KAGGLE_SOURCE_NAME for row in rows), 20)
        self.assertTrue(documents[ACME_DOCUMENT_ID].path.read_text(encoding="utf-8").strip())

        for path in jpg_files:
            with path.open("rb") as file:
                self.assertEqual(file.read(3), b"\xff\xd8\xff")

    def test_version_020_corpus_does_not_embed_ocr_text(self) -> None:
        raw = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        rendered = json.dumps(raw)

        self.assertNotIn("source_ocr_text", rendered)
        self.assertNotIn("OCRed Text", rendered)

    def test_version_020_ground_truth_matches_inline_data_model(self) -> None:
        for row in load_corpus(CORPUS_PATH):
            self.assertEqual(normalize_json_value(row.ground_truth, row.data_model), row.ground_truth)

    def test_version_020_invoice_batch_amounts_are_numbers(self) -> None:
        rows = [row for row in load_corpus(CORPUS_PATH) if row.data_model["title"] == "InvoiceExtraction"]

        for row in rows:
            item_properties = row.data_model["properties"]["items"]["items"]["properties"]
            subtotal_properties = row.data_model["properties"]["subtotal"]["properties"]
            self.assertEqual(item_properties["quantity"]["type"], "number")
            self.assertEqual(item_properties["total_price"]["type"], "number")
            self.assertEqual(subtotal_properties["tax"]["type"], "number")
            self.assertEqual(subtotal_properties["total"]["type"], "number")

            for item in row.ground_truth["items"]:
                self.assertIsInstance(item["quantity"], (int, float))
                self.assertIsInstance(item["total_price"], (int, float))
            self.assertIsInstance(row.ground_truth["subtotal"]["tax"], (int, float))
            self.assertIsInstance(row.ground_truth["subtotal"]["total"], (int, float))

    def test_version_020_invoice_batch_marks_text_noise_fields_as_fuzzy(self) -> None:
        rows = [row for row in load_corpus(CORPUS_PATH) if row.data_model["title"] == "InvoiceExtraction"]

        for row in rows:
            invoice_properties = row.data_model["properties"]["invoice"]["properties"]
            item_properties = row.data_model["properties"]["items"]["items"]["properties"]
            self.assertEqual(invoice_properties["client_address"]["evaluation"]["comparison"], "fuzzy_text")
            self.assertEqual(invoice_properties["seller_address"]["evaluation"]["comparison"], "fuzzy_text")
            self.assertEqual(item_properties["description"]["evaluation"]["comparison"], "fuzzy_text")
            self.assertNotIn("evaluation", row.data_model["properties"]["payment_instructions"]["properties"]["account_number"])


class Version030MiniCorpusTests(unittest.TestCase):
    def test_loads_version_030_mini_mixed_corpus(self) -> None:
        rows = load_corpus(MINI_CORPUS_PATH)
        corpora = load_corpora(CORPORA_PATH)
        documents = load_documents(DOCUMENTS_PATH)

        self.assertIn(MINI_CORPUS_ID, corpora)
        self.assertEqual(corpora[MINI_CORPUS_ID].version, "0.3.0")
        self.assertEqual(len(rows), 2)
        self.assertEqual({row.corpus_id for row in rows}, {MINI_CORPUS_ID})
        self.assertEqual(rows[0].document_id, ACME_DOCUMENT_ID)
        self.assertEqual(documents[rows[0].document_id].path.name, "acme_invoice.txt")
        self.assertEqual(documents[rows[1].document_id].path.suffix, ".jpg")
        self.assertEqual(documents[rows[1].document_id].source_name, KAGGLE_SOURCE_NAME)
        self.assertEqual(documents[rows[1].document_id].source_record_id, "batch1-0042")
        self.assertEqual(rows[0].data_model["title"], "Invoice")
        self.assertEqual(rows[1].data_model["title"], "InvoiceExtraction")

    def test_version_030_invoice_batch_amounts_are_numbers(self) -> None:
        row = load_corpus(MINI_CORPUS_PATH)[1]
        item_properties = row.data_model["properties"]["items"]["items"]["properties"]
        subtotal_properties = row.data_model["properties"]["subtotal"]["properties"]

        self.assertEqual(item_properties["quantity"]["type"], "number")
        self.assertEqual(item_properties["total_price"]["type"], "number")
        self.assertEqual(subtotal_properties["tax"]["type"], "number")
        self.assertEqual(subtotal_properties["total"]["type"], "number")
        self.assertIsInstance(row.ground_truth["items"][0]["quantity"], (int, float))
        self.assertIsInstance(row.ground_truth["items"][0]["total_price"], (int, float))
        self.assertIsInstance(row.ground_truth["subtotal"]["tax"], (int, float))
        self.assertIsInstance(row.ground_truth["subtotal"]["total"], (int, float))

    def test_version_030_invoice_batch_marks_text_noise_fields_as_fuzzy(self) -> None:
        row = load_corpus(MINI_CORPUS_PATH)[1]
        invoice_properties = row.data_model["properties"]["invoice"]["properties"]
        item_properties = row.data_model["properties"]["items"]["items"]["properties"]

        self.assertEqual(invoice_properties["client_address"]["evaluation"]["comparison"], "fuzzy_text")
        self.assertEqual(invoice_properties["seller_address"]["evaluation"]["comparison"], "fuzzy_text")
        self.assertEqual(item_properties["description"]["evaluation"]["comparison"], "fuzzy_text")
        self.assertNotIn("evaluation", row.data_model["properties"]["payment_instructions"]["properties"]["account_number"])


if __name__ == "__main__":
    unittest.main()
