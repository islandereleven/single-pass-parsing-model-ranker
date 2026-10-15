"""Immutable local result bundles for completed evaluator runs."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from single_pass_parsing_ranker.models import FieldComparison, Run, RunTestCase


def write_run_bundle(
    output_dir: str | Path,
    run: Run,
    test_cases: Sequence[RunTestCase],
    field_comparisons: Sequence[FieldComparison],
) -> Path:
    """Write one complete, immutable result bundle and return its directory."""

    run_payload = run.model_dump_json() + "\n"
    test_case_payload = _jsonl(test_cases)
    field_comparison_payload = _jsonl(field_comparisons)

    run_dir = Path(output_dir) / f"run_id={run.run_id}"
    run_dir.mkdir(parents=True, exist_ok=False)

    (run_dir / "run_test_cases.jsonl").write_text(test_case_payload, encoding="utf-8")
    (run_dir / "field_comparisons.jsonl").write_text(field_comparison_payload, encoding="utf-8")
    (run_dir / "run.json").write_text(run_payload, encoding="utf-8")
    return run_dir


def _jsonl(rows: Sequence[BaseModel]) -> str:
    return "".join(f"{row.model_dump_json()}\n" for row in rows)
