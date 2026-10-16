"""Shared data models for corpus loading and evaluator results."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_serializer,
    field_validator,
    model_validator,
)
from upath import UPath


JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None
JsonObject = dict[str, Any]


class CorpusLoadError(ValueError):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _utc_now() -> datetime:
    return datetime.now(UTC)


# Evaluation metadata


class FieldComparisonMethod(StrEnum):
    EXACT = "exact"
    FUZZY_TEXT = "fuzzy_text"


class FieldEvaluation(StrictModel):
    comparison: FieldComparisonMethod = FieldComparisonMethod.EXACT


# Corpus files


class DataModelSchema(RootModel[JsonObject]):
    """JSON Schema object used as an extraction contract."""

    @model_validator(mode="after")
    def _validate_object_contract(self) -> "DataModelSchema":
        schema = self.root
        _validate_evaluation_metadata(schema)
        schema_type = schema.get("type")
        if schema_type not in (None, "object"):
            raise ValueError("data_model must declare an object-shaped top-level schema")

        properties = schema.get("properties")
        if properties is not None and not isinstance(properties, dict):
            raise ValueError("data_model.properties must be an object when present")

        required = schema.get("required")
        if required is not None and (
            not isinstance(required, list) or not all(isinstance(field, str) for field in required)
        ):
            raise ValueError("data_model.required must be a list of field names when present")

        return self

    def as_dict(self) -> JsonObject:
        return self.model_dump()


class Document(StrictModel):
    document_id: UUID
    path: UPath
    source_name: str = Field(min_length=1)
    source_record_id: str | None = None
    sha256: str | None = None

    @field_validator("path", mode="before")
    @classmethod
    def _parse_path(cls, value: str | Path | UPath) -> str | UPath:
        if isinstance(value, UPath):
            return value
        if isinstance(value, Path):
            return str(value)
        return value

    @field_serializer("path")
    def _serialize_path(self, value: UPath) -> str:
        return str(value)


class Corpus(StrictModel):
    corpus_id: UUID
    version: str = Field(min_length=1)


class TestCase(StrictModel):
    corpus_id: UUID
    test_case_id: UUID
    document_id: UUID
    data_model: JsonObject
    prompt: str = Field(min_length=1)
    ground_truth: JsonObject

    @field_validator("data_model")
    @classmethod
    def _data_model_must_be_valid(cls, value: JsonObject) -> JsonObject:
        return DataModelSchema(value).as_dict()

    @field_validator("prompt")
    @classmethod
    def _prompt_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value


# Run strategies


class LayoutToTextStrategy(StrEnum):
    NATIVE_LAYOUT_TO_TEXT = "native_layout_to_text"


class OcrStrategy(StrEnum):
    PYTESSERACT = "pytesseract"


# LLM call results


class LLMCallResult(StrictModel):
    raw_output: str
    raw_response_metadata: JsonObject = Field(default_factory=dict)
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)


# Result rows


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AttemptStatus(StrEnum):
    SCORED = "scored"
    ZERO_SCORE = "zero_score"
    FAILED = "failed"


class FailureReason(StrEnum):
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    NETWORK_ERROR = "network_error"
    NO_RESPONSE = "no_response"
    EMPTY_RESPONSE = "empty_response"
    REFUSAL = "refusal"
    DOCUMENT_TEXT_EXTRACTION_ERROR = "document_text_extraction_error"
    INVALID_JSON = "invalid_json"
    SCHEMA_VALIDATION_ERROR = "schema_validation_error"
    NORMALIZATION_ERROR = "normalization_error"
    UNKNOWN = "unknown"


class Run(StrictModel):
    """One model/corpus evaluation run and its persisted status."""

    run_id: UUID
    model: str = Field(min_length=1)
    corpus_id: UUID
    status: RunStatus = RunStatus.RUNNING
    provider: str | None = None
    model_settings: JsonObject = Field(default_factory=dict)
    model_metadata: JsonObject = Field(default_factory=dict)
    layout_to_text_strategy: LayoutToTextStrategy = LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT
    ocr_strategy: OcrStrategy = OcrStrategy.PYTESSERACT
    failure_reason: FailureReason | None = None
    started_at: datetime = Field(default_factory=_utc_now)
    ended_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utc_now)


class RunTestCase(StrictModel):
    """Storage row for one test case attempt inside a run."""

    run_id: UUID
    test_case_id: UUID
    status: AttemptStatus
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    failure_reason: FailureReason | None = None
    raw_output: str | None = None
    raw_response_metadata: JsonObject = Field(default_factory=dict)
    parsed_output: JsonValue = None
    normalized_output: JsonValue = None
    document_text_sha256: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    input_cost_usd: float | None = Field(default=None, ge=0.0)
    output_cost_usd: float | None = Field(default=None, ge=0.0)
    reasoning_cost_usd: float | None = Field(default=None, ge=0.0)
    started_at: datetime = Field(default_factory=_utc_now)
    ended_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utc_now)


class FieldComparison(StrictModel):
    """One normalized field comparison for one run test case."""

    run_id: UUID
    test_case_id: UUID
    field_path: str = Field(min_length=1)
    expected_value: JsonValue = None
    actual_value: JsonValue = None
    expected_present: bool = True
    actual_present: bool = True
    matched: bool
    score: float = Field(ge=0.0, le=1.0)
    comparison_method: FieldComparisonMethod = FieldComparisonMethod.EXACT
    created_at: datetime = Field(default_factory=_utc_now)


def storage_schemas() -> dict[str, JsonObject]:
    return {
        "runs": Run.model_json_schema(),
        "run_test_cases": RunTestCase.model_json_schema(),
        "field_comparisons": FieldComparison.model_json_schema(),
    }


def extraction_schema(data_model: JsonObject) -> JsonObject:
    """Return the JSON Schema used for provider calls and value validation."""

    return _strip_evaluation_metadata(DataModelSchema(data_model).as_dict())


def _validate_evaluation_metadata(value: Any) -> None:
    if isinstance(value, dict):
        evaluation = value.get("evaluation")
        if evaluation is not None:
            FieldEvaluation.model_validate(evaluation)

        properties = value.get("properties")
        if isinstance(properties, dict):
            for property_schema in properties.values():
                _validate_evaluation_metadata(property_schema)

        items = value.get("items")
        if isinstance(items, dict):
            _validate_evaluation_metadata(items)

        for key in ("anyOf", "oneOf", "allOf"):
            schemas = value.get(key)
            if isinstance(schemas, list):
                for schema in schemas:
                    _validate_evaluation_metadata(schema)


def _strip_evaluation_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {
            key: _strip_evaluation_metadata(child)
            for key, child in value.items()
            if key != "evaluation"
        }

        properties = value.get("properties")
        if isinstance(properties, dict):
            cleaned["properties"] = {
                name: _strip_evaluation_metadata(property_schema)
                for name, property_schema in properties.items()
            }

        return cleaned

    if isinstance(value, list):
        return [_strip_evaluation_metadata(item) for item in value]

    return value
