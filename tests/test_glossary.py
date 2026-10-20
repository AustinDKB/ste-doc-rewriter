"""Glossary schema validation."""

import json
from pathlib import Path

import pytest

from ste_doc_rewriter.glossary import (
    DEFAULT_GLOSSARY_DIR,
    iter_glossary_files,
    load_entries,
    validate_glossary_dir,
)


def test_bundled_glossary_validates():
    errors = validate_glossary_dir(DEFAULT_GLOSSARY_DIR)
    assert errors == [], errors


def test_entries_have_sources():
    entries = [
        entry
        for path in iter_glossary_files(DEFAULT_GLOSSARY_DIR)
        if path.relative_to(DEFAULT_GLOSSARY_DIR).parts[0] != "local"
        for entry in json.loads(path.read_text(encoding="utf-8"))
    ]
    assert len(entries) >= 40
    missing = [e["term"] for e in entries if not e.get("source_url")]
    assert missing == [], f"missing source_url: {missing}"


def test_invalid_entry_detected(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text('[{"term": "x", "kind": "ste_swap"}]', encoding="utf-8")
    errors = validate_glossary_dir(tmp_path)
    assert errors


def test_missing_dir_and_schema_raise(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_entries(tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        load_entries(tmp_path)
    (tmp_path / "ok.json").write_text("[]", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        validate_glossary_dir(tmp_path, schema_path=tmp_path / "missing.json")


def test_checkout_under_a_local_dir_still_loads(tmp_path: Path):
    root = tmp_path / "local" / "glossary"
    root.mkdir(parents=True)
    (root / "a.json").write_text(
        '[{"term": "utilize", "replace": "use", "kind": "ste_swap"}]', encoding="utf-8"
    )
    assert [e["term"] for e in load_entries(root)] == ["utilize"]
