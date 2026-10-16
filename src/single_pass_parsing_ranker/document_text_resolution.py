"""Resolve fixed source documents into model-ready text."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Any

from single_pass_parsing_ranker.models import (
    Document,
    LayoutToTextStrategy,
    OcrStrategy,
)


class DocumentTextResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedDocumentText:
    text: str
    sha256: str


@dataclass(frozen=True)
class LayoutTextBlock:
    text: str
    page: int
    x0: float | None = None
    y0: float | None = None
    x1: float | None = None
    y1: float | None = None


_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
_PDF_SUFFIX = ".pdf"
_MIN_NATIVE_PDF_CHARS = 20


def resolve_document_text(
    document: Document,
    *,
    layout_to_text_strategy: LayoutToTextStrategy,
    ocr_strategy: OcrStrategy,
) -> ResolvedDocumentText:
    if layout_to_text_strategy != LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT:
        raise DocumentTextResolutionError(f"Unsupported layout_to_text_strategy: {layout_to_text_strategy}")

    suffix = document.path.suffix.lower()
    if suffix not in {*_IMAGE_SUFFIXES, _PDF_SUFFIX, ".txt"}:
        raise DocumentTextResolutionError(
            "Document type is not supported by native layout-to-text yet: "
            f"{document.path.suffix or document.path.name} with OCR strategy {ocr_strategy.value}"
        )

    payload = _read_document_bytes(document)
    if suffix == ".txt":
        return _read_text_document(payload, source=str(document.path))
    if suffix in _IMAGE_SUFFIXES:
        return _resolve_image_document(payload, source=str(document.path), ocr_strategy=ocr_strategy)
    return _resolve_pdf_document(payload, source=str(document.path), ocr_strategy=ocr_strategy)


def _read_document_bytes(document: Document) -> bytes:
    try:
        payload = document.path.read_bytes()
    except OSError as exc:
        raise DocumentTextResolutionError(f"Could not read document: {document.path}") from exc

    if document.sha256 and sha256(payload).hexdigest() != document.sha256:
        raise DocumentTextResolutionError(f"Checksum mismatch for document_id: {document.document_id}")
    return payload


def _read_text_document(payload: bytes, *, source: str) -> ResolvedDocumentText:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentTextResolutionError(f"Document is not valid UTF-8 text: {source}") from exc
    return ResolvedDocumentText(text=text, sha256=sha256(text.encode("utf-8")).hexdigest())


def _resolve_image_document(
    payload: bytes,
    *,
    source: str,
    ocr_strategy: OcrStrategy,
) -> ResolvedDocumentText:
    blocks = _ocr_bytes_to_blocks(payload, source=source, page=1, ocr_strategy=ocr_strategy)
    return _resolved_text_from_blocks(blocks)


def _resolve_pdf_document(
    payload: bytes,
    *,
    source: str,
    ocr_strategy: OcrStrategy,
) -> ResolvedDocumentText:
    native_blocks = _extract_pdf_native_layout_blocks(payload, source=source)
    native_text = _serialize_layout_text(native_blocks)
    if len(native_text.strip()) >= _MIN_NATIVE_PDF_CHARS:
        return _resolved_text(native_text)

    ocr_blocks: list[LayoutTextBlock] = []
    for page_index, image in enumerate(_render_pdf_pages(payload, source=source), start=1):
        ocr_blocks.extend(_ocr_image_to_blocks(image, page=page_index, ocr_strategy=ocr_strategy))
    return _resolved_text_from_blocks(tuple(ocr_blocks))


def _extract_pdf_native_layout_blocks(payload: bytes, *, source: str) -> tuple[LayoutTextBlock, ...]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise DocumentTextResolutionError("pdfplumber is required for PDF layout text extraction") from exc

    try:
        blocks: list[LayoutTextBlock] = []
        with pdfplumber.open(BytesIO(payload)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                words = page.extract_words(
                    keep_blank_chars=False,
                    use_text_flow=True,
                    x_tolerance=2,
                    y_tolerance=3,
                )
                blocks.extend(_words_to_line_blocks(words, page=page_index))
    except Exception as exc:
        raise DocumentTextResolutionError(f"Could not extract native PDF layout text: {source}") from exc
    return tuple(blocks)


def _render_pdf_pages(payload: bytes, *, source: str) -> tuple[Any, ...]:
    try:
        from pdf2image import convert_from_bytes
    except ImportError as exc:
        raise DocumentTextResolutionError("pdf2image is required for scanned PDF OCR") from exc

    try:
        return tuple(convert_from_bytes(payload, dpi=300))
    except Exception as exc:
        raise DocumentTextResolutionError(f"Could not render PDF pages for OCR: {source}") from exc


def _ocr_bytes_to_blocks(
    payload: bytes,
    *,
    source: str,
    page: int,
    ocr_strategy: OcrStrategy,
) -> tuple[LayoutTextBlock, ...]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise DocumentTextResolutionError("Pillow is required for image OCR") from exc

    try:
        with Image.open(BytesIO(payload)) as image:
            return _ocr_image_to_blocks(image, page=page, ocr_strategy=ocr_strategy)
    except DocumentTextResolutionError:
        raise
    except Exception as exc:
        raise DocumentTextResolutionError(f"Could not OCR image document: {source}") from exc


def _ocr_image_to_blocks(image: Any, *, page: int, ocr_strategy: OcrStrategy) -> tuple[LayoutTextBlock, ...]:
    if ocr_strategy != OcrStrategy.PYTESSERACT:
        raise DocumentTextResolutionError(f"Unsupported ocr_strategy: {ocr_strategy}")

    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:
        raise DocumentTextResolutionError("pytesseract is required for OCR") from exc

    try:
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise DocumentTextResolutionError("The tesseract binary is required for OCR but was not found") from exc
    except Exception as exc:
        raise DocumentTextResolutionError("PyTesseract OCR failed") from exc

    return _tesseract_data_to_line_blocks(data, page=page)


def _tesseract_data_to_line_blocks(data: dict[str, list[Any]], *, page: int) -> tuple[LayoutTextBlock, ...]:
    line_words: dict[tuple[int, int, int], list[tuple[int, str, float, float, float, float]]] = {}
    count = len(data.get("text", []))
    for index in range(count):
        text = str(data["text"][index]).strip()
        if not text or _ocr_confidence(data, index) <= 0:
            continue
        key = (
            int(data.get("block_num", [0] * count)[index]),
            int(data.get("par_num", [0] * count)[index]),
            int(data.get("line_num", [0] * count)[index]),
        )
        x = float(data.get("left", [0] * count)[index])
        y = float(data.get("top", [0] * count)[index])
        width = float(data.get("width", [0] * count)[index])
        height = float(data.get("height", [0] * count)[index])
        line_words.setdefault(key, []).append((int(x), text, x, y, x + width, y + height))

    blocks = []
    for words in line_words.values():
        ordered = sorted(words, key=lambda item: item[0])
        line_text = " ".join(word[1] for word in ordered).strip()
        if not line_text:
            continue
        blocks.append(
            LayoutTextBlock(
                text=line_text,
                page=page,
                x0=min(word[2] for word in ordered),
                y0=min(word[3] for word in ordered),
                x1=max(word[4] for word in ordered),
                y1=max(word[5] for word in ordered),
            )
        )
    return tuple(sorted(blocks, key=lambda block: (block.page, block.y0 or 0, block.x0 or 0)))


def _words_to_line_blocks(words: list[dict[str, Any]], *, page: int) -> tuple[LayoutTextBlock, ...]:
    line_words: dict[int, list[dict[str, Any]]] = {}
    for word in words:
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        line_key = round(float(word.get("top", 0)) / 3)
        line_words.setdefault(line_key, []).append(word)

    blocks = []
    for grouped_words in line_words.values():
        ordered = sorted(grouped_words, key=lambda item: float(item.get("x0", 0)))
        line_text = " ".join(str(word.get("text", "")).strip() for word in ordered).strip()
        if not line_text:
            continue
        blocks.append(
            LayoutTextBlock(
                text=line_text,
                page=page,
                x0=min(float(word.get("x0", 0)) for word in ordered),
                y0=min(float(word.get("top", 0)) for word in ordered),
                x1=max(float(word.get("x1", 0)) for word in ordered),
                y1=max(float(word.get("bottom", 0)) for word in ordered),
            )
        )
    return tuple(sorted(blocks, key=lambda block: (block.page, block.y0 or 0, block.x0 or 0)))


def _ocr_confidence(data: dict[str, list[Any]], index: int) -> float:
    try:
        return float(data.get("conf", [0])[index])
    except (TypeError, ValueError):
        return 0.0


def _resolved_text_from_blocks(blocks: tuple[LayoutTextBlock, ...]) -> ResolvedDocumentText:
    text = _serialize_layout_text(blocks)
    if not text.strip():
        raise DocumentTextResolutionError("Document text resolution produced no text")
    return _resolved_text(text)


def _serialize_layout_text(blocks: tuple[LayoutTextBlock, ...]) -> str:
    pages: dict[int, list[LayoutTextBlock]] = {}
    for block in sorted(blocks, key=lambda item: (item.page, item.y0 or 0, item.x0 or 0)):
        if block.text.strip():
            pages.setdefault(block.page, []).append(block)

    sections = []
    for page in sorted(pages):
        lines = [f"Page {page}"]
        lines.extend(block.text for block in pages[page])
        sections.append("\n".join(lines))
    return "\n\n".join(sections).strip() + ("\n" if sections else "")


def _resolved_text(text: str) -> ResolvedDocumentText:
    return ResolvedDocumentText(text=text, sha256=sha256(text.encode("utf-8")).hexdigest())
