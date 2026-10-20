"""Command line entry point for the evaluator."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from single_pass_parsing_ranker import LayoutToTextStrategy, OcrStrategy, RunStatus, run_evaluation
from single_pass_parsing_ranker.observability import configure_logging


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="single-pass-ranker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one model against one corpus.")
    run_parser.add_argument("--model", required=True, help="LiteLLM model id, such as gemini/gemini-2.5-flash.")
    run_parser.add_argument("--provider", help="Provider label stored on the run row.")
    run_parser.add_argument("--corpus", required=True, help="Local path or URI to the corpus test-case table.")
    run_parser.add_argument(
        "--documents",
        required=True,
        help="Local path or URI to the document registry table.",
    )
    run_parser.add_argument("--temperature", type=float, help="Optional model temperature.")
    run_parser.add_argument(
        "--layout-to-text-strategy",
        choices=tuple(item.value for item in LayoutToTextStrategy),
        default=LayoutToTextStrategy.NATIVE_LAYOUT_TO_TEXT.value,
        help="Document-to-text strategy stored on the run row.",
    )
    run_parser.add_argument(
        "--ocr-strategy",
        choices=tuple(item.value for item in OcrStrategy),
        default=OcrStrategy.PYTESSERACT.value,
        help="OCR strategy stored on the run row.",
    )
    run_parser.add_argument(
        "--output-format",
        choices=("pretty", "jsonl", "quiet"),
        default="pretty",
        help="Terminal output format; quiet suppresses result output.",
    )
    run_parser.add_argument(
        "--output-dir",
        default="runs",
        help="Local path or URI for immutable per-run result bundles.",
    )
    run_parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        type=str.upper,
        help="Package log threshold (default: INFO).",
    )
    run_parser.add_argument(
        "--log-format",
        choices=("human", "json"),
        default="human",
        type=str.lower,
        help="Package log format (default: human).",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        configure_logging(level=args.log_level, log_format=args.log_format)
        run = run_evaluation(
            model=args.model,
            provider=args.provider,
            corpus_path=args.corpus,
            document_registry_path=args.documents,
            model_settings=_model_settings(args),
            layout_to_text_strategy=args.layout_to_text_strategy,
            ocr_strategy=args.ocr_strategy,
            output_format=args.output_format,
            output_dir=args.output_dir,
        )
        return 1 if run.status == RunStatus.FAILED else 0

    return 0


def _model_settings(args: argparse.Namespace) -> dict[str, float]:
    settings = {}
    if args.temperature is not None:
        settings["temperature"] = args.temperature
    return settings


if __name__ == "__main__":
    raise SystemExit(main())
