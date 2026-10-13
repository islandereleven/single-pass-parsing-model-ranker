"""JSON parsing and schema validation for evaluator values."""

from __future__ import annotations

import json
from json import JSONDecodeError

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from single_pass_parsing_ranker.models import JsonObject, JsonValue, extraction_schema


class NormalizationError(ValueError):
    pass


class JsonParseError(NormalizationError):
    pass


class SchemaValidationError(NormalizationError):
    pass


def parse_json_output(raw_output: str) -> JsonValue:
    if not raw_output.strip():
        raise JsonParseError("raw_output must not be blank")
    try:
        return json.loads(raw_output)
    except JSONDecodeError as exc:
        raise JsonParseError("raw_output is not valid JSON") from exc


def normalize_json_value(value: JsonValue, data_model: JsonObject) -> JsonValue:
    schema = extraction_schema(data_model)
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
    except SchemaError as exc:
        raise SchemaValidationError("data_model is not a valid JSON Schema") from exc
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.path)
        prefix = f"{location}: " if location else ""
        raise SchemaValidationError(f"value does not match data_model: {prefix}{exc.message}") from exc
    return value
