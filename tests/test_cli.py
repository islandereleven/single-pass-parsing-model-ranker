import unittest
from unittest.mock import patch

from single_pass_parsing_ranker import cli


class CLITests(unittest.TestCase):
    def test_run_command_calls_evaluator(self) -> None:
        calls = []

        def fake_run_evaluation(**kwargs):
            calls.append(kwargs)

        with patch.object(cli, "run_evaluation", fake_run_evaluation):
            cli.main(
                [
                    "run",
                    "--model",
                    "gemini/gemini-2.5-flash",
                    "--provider",
                    "gemini",
                    "--corpus",
                    "corpora/0.1.0.json",
                    "--temperature",
                    "0",
                ]
            )

        self.assertEqual(
            calls,
            [
                {
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "corpus_path": "corpora/0.1.0.json",
                    "model_settings": {"temperature": 0.0},
                    "output_format": "pretty",
                }
            ],
        )

    def test_run_command_supports_jsonl_output(self) -> None:
        calls = []

        def fake_run_evaluation(**kwargs):
            calls.append(kwargs)

        with patch.object(cli, "run_evaluation", fake_run_evaluation):
            cli.main(
                [
                    "run",
                    "--model",
                    "gemini/gemini-2.5-flash",
                    "--corpus",
                    "corpora/0.1.0.json",
                    "--output-format",
                    "jsonl",
                ]
            )

        self.assertEqual(calls[0]["provider"], None)
        self.assertEqual(calls[0]["model_settings"], {})
        self.assertEqual(calls[0]["output_format"], "jsonl")


if __name__ == "__main__":
    unittest.main()
