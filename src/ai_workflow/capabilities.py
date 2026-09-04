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
    r"|\b(?:vector search|chat with (?:uploaded )?documents?|"
    r"(?:ask|answer) questions? (?:about|over|from) documents?)\b"
)
_NEGATED = re.compile(r"(?i)\b(?:not required|out of scope|non-goal|will not|do not)\b")
_SCRAPING_DECISION = re.compile(
    r"(?mi)^\s*(?:[-*]\s*)?(?:web[ -]?scraping|website scraping)\s*:\s*"
    r"(?P<value>required|not required)\s*$"
)
_SCRAPING_TERMS = re.compile(
    r"(?i)\b(?:web[ -]?scrap(?:e|er|ing)|website scrap(?:e|er|ing)|crawl(?:er|ing)?|"
    r"extract(?:ion)? (?:data )?from (?:a )?(?:website|web page)|"
    r"monitor (?:a )?website for|scrape (?:https?://|www\.|[a-z0-9.-]+\.[a-z]{2,}))\b"
)


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
        rag_required = decisions[0] == "required"
        if not rag_required and affirmative_lines:
            raise RuntimeError("PRD declares RAG not required but also contains a RAG requirement")
    else:
        rag_required = bool(affirmative_lines)

    scraping_decisions = [
        match.group("value").lower() for match in _SCRAPING_DECISION.finditer(text)
    ]
    if len(set(scraping_decisions)) > 1:
        raise RuntimeError("conflicting web-scraping capability declarations in PRD")
    scraping_lines = [
        line
        for line in text.splitlines()
        if _SCRAPING_TERMS.search(line) and not _NEGATED.search(line)
    ]
    if scraping_decisions:
        webscraping_required = scraping_decisions[0] == "required"
        if not webscraping_required and scraping_lines:
            raise RuntimeError(
                "PRD declares web scraping not required but also contains a scraping requirement"
            )
    else:
        webscraping_required = bool(scraping_lines)
    return {"rag": rag_required, "webscraping": webscraping_required}
