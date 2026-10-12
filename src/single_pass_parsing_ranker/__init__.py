"""Tools for ranking single-pass document parsing models."""

from single_pass_parsing_ranker.data import load_corpora, load_corpus, load_documents
from single_pass_parsing_ranker.llm import (
    LLMCallError,
    LLMResponseError,
    StructuredOutputValidationError,
    extract_litellm_result,
    request_structured_parse,
    response_format_for_schema,
)
from single_pass_parsing_ranker.models import (
    AttemptStatus,
    Corpus,
    CorpusLoadError,
    DataModelSchema,
    Document,
    FailureReason,
    LLMCallResult,
    Run,
    RunStatus,
    RunTestCase,
    TestCase,
    storage_schemas,
)
from single_pass_parsing_ranker.normalize import (
    JsonParseError,
    NormalizationError,
    SchemaValidationError,
    normalize_json_value,
    parse_json_output,
)
from single_pass_parsing_ranker.prompts import build_prompt
from single_pass_parsing_ranker.runner import RunnerError, run_evaluation
from single_pass_parsing_ranker.scoring import field_scores, flatten_json_value, score_json_values
from single_pass_parsing_ranker.storage import append_jsonl, append_run, append_run_test_case

__all__ = [
    "AttemptStatus",
    "Corpus",
    "CorpusLoadError",
    "DataModelSchema",
    "Document",
    "FailureReason",
    "JsonParseError",
    "LLMCallError",
    "LLMCallResult",
    "LLMResponseError",
    "NormalizationError",
    "Run",
    "RunnerError",
    "RunStatus",
    "RunTestCase",
    "SchemaValidationError",
    "StructuredOutputValidationError",
    "TestCase",
    "append_jsonl",
    "append_run",
    "append_run_test_case",
    "build_prompt",
    "extract_litellm_result",
    "field_scores",
    "flatten_json_value",
    "load_corpora",
    "load_corpus",
    "load_documents",
    "normalize_json_value",
    "parse_json_output",
    "request_structured_parse",
    "response_format_for_schema",
    "run_evaluation",
    "score_json_values",
    "storage_schemas",
]
