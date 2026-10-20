"""Programmatic STE-oriented lint checks (Phase 1 subset)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from ste_doc_rewriter.dictionary import (
    ADMONITION,
    HEADING,
    LIST_ITEM,
    UNDERLINE,
    compile_rules,
    unquote,
    word_pattern,
)
from ste_doc_rewriter.glossary import (
    KIND_APPROVED,
    KIND_PROTECT,
    KINDS_EXPAND,
    KINDS_NOT_APPROVED,
)
from ste_doc_rewriter.protect import PLACEHOLDER


Mode = Literal["descriptive", "procedure"]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
_PASSIVE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)\s+"
    r"(?:\w+ly\s+)?"
    r"\w+ed\b",
    re.IGNORECASE,
)
# Common irregular past participles after be-verbs
_PASSIVE_IRREGULAR = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)\s+"
    r"(?:\w+ly\s+)?"
    r"(?:made|done|written|given|taken|shown|built|set|put|sent|found|"
    r"left|held|kept|known|seen|used|run|begun|chosen|drawn|driven|"
    r"eaten|fallen|felt|fought|forgotten|frozen|gotten|gotten|"
    r"gone|grown|heard|hidden|hit|hurt|led|lost|met|paid|read|"
    r"ridden|risen|said|sold|sung|sunk|slept|spoken|spent|stood|"
    r"struck|swum|taught|torn|thought|thrown|understood|worn|won|"
    r"written)\b",
    re.IGNORECASE,
)
_ING_VERB = re.compile(
    r"\b(?:is|are|was|were|am|be|been|being|start|starts|started|"
    r"begin|begins|began|keep|keeps|kept|continue|continues|continued|"
    r"by)\s+(\w+ing)\b",
    re.IGNORECASE,
)
# Avoid gerund subjects / adjectives: "The following items" — still may false-positive
_STOP_ING = frozenset({
    "during", "something", "anything", "everything", "nothing",
    "morning", "evening", "warning", "string", "being",
})

# Noun-cluster tokens: a run breaker ("\x00") or a word.
_BREAK = " \x00 "
_CLUSTER_TOKEN = re.compile(r"\x00|" + _WORD.pattern)
_PAREN_WORD = re.compile(r"\(\w+\)")
_FUNCTION_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on",
    "for", "with", "by", "from", "as", "at", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those", "it", "its",
    "you", "your", "we", "our", "they", "their", "not", "can", "may",
    "must", "should", "will", "shall", "do", "does", "did", "has", "have",
    "had", "when", "where", "while", "after", "before", "into", "onto",
    "over", "under", "than", "then", "also", "only", "just", "about",
    "across", "through", "between", "within", "without", "during", "per",
    "via", "against", "along", "around", "behind", "below", "above", "up",
    "down", "out", "off", "so", "because", "until", "each", "every", "all",
    "some", "any", "no", "which", "who", "what", "how", "why", "there",
    "here", "he", "she", "him", "her", "them", "i", "me", "my", "us",
    "could", "would", "might",
})
# Common verbs and adverbs in technical docs; glossary verbs are added per run.
_COMMON_VERBS = (
    "add", "allow", "apply", "build", "change", "check", "click", "close",
    "configure", "copy", "create", "delete", "deploy", "disable", "enable",
    "enter", "find", "fix", "get", "give", "go", "help", "install", "keep",
    "let", "load", "make", "move", "need", "open", "pull", "push", "put",
    "read", "remove", "restart", "run", "save", "see", "select", "send",
    "set", "show", "start", "stop", "take", "try", "type", "update", "use",
    "wait", "write",
)
_COMMON_ADVERBS = frozenset({
    "now", "always", "never", "often", "again", "soon", "today", "still",
    "already", "first", "next", "last", "too", "very", "more", "most",
    "less", "least", "well",
})


@dataclass
class Finding:
    rule: str
    line: int
    message: str
    suggestion: str | None = None


@dataclass
class LintResult:
    score: float  # percent of sentences that pass all rules (0–100)
    sentence_count: int
    passing_sentences: int
    findings: list[Finding] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "sentence_count": self.sentence_count,
            "passing_sentences": self.passing_sentences,
            "findings": [
                {
                    "rule": f.rule,
                    "line": f.line,
                    "message": f.message,
                    **({"suggestion": f.suggestion} if f.suggestion else {}),
                }
                for f in self.findings
            ],
            "skipped": self.skipped,
        }


def split_sentences(text: str) -> list[str]:
    return [s for s, _ in _sentences(text)]


def _sentences(text: str) -> list[tuple[str, bool]]:
    """Join wrapped lines of a paragraph, then split on .!?.

    A blank line, list item, "===" / "---" line (setext underline or rule),
    admonition marker ("[!NOTE]") or fenced code block (a placeholder line
    followed by a blank line) starts a new group, so a setext title does not
    join the text after it. An ATX heading or table row is a group of its own.
    Heading and list markers ("#", "-", "1.") are removed, so they are not
    sentences. Lines are read without their blockquote markers (">").

    Pieces with no words outside protected placeholders are not sentences.
    Returns (sentence, prose) pairs; table-row and list-item sentences are not prose.
    """
    lines = [unquote(raw).strip() for raw in text.splitlines()]
    current: list[str] = []
    groups = [(current, True)]
    for i, line in enumerate(lines):
        heading = HEADING.match(line)
        item = LIST_ITEM.match(line)
        alone = heading is not None or line.startswith("|")
        block = UNDERLINE.fullmatch(line) or ADMONITION.fullmatch(line) or not PLACEHOLDER.sub("", line).strip() and (
            not line or i + 1 == len(lines) or not lines[i + 1]
        )
        if block or alone or item:
            if alone:
                groups.append(([line[heading.end():] if heading else line], heading is not None))
            current = []
            groups.append((current, item is None))
        if block or alone:
            continue
        current.append(line[item.end():] if item else line)
    out: list[tuple[str, bool]] = []
    for group, prose in groups:
        parts = _SENTENCE_SPLIT.split(" ".join(group))
        out.extend(
            (p.strip(), prose) for p in parts if _WORD.search(PLACEHOLDER.sub(" ", p))
        )
    return out


def split_paragraphs(text: str) -> list[str]:
    blocks = re.split(r"\n[\s>]*\n", text.strip())
    return [b.strip() for b in blocks if b.strip()]


def word_count(sentence: str) -> int:
    return len(_WORD.findall(sentence))


def _line_of(text: str, snippet: str) -> int:
    """1-based line number of the first occurrence of snippet; it may wrap across
    lines and blockquote markers."""
    found = re.search(r"[\s>]+".join(map(re.escape, snippet.split())), text)
    if found is None:
        return 1
    return text[:found.start()].count("\n") + 1


def _verb_forms(words: Iterable[str]) -> set[str]:
    return {form for w in words for form in (w, w + "s", w + "es")}


_COMMON_NON_NOUNS = frozenset(
    _FUNCTION_WORDS | _COMMON_ADVERBS | _verb_forms(_COMMON_VERBS)
)


def _is_non_noun(token: str, non_nouns: frozenset[str]) -> bool:
    low = token.lower()
    return (
        token == "\x00"
        or token.isdigit()
        or low in non_nouns
        or (len(low) > 4 and low.endswith("ly"))
    )


def _noun_cluster_hits(
    sentence: str,
    *,
    expansions: list[re.Pattern[str]] | None = None,
    non_nouns: frozenset[str] = _COMMON_NON_NOUNS,
) -> list[str]:
    """Flag runs of 4+ adjacent words that are not function words, verbs or adverbs.

    Protected spans, acronym expansions ("X Y (XY)") and "(XY)" break a run.
    """
    masked = PLACEHOLDER.sub(_BREAK, sentence)
    for pattern in expansions or []:
        masked = pattern.sub(_BREAK, masked)
    masked = _PAREN_WORD.sub(_BREAK, masked)
    clusters: list[str] = []
    run: list[str] = []
    for tok in _CLUSTER_TOKEN.findall(masked):
        if _is_non_noun(tok, non_nouns):
            if len(run) > 3:
                clusters.append(" ".join(run))
            run = []
        else:
            run.append(tok)
    if len(run) > 3:
        clusters.append(" ".join(run))
    return clusters


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


def lint(
    text: str,
    *,
    mode: Mode = "descriptive",
    glossary: list[dict[str, Any]] | None = None,
) -> LintResult:
    """Run Phase-1 STE-oriented checks. Score = % sentences with zero findings.

    Protected spans should already be placeholders (see protect.protect); each one
    counts as one neutral word. The approved_vocabulary check runs only when the
    glossary has "approved" entries (a licensed list in glossary/local/).
    """
    max_words = 20 if mode == "procedure" else 25
    findings: list[Finding] = []
    entries = glossary or []
    banned = compile_rules(entries, KINDS_NOT_APPROVED)
    expansions = [
        word_pattern(e["replace"], False)
        for e in entries if e.get("kind") in KINDS_EXPAND
    ]
    non_nouns = _COMMON_NON_NOUNS | _verb_forms(
        w.lower() for e in entries if e.get("pos") in {"verb", "adverb"}
        for w in (e["term"], e["replace"]) if _WORD.fullmatch(w)
    )
    approved: set[str] | None = None
    skipped: list[str] = []
    if any(e.get("kind") == KIND_APPROVED for e in entries):
        approved = set().union(
            *(_words(e["replace"]) for e in entries if e.get("kind") != KIND_PROTECT)
        )
    else:
        skipped.append("approved_vocabulary")

    sentences = split_sentences(text)
    if not sentences:
        return LintResult(
            score=100.0, sentence_count=0, passing_sentences=0, skipped=skipped,
        )

    bad_sentences: set[int] = set()

    for si, sentence in enumerate(sentences):
        line = _line_of(text, sentence)
        words = word_count(sentence)
        if words > max_words:
            findings.append(Finding(
                rule="sentence_length",
                line=line,
                message=(
                    f"Sentence has {words} words "
                    f"(max {max_words} for {mode} text)"
                ),
            ))
            bad_sentences.add(si)

        # not-approved words: same patterns as the dictionary swaps
        claimed: list[tuple[int, int]] = []
        for entry, pattern in banned:
            for m in pattern.finditer(sentence):
                if any(m.start() < end and start < m.end() for start, end in claimed):
                    continue
                claimed.append(m.span())
                findings.append(Finding(
                    rule="not_approved",
                    line=line,
                    message=f"Not-approved word {m.group(0)!r}",
                    suggestion=entry["replace"],
                ))
                bad_sentences.add(si)

        if approved is not None:
            prose = PLACEHOLDER.sub(" ", sentence)
            unknown = dict.fromkeys(
                tok for tok in _WORD.findall(prose)
                if not tok.isdigit() and tok.lower() not in approved
            )
            for tok in unknown:
                findings.append(Finding(
                    rule="approved_vocabulary",
                    line=line,
                    message=f"Word {tok!r} is not in the approved vocabulary",
                ))
                bad_sentences.add(si)

        if _PASSIVE.search(sentence) or _PASSIVE_IRREGULAR.search(sentence):
            findings.append(Finding(
                rule="passive_voice",
                line=line,
                message="Possible passive voice",
                suggestion="Prefer active voice",
            ))
            bad_sentences.add(si)

        for cluster in _noun_cluster_hits(
            sentence, expansions=expansions, non_nouns=non_nouns,
        ):
            findings.append(Finding(
                rule="noun_cluster",
                line=line,
                message=f"Noun cluster longer than 3 words: {cluster!r}",
                suggestion="Split or rephrase the cluster",
            ))
            bad_sentences.add(si)

        for m in _ING_VERB.finditer(sentence):
            ing = m.group(1)
            if ing.lower() in _STOP_ING:
                continue
            findings.append(Finding(
                rule="ing_verb",
                line=line,
                message=f"-ing form used as verb: {ing!r}",
                suggestion="Prefer a simple verb form",
            ))
            bad_sentences.add(si)

    # Paragraph length (max 6 prose sentences) — attribute to first line of paragraph
    for para in split_paragraphs(text):
        para_sents = [s for s, prose in _sentences(para) if prose]
        if len(para_sents) > 6:
            line = _line_of(text, para)
            findings.append(Finding(
                rule="paragraph_length",
                line=line,
                message=f"Paragraph has {len(para_sents)} sentences (max 6)",
            ))
            # Mark all sentences in this paragraph as failing the paragraph rule
            for s in para_sents:
                try:
                    bad_sentences.add(sentences.index(s))
                except ValueError:
                    pass

    passing = len(sentences) - len(bad_sentences)
    score = 100.0 * passing / len(sentences)
    return LintResult(
        score=score,
        sentence_count=len(sentences),
        passing_sentences=passing,
        findings=findings,
        skipped=skipped,
    )


def format_text_report(result: LintResult) -> str:
    lines = [
        f"STE lint score: {result.score:.1f}% "
        f"({result.passing_sentences}/{result.sentence_count} sentences pass)",
    ]
    if "approved_vocabulary" in result.skipped:
        lines.append(
            "Skipped approved_vocabulary: no 'approved' entries in the glossary "
            "(add a licensed STE word list under glossary/local/)."
        )
    if not result.findings:
        lines.append("No findings.")
        return "\n".join(lines)
    lines.append("Findings:")
    for f in result.findings:
        sug = f" → {f.suggestion}" if f.suggestion else ""
        lines.append(f"  L{f.line} [{f.rule}] {f.message}{sug}")
    return "\n".join(lines)
