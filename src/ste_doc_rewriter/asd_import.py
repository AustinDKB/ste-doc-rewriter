"""Import an ASD-STE100 Issue 9 dictionary layout into glossary overlay rows.

Reads a pdftotext -layout dump (or runs pdftotext on a PDF). Keeps the term,
its listed spellings, part of speech, and the replacement word. Definitions
and examples are not stored.
"""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

from ste_doc_rewriter.glossary import load_schema

POS_MAP = {
    "n": "noun",
    "v": "verb",
    "adj": "adjective",
    "adv": "adverb",
    "pron": "pronoun",
    "art": "article",
    "prep": "preposition",
    "conj": "conjunction",
}
POS_ALT = r"n|v|adj|adv|pron|art|prep|conj"
# POS paren is the first (n)/(v)/... tag. An earlier paren is a variant
# such as "(a few)" or "(or MATTE)", not the part of speech.
# One space inside the headword. A wider gap is the next column, so
# "according to       REFER (v)" is not one headword.
HEAD_RE = re.compile(
    rf"^(?P<raw>[A-Za-z][A-Za-z0-9'’./-]*"
    rf"(?:[ \t][A-Za-z0-9'’./-]+)*"
    rf"(?:[ \t]\((?!{POS_ALT}|prefix\))[^)]+\))?)"
    rf"[ \t]{{1,2}}\((?P<pos>{POS_ALT}|prefix)\)(?P<comma>,)?(?=[ \t]|$)"
)
POS_ONLY_RE = re.compile(rf"^\((?P<pos>{POS_ALT})\)$")
POS_INNER_RE = re.compile(
    rf"^\((?P<inner>[^)]+)\)[ \t]+\((?P<pos>{POS_ALT})\)$"
)
FORM_WORD = r"[A-Z][A-Z0-9'’/-]*"
FORM_RE = re.compile(
    rf"^{FORM_WORD}(?:[ \t]+{FORM_WORD})*"
    rf"(?:,[ \t]*{FORM_WORD}(?:[ \t]+{FORM_WORD})*)*,?$"
)
ALSO_RE = re.compile(rf"^\(also[ \t]+(?P<body>[A-Z][A-Z ,’'/-]+)\)[ \t]*$")
PAREN_FORM_RE = re.compile(rf"^\([A-Z][A-Z ,’'/-]*,?$|^{FORM_WORD}(?:[ \t]+{FORM_WORD})*\)[ \t]*$|^\([A-Z][A-Z ,’'/-]+\)$")
TOKEN_RE = re.compile(
    rf"\((?:TN|TV)\)"
    rf"|\((?:{POS_ALT})\)"
    rf"|\([A-Z][A-Z0-9'’/-]*\)"
    rf"|[A-Z][A-Z0-9'’/-]*"
    rf"|…+"
    rf"|\.\.\."
)
TECHNICAL_RE = re.compile(r"([A-Z][A-Z0-9'’/-]*)[ \t]*[(\[]T[NV][)\]]")
SOURCE = "https://www.asd-ste100.org/"


@dataclass
class Entry:
    term_raw: str
    pos: str
    approved: bool
    forms: list[str] = field(default_factory=list)
    alts: list[str] = field(default_factory=list)
    page: str = ""
    skip: str = ""


@dataclass
class Line:
    col1: str
    alt: str
    full: str
    page: str
    alt_col: int
    ste_col: int
    non_col: int


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("…", "...")
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _lower(text: str) -> str:
    return _norm(text).lower()


def _is_footer(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith(("Issue 9", "Page 2-", "2025-", "2024-")):
        return True
    if "Part 2" in s and "Dictionary" in s and ("Issue" in s or "Page" in s):
        return True
    return False


def _header(lines: list[str]) -> tuple[int, int, int, int] | None:
    for i, line in enumerate(lines[:10]):
        if line.strip().startswith("Word") and "Approved meaning" in line:
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            alt = line.find("Approved")
            ste = nxt.find("STE EXAMPLE")
            if ste < 0:
                ste = line.find("STE EXAMPLE")
            non = nxt.find("Non-STE")
            if non < 0:
                non = line.find("Non-STE")
            if alt > 0 and ste > alt:
                return i, alt, ste, non if non > ste else ste + 24
    return None


def _page_id(page: str) -> str:
    m = re.search(r"Page (2-1-\S+)", page)
    return m.group(1) if m else ""


def _bleed_trim(line: str, start: int, ste: int, non: int) -> str:
    if start >= len(line):
        return ""
    end = ste if ste > start else len(line)
    chunk = line[start:end]
    if non <= start or non >= len(line):
        return chunk.rstrip()
    nonste = line[non:].strip()
    words = re.findall(r"[A-Za-z0-9'’]+", nonste)
    if len(words) < 2:
        return chunk.rstrip()
    prefix = " ".join(w.upper() for w in words[:8])
    region = line[start:non]
    idx = region.upper().find(prefix)
    if idx > 0 and start + idx < ste:
        chunk = region[:idx]
    return chunk.rstrip()


def body_lines(text: str) -> list[Line]:
    out: list[Line] = []
    for page in text.split("\f"):
        if "Page 2-1-" not in page:
            continue
        lines = page.splitlines()
        header = _header(lines)
        if not header:
            continue
        idx, alt_col, ste_col, non_col = header
        pid = _page_id(page)
        for line in lines[idx + 2 :]:
            if _is_footer(line):
                break
            if "Simplified Technical English" in line:
                continue
            alt = _clean_alt(_bleed_trim(line, alt_col, ste_col, non_col))
            out.append(Line(
                line[:alt_col].rstrip(), alt, line, pid, alt_col, ste_col, non_col,
            ))
    return out


def _merge_wrapped_heads(lines: list[Line]) -> list[Line]:
    merged: list[Line] = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        c1 = cur.col1.strip()
        if (
            c1
            and not c1.startswith("(")
            and c1.count("(") > c1.count(")")
            and i + 1 < len(lines)
        ):
            nxt = lines[i + 1]
            raw = f"{c1} {nxt.col1.strip()}".strip()
            merged.append(Line(
                raw, cur.alt, cur.full, cur.page, cur.alt_col, cur.ste_col, cur.non_col,
            ))
            if nxt.alt.strip():
                merged.append(Line(
                    "", nxt.alt, nxt.full, nxt.page, nxt.alt_col, nxt.ste_col, nxt.non_col,
                ))
            i += 2
            continue
        merged.append(cur)
        i += 1
    return merged


def _clean_alt(alt: str) -> str:
    """Keep the left alternative cell. Indented or gapped text is the example."""
    if not alt.strip() or re.match(r"^[ \t]{3,}", alt):
        return ""
    return re.split(r"\s{2,}", alt.strip(), maxsplit=1)[0]


def _left_cell(text: str) -> str:
    return re.split(r"\s{2,}", text.strip(), maxsplit=1)[0].strip()


def _leading_form(text: str) -> str:
    left = _left_cell(text)
    if not FORM_RE.fullmatch(left):
        return ""
    if re.match(rf"^\((?:{POS_ALT}|prefix)\)", left):
        return ""
    return left


def _form_phrases(text: str, width: int) -> list[str]:
    body = re.sub(r"^\(also\s+", "", text.strip(), flags=re.I).strip("() ")
    phrases: list[str] = []
    for part in body.split(","):
        words = [w for w in part.strip().split() if re.fullmatch(r"[A-Z][A-Z0-9'’/-]*", w)]
        if not words:
            continue
        if width > 1 and len(words) % width == 0:
            for i in range(0, len(words), width):
                phrases.append(" ".join(words[i:i + width]))
        else:
            phrases.extend(words)
    return phrases


def _leading_head(text: str) -> str:
    """Word-column token(s) before a case change or a wide column gap."""
    text = text.strip()
    if not text:
        return ""
    if text[0].islower():
        m = re.match(
            r"^[a-z][a-z0-9'’./-]*(?:[ \t]+[a-z][a-z0-9'’./-]*)*(?:[ \t]+\([^)]+\))?",
            text,
        )
        return m.group(0).strip() if m else ""
    words: list[str] = []
    rest = text
    while rest:
        m = re.match(r"^([A-Z][A-Z0-9'’./-]*)", rest)
        if not m or not m.group(1):
            break
        after = rest[m.end():]
        if after[:1].islower():
            break
        words.append(m.group(1))
        if not after[:1].isspace():
            break
        nxt = after.lstrip(" \t")
        paren = re.match(r"^\([^)]+\)", nxt)
        if paren and not re.match(rf"^\((?:{POS_ALT}|prefix)\)", paren.group(0)):
            words.append(paren.group(0))
            break
        if not nxt[:1].isupper():
            break
        rest = nxt
    return " ".join(words).strip()


def _is_paren_form(col1: str) -> bool:
    return PAREN_FORM_RE.fullmatch(col1.strip()) is not None


def _terms_from_raw(raw: str) -> list[str]:
    raw = _norm(raw)
    m = re.fullmatch(r"(.+?)\s+\((.+)\)", raw)
    if not m:
        return [_lower(raw)]
    base, inner = m.group(1).strip(), m.group(2).strip()
    if inner.lower().startswith("or "):
        return [_lower(base), _lower(inner[3:])]
    if " " in inner or inner.lower().startswith(("a ", "an ")):
        return [_lower(inner)]
    if inner.lower() in {"from", "that"}:
        return [f"{_lower(base)} {_lower(inner)}"]
    return [_lower(base)]


def _plural(term: str) -> str:
    if not term[-1:].isalpha():
        return ""
    if re.search(r"(?:s|x|z|ch|sh)$", term):
        return term + "es"
    if re.search(r"[^aeiou]y$", term):
        return term[:-1] + "ies"
    return term + "s"


def _approved_spellings(raw: str, forms: list[str], pos: str) -> list[str]:
    terms = _terms_from_raw(raw)
    plurals = [_plural(t) for t in terms] if pos == "n" else []
    seen: list[str] = []
    for term in terms + [_lower(f) for f in forms] + plurals:
        if term and term not in seen:
            seen.append(term)
    return seen


def _tokens(chunk: str) -> list[str]:
    return TOKEN_RE.findall(chunk)


def _phrase(tokens: list[str]) -> str:
    words: list[str] = []
    for tok in tokens:
        if tok in {"(TN)", "(TV)"}:
            continue
        if re.fullmatch(r"\([A-Z][A-Z0-9'’/-]*\)", tok):
            words.append(tok[1:-1])
            continue
        if tok.startswith("("):
            continue
        words.append(tok)
    phrase = _lower(" ".join(words))
    phrase = phrase.replace("...", " ... ")
    phrase = re.sub(r"\s+", " ", phrase).strip(" .")
    phrase = re.sub(r"\s*\.\.\.\s*", " ... ", phrase).strip()
    return phrase


_CONTINUATORS = frozenset({
    "THE", "OF", "A", "AN", "TO", "AND", "OR", "THAN", "WITH", "FROM",
    "IN", "ON", "FOR", "…", "...",
})


def _strip_usage_notes(chunks: list[str]) -> list[str]:
    """Drop parenthetical method notes such as '(WITH A CLAMP [TN])'."""
    out: list[str] = []
    skipping = False
    for chunk in chunks:
        s = chunk.strip()
        if not s:
            if not skipping:
                out.append("")
            continue
        if not skipping and re.match(r"^\((?!TN\)|TV\))", s) and (
            "[TN]" in s or "[TV]" in s or re.match(r"^\((?:WITH|A|AN|FOR|ON|IN|BY)\b", s, re.I)
        ):
            if s.count("(") > s.count(")"):
                skipping = True
            continue
        if skipping:
            if s.count(")") >= s.count("("):
                skipping = False
            continue
        s = re.sub(r"\([^)]*\[(?:TN|TV)\][^)]*\)", " ", s)
        out.append(s)
    return out


def _alts_from_chunks(chunks: list[str]) -> list[str]:
    alts: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if not pending:
            return
        phrase = _phrase(pending)
        pending.clear()
        words = phrase.split()
        if (
            phrase
            and phrase not in alts
            and 1 <= len(words) <= (8 if "..." in phrase else 4)
            and re.search(r"[a-z]", phrase)
            and " tn" not in f" {phrase}"
            and " tv" not in f" {phrase}"
            and all(len(w) > 1 or w in {"a", "i", "..."} for w in words)
        ):
            alts.append(phrase)

    def _content_count(toks: list[str]) -> int:
        return sum(
            1 for t in toks
            if t not in {"(TN)", "(TV)", "…", "..."} and not t.startswith("(")
        )

    def continues(toks: list[str]) -> bool:
        if not pending:
            return True
        has_pos = any(re.fullmatch(rf"\((?:{POS_ALT})\)", t) for t in toks)
        if pending[-1] in _CONTINUATORS or pending[-1] in {"(TN)", "(TV)", "…", "..."}:
            return not has_pos
        # A one-word alternative can wrap ("INCORRECTLY" / "ADJUSTED").
        return _content_count(pending) < 2 and not has_pos

    cleaned = _strip_usage_notes(chunks)
    for idx, chunk in enumerate(cleaned):
        s = chunk.strip()
        nxt = cleaned[idx + 1].strip() if idx + 1 < len(cleaned) else ""
        # "(adv)" on the next line closes a one-word alternative. Extra caps
        # on this line are the example column running into the cell.
        if (
            re.fullmatch(rf"\((?:{POS_ALT})\)", nxt)
            and " " in s
            and not re.search(rf"\((?:{POS_ALT}|TN|TV)\)", s)
        ):
            s = s.split()[0]
        if not s:
            flush()
            continue
        outside = re.sub(r"\([^)]*\)", "", s)
        if re.search(r"[a-z]", outside):
            flush()
            continue
        toks = _tokens(s)
        if not toks:
            flush()
            continue
        # Caps after a part-of-speech tag on this line are example overflow.
        groups: list[list[str]] = [[]]
        for tok in toks:
            if re.fullmatch(rf"\((?:{POS_ALT})\)", tok):
                groups[-1].append(tok)
                groups.append([])
            else:
                groups[-1].append(tok)
        if len(groups) > 1 and groups[-1] and not any(
            re.fullmatch(rf"\((?:{POS_ALT})\)", t) for t in groups[-1]
        ):
            groups.pop()
        for group in groups:
            if not group:
                continue
            if pending and not continues(group):
                flush()
            for tok in group:
                if re.fullmatch(rf"\((?:{POS_ALT})\)", tok):
                    flush()
                else:
                    pending.append(tok)
        # A line that ends in (TN) or (TV) closes the alternative.
        if toks[-1] in {"(TN)", "(TV)"}:
            flush()
    flush()
    return alts


def parse_entries(lines: list[Line]) -> tuple[list[Entry], list[tuple[str, str]]]:
    lines = _merge_wrapped_heads(lines)
    entries: list[Entry] = []
    skipped: list[tuple[str, str]] = []
    current: Entry | None = None
    forms_open = False
    paren_open = False
    alt_chunks: list[str] = []

    def close() -> None:
        nonlocal current, forms_open, paren_open, alt_chunks
        if current is None:
            return
        if current.pos == "prefix":
            current.skip = "prefix"
            skipped.append((current.term_raw, "prefix"))
        elif not current.approved:
            current.alts = _alts_from_chunks(alt_chunks)
            if not current.alts:
                current.skip = "no_alternative"
                skipped.append((current.term_raw, "no_alternative"))
        entries.append(current)
        current = None
        forms_open = False
        paren_open = False
        alt_chunks = []

    def start(raw: str, pos: str, comma: bool, alt: str, page: str) -> None:
        nonlocal current, forms_open, paren_open, alt_chunks
        close()
        letters = re.sub(r"\([^)]*\)", "", raw)
        letters = re.sub(r"[^A-Za-z]", "", letters)
        approved = letters.isupper() and pos != "prefix"
        current = Entry(raw, pos, approved, page=page)
        if approved:
            forms_open = comma
        alt_chunks = [alt] if alt.strip() else []
        paren_open = False

    i = 0
    while i < len(lines):
        line = lines[i]
        c1 = line.col1.strip()
        # column-0 head with pos on this line
        if line.full[:1].isalpha() and (m := HEAD_RE.match(line.full)):
            alt = line.alt
            if m.end() > line.alt_col:
                alt = _bleed_trim(line.full, m.end(), line.ste_col, line.non_col)
            start(m.group("raw"), m.group("pos"), bool(m.group("comma")), alt, line.page)
            i += 1
            continue
        nxt_is_pos = False
        if c1 and i + 1 < len(lines):
            j = i + 1
            while j < len(lines) and not lines[j].col1.strip():
                j += 1
            if j < len(lines) and (
                POS_ONLY_RE.fullmatch(lines[j].col1.strip())
                or POS_INNER_RE.fullmatch(lines[j].col1.strip())
            ):
                nxt_is_pos = True
        left_cell = _left_cell(line.full)
        form = _leading_form(line.full) if current and current.approved else ""
        if (
            current
            and current.approved
            and not nxt_is_pos
            and form
            and not line.full[:1].isspace()
            and (forms_open or paren_open)
        ):
            width = _head_width(current.term_raw)
            current.forms.extend(_form_phrases(form, width))
            if form.endswith(","):
                forms_open = True
            else:
                forms_open = False
                paren_open = False
            i += 1
            continue
        if (
            current
            and current.approved
            and not nxt_is_pos
            and not line.full[:1].isspace()
            and (ALSO_RE.fullmatch(left_cell) or _is_paren_form(left_cell))
        ):
            width = _head_width(current.term_raw)
            current.forms.extend(_form_phrases(left_cell, width))
            if left_cell.endswith(",") or ("(" in left_cell and ")" not in left_cell):
                forms_open = True
                paren_open = "(" in left_cell and ")" not in left_cell
            else:
                forms_open = False
                paren_open = False
            i += 1
            continue
        # bare headword, pos on the next non-empty col1
        lead = _leading_head(c1)
        if lead and not lead.lower().startswith("no other") and lead != "forms.":
            j = i + 1
            while j < len(lines) and not lines[j].col1.strip():
                j += 1
            if j < len(lines):
                nxt = lines[j].col1.strip()
                pm = POS_ONLY_RE.fullmatch(nxt) or POS_INNER_RE.fullmatch(nxt)
                if pm and (lead == c1.strip() or lead == _leading_head(line.full)):
                    raw = pm.group("inner") if pm.groupdict().get("inner") else lead
                    alt = line.alt
                    if not alt.strip():
                        alt = _bleed_trim(line.full, len(lead), line.ste_col, line.non_col)
                    start(raw, pm.group("pos"), False, alt, line.page)
                    if lines[j].alt.strip():
                        alt_chunks.append(lines[j].alt)
                    i = j + 1
                    continue
        if current is not None and line.alt.strip():
            alt_chunks.append(line.alt)
        i += 1
    close()
    return entries, skipped


def _head_width(raw: str) -> int:
    base = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    return max(1, len(base.split()))


def technical_words(text: str) -> set[str]:
    """Words the dictionary tags as a technical name or verb."""
    return {_lower(word) for word in TECHNICAL_RE.findall(text)}


def rows_for(entries: list[Entry], technical: set[str]) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple] = set()

    def add(term: str, replace: str, kind: str, pos: str) -> None:
        key = (term, replace, kind, pos)
        if key in seen:
            return
        seen.add(key)
        rows.append({
            "term": term,
            "replace": replace,
            "kind": kind,
            "pos": pos,
            "source_url": SOURCE,
        })

    live = [entry for entry in entries if not entry.skip]
    for entry in live:
        if entry.approved:
            for spelling in _approved_spellings(entry.term_raw, entry.forms, entry.pos):
                add(spelling, spelling, "approved", POS_MAP[entry.pos])
    approved = {row["term"] for row in rows}
    for entry in live:
        if entry.approved:
            continue
        for term in _terms_from_raw(entry.term_raw):
            # STE permits a technical name or verb, and nothing reads pos.
            if term in approved or term in technical:
                continue
            for alt in entry.alts:
                add(term, alt, "ste_swap", POS_MAP[entry.pos])
    rows.sort(key=lambda row: (row["kind"], row["term"], row["pos"]))
    return rows


@dataclass(frozen=True)
class ImportStats:
    approved_rows: int
    swap_rows: int
    skipped: dict[str, int]


OVERLAY_NAME = "asd-ste100.json"


def import_dictionary_text(text: str) -> tuple[list[dict], ImportStats]:
    """Parse a layout dump into schema-shaped rows and skip counts."""
    entries, skipped = parse_entries(body_lines(text))
    rows = rows_for(entries, technical_words(text))
    reasons = Counter(reason for _, reason in skipped)
    return rows, ImportStats(
        approved_rows=sum(row["kind"] == "approved" for row in rows),
        swap_rows=sum(row["kind"] == "ste_swap" for row in rows),
        skipped=dict(sorted(reasons.items())),
    )


def read_dictionary_source(path: Path) -> str:
    """Return layout text. PDFs are converted with pdftotext -layout."""
    if path.suffix.lower() == ".pdf":
        try:
            proc = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as err:
            raise ValueError(
                "pdftotext is required to read a PDF (poppler-utils)"
            ) from err
        if proc.returncode != 0:
            detail = proc.stderr.strip() or "pdftotext failed"
            raise ValueError(detail)
        return proc.stdout
    return path.read_text(encoding="utf-8")


def write_overlay(rows: list[dict], out_dir: Path) -> Path:
    """Write one schema-valid overlay file. Raises ValueError if a row is invalid
    or no row is approved."""
    if not any(row.get("kind") == "approved" for row in rows):
        raise ValueError("no approved rows parsed; overlay not written")
    validator = Draft202012Validator(load_schema())
    for i, row in enumerate(rows):
        errors = sorted(validator.iter_errors(row), key=lambda err: list(err.path))
        if errors:
            raise ValueError(f"row {i} term={row.get('term', '?')!r}: {errors[0].message}")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / OVERLAY_NAME
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return path
