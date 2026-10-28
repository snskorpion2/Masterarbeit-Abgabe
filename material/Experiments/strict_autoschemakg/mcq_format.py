"""Opt-in syntax bridge for the original MCQ parser, without JSON repair.

The upstream parser reads json.loads(response.split('```')[1]). A complete
labelled JSON fence is valid model output but its language label is not JSON.
Only that label is removed. The body is never serialized or otherwise changed.
"""
from __future__ import annotations

import hashlib
import json
import re


_SINGLE_FENCE = re.compile(
    r"\A[ \t\r\n]*```(?P<label>json)(?P<body>\r?\n[\s\S]*?\r?\n)```[ \t\r\n]*\Z"
)


def _reject_non_json_constant(value):
    raise ValueError(f"Not a JSON constant: {value}")


def remove_json_fence_label(text: str) -> tuple[str, dict | None]:
    """Remove exactly ``json`` from one complete fenced list of MCQ objects.

Outer whitespace, line endings, ordering, values and original body spelling
are retained. Additional prose/fences, malformed JSON and other response
shapes pass through unchanged. This does not validate question quality.
"""
    if text.count("```") != 2:
        return text, None
    match = _SINGLE_FENCE.fullmatch(text)
    if match is None:
        return text, None
    try:
        questions = json.loads(match["body"], parse_constant=_reject_non_json_constant)
    except (ValueError, RecursionError):
        return text, None
    if not isinstance(questions, list) or not questions or not all(
        isinstance(question, dict) and {"question", "options", "answer"} <= question.keys()
        for question in questions
    ):
        return text, None
    after = text[:match.start("label")] + text[match.end("label"):]
    audit = {
        "operation": "remove_json_code_fence_language_label",
        "before_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "after_sha256": hashlib.sha256(after.encode("utf-8")).hexdigest(),
        "json_body_sha256": hashlib.sha256(match["body"].encode("utf-8")).hexdigest(),
        "question_count": len(questions),
    }
    return after, audit
