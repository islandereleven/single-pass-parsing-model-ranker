from types import SimpleNamespace
import unittest

from single_pass_parsing_ranker import (
    LLMResponseError,
    extract_litellm_result,
    request_structured_parse,
    response_format_for_schema,
)


INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": "string"},
        "total": {"type": "number"},
    },
}


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="response-001",
        model="openai/gpt-4o-mini",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=2),
        ),
        _hidden_params={
            "_response_ms": 432.7,
            "response_cost": 0.0123,
        },
    )


def _dict_usage_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="response-002",
        model="gemini-2.5-flash",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
        usage={
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28,
            "completion_tokens_details": {"reasoning_tokens": 3},
        },
        _hidden_params={
            "_response_ms": 100.2,
            "response_cost": 0.0045,
        },
    )


def _direct_reasoning_tokens_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=9,
            completion_tokens=4,
            reasoning_tokens=7,
            total_tokens=20,
        ),
        _hidden_params={},
    )


class LLMTests(unittest.TestCase):
    def test_extract_litellm_result_keeps_structured_output_as_raw_string(self) -> None:
        result = extract_litellm_result(_response('{"vendor":"Acme Corp","total":123.45}'))

        self.assertEqual(result.raw_output, '{"vendor":"Acme Corp","total":123.45}')
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.reasoning_tokens, 2)
        self.assertEqual(result.total_tokens, 15)
        self.assertEqual(result.latency_ms, 433)
        self.assertEqual(result.estimated_cost_usd, 0.0123)
        self.assertEqual(result.raw_response_metadata["hidden_params"]["response_cost"], 0.0123)

    def test_extract_litellm_result_accepts_dict_usage_metadata(self) -> None:
        result = extract_litellm_result(_dict_usage_response('{"vendor":"Acme Corp","total":123.45}'))

        self.assertEqual(result.raw_output, '{"vendor":"Acme Corp","total":123.45}')
        self.assertEqual(result.raw_response_metadata["id"], "response-002")
        self.assertEqual(result.raw_response_metadata["model"], "gemini-2.5-flash")
        self.assertEqual(result.input_tokens, 20)
        self.assertEqual(result.output_tokens, 8)
        self.assertEqual(result.reasoning_tokens, 3)
        self.assertEqual(result.total_tokens, 28)
        self.assertEqual(result.latency_ms, 100)
        self.assertEqual(result.estimated_cost_usd, 0.0045)

    def test_extract_litellm_result_accepts_direct_reasoning_tokens(self) -> None:
        result = extract_litellm_result(_direct_reasoning_tokens_response('{"vendor":"Acme Corp","total":123.45}'))

        self.assertEqual(result.reasoning_tokens, 7)
        self.assertEqual(result.raw_response_metadata["usage"]["reasoning_tokens"], 7)

    def test_request_structured_parse_uses_litellm_schema_validation(self) -> None:
        calls = []

        def fake_completion(**kwargs):
            calls.append(kwargs)
            return _response('{"vendor":"Acme Corp","total":123.45}')

        result = request_structured_parse(
            model="openai/gpt-4o-mini",
            prompt="Extract invoice fields.",
            data_model=INVOICE_SCHEMA,
            model_settings={"temperature": 0},
            completion_fn=fake_completion,
        )

        self.assertEqual(result.raw_output, '{"vendor":"Acme Corp","total":123.45}')
        self.assertEqual(calls[0]["model"], "openai/gpt-4o-mini")
        self.assertEqual(calls[0]["messages"], [{"role": "user", "content": "Extract invoice fields."}])
        self.assertEqual(calls[0]["response_format"], response_format_for_schema(INVOICE_SCHEMA))
        self.assertTrue(calls[0]["enable_json_schema_validation"])
        self.assertEqual(calls[0]["temperature"], 0)

    def test_response_format_strips_evaluation_metadata(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "evaluation": {"comparison": "fuzzy_text"},
                }
            },
        }

        response_format = response_format_for_schema(schema)

        self.assertEqual(response_format["json_schema"]["schema"], {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
            },
        })

    def test_extract_litellm_result_rejects_missing_message_content(self) -> None:
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])

        with self.assertRaises(LLMResponseError):
            extract_litellm_result(response)


if __name__ == "__main__":
    unittest.main()
