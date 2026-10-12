"""Prompt assembly for single-pass parsing attempts."""

from __future__ import annotations

import json

from single_pass_parsing_ranker.models import JsonObject


def build_prompt(
    *,
    instruction: str,
    document_text: str,
    data_model: JsonObject,
) -> str:
    """Build the plain text prompt sent to the model."""

    clean_instruction = instruction.strip()
    if not clean_instruction:
        raise ValueError("instruction must not be blank")
    if not document_text.strip():
        raise ValueError("document_text must not be blank")

    data_model_json = json.dumps(data_model, indent=2, sort_keys=True)
    return (
        f"{clean_instruction}\n\n"
        f"Data model:\n{data_model_json}\n\n"
        f"Document:\n{document_text}"
    )
