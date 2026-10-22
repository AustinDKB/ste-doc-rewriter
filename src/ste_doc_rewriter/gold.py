"""Gold pair helpers (Phase 2): protected spans, lint score, length band."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ste_doc_rewriter import protect as _protect
from ste_doc_rewriter.glossary import DEFAULT_GLOSSARY_DIR, iter_glossary_files, product_names
from ste_doc_rewriter.lint import lint, word_count

GOLD_DIR = Path(__file__).resolve().parents[2] / "data" / "gold"
PAIR_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "pair.schema.json"

# License of each gold input source (see SOURCES.md for the attribution terms).
DATASET_LICENSES = {
    "HuggingFaceH4/stack-exchange-preferences": "CC BY-SA 4.0",
    "open-index/open-github-issues": "ODC-By 1.0 (GitHub Terms of Service apply to the text)",
    "elihoole/asrs-aviation-reports": "Apache-2.0 (NASA ASRS, U.S. government work)",
    "stindardlogic/writing-quality-dpo-100k": "Apache-2.0",
    "grammarly/coedit": "Apache-2.0",
    "chaojiang06/wiki_auto": "CC BY-SA 3.0 (Wikipedia text)",
}

# Section 5.2 length bands (input words, inclusive).
BANDS = (("sentence", 15, 35), ("paragraph", 80, 180), ("section", 180, 250), ("chunk", 250, 400))

# Same order as protect.protect(), so a span gets the kind of the pattern that took it.
_KINDS = (
    ("front_matter", _protect._FRONT_MATTER),
    ("code", _protect._FENCED),
    ("code", _protect._INLINE),
    ("link", _protect._LINK_TARGET),
    ("url", _protect._URL),
    ("path", _protect._PATH),
    ("cli", _protect._FLAG),
    ("number", _protect._NUMBER_UNIT),
)


def bundled_entries() -> list[dict[str, Any]]:
    """Glossary entries without the gitignored glossary/local/ overlay, so gold scores reproduce."""
    return [
        entry
        for path in iter_glossary_files(DEFAULT_GLOSSARY_DIR)
        if path.relative_to(DEFAULT_GLOSSARY_DIR).parts[0] != "local"
        for entry in json.loads(path.read_text(encoding="utf-8"))
    ]


def length_band(text: str) -> str | None:
    words = word_count(text)
    return next((name for name, lo, hi in BANDS if lo <= words <= hi), None)


def protected_spans(text: str, entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Distinct spans protect() takes from text, in text order, with their kind."""
    spans = dict.fromkeys(_protect.protect(text, product_names(entries)).spans.values())
    out = []
    for span in sorted(spans, key=text.find):
        kind = next((k for k, pattern in _KINDS if pattern.fullmatch(span)), "product")
        out.append({"text": span, "kind": kind})
    return out


def lint_score(text: str, entries: list[dict[str, Any]]) -> float:
    """Lint score as a fraction (0–1), as section 11.1 stores it."""
    protected = _protect.protect(text, product_names(entries))
    return round(lint(protected.text, glossary=entries).score / 100, 4)


def fill_qc(pair: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Return pair with protected_spans and qc.ste_lint_score recomputed."""
    return {
        **pair,
        "protected_spans": protected_spans(pair["input"], entries),
        "qc": {**pair["qc"], "ste_lint_score": lint_score(pair["output"], entries)},
    }


def missing_spans(pair: dict[str, Any], entries: list[dict[str, Any]]) -> list[str]:
    """Protected input spans that no protected span of the output keeps unchanged.

    A span inside a larger output span counts as kept, for example a "1/NT" that
    the rewrite moved into a code block.
    """
    kept = _protect.protect(pair["output"], product_names(entries)).spans.values()
    return [s["text"] for s in pair["protected_spans"] if not any(s["text"] in k for k in kept)]


def read_pairs(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_ids(path: Path) -> list[str]:
    """Pair ids from a one-id-per-line list (blank lines and "#" comments skipped)."""
    if not path.is_file():
        return []
    return [s for line in path.read_text(encoding="utf-8").splitlines() if (s := re.sub(r"#.*", "", line).strip())]

