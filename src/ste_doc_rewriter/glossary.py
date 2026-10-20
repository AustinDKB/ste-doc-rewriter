"""Load and validate glossary JSON files against the entry schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

KINDS_SWAP = frozenset({"ste_swap", "prefer", "abbrev_expand", "acronym_expand"})
KINDS_EXPAND = frozenset({"abbrev_expand", "acronym_expand"})
# Lint flags these; "avoid" rows need sentence context, so rewrite leaves them.
KINDS_NOT_APPROVED = frozenset({"ste_swap", "prefer", "avoid"})
KIND_APPROVED = "approved"
KIND_PROTECT = "protect"

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "glossary.schema.json"
DEFAULT_GLOSSARY_DIR = Path(__file__).resolve().parents[2] / "glossary"


def load_schema(schema_path: Path | None = None) -> dict[str, Any]:
    path = schema_path or SCHEMA_PATH
    if not path.is_file():
        raise FileNotFoundError(
            f"glossary schema not found: {path} "
            "(Phase 1 runs from a repo checkout: use 'uv run' there, or pass the schema path)"
        )
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_glossary_files(glossary_dir: Path) -> list[Path]:
    if not glossary_dir.is_dir():
        raise FileNotFoundError(
            f"glossary directory not found: {glossary_dir} "
            "(Phase 1 runs from a repo checkout: use 'uv run' there, or pass -g/--glossary)"
        )
    files = sorted(glossary_dir.rglob("*.json"))
    if not files:
        raise FileNotFoundError(f"no glossary JSON files under {glossary_dir}")
    return files


def load_entries(glossary_dir: Path | None = None) -> list[dict[str, Any]]:
    root = glossary_dir or DEFAULT_GLOSSARY_DIR
    errors = validate_glossary_dir(root)
    if errors:
        raise ValueError(
            f"glossary failed schema validation ({len(errors)} error(s)): {errors[0]}; "
            "run 'ste-rewrite glossary validate' for all"
        )
    entries: list[dict[str, Any]] = []
    for path in iter_glossary_files(root):
        with path.open(encoding="utf-8") as f:
            entries.extend(json.load(f))
    return entries


def validate_glossary_dir(
    glossary_dir: Path | None = None,
    schema_path: Path | None = None,
) -> list[str]:
    """Return a list of human-readable validation errors (empty = ok)."""
    root = glossary_dir or DEFAULT_GLOSSARY_DIR
    errors: list[str] = []
    validator = Draft202012Validator(load_schema(schema_path))
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
            for err in sorted(validator.iter_errors(item), key=lambda e: e.path):
                loc = ".".join(str(p) for p in err.path) or "(root)"
                errors.append(
                    f"{path.name}[{i}] term={item.get('term', '?')!r} {loc}: {err.message}"
                )
    return errors


def product_names(entries: list[dict[str, Any]]) -> list[str]:
    return [e["term"] for e in entries if e.get("kind") == KIND_PROTECT]
