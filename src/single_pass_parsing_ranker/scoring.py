"""Exact field scoring for normalized JSON values."""

from __future__ import annotations

from single_pass_parsing_ranker.models import JsonValue


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
