import os
import unittest
from unittest.mock import patch

from single_pass_parsing_ranker import cli


class CLITests(unittest.TestCase):
    def setUp(self) -> None:
        configure_logging_patcher = patch.object(cli, "configure_logging")
        self.configure_logging = configure_logging_patcher.start()
        self.addCleanup(configure_logging_patcher.stop)

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
                    "--documents",
                    "documents/documents.json",
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
                    "document_registry_path": "documents/documents.json",
                    "model_settings": {"temperature": 0.0},
                    "layout_to_text_strategy": "native_layout_to_text",
                    "ocr_strategy": "pytesseract",
                    "output_format": "pretty",
                    "output_dir": "runs",
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
                    "--documents",
                    "documents/documents.json",
                    "--output-format",
                    "jsonl",
                ]
            )

        self.assertEqual(calls[0]["provider"], None)
        self.assertEqual(calls[0]["model_settings"], {})
        self.assertEqual(calls[0]["layout_to_text_strategy"], "native_layout_to_text")
        self.assertEqual(calls[0]["ocr_strategy"], "pytesseract")
        self.assertEqual(calls[0]["output_format"], "jsonl")
        self.assertEqual(calls[0]["output_dir"], "runs")

    def test_run_command_accepts_document_text_strategy_flags(self) -> None:
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
                    "--documents",
                    "documents/documents.json",
                    "--layout-to-text-strategy",
                    "native_layout_to_text",
                    "--ocr-strategy",
                    "pytesseract",
                ]
            )

        self.assertEqual(calls[0]["layout_to_text_strategy"], "native_layout_to_text")
        self.assertEqual(calls[0]["ocr_strategy"], "pytesseract")

    def test_run_command_accepts_output_directory(self) -> None:
        calls = []

        with patch.object(cli, "run_evaluation", lambda **kwargs: calls.append(kwargs)):
            cli.main(
                [
                    "run",
                    "--model",
                    "gemini/gemini-2.5-flash",
                    "--corpus",
                    "corpora/0.1.0.json",
                    "--documents",
                    "documents/documents.json",
                    "--output-dir",
                    "artifacts/local-run",
                ]
            )

        self.assertEqual(calls[0]["output_dir"], "artifacts/local-run")

    def test_run_command_passes_through_s3_uris(self) -> None:
        calls = []

        with patch.object(cli, "run_evaluation", lambda **kwargs: calls.append(kwargs)):
            cli.main(
                [
                    "run",
                    "--model",
                    "gemini/gemini-2.5-flash",
                    "--corpus",
                    "s3://example-bucket/raw/corpora/0.3.0.json",
                    "--documents",
                    "s3://example-bucket/raw/documents/documents.json",
                    "--output-dir",
                    "s3://example-bucket/silver/ranker",
                ]
            )

        self.assertEqual(calls[0]["corpus_path"], "s3://example-bucket/raw/corpora/0.3.0.json")
        self.assertEqual(
            calls[0]["document_registry_path"],
            "s3://example-bucket/raw/documents/documents.json",
        )
        self.assertEqual(calls[0]["output_dir"], "s3://example-bucket/silver/ranker")

    def test_run_command_configures_logging_from_flags(self) -> None:
        with patch.object(cli, "run_evaluation"):
            cli.main(
                [
                    "run",
                    "--model",
                    "gemini/gemini-2.5-flash",
                    "--corpus",
                    "corpora/0.1.0.json",
                    "--documents",
                    "documents/documents.json",
                    "--log-level",
                    "warning",
                    "--log-format",
                    "json",
                ]
            )

        self.configure_logging.assert_called_once_with(level="WARNING", log_format="json")

    def test_run_command_uses_logging_environment_defaults(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"SPPR_LOG_LEVEL": "error", "SPPR_LOG_FORMAT": "json"},
                clear=False,
            ),
            patch.object(cli, "run_evaluation"),
        ):
            cli.main(
                [
                    "run",
                    "--model",
                    "gemini/gemini-2.5-flash",
                    "--corpus",
                    "corpora/0.1.0.json",
                    "--documents",
                    "documents/documents.json",
                ]
            )

        self.configure_logging.assert_called_once_with(level="ERROR", log_format="json")


if __name__ == "__main__":
    unittest.main()
