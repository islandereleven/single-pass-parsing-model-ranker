"""Thin LiteLLM call boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from single_pass_parsing_ranker.models import DataModelSchema, JsonObject, LLMCallResult


class LLMCallError(RuntimeError):
    pass


class StructuredOutputValidationError(LLMCallError):
    pass


class LLMResponseError(LLMCallError):
    pass


def request_structured_parse(
    *,
    model: str,
    prompt: str,
    data_model: JsonObject,
    model_settings: JsonObject | None = None,
    completion_fn: Callable[..., Any] | None = None,
) -> LLMCallResult:
    schema_validation_errors: tuple[type[BaseException], ...] = ()
    if completion_fn is None:
        try:
            from litellm import completion as completion_fn
            from litellm.exceptions import JSONSchemaValidationError
        except ImportError as exc:
            raise LLMCallError("LiteLLM is not installed") from exc
        schema_validation_errors = (JSONSchemaValidationError,)

    try:
        response = completion_fn(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=response_format_for_schema(data_model),
            enable_json_schema_validation=True,
            **dict(model_settings or {}),
        )
    except Exception as exc:
        if schema_validation_errors and isinstance(exc, schema_validation_errors):
            raise StructuredOutputValidationError("LiteLLM structured output failed JSON Schema validation") from exc
        raise LLMCallError("LiteLLM call failed") from exc

    return extract_litellm_result(response)


def response_format_for_schema(data_model: JsonObject) -> JsonObject:
    schema = DataModelSchema(data_model).as_dict()
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "parsed_response",
            "schema": schema,
            "strict": True,
        },
    }


def extract_litellm_result(response: Any) -> LLMCallResult:
    raw_output = _message_content(response)
    usage = getattr(response, "usage", None)
    hidden_params = getattr(response, "_hidden_params", {}) or {}

    return LLMCallResult(
        raw_output=raw_output,
        raw_response_metadata=_response_metadata(response, usage, hidden_params),
        latency_ms=_optional_int(hidden_params.get("_response_ms") if isinstance(hidden_params, Mapping) else None),
        input_tokens=_optional_int(_get_attr_or_key(usage, "prompt_tokens")),
        output_tokens=_optional_int(_get_attr_or_key(usage, "completion_tokens")),
        reasoning_tokens=_optional_int(_reasoning_tokens(usage)),
        total_tokens=_optional_int(_get_attr_or_key(usage, "total_tokens")),
        estimated_cost_usd=_optional_float(hidden_params.get("response_cost") if isinstance(hidden_params, Mapping) else None),
    )


def _message_content(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        raise LLMResponseError("LiteLLM response contained no choices")

    message = getattr(choices[0], "message", None)
    raw_output = getattr(message, "content", None)
    if raw_output is None:
        raise LLMResponseError("LiteLLM response choice contained no message content")
    if not isinstance(raw_output, str):
        raise LLMResponseError("LiteLLM response message content was not a string")
    return raw_output


def _response_metadata(response: Any, usage: Any, hidden_params: Any) -> JsonObject:
    metadata: JsonObject = {}
    for key in ("id", "model", "created"):
        value = getattr(response, key, None)
        if value is not None:
            metadata[key] = value

    usage_data = {
        key: value
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if (value := _get_attr_or_key(usage, key)) is not None
    }
    reasoning_tokens = _reasoning_tokens(usage)
    if reasoning_tokens is not None:
        usage_data["reasoning_tokens"] = reasoning_tokens
    if usage_data:
        metadata["usage"] = usage_data

    if isinstance(hidden_params, Mapping):
        hidden_data = {
            key: hidden_params[key]
            for key in ("_response_ms", "response_cost")
            if key in hidden_params
        }
        if hidden_data:
            metadata["hidden_params"] = hidden_data

    return metadata


def _reasoning_tokens(usage: Any) -> Any:
    direct = _get_attr_or_key(usage, "reasoning_tokens")
    if direct is not None:
        return direct

    details = _get_attr_or_key(usage, "completion_tokens_details")
    return _get_attr_or_key(details, "reasoning_tokens")


def _get_attr_or_key(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(round(float(value)))


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
