"""Reference-free selection of one complete, visibly offered MCQ option.

Adapted from analyze_d8_mcq_format_diagnosis_v1.select_answer. This module
has no dependency on answers, questions, contexts, or historical result paths.
"""
from __future__ import annotations

import re
import unicodedata


PROTOCOL = "option_bound_complete_text_v1"


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split()).removesuffix(".")


def validate_visible_options(options, variant):
    """Reject malformed or normalized-duplicate offered choices before use."""
    letters = "ABCDE" if variant == "ae" else "ABCD" if variant == "ad" else None
    if letters is None or not isinstance(options, list) or len(options) != len(letters):
        raise ValueError("Invalid visible MCQ options")
    if not all(isinstance(option, str) and option.startswith(letter + (". " if letter == "E" else ": "))
               and option[3:].strip() for letter, option in zip(letters, options)):
        raise ValueError("Invalid visible MCQ option labels")
    texts = [normalized(option[3:]) for option in options]
    if len(set(texts)) != len(texts):
        raise ValueError("Ambiguous MCQ option texts")
    return letters, texts


def select_answer(content, options, variant):
    """Return (letter, reason), or reject an incomplete/ambiguous selection."""
    letters, texts = validate_visible_options(options, variant)
    if not isinstance(content, str):
        raise ValueError("MCQ answer must be text")
    answer = content.strip()
    if re.fullmatch(f"[{letters}]", answer):
        return answer, "original_exact_letter"
    match = re.fullmatch(rf"([{letters}])(?:[.):\-]\s*|\s+)(.+)", answer, flags=re.DOTALL)
    if not match:
        raise ValueError("No bounded MCQ option form")
    letter, remainder = match.groups()
    index = letters.index(letter)
    if normalized(remainder) not in {texts[index], normalized(options[index])}:
        raise ValueError("Nonmatching or extended MCQ option text")
    return letter, "full_matching_option_text"
