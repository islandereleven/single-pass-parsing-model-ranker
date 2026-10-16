from hashlib import sha256
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from upath import UPath

from single_pass_parsing_ranker import (
    Document,
    DocumentTextResolutionError,
    LayoutToTextStrategy,
    OcrStrategy,
    load_documents,
    resolve_document_text,
)
from single_pass_parsing_ranker import document_text_resolution as resolution


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_PATH = PROJECT_ROOT / "documents" / "documents.json"
ACME_DOCUMENT_ID = UUID("2dcad689-51a8-4c19-8a6e-8ed72fb2e4d9")
TEST_SOURCE = {
    "source_name": "Test Source",
}


class DocumentTextResolutionTests(unittest.TestCase):
    def test_native_layout_to_text_passes_through_text_documents(self) -> None:
        document = load_documents(DOCUMENTS_PATH)[ACME_DOCUMENT_ID]

        resolved = resolve_document_text(
            document,
            layout_to_text_strategy=LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT,
            ocr_strategy=OcrStrategy.PYTESSERACT,
        )

        self.assertIn("Invoice INV-0001", resolved.text)
        self.assertEqual(resolved.sha256, sha256(resolved.text.encode("utf-8")).hexdigest())

    def test_native_layout_to_text_ocr_resolves_images(self) -> None:
        document = Document(
            document_id=UUID("9c924967-7894-48ca-a488-fb786d0d7be1"),
            path=PROJECT_ROOT
            / "documents"
            / "invoice-batch-1-sample-20-v0.1"
            / "9c924967-7894-48ca-a488-fb786d0d7be1.jpg",
            **TEST_SOURCE,
        )
        blocks = (resolution.LayoutTextBlock(text="Invoice no: 86736203", page=1, x0=10, y0=20, x1=100, y1=30),)

        with (
            patch.object(resolution, "_read_document_bytes", return_value=b"image-bytes"),
            patch.object(resolution, "_ocr_bytes_to_blocks", return_value=blocks) as ocr_bytes_to_blocks,
        ):
            resolved = resolve_document_text(
                document,
                layout_to_text_strategy=LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT,
                ocr_strategy=OcrStrategy.PYTESSERACT,
            )

        self.assertEqual(resolved.text, "Page 1\nInvoice no: 86736203\n")
        self.assertEqual(resolved.sha256, sha256(resolved.text.encode("utf-8")).hexdigest())
        ocr_bytes_to_blocks.assert_called_once_with(
            b"image-bytes",
            source=str(document.path),
            page=1,
            ocr_strategy=OcrStrategy.PYTESSERACT,
        )

    def test_native_layout_to_text_uses_native_pdf_text_before_ocr(self) -> None:
        document = Document(
            document_id=UUID("11111111-1111-4111-8111-111111111111"),
            path=PROJECT_ROOT / "documents" / "sample.pdf",
            **TEST_SOURCE,
        )
        blocks = (resolution.LayoutTextBlock(text="Native PDF invoice text is present", page=1),)

        with (
            patch.object(resolution, "_read_document_bytes", return_value=b"pdf-bytes"),
            patch.object(resolution, "_extract_pdf_native_layout_blocks", return_value=blocks) as extract_blocks,
            patch.object(resolution, "_render_pdf_pages") as render_pdf_pages,
        ):
            resolved = resolve_document_text(
                document,
                layout_to_text_strategy=LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT,
                ocr_strategy=OcrStrategy.PYTESSERACT,
            )

        self.assertEqual(resolved.text, "Page 1\nNative PDF invoice text is present\n")
        extract_blocks.assert_called_once_with(b"pdf-bytes", source=str(document.path))
        render_pdf_pages.assert_not_called()

    def test_native_layout_to_text_ocr_falls_back_for_pdf_without_native_text(self) -> None:
        document = Document(
            document_id=UUID("22222222-2222-4222-8222-222222222222"),
            path=PROJECT_ROOT / "documents" / "scanned.pdf",
            **TEST_SOURCE,
        )
        blocks = (resolution.LayoutTextBlock(text="OCR PDF invoice text", page=1),)

        with (
            patch.object(resolution, "_read_document_bytes", return_value=b"pdf-bytes"),
            patch.object(resolution, "_extract_pdf_native_layout_blocks", return_value=()),
            patch.object(resolution, "_render_pdf_pages", return_value=("page-image",)),
            patch.object(resolution, "_ocr_image_to_blocks", return_value=blocks) as ocr_image_to_blocks,
        ):
            resolved = resolve_document_text(
                document,
                layout_to_text_strategy=LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT,
                ocr_strategy=OcrStrategy.PYTESSERACT,
            )

        self.assertEqual(resolved.text, "Page 1\nOCR PDF invoice text\n")
        ocr_image_to_blocks.assert_called_once_with(
            "page-image",
            page=1,
            ocr_strategy=OcrStrategy.PYTESSERACT,
        )

    def test_rejects_document_checksum_drift_during_resolution(self) -> None:
        document = Document(
            document_id=ACME_DOCUMENT_ID,
            path=PROJECT_ROOT / "documents" / "acme_invoice.txt",
            sha256="0" * 64,
            **TEST_SOURCE,
        )

        with self.assertRaisesRegex(DocumentTextResolutionError, "Checksum mismatch"):
            resolve_document_text(
                document,
                layout_to_text_strategy=LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT,
                ocr_strategy=OcrStrategy.PYTESSERACT,
            )

    def test_reads_text_document_from_remote_filesystem(self) -> None:
        path = UPath(f"memory://sppr-document-{uuid4()}/invoice.txt")
        path.parent.mkdir(parents=True)
        payload = b"Invoice REMOTE-1\n"
        path.write_bytes(payload)
        document = Document(
            document_id=ACME_DOCUMENT_ID,
            path=path,
            sha256=sha256(payload).hexdigest(),
            **TEST_SOURCE,
        )

        resolved = resolve_document_text(
            document,
            layout_to_text_strategy=LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT,
            ocr_strategy=OcrStrategy.PYTESSERACT,
        )

        self.assertEqual(resolved.text, payload.decode("utf-8"))

    def test_tesseract_data_is_serialized_in_reading_order(self) -> None:
        data = {
            "text": ["", "Invoice", "86736203", "Total", "15 574,11"],
            "conf": ["-1", "95", "94", "90", "88"],
            "block_num": [0, 1, 1, 1, 1],
            "par_num": [0, 1, 1, 1, 1],
            "line_num": [0, 1, 1, 2, 2],
            "left": [0, 20, 80, 20, 80],
            "top": [0, 10, 10, 40, 40],
            "width": [0, 50, 60, 45, 80],
            "height": [0, 10, 10, 10, 10],
        }

        blocks = resolution._tesseract_data_to_line_blocks(data, page=1)

        self.assertEqual([block.text for block in blocks], ["Invoice 86736203", "Total 15 574,11"])


if __name__ == "__main__":
    unittest.main()
