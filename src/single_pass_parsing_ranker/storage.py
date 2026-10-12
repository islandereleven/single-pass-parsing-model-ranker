"""Append-only JSONL storage for evaluator rows."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from single_pass_parsing_ranker.models import Run, RunTestCase


def append_jsonl(path: str | Path, row: BaseModel) -> None:
    print(row.model_dump_json())

    # output_path = Path(path)
    # output_path.parent.mkdir(parents=True, exist_ok=True)
    # with output_path.open("a", encoding="utf-8") as file:
    #     file.write(row.model_dump_json())
    #     file.write("\n")


def append_run(path: str | Path, run: Run) -> None:
    append_jsonl(path, run)


def append_run_test_case(path: str | Path, row: RunTestCase) -> None:
    append_jsonl(path, row)
