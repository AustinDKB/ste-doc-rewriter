"""Load and validate glossary JSON files against the entry schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

KINDS_SWAP = frozenset({"ste_swap", "prefer", "abbrev_expand", "acronym_expand"})
KIND_PROTECT = "protect"

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "glossary.schema.json"
DEFAULT_GLOSSARY_DIR = Path(__file__).resolve().parents[2] / "glossary"
LOCAL_OVERLAY = "local"  # gitignored; optional restricted STE import


def load_schema(schema_path: Path | None = None) -> dict[str, Any]:
    path = schema_path or SCHEMA_PATH
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_glossary_files(glossary_dir: Path) -> list[Path]:
    files: list[Path] = []
    if not glossary_dir.is_dir():
        return files
    for path in sorted(glossary_dir.rglob("*.json")):
        # Skip schema-shaped junk; only JSON arrays of entries
        files.append(path)
    return files


def load_entries(
    glossary_dir: Path | None = None,
    *,
    include_local: bool = True,
) -> list[dict[str, Any]]:
    root = glossary_dir or DEFAULT_GLOSSARY_DIR
    entries: list[dict[str, Any]] = []
    for path in iter_glossary_files(root):
        if not include_local and LOCAL_OVERLAY in path.parts:
            continue
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"{path}: glossary file must be a JSON array of entries")
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"{path}[{i}]: entry must be an object")
            entries.append(item)
    return entries


def validate_entries(
    entries: list[dict[str, Any]],
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return a list of human-readable validation errors (empty = ok)."""
    validator = Draft202012Validator(schema or load_schema())
    errors: list[str] = []
    for i, entry in enumerate(entries):
        for err in sorted(validator.iter_errors(entry), key=lambda e: e.path):
            loc = ".".join(str(p) for p in err.path) or "(root)"
            term = entry.get("term", "?")
            errors.append(f"[{i}] term={term!r} {loc}: {err.message}")
    return errors


def validate_glossary_dir(
    glossary_dir: Path | None = None,
    schema_path: Path | None = None,
) -> list[str]:
    root = glossary_dir or DEFAULT_GLOSSARY_DIR
    errors: list[str] = []
    schema = load_schema(schema_path)
    for path in iter_glossary_files(root):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            errors.append(f"{path}: must be a JSON array")
            continue
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                errors.append(f"{path}[{i}]: not an object")
                continue
            for err in sorted(
                Draft202012Validator(schema).iter_errors(item),
                key=lambda e: e.path,
            ):
                loc = ".".join(str(p) for p in err.path) or "(root)"
                errors.append(
                    f"{path.name}[{i}] term={item.get('term', '?')!r} {loc}: {err.message}"
                )
    return errors


def product_names(entries: list[dict[str, Any]]) -> list[str]:
    return [e["term"] for e in entries if e.get("kind") == KIND_PROTECT]


def swap_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entries if e.get("kind") in KINDS_SWAP]
