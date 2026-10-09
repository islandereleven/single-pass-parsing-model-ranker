from pathlib import Path
import json
import shutil
import tempfile
import unittest

from single_pass_parsing_ranker import CorpusLoadError, load_corpus


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CORPUS = PROJECT_ROOT / "corpora" / "0.1.0.json"
EXAMPLE_DOCUMENTS = PROJECT_ROOT / "documents"


class CorpusTests(unittest.TestCase):
    def test_loads_example_corpus_table(self) -> None:
        corpus = load_corpus(EXAMPLE_CORPUS)

        self.assertEqual(corpus.corpus_id, "example-invoices")
        self.assertEqual(corpus.version, "0.1.0")
        self.assertEqual(tuple(row.test_case_id for row in corpus.rows), ("acme-invoice-0001.invoice-v1",))
        self.assertEqual(tuple(corpus.documents), ("acme-invoice-0001",))

        row = corpus.require_test_case("acme-invoice-0001.invoice-v1")
        self.assertEqual(row.document_id, "acme-invoice-0001")
        self.assertIn("Return exactly one JSON object", row.prompt)

    def test_reads_document_and_inline_row_payloads(self) -> None:
        corpus = load_corpus(EXAMPLE_CORPUS)
        row = corpus.require_test_case("acme-invoice-0001.invoice-v1")
        document = corpus.read_document(row)

        self.assertIn("Invoice INV-0001", document)
        self.assertEqual(row.data_model["title"], "Invoice")
        self.assertEqual(row.data_model["type"], "object")
        self.assertIn("provided data model", row.prompt)
        self.assertEqual(row.ground_truth["invoice_number"], "INV-0001")
        self.assertEqual(row.ground_truth["total"], 175.5)

    def test_rejects_fixed_document_checksum_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            copied_corpus = temp_root / "corpora" / "0.1.0.json"
            copied_documents = temp_root / "documents"
            copied_corpus.parent.mkdir(parents=True)
            shutil.copy2(EXAMPLE_CORPUS, copied_corpus)
            shutil.copytree(EXAMPLE_DOCUMENTS, copied_documents)

            document = copied_documents / "acme_invoice.txt"
            edited = document.read_text(encoding="utf-8") + "\nUnexpected edit.\n"
            document.write_text(edited, encoding="utf-8")

            with self.assertRaises(CorpusLoadError):
                load_corpus(copied_corpus)

    def test_rejects_rows_that_reference_unknown_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            copied_corpus = temp_root / "corpora" / "0.1.0.json"
            copied_documents = temp_root / "documents"
            copied_corpus.parent.mkdir(parents=True)
            shutil.copy2(EXAMPLE_CORPUS, copied_corpus)
            shutil.copytree(EXAMPLE_DOCUMENTS, copied_documents)

            manifest = json.loads(copied_corpus.read_text(encoding="utf-8"))
            manifest["rows"][0]["document_id"] = "missing-document"
            copied_corpus.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            with self.assertRaises(CorpusLoadError):
                load_corpus(copied_corpus)


if __name__ == "__main__":
    unittest.main()
