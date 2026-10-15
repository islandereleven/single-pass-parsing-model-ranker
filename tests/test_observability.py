from contextlib import redirect_stderr
from io import StringIO
import json
import logging
from pathlib import Path
import unittest
from uuid import UUID

from single_pass_parsing_ranker.observability import (
    PACKAGE_LOGGER_NAME,
    SERVICE_NAME,
    configure_logging,
    log_event,
)


class ObservabilityTests(unittest.TestCase):
    def tearDown(self) -> None:
        package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
        for handler in tuple(package_logger.handlers):
            if getattr(handler, "_sppr_managed", False):
                package_logger.removeHandler(handler)
                handler.close()
        package_logger.setLevel(logging.NOTSET)
        package_logger.propagate = True

    def test_json_formatter_emits_the_stable_event_contract(self) -> None:
        output = StringIO()
        configure_logging(level="INFO", log_format="json", stream=output)

        log_event(
            logging.getLogger(f"{PACKAGE_LOGGER_NAME}.test"),
            logging.INFO,
            "case.finished",
            "Evaluation case completed",
            run_id=UUID("72b60a7f-2a08-4d18-91f6-cb524ec777a0"),
            output_path=Path("runs/results.jsonl"),
            outcome="scored",
            optional_value=None,
        )

        record = json.loads(output.getvalue())
        self.assertEqual(record["level"], "INFO")
        self.assertEqual(record["service"], SERVICE_NAME)
        self.assertEqual(record["event"], "case.finished")
        self.assertEqual(record["message"], "Evaluation case completed")
        self.assertEqual(record["run_id"], "72b60a7f-2a08-4d18-91f6-cb524ec777a0")
        self.assertEqual(record["output_path"], "runs/results.jsonl")
        self.assertEqual(record["outcome"], "scored")
        self.assertNotIn("optional_value", record)
        self.assertRegex(record["timestamp"], r"^\d{4}-\d{2}-\d{2}T.*Z$")

    def test_human_formatter_keeps_event_and_fields_readable(self) -> None:
        output = StringIO()
        configure_logging(level="INFO", log_format="human", stream=output)

        log_event(
            logging.getLogger(f"{PACKAGE_LOGGER_NAME}.test"),
            logging.WARNING,
            "case.finished",
            "Evaluation case completed",
            outcome="zero_score",
        )

        line = output.getvalue()
        self.assertIn("WARNING case.finished Evaluation case completed", line)
        self.assertIn('outcome="zero_score"', line)

    def test_default_stream_is_stderr(self) -> None:
        stderr = StringIO()
        with redirect_stderr(stderr):
            configure_logging(level="INFO", log_format="json")
            log_event(
                logging.getLogger(f"{PACKAGE_LOGGER_NAME}.test"),
                logging.INFO,
                "run.started",
                "Evaluation run started",
            )

        self.assertEqual(json.loads(stderr.getvalue())["event"], "run.started")

    def test_level_filtering_and_reconfiguration_do_not_duplicate_events(self) -> None:
        output = StringIO()
        configure_logging(level="WARNING", log_format="json", stream=output)
        configure_logging(level="WARNING", log_format="json", stream=output)
        logger = logging.getLogger(f"{PACKAGE_LOGGER_NAME}.test")

        log_event(logger, logging.INFO, "case.started", "Case started")
        log_event(logger, logging.ERROR, "case.finished", "Case failed", outcome="failed")

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["event"], "case.finished")

    def test_reserved_fields_cannot_override_the_contract(self) -> None:
        configure_logging(level="INFO", log_format="json", stream=StringIO())

        with self.assertRaises(ValueError):
            log_event(
                logging.getLogger(f"{PACKAGE_LOGGER_NAME}.test"),
                logging.INFO,
                "run.started",
                "Run started",
                service="different-service",
            )


if __name__ == "__main__":
    unittest.main()
