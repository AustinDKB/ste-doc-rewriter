"""Glossary schema validation."""

from pathlib import Path

from ste_doc_rewriter.glossary import (
    DEFAULT_GLOSSARY_DIR,
    load_entries,
    validate_glossary_dir,
)


def test_bundled_glossary_validates():
    errors = validate_glossary_dir(DEFAULT_GLOSSARY_DIR)
    assert errors == [], errors


def test_entries_have_sources():
    entries = load_entries(DEFAULT_GLOSSARY_DIR, include_local=False)
    assert len(entries) >= 40
    missing = [e["term"] for e in entries if not e.get("source_url")]
    assert missing == [], f"missing source_url: {missing}"


def test_invalid_entry_detected(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text('[{"term": "x", "kind": "ste_swap"}]', encoding="utf-8")
    errors = validate_glossary_dir(tmp_path)
    assert errors
