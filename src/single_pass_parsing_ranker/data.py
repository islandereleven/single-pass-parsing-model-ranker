"""Load fixed documents and versioned corpus rows."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


CORPUS_SCHEMA_VERSION = "single-pass-corpus/v1"
DOCUMENT_REGISTRY_SCHEMA_VERSION = "single-pass-documents/v1"

JsonObject = dict[str, Any]


class CorpusLoadError(ValueError):
    pass


@dataclass(frozen=True)
class Document:
    document_id: str
    path: Path
    sha256: str | None = None


@dataclass(frozen=True)
class TestCase:
    test_case_id: str
    document_id: str
    data_model: JsonObject
    ground_truth: JsonObject


@dataclass(frozen=True)
class Corpus:
    corpus_id: str
    version: str
    documents: dict[str, Document]
    rows: tuple[TestCase, ...]

    def require_test_case(self, test_case_id: str) -> TestCase:
        for row in self.rows:
            if row.test_case_id == test_case_id:
                return row
        raise CorpusLoadError(f"Unknown test_case_id: {test_case_id}")

    def read_document(self, test_case: TestCase | str) -> str:
        row = self.require_test_case(test_case) if isinstance(test_case, str) else test_case
        try:
            document = self.documents[row.document_id]
        except KeyError as exc:
            raise CorpusLoadError(f"Unknown document_id: {row.document_id}") from exc
        return document.path.read_text(encoding="utf-8")


def load_corpus(path: str | Path) -> Corpus:
    path = Path(path).resolve()
    raw = _read_json(path)
    if raw.get("schema_version") != CORPUS_SCHEMA_VERSION:
        raise CorpusLoadError(f"Unsupported corpus schema_version in {path}")

    documents = _load_documents(path.parent / raw["document_registry"])
    rows = _load_rows(raw["rows"], documents)
    return Corpus(raw["corpus_id"], raw["version"], documents, rows)


def _load_documents(path: Path) -> dict[str, Document]:
    raw = _read_json(path.resolve())
    if raw.get("schema_version") != DOCUMENT_REGISTRY_SCHEMA_VERSION:
        raise CorpusLoadError(f"Unsupported document registry schema_version in {path}")

    root = (path.parent / raw["document_root"]).resolve()
    documents: dict[str, Document] = {}
    for item in raw["documents"]:
        document_id = item["document_id"]
        document = Document(
            document_id=document_id,
            path=(root / item["path"]).resolve(),
            sha256=item.get("sha256"),
        )
        if document_id in documents:
            raise CorpusLoadError(f"Duplicate document_id: {document_id}")
        if not document.path.is_file():
            raise CorpusLoadError(f"Missing document file: {document.path}")
        if document.sha256 and _sha256(document.path) != document.sha256:
            raise CorpusLoadError(f"Checksum mismatch for document_id: {document_id}")
        documents[document_id] = document
    return documents


def _load_rows(raw_rows: list[JsonObject], documents: dict[str, Document]) -> tuple[TestCase, ...]:
    rows: list[TestCase] = []
    seen: set[str] = set()
    for item in raw_rows:
        row = TestCase(
            test_case_id=item["test_case_id"],
            document_id=item["document_id"],
            data_model=item["data_model"],
            ground_truth=item["ground_truth"],
        )
        if row.test_case_id in seen:
            raise CorpusLoadError(f"Duplicate test_case_id: {row.test_case_id}")
        if row.document_id not in documents:
            raise CorpusLoadError(f"Unknown document_id: {row.document_id}")
        if not isinstance(row.data_model, dict) or not isinstance(row.ground_truth, dict):
            raise CorpusLoadError(f"Invalid row payload: {row.test_case_id}")
        seen.add(row.test_case_id)
        rows.append(row)
    return tuple(rows)


def _read_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CorpusLoadError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CorpusLoadError(f"Invalid JSON file: {path}") from exc
    if not isinstance(value, dict):
        raise CorpusLoadError(f"JSON file must contain an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

