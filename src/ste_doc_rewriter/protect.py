"""Protect code, URLs, paths, flags, numbers-with-units, and product names."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ProtectResult:
    text: str
    spans: dict[str, str] = field(default_factory=dict)


PLACEHOLDER = re.compile(r"\x00P(\d+)\x00")
_PLACEHOLDER_LINES = re.compile(r"(\x00P\d+\x00)(\n*)")

# Order matters: longer / more specific first.
# YAML front matter: "---" on the first line, then a non-blank line, up to "---".
_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(?=[ \t]*\S)[\s\S]*?\n---[ \t]*(?=\n|\Z)")
_FENCED = re.compile(r"```[\s\S]*?```")
_INLINE = re.compile(r"`[^`\n]+`")
# Markdown link target: the "(...)" after "]"
_LINK_TARGET = re.compile(r"(?<=\])\([^)\n]*\)")
_URL = re.compile(r"https?://[^\s<>\]\)\"']*[^\s<>\]\)\"'.,;:!?]")
# Absolute or relative paths with a slash and a file-ish tail; a trailing
# sentence mark (". , ; : ! ?") stays outside, as for URLs and flag values.
_PATH = re.compile(
    r"(?<![\w/])(?:\.{0,2}/)?(?:[\w.-]+/)+[\w.-]*\w(?![\w/])"
)
_FLAG = re.compile(r"(?<![\w-])--?[A-Za-z][\w-]*(?:=[^\s]*[^\s.,;:!?])?(?![\w-])")
# Numbers with common units (space optional): 10ms, 2.5 GB, 80%
_NUMBER_UNIT = re.compile(
    r"(?<!\w)\d+(?:\.\d+)?\s?(?:"
    r"%|ms|s|m|h|kb|mb|gb|tb|kib|mib|gib|tib|"
    r"KB|MB|GB|TB|KiB|MiB|GiB|TiB|Hz|kHz|MHz|GHz|"
    r"px|em|rem|deg|rpm"
    r")(?!\w)"
)


def _product_pattern(names: list[str]) -> re.Pattern[str] | None:
    if not names:
        return None
    # Longest first so "GitHub Actions" wins over "GitHub"
    ordered = sorted({n for n in names if n}, key=len, reverse=True)
    alts = "|".join(re.escape(n) for n in ordered)
    return re.compile(rf"(?<!\w)(?:{alts})(?!\w)")


def protect(text: str, product_names: list[str] | None = None) -> ProtectResult:
    """Replace protected spans with opaque placeholders; restore with restore().

    A multi-line span (front matter, a fenced code block) keeps its newlines after
    the placeholder, so line numbers match and the block stays its own paragraph.
    """
    spans: dict[str, str] = {}
    counter = 0

    def stash(match: re.Match[str]) -> str:
        nonlocal counter
        key = f"\x00P{counter}\x00"
        spans[key] = match.group(0)
        counter += 1
        return key + "\n" * match.group(0).count("\n")

    out = text
    for pattern in (
        _FRONT_MATTER, _FENCED, _INLINE, _LINK_TARGET, _URL, _PATH, _FLAG, _NUMBER_UNIT,
    ):
        out = pattern.sub(stash, out)

    prod = _product_pattern(product_names or [])
    if prod is not None:
        out = prod.sub(stash, out)

    return ProtectResult(text=out, spans=spans)


def restore(text: str, spans: dict[str, str]) -> str:
    """Put protected spans back. Unknown placeholders are left as-is."""

    def unstash(match: re.Match[str]) -> str:
        key, newlines = match.groups()
        if key not in spans:
            return match.group(0)
        span = spans[key]
        return span + newlines[span.count("\n"):]

    return _PLACEHOLDER_LINES.sub(unstash, text)
