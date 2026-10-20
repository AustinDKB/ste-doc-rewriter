"""Protect → dictionary swap → lint → restore (Phase 1, no model)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ste_doc_rewriter.dictionary import apply_swaps
from ste_doc_rewriter.glossary import KINDS_EXPAND, load_entries, product_names
from ste_doc_rewriter.lint import LintResult, Mode, lint
from ste_doc_rewriter.protect import protect, restore


@dataclass
class RewriteResult:
    text: str
    expansions_applied: list[str]
    lint: LintResult


def rewrite(
    text: str,
    *,
    glossary_dir: Path | None = None,
    mode: Mode = "descriptive",
    expand_acronyms: bool = True,
) -> RewriteResult:
    entries = load_entries(glossary_dir)
    swaps = [
        e for e in entries
        if expand_acronyms or e.get("kind") not in KINDS_EXPAND
    ]

    protected = protect(text, product_names=product_names(entries))
    swapped, applied = apply_swaps(protected.text, swaps)
    lint_result = lint(swapped, mode=mode, glossary=entries)
    return RewriteResult(
        text=restore(swapped, protected.spans),
        expansions_applied=applied,
        lint=lint_result,
    )


def lint_text(
    text: str,
    *,
    glossary_dir: Path | None = None,
    mode: Mode = "descriptive",
) -> LintResult:
    entries = load_entries(glossary_dir)
    protected = protect(text, product_names=product_names(entries))
    return lint(protected.text, mode=mode, glossary=entries)
