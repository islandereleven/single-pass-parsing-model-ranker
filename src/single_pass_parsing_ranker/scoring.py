"""Exact field scoring for normalized JSON values."""

from __future__ import annotations

import re
from uuid import UUID

from rapidfuzz import fuzz

from single_pass_parsing_ranker.models import (
    FieldComparison,
    FieldComparisonMethod,
    FieldEvaluation,
    JsonObject,
    JsonValue,
)


_MISSING = object()


def score_json_values(output: JsonValue, ground_truth: JsonValue) -> float:
    scores = field_scores(output, ground_truth)
    return sum(scores.values()) / len(scores)


def field_scores(output: JsonValue, ground_truth: JsonValue) -> dict[str, int]:
    output_fields = flatten_json_value(output)
    ground_truth_fields = flatten_json_value(ground_truth)
    paths = sorted(set(output_fields) | set(ground_truth_fields))
    return {
        path: int(output_fields.get(path, _MISSING) == ground_truth_fields.get(path, _MISSING))
        for path in paths
    }


def field_comparisons(
    *,
    run_id: UUID,
    test_case_id: UUID,
    output: JsonValue,
    ground_truth: JsonValue,
    data_model: JsonObject | None = None,
) -> tuple[FieldComparison, ...]:
    output_fields = flatten_json_value(output)
    ground_truth_fields = flatten_json_value(ground_truth)
    paths = sorted(set(output_fields) | set(ground_truth_fields))
    comparisons = []

    for path in paths:
        expected_present = path in ground_truth_fields
        actual_present = path in output_fields
        expected_value = ground_truth_fields[path] if expected_present else None
        actual_value = output_fields[path] if actual_present else None
        comparison_method = comparison_method_for_path(data_model, path)
        score = compare_field_values(
            expected_value=expected_value,
            actual_value=actual_value,
            expected_present=expected_present,
            actual_present=actual_present,
            comparison_method=comparison_method,
        )
        comparisons.append(
            FieldComparison(
                run_id=run_id,
                test_case_id=test_case_id,
                field_path=path,
                expected_value=expected_value,
                actual_value=actual_value,
                expected_present=expected_present,
                actual_present=actual_present,
                matched=score == 1.0,
                score=score,
                comparison_method=comparison_method,
            )
        )

    return tuple(comparisons)


def score_field_comparisons(comparisons: tuple[FieldComparison, ...]) -> float:
    if not comparisons:
        return 1.0
    return sum(comparison.score for comparison in comparisons) / len(comparisons)


def compare_field_values(
    *,
    expected_value: JsonValue,
    actual_value: JsonValue,
    expected_present: bool,
    actual_present: bool,
    comparison_method: FieldComparisonMethod,
) -> float:
    if not expected_present or not actual_present:
        return 0.0

    if comparison_method == FieldComparisonMethod.FUZZY_TEXT:
        return fuzzy_text_score(expected_value, actual_value)

    return 1.0 if expected_value == actual_value else 0.0


def fuzzy_text_score(expected_value: JsonValue, actual_value: JsonValue) -> float:
    if not isinstance(expected_value, str) or not isinstance(actual_value, str):
        return 1.0 if expected_value == actual_value else 0.0

    expected_text = _normalize_fuzzy_text(expected_value)
    actual_text = _normalize_fuzzy_text(actual_value)
    if expected_text == actual_text:
        return 1.0
    if not expected_text or not actual_text:
        return 0.0
    return fuzz.WRatio(expected_text, actual_text) / 100


def comparison_method_for_path(
    data_model: JsonObject | None,
    field_path: str,
) -> FieldComparisonMethod:
    if data_model is None:
        return FieldComparisonMethod.EXACT

    schema = _schema_for_field_path(data_model, field_path)
    if schema is None:
        return FieldComparisonMethod.EXACT

    evaluation = schema.get("evaluation")
    if evaluation is None:
        return FieldComparisonMethod.EXACT
    return FieldEvaluation.model_validate(evaluation).comparison


def flatten_json_value(value: JsonValue, path: str = "$") -> dict[str, JsonValue]:
    if isinstance(value, dict):
        if not value:
            return {path: value}

        fields: dict[str, JsonValue] = {}
        for key in sorted(value):
            child_path = key if path == "$" else f"{path}.{key}"
            fields.update(flatten_json_value(value[key], child_path))
        return fields

    if isinstance(value, list):
        if not value:
            return {path: value}

        fields = {}
        for index, item in enumerate(value):
            child_path = f"{path}[{index}]"
            fields.update(flatten_json_value(item, child_path))
        return fields

    return {path: value}


def _schema_for_field_path(data_model: JsonObject, field_path: str) -> JsonObject | None:
    schema = data_model
    for token in _field_path_tokens(field_path):
        if isinstance(token, str):
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                return None
            child_schema = properties.get(token)
            if not isinstance(child_schema, dict):
                return None
            schema = child_schema
        else:
            items = schema.get("items")
            if not isinstance(items, dict):
                return None
            schema = items
    return schema


def _field_path_tokens(field_path: str) -> tuple[str | int, ...]:
    if field_path == "$":
        return ()

    tokens: list[str | int] = []
    for part in field_path.split("."):
        position = 0
        while position < len(part):
            match = re.match(r"([^\[\]]+)|\[(\d+)\]", part[position:])
            if match is None:
                return tuple(tokens)
            name, index = match.groups()
            tokens.append(name if name is not None else int(index))
            position += len(match.group(0))
    return tuple(tokens)


def _normalize_fuzzy_text(value: str) -> str:
    return " ".join(value.casefold().split())
