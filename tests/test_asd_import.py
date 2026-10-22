"""Importer for a dictionary layout dump. The fixture words are invented."""

import json
from pathlib import Path

import pytest

from ste_doc_rewriter.asd_import import import_dictionary_text, write_overlay
from ste_doc_rewriter.cli import main
from ste_doc_rewriter.glossary import validate_glossary_dir

# Column positions match a layout dump: alternatives at 19, examples at 48.
FIXTURE = """\
                        Zorp Reference

Word               Approved meaning/
(part of speech)   ALTERNATIVES             STE EXAMPLE            Non-STE example
ZORB (v),          To do a made-up action   ZORB THE FLIM.
ZORBS,
ZORBED,
ZORBED
       No other verb
       forms.
FLIM (adj)         A made-up quality        USE A FLIM.
(FLIMMER,
FLIMMEST)
QUONK (v),         To quonk something       QUONK THE FLIM.
QUONK,
QUONKED
(also QUON, QUONT)
BLORT              For a short time         DO IT BLORT.
(adv)
MATTIX (or MATTOX) A made-up surface        APPLY MATTIX.
(adj)
GLORP (n)          A made-up part           GET A GLORP.
SKARCH (n)         A made-up tool           USE THE SKARCH.
WIDGY (n)          A made-up item           GET A WIDGY.
MOOSEL (n),        A made-up animal         FEED THE MOOSEL.
MEESEL
flim (n)           PLINTH (n)               GET A PLINTH.          Get a flim.
glorps (v)         ZORB (v)                 ZORB IT.               Glorps it.
plink (v)          ZORB (v)                 ZORB THE FLIM.         Plink the flim.
                   BRACK (v)                BRACK THE FLIM.        Plink it again.
snarp              PLINTH (n)               GET A PLINTH.          Get a snarp.
(n)
wibble (adv)       AT THE SAME TIME         DO THE TWO STEPS       Do the two steps
                                            AT THE SAME TIME.      wibble.
glip (from) (v)    ZORB (v)                 ZORB IT.               Glip it from the side.
noalt (n)          Use a different
                   construction.
re- (prefix)       In general, use
                   the other word.
wirex (v)          BRACK (v)                BRACK THE FLIM.        Wirex the flim.
                   (WITH A ZORB [TN])

Issue 9                                 Part 2 - Dictionary                        Page 2-1-Z1
2025-01-15
"""


def test_layout_import_keeps_spellings_and_replacements_only():
    rows, stats = import_dictionary_text(FIXTURE)
    by_key = {(row["term"], row["kind"], row["pos"]): row for row in rows}

    assert by_key[("zorb", "approved", "verb")]["replace"] == "zorb"
    assert ("zorbs", "approved", "verb") in by_key
    assert ("zorbed", "approved", "verb") in by_key
    assert by_key[("flim", "approved", "adjective")]["replace"] == "flim"
    assert ("flimmer", "approved", "adjective") in by_key
    assert ("flimmest", "approved", "adjective") in by_key
    assert ("quonk", "approved", "verb") in by_key
    assert ("quonked", "approved", "verb") in by_key
    assert ("quon", "approved", "verb") in by_key
    assert ("quont", "approved", "verb") in by_key
    assert ("blort", "approved", "adverb") in by_key
    assert ("mattix", "approved", "adjective") in by_key
    assert ("mattox", "approved", "adjective") in by_key

    assert by_key[("plink", "ste_swap", "verb")]["replace"] == "zorb"
    assert by_key[("snarp", "ste_swap", "noun")]["replace"] == "plinth"
    assert by_key[("wibble", "ste_swap", "adverb")]["replace"] == "at the same time"
    assert by_key[("glip from", "ste_swap", "verb")]["replace"] == "zorb"
    assert by_key[("wirex", "ste_swap", "verb")]["replace"] == "brack"

    blob = json.dumps(rows)
    assert "made-up" not in blob
    assert "WITH A ZORB" not in blob
    assert stats.skipped == {"no_alternative": 1, "prefix": 1}
    assert stats.approved_rows == sum(row["kind"] == "approved" for row in rows)
    assert stats.swap_rows == sum(row["kind"] == "ste_swap" for row in rows)
    assert all(row["source_url"] == "https://www.asd-ste100.org/" for row in rows)
    assert all(row["replace"] == row["term"] for row in rows if row["kind"] == "approved")


def test_second_alternative_is_kept():
    rows, _stats = import_dictionary_text(FIXTURE)
    swaps = [row["replace"] for row in rows if row["term"] == "plink"]
    assert swaps == ["brack", "zorb"]


def test_approved_nouns_get_regular_and_printed_plurals():
    rows, _stats = import_dictionary_text(FIXTURE)
    nouns = {row["term"] for row in rows if row["kind"] == "approved" and row["pos"] == "noun"}
    assert {"glorp", "glorps", "skarch", "skarches", "widgy", "widgies"} <= nouns
    assert {"moosel", "meesel", "moosels"} <= nouns
    verbs = {row["term"] for row in rows if row["kind"] == "approved" and row["pos"] == "verb"}
    assert "zorbs" in verbs and "zorbses" not in verbs


def test_no_swap_for_a_spelling_approved_in_another_part_of_speech():
    rows, _stats = import_dictionary_text(FIXTURE)
    swap_terms = {row["term"] for row in rows if row["kind"] == "ste_swap"}
    assert "flim" not in swap_terms
    assert "glorps" not in swap_terms
    assert {"plink", "snarp", "wibble", "glip from", "wirex"} <= swap_terms


@pytest.fixture
def glossary_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "glossary"
    monkeypatch.setattr("ste_doc_rewriter.cli.DEFAULT_GLOSSARY_DIR", root)
    return root


def test_cli_writes_schema_valid_overlay(tmp_path: Path, glossary_root: Path, capsys):
    src = tmp_path / "dict.txt"
    src.write_text(FIXTURE, encoding="utf-8")
    out = glossary_root / "local"
    with pytest.raises(SystemExit) as exc:
        main(["import-asd", str(src), "--out", str(out)])
    assert exc.value.code == 0
    assert validate_glossary_dir(out) == []
    text = capsys.readouterr().out
    assert "approved rows:" in text
    assert "swap rows:" in text
    assert "no_alternative: 1" in text
    assert "prefix: 1" in text
    written = json.loads((out / "asd-ste100.json").read_text(encoding="utf-8"))
    assert write_overlay(written, tmp_path / "again") == tmp_path / "again" / "asd-ste100.json"


def test_cli_defaults_to_glossary_local(tmp_path: Path, glossary_root: Path):
    src = tmp_path / "dict.txt"
    src.write_text(FIXTURE, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["import-asd", str(src)])
    assert exc.value.code == 0
    assert validate_glossary_dir(glossary_root / "local") == []
    assert (glossary_root / "local" / "asd-ste100.json").is_file()


@pytest.mark.parametrize("out", ["glossary", "glossary/local/..", "elsewhere"])
def test_cli_refuses_out_outside_glossary_local(
    tmp_path: Path, glossary_root: Path, capsys, out: str
):
    src = tmp_path / "dict.txt"
    src.write_text(FIXTURE, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["import-asd", str(src), "--out", str(tmp_path / out)])
    assert exc.value.code == 2
    assert "--out must be" in capsys.readouterr().err
    assert not list(tmp_path.rglob("asd-ste100.json"))


def test_pdf_input_runs_pdftotext(tmp_path: Path, glossary_root: Path, monkeypatch):
    pdf = tmp_path / "dict.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    seen: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        seen.append(cmd)

        class Proc:
            returncode = 0
            stdout = FIXTURE
            stderr = ""

        return Proc()

    monkeypatch.setattr("ste_doc_rewriter.asd_import.subprocess.run", fake_run)
    out = glossary_root / "local"
    with pytest.raises(SystemExit) as exc:
        main(["import-asd", str(pdf), "--out", str(out)])
    assert exc.value.code == 0
    assert seen == [["pdftotext", "-layout", str(pdf), "-"]]
    assert (out / "asd-ste100.json").is_file()
