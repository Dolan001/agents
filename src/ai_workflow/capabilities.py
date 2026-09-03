"""Deterministic requirement-triggered capability detection."""

from __future__ import annotations

import re
from pathlib import Path

_RAG_DECISION = re.compile(
    r"(?mi)^\s*(?:[-*]\s*)?(?:rag|retrieval[- ]augmented generation)\s*:\s*"
    r"(?P<value>required|not required)\s*$"
)
_RAG_TERMS = re.compile(
    r"(?i)\b(?:RAG|retrieval[- ]augmented generation|semantic (?:search|retrieval)|"
    r"document (?:Q&A|question answering)|knowledge[- ]base (?:assistant|chat)|"
    r"grounded (?:answer|response)s?|answer(?:ing)? (?:from|over) (?:uploaded )?documents?)\b"
)
_NEGATED = re.compile(r"(?i)\b(?:not required|out of scope|non-goal|will not|do not)\b")


def detect_prd_capabilities(path: Path) -> dict[str, bool]:
    """Resolve explicit optional capabilities without heuristic framework selection."""
    text = path.read_text(encoding="utf-8")
    decisions = [match.group("value").lower() for match in _RAG_DECISION.finditer(text)]
    if len(set(decisions)) > 1:
        raise RuntimeError("conflicting RAG capability declarations in PRD")
    affirmative_lines = [
        line for line in text.splitlines() if _RAG_TERMS.search(line) and not _NEGATED.search(line)
    ]
    if decisions:
        required = decisions[0] == "required"
        if not required and affirmative_lines:
            raise RuntimeError("PRD declares RAG not required but also contains a RAG requirement")
        return {"rag": required}
    return {"rag": bool(affirmative_lines)}

