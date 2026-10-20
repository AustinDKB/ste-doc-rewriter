"""Deterministic glossary swaps and acronym expansion (Phase 1, no model)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ste_doc_rewriter.glossary import KINDS_SWAP

# Only "etc." can end a sentence: at the end of a paragraph, or before a capital
# or a protected span (also after ")"). "e.g." and "i.e." never do.
_SENTENCE_FINAL_TERMS = frozenset({"etc."})
_PARAGRAPH_END = re.compile(r"[ \t]*(?:\n[ \t]*\n|$)")
_NEXT_SENTENCE = re.compile(r"(\)?)\s+(?:[A-Z]|\x00P)")
# Line text before a match that starts a sentence: nothing, a heading or list
# marker, or a finished sentence.
_SENTENCE_START = re.compile(r"[ \t]*(?:#+|[-*+]|\d+[.)])?[ \t]*|.*[.!?][ \t]+")


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


def _starts_sentence(text: str, start: int) -> bool:
    return _SENTENCE_START.fullmatch(text, text.rfind("\n", 0, start) + 1, start) is not None


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
            new = replace
            if _starts_sentence(out, first.start()):
                new = replace[:1].upper() + replace[1:]
            out = out[:first.start()] + new + out[first.end():]
            applied.append(f"{term}→{replace}")
            continue

        case_sensitive = bool(entry.get("case_sensitive", False))
        parts: list[str] = []
        pos = 0
        for match in pattern.finditer(out):
            applied.append(f"{term}→{replace}")
            new = replace if case_sensitive else _match_case(match.group(0), replace)
            end = match.end()
            if term in _SENTENCE_FINAL_TERMS:
                nxt = _NEXT_SENTENCE.match(out, end)
                if nxt and nxt.group(1):
                    new += ")."
                    end += 1
                elif nxt or _PARAGRAPH_END.match(out, end):
                    new += "."
            parts += [out[pos:match.start()], new]
            pos = end
        out = "".join(parts) + out[pos:]

    return out, applied
