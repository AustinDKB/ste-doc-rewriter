"""Deterministic glossary swaps and acronym expansion (Phase 1, no model)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ste_doc_rewriter.glossary import KINDS_SWAP

# A dotted term at end of line also ends the sentence. Only "etc." can end a
# sentence mid-line: before a capital or a protected span, also after ")".
_LINE_END = re.compile(r"[ \t]*(?:\n|$)")
_NEXT_SENTENCE = re.compile(r"\)?\s+(?:[A-Z]|\x00P)")
_SENTENCE_FINAL_TERMS = frozenset({"etc."})


def word_pattern(term: str, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    # Word-boundary-ish: don't match inside longer identifiers or file names
    escaped = re.escape(term)
    return re.compile(rf"(?<![\w.-]){escaped}(?![\w-]|\.\w)", flags)


def compile_rules(
    entries: list[dict[str, Any]],
    kinds: Iterable[str],
) -> list[tuple[dict[str, Any], re.Pattern[str]]]:
    """Entries of the given kinds with their match patterns, longest term first.

    Identity rows (term == replace) only record domain coverage, so they are left out.
    """
    kinds = frozenset(kinds)
    rules = [
        (e, word_pattern(e["term"], bool(e.get("case_sensitive", False))))
        for e in entries
        if e.get("kind") in kinds and e["term"].lower() != e["replace"].lower()
    ]
    return sorted(rules, key=lambda r: len(r[0]["term"]), reverse=True)


def _match_case(found: str, replace: str) -> str:
    if len(found) > 1 and found.isupper():
        return replace.upper()
    if found[:1].isupper():
        return replace[:1].upper() + replace[1:]
    return replace


def _wrapped(text: str, match: re.Match[str]) -> bool:
    return text[match.start() - 1:match.start()] == "(" and text[match.end():match.end() + 1] == ")"


def apply_swaps(
    text: str,
    entries: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """Apply ste_swap / prefer / abbrev_expand / acronym_expand longest-first.

    Acronym expansions ("X Y (XY)") apply to the first use only, and not at all
    when the text already has "(XY)", so a second run changes nothing.

    Returns (rewritten_text, list of "term→replace" applied).
    """
    applied: list[str] = []
    out = text
    for entry, pattern in compile_rules(entries, KINDS_SWAP):
        term = entry["term"]
        replace = entry["replace"]

        if replace.endswith(f"({term})"):
            matches = list(pattern.finditer(out))
            if not matches or any(_wrapped(out, m) for m in matches):
                continue
            first = matches[0]
            out = out[:first.start()] + replace + out[first.end():]
            applied.append(f"{term}→{replace}")
            continue

        case_sensitive = bool(entry.get("case_sensitive", False))

        def _repl(
            match: re.Match[str],
            _replace: str = replace,
            _term: str = term,
            _case_sensitive: bool = case_sensitive,
        ) -> str:
            applied.append(f"{_term}→{_replace}")
            new = _replace if _case_sensitive else _match_case(match.group(0), _replace)
            end = match.end()
            if _term.endswith(".") and (
                _LINE_END.match(match.string, end)
                or (_term in _SENTENCE_FINAL_TERMS and _NEXT_SENTENCE.match(match.string, end))
            ):
                new += "."
            return new

        out = pattern.sub(_repl, out)

    return out, applied
