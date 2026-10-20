"""Protect → dictionary swap → restore → lint (Phase 1, no model)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ste_doc_rewriter.dictionary import apply_swaps
from ste_doc_rewriter.glossary import load_entries, product_names, swap_entries
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
    products = product_names(entries)
    swaps = swap_entries(entries)
    if not expand_acronyms:
        swaps = [
            e for e in swaps
            if e.get("kind") not in {"acronym_expand", "abbrev_expand"}
        ]

    protected = protect(text, product_names=products)
    swapped, applied = apply_swaps(protected.text, swaps)
    restored = restore(swapped, protected.spans)
    lint_result = lint(restored, mode=mode, not_approved=swaps)
    return RewriteResult(
        text=restored,
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
    swaps = swap_entries(entries)
    return lint(text, mode=mode, not_approved=swaps)
