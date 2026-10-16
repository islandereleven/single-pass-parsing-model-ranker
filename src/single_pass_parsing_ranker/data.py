"""Load fixed documents and versioned test cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from upath import UPath

from single_pass_parsing_ranker.models import (
    Corpus,
    CorpusLoadError,
    Document,
    TestCase,
)


def load_corpus(
    path: str | Path | UPath,
    *,
    document_registry_path: str | Path | UPath,
    corpus_table_path: str | Path | UPath | None = None,
) -> tuple[TestCase, ...]:
    path = UPath(path)
    payload = _read_json(path)
    try:
        raw = TypeAdapter(tuple[TestCase, ...]).validate_python(payload)
    except ValidationError as exc:
        raise CorpusLoadError(f"Invalid corpus table in {path}") from exc

    corpus_path = UPath(corpus_table_path) if corpus_table_path else path.parent / "corpora.json"
    registry_path = UPath(document_registry_path)
    corpora = load_corpora(corpus_path)
    documents = load_documents(registry_path)
    return _load_rows(raw, corpora, documents)


def load_corpora(path: str | Path | UPath) -> dict[UUID, Corpus]:
    path = UPath(path)
    payload = _read_json(path)
    try:
        raw = TypeAdapter(tuple[Corpus, ...]).validate_python(payload)
    except ValidationError as exc:
        raise CorpusLoadError(f"Invalid corpus table in {path}") from exc

    corpora: dict[UUID, Corpus] = {}
    for item in raw:
        if item.corpus_id in corpora:
            raise CorpusLoadError(f"Duplicate corpus_id: {item.corpus_id}")
        corpora[item.corpus_id] = item
    return corpora


def load_documents(path: str | Path | UPath) -> dict[UUID, Document]:
    path = UPath(path)
    payload = _read_json(path)
    try:
        raw = TypeAdapter(tuple[Document, ...]).validate_python(payload)
    except ValidationError as exc:
        raise CorpusLoadError(f"Invalid document registry in {path}") from exc

    root = path.parent
    documents: dict[UUID, Document] = {}
    for item in raw:
        document_id = item.document_id
        document_path = item.path if item.path.is_absolute() else root / str(item.path)
        document = item.model_copy(update={"path": document_path})
        if document_id in documents:
            raise CorpusLoadError(f"Duplicate document_id: {document_id}")
        documents[document_id] = document
    return documents


def _load_rows(
    raw_rows: tuple[TestCase, ...],
    corpora: dict[UUID, Corpus],
    documents: dict[UUID, Document],
) -> tuple[TestCase, ...]:
    rows: list[TestCase] = []
    seen: set[tuple[UUID, UUID]] = set()
    for item in raw_rows:
        row_key = (item.corpus_id, item.test_case_id)
        if row_key in seen:
            raise CorpusLoadError(f"Duplicate test_case_id in corpus {item.corpus_id}: {item.test_case_id}")
        if item.corpus_id not in corpora:
            raise CorpusLoadError(f"Unknown corpus_id: {item.corpus_id}")
        if item.document_id not in documents:
            raise CorpusLoadError(f"Unknown document_id: {item.document_id}")

        seen.add(row_key)
        rows.append(item)
    return tuple(rows)


def _read_json(path: UPath) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CorpusLoadError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CorpusLoadError(f"Invalid JSON file: {path}") from exc
