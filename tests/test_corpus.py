from pathlib import Path
import json
import shutil
import tempfile
import unittest
from uuid import UUID

from single_pass_parsing_ranker import (
    CorpusLoadError,
    DataModelSchema,
    load_corpora,
    load_corpus,
    load_documents,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CORPUS = PROJECT_ROOT / "corpora" / "0.1.0.json"
EXAMPLE_CORPORA = PROJECT_ROOT / "corpora" / "corpora.json"
EXAMPLE_DOCUMENTS = PROJECT_ROOT / "documents"
CORPUS_ID = UUID("3d2f2e84-7f80-4d8d-a243-3b2d273d4a04")
DOCUMENT_ID = UUID("2dcad689-51a8-4c19-8a6e-8ed72fb2e4d9")
TEST_CASE_ID = UUID("5c9c0d9b-a412-4f0a-9cc6-fdb164b2c1f5")
MISSING_CORPUS_ID = "8f2d5d98-9db0-41fa-b1b3-4a7fb95eb781"
MISSING_DOCUMENT_ID = "f2169cf3-bf4d-4f14-8890-bf69517bff89"


def copy_fixture(temp_root: Path) -> Path:
    copied_corpus = temp_root / "corpora" / "0.1.0.json"
    copied_corpora = temp_root / "corpora" / "corpora.json"
    copied_documents = temp_root / "documents"
    copied_corpus.parent.mkdir(parents=True)
    shutil.copy2(EXAMPLE_CORPUS, copied_corpus)
    shutil.copy2(EXAMPLE_CORPORA, copied_corpora)
    shutil.copytree(EXAMPLE_DOCUMENTS, copied_documents)
    return copied_corpus


class TestCaseLoadingTests(unittest.TestCase):
    def test_loads_example_corpus_table(self) -> None:
        rows = load_corpus(EXAMPLE_CORPUS)
        corpora = load_corpora(EXAMPLE_CORPORA)
        raw_corpus = json.loads(EXAMPLE_CORPUS.read_text(encoding="utf-8"))
        raw_documents = json.loads((EXAMPLE_DOCUMENTS / "documents.json").read_text(encoding="utf-8"))

        self.assertEqual(tuple(row.test_case_id for row in rows), (TEST_CASE_ID,))
        self.assertIn(CORPUS_ID, corpora)
        self.assertIsInstance(raw_corpus, list)
        self.assertEqual(raw_corpus[0]["corpus_id"], str(CORPUS_ID))
        self.assertEqual(raw_corpus[0]["test_case_id"], str(TEST_CASE_ID))
        self.assertEqual(raw_corpus[0]["data_model"]["title"], "Invoice")
        self.assertNotIn("data_model_id", raw_corpus[0])
        self.assertIsInstance(raw_documents, list)
        self.assertEqual(raw_documents[0]["document_id"], str(DOCUMENT_ID))
        self.assertEqual(raw_documents[0]["source_name"], "ACME Invoice Fixture")
        self.assertEqual(raw_documents[0]["source_record_id"], "acme_invoice")

        row = rows[0]
        self.assertEqual(row.corpus_id, CORPUS_ID)
        self.assertEqual(row.document_id, DOCUMENT_ID)
        self.assertEqual(row.data_model["title"], "Invoice")
        self.assertIn("Return exactly one JSON object", row.prompt)

    def test_reads_document_and_inline_data_model(self) -> None:
        row = load_corpus(EXAMPLE_CORPUS)[0]
        documents = load_documents(EXAMPLE_DOCUMENTS / "documents.json")
        document = documents[row.document_id].path.read_text(encoding="utf-8")
        data_model = row.data_model

        self.assertIn("Invoice INV-0001", document)
        self.assertEqual(documents[row.document_id].path.name, "acme_invoice.txt")
        self.assertEqual(data_model["title"], "Invoice")
        self.assertEqual(data_model["type"], "object")
        self.assertIn("provided data model", row.prompt)
        self.assertEqual(row.ground_truth["invoice_number"], "INV-0001")
        self.assertEqual(row.ground_truth["total"], 175.5)

    def test_exposes_the_row_data_model_as_a_contract_model(self) -> None:
        data_model = DataModelSchema({"title": "Invoice", "type": "object", "properties": {}})

        self.assertEqual(data_model.as_dict()["title"], "Invoice")

    def test_rejects_non_object_row_data_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            copied_corpus = copy_fixture(temp_root)

            table = json.loads(copied_corpus.read_text(encoding="utf-8"))
            table[0]["data_model"] = {"type": "array", "items": {"type": "string"}}
            copied_corpus.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")

            with self.assertRaises(CorpusLoadError):
                load_corpus(copied_corpus)

    def test_rejects_fixed_document_checksum_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            copied_corpus = copy_fixture(temp_root)
            copied_documents = temp_root / "documents"

            document = copied_documents / "acme_invoice.txt"
            edited = document.read_text(encoding="utf-8") + "\nUnexpected edit.\n"
            document.write_text(edited, encoding="utf-8")

            with self.assertRaises(CorpusLoadError):
                load_corpus(copied_corpus)

    def test_rejects_rows_that_reference_unknown_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            copied_corpus = copy_fixture(temp_root)

            table = json.loads(copied_corpus.read_text(encoding="utf-8"))
            table[0]["document_id"] = MISSING_DOCUMENT_ID
            copied_corpus.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")

            with self.assertRaises(CorpusLoadError):
                load_corpus(copied_corpus)

    def test_rejects_rows_that_reference_unknown_corpora(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            copied_corpus = copy_fixture(temp_root)

            table = json.loads(copied_corpus.read_text(encoding="utf-8"))
            table[0]["corpus_id"] = MISSING_CORPUS_ID
            copied_corpus.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")

            with self.assertRaises(CorpusLoadError):
                load_corpus(copied_corpus)


if __name__ == "__main__":
    unittest.main()
