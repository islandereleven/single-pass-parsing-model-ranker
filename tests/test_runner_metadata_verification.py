from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from uuid import UUID

from single_pass_parsing_ranker import LLMCallResult, Run, RunStatus, RunTestCase, load_corpus, run_evaluation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CORPUS = PROJECT_ROOT / "corpora" / "0.1.0.json"
DOCUMENT_REGISTRY = PROJECT_ROOT / "documents" / "documents.json"
RUN_ID = UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0")


class RunnerMetadataVerificationTests(unittest.TestCase):
    def test_runner_copies_litellm_metadata_to_run_test_case_row(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]
        metadata = {
            "id": "response-001",
            "model": "gemini-2.5-flash",
            "usage": {
                "prompt_tokens": 711,
                "completion_tokens": 444,
                "reasoning_tokens": 284,
                "total_tokens": 1155,
            },
            "hidden_params": {
                "_response_ms": 3235.7,
                "response_cost": 0.0013233,
            },
        }

        def fake_request(**kwargs):
            return LLMCallResult(
                raw_output=json.dumps(test_case.ground_truth),
                raw_response_metadata=metadata,
                latency_ms=3236,
                input_tokens=711,
                output_tokens=444,
                reasoning_tokens=284,
                total_tokens=1155,
                estimated_cost_usd=0.0013233,
            )

        case_row, run_row = _run_jsonl(fake_request)

        self.assertEqual(case_row.raw_response_metadata, metadata)
        self.assertEqual(case_row.latency_ms, 3236)
        self.assertEqual(case_row.input_tokens, 711)
        self.assertEqual(case_row.output_tokens, 444)
        self.assertEqual(case_row.reasoning_tokens, 284)
        self.assertEqual(case_row.total_tokens, 1155)
        self.assertEqual(case_row.estimated_cost_usd, 0.0013233)
        self.assertIsNone(case_row.input_cost_usd)
        self.assertIsNone(case_row.output_cost_usd)
        self.assertIsNone(case_row.reasoning_cost_usd)

        self.assertEqual(run_row.status, RunStatus.COMPLETED)
        self.assertEqual(run_row.model_metadata, {})
        self.assertFalse(hasattr(run_row, "total_tokens"))
        self.assertFalse(hasattr(run_row, "estimated_cost_usd"))

    def test_runner_leaves_missing_metadata_null_and_does_not_guess(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]

        case_row, run_row = _run_jsonl(lambda **kwargs: LLMCallResult(raw_output=json.dumps(test_case.ground_truth)))

        self.assertEqual(case_row.score, 1.0)
        self.assertEqual(case_row.raw_response_metadata, {})
        self.assertIsNone(case_row.latency_ms)
        self.assertIsNone(case_row.input_tokens)
        self.assertIsNone(case_row.output_tokens)
        self.assertIsNone(case_row.reasoning_tokens)
        self.assertIsNone(case_row.total_tokens)
        self.assertIsNone(case_row.estimated_cost_usd)
        self.assertIsNone(case_row.input_cost_usd)
        self.assertIsNone(case_row.output_cost_usd)
        self.assertIsNone(case_row.reasoning_cost_usd)
        self.assertEqual(run_row.status, RunStatus.COMPLETED)

    def test_pretty_output_summarizes_metadata_without_raw_response_blob(self) -> None:
        test_case = load_corpus(EXAMPLE_CORPUS, document_registry_path=DOCUMENT_REGISTRY)[0]

        def fake_request(**kwargs):
            return LLMCallResult(
                raw_output=json.dumps(test_case.ground_truth),
                raw_response_metadata={"id": "response-001"},
                latency_ms=987,
                input_tokens=30,
                output_tokens=12,
                reasoning_tokens=4,
                total_tokens=46,
                estimated_cost_usd=0.000321,
            )

        output = StringIO()
        with redirect_stdout(output):
            run_evaluation(
                model="gemini/gemini-2.5-flash",
                corpus_path=EXAMPLE_CORPUS,
                document_registry_path=DOCUMENT_REGISTRY,
                run_id=RUN_ID,
                env_path=None,
                structured_parse_request=fake_request,
            )

        text = output.getvalue()
        self.assertIn("latency: 987ms", text)
        self.assertIn("tokens: 46 (in 30, out 12, reasoning 4)", text)
        self.assertIn("cost: $0.000321", text)
        self.assertNotIn("raw_response_metadata", text)
        self.assertNotIn("response-001", text)
        self.assertNotIn("raw_output", text)


def _run_jsonl(structured_parse_request) -> tuple[RunTestCase, Run]:
    output = StringIO()
    with redirect_stdout(output):
        run_evaluation(
            model="gemini/gemini-2.5-flash",
            corpus_path=EXAMPLE_CORPUS,
            document_registry_path=DOCUMENT_REGISTRY,
            run_id=RUN_ID,
            env_path=None,
            output_format="jsonl",
            structured_parse_request=structured_parse_request,
        )

    lines = output.getvalue().splitlines()
    if len(lines) != 2:
        raise AssertionError(f"expected 2 JSONL rows, got {len(lines)}: {lines!r}")
    return RunTestCase.model_validate_json(lines[0]), Run.model_validate_json(lines[1])


if __name__ == "__main__":
    unittest.main()
