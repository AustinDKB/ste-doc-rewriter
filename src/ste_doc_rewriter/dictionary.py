"""Deterministic glossary swaps and acronym expansion (Phase 1, no model)."""

from __future__ import annotations

import re
from typing import Any


def _word_pattern(term: str, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    # Word-boundary-ish: don't match inside longer identifiers
    escaped = re.escape(term)
    return re.compile(rf"(?<![\w-]){escaped}(?![\w-])", flags)


def apply_swaps(
    text: str,
    entries: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """Apply ste_swap / prefer / abbrev_expand / acronym_expand longest-first.

    Returns (rewritten_text, list of "term→replace" applied).
    """
    swaps = [e for e in entries if e.get("kind") in {
        "ste_swap", "prefer", "abbrev_expand", "acronym_expand",
    }]
    # Longest term first to avoid partial overlaps
    swaps = sorted(swaps, key=lambda e: len(e.get("term", "")), reverse=True)

    applied: list[str] = []
    out = text
    for entry in swaps:
        term = entry["term"]
        replace = entry["replace"]
        if term.lower() == replace.lower():
            continue  # domain coverage / identity entries
        case_sensitive = bool(entry.get("case_sensitive", False))
        pattern = _word_pattern(term, case_sensitive)

        def _repl(
            match: re.Match[str],
            _replace: str = replace,
            _term: str = term,
        ) -> str:
            applied.append(f"{_term}→{_replace}")
            return _replace

        out, _n = pattern.subn(_repl, out)

    return out, applied
