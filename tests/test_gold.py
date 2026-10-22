"""Gold pairs (data/gold/*.jsonl): schema, protected spans, lint scores, review page."""

import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ste_doc_rewriter.gold import (
    DATASET_LICENSES,
    GOLD_DIR,
    PAIR_SCHEMA_PATH,
    bundled_entries,
    length_band,
    lint_score,
    missing_spans,
    protected_spans,
    read_ids,
    read_pairs,
)

ROOT = Path(__file__).resolve().parents[1]
PILOT = GOLD_DIR / "pilot.jsonl"
PAIRS = read_pairs(PILOT)
BATCHES = {path.name: read_pairs(path) for path in sorted(GOLD_DIR.glob("batch-*.jsonl"))}
ALL_PAIRS = PAIRS + [p for pairs in BATCHES.values() for p in pairs]
ENTRIES = bundled_entries()


def _ids(pairs):
    return [p["id"] for p in pairs]


def test_every_line_matches_schema():
    validator = Draft202012Validator(json.loads(PAIR_SCHEMA_PATH.read_text(encoding="utf-8")))
    errors = [f"{p['id']}: {e.message}" for p in ALL_PAIRS for e in validator.iter_errors(p)]
    assert errors == []


def test_pilot_mix():
    assert len(PAIRS) == 50
    assert len(set(_ids(PAIRS))) == 50
    assert Counter(length_band(p["input"]) for p in PAIRS) == {
        "sentence": 5,
        "paragraph": 25,
        "section": 10,
        "chunk": 10,
    }
    assert Counter(p["messiness"] for p in PAIRS) == {"ultra": 20, "mid": 20, "near": 10}
    assert all(p["source"]["dataset"] in DATASET_LICENSES for p in PAIRS)
    assert not any(p["qc"]["human_reviewed"] for p in PAIRS)


@pytest.mark.parametrize("name", BATCHES)
def test_batch_mix_and_meaning_check(name):
    pairs = BATCHES[name]
    assert len(pairs) == 50
    assert Counter(length_band(p["input"]) for p in pairs) == {
        "sentence": 5,
        "paragraph": 25,
        "section": 10,
        "chunk": 10,
    }
    assert Counter(p["messiness"] for p in pairs) == {"ultra": 20, "mid": 20, "near": 10}
    assert all(p["source"]["dataset"] in DATASET_LICENSES for p in pairs)
    assert not any(p["qc"]["human_reviewed"] for p in pairs)
    # A pair that changes the meaning of its input never enters the gold set.
    assert all(p["qc"]["meaning_ok"] is True and p["qc"]["meaning_note"] for p in pairs)


def test_ids_run_in_order_and_inputs_are_unique():
    assert _ids(ALL_PAIRS) == [f"pair_{n:06d}" for n in range(1, len(ALL_PAIRS) + 1)]
    assert len({p["input"] for p in ALL_PAIRS}) == len(ALL_PAIRS)


def test_no_hydraulic_leak_reports():
    assert [p["id"] for p in ALL_PAIRS if "hydraul" in (p["input"] + p["output"]).lower()] == []


@pytest.mark.parametrize("pair", ALL_PAIRS, ids=_ids(ALL_PAIRS))
def test_protected_spans_match_input_and_survive(pair):
    assert pair["protected_spans"] == protected_spans(pair["input"], ENTRIES)
    assert missing_spans(pair, ENTRIES) == []


@pytest.mark.parametrize("pair", ALL_PAIRS, ids=_ids(ALL_PAIRS))
def test_lint_score_recomputes(pair):
    score = lint_score(pair["output"], ENTRIES)
    assert pair["qc"]["ste_lint_score"] == score
    assert score >= 0.80


def test_strict_ste_field_and_lint_target():
    assert all(p["qc"]["ste_strict_unapproved"] == [] for p in ALL_PAIRS)
    scores = sorted(p["qc"]["ste_lint_score"] for p in ALL_PAIRS)
    assert scores[len(scores) // 2] >= 0.85


# data/gold/README.md names these as words that no ASD-STE100 rule 1.5 category covers.
NOT_COVERED = {"simple", "fear", "price"}


@pytest.mark.parametrize("pair", ALL_PAIRS, ids=_ids(ALL_PAIRS))
def test_technical_terms_skip_words_no_category_covers(pair):
    # A capitalized entry may stay only as a name that the input itself uses.
    terms = pair["qc"]["ste_technical_terms"]
    flagged = [t for t in terms if NOT_COVERED & {t.lower(), t.lower().removesuffix("s")}]
    assert [t for t in flagged if t.islower() or not re.search(rf"\b{re.escape(t)}\b", pair["input"])] == []


def test_id_lists_name_gold_pairs():
    spot = read_ids(GOLD_DIR / "spot_check.txt")
    hard = read_ids(GOLD_DIR / "hard_cases.txt")
    assert len(set(spot)) == len(spot) and set(spot) <= set(_ids(ALL_PAIRS))
    assert set(hard) <= set(_ids(ALL_PAIRS))
    pilot = set(_ids(PAIRS))
    assert len(pilot & set(spot)) == 8
    assert 10 <= len(pilot & set(hard)) <= 15
    # About 15% spot check (37 of 250) and 5 to 8 hard cases in each batch.
    for pairs in BATCHES.values():
        ids = set(_ids(pairs))
        assert len(ids & set(spot)) in (7, 8)
        assert 5 <= len(ids & set(hard)) <= 8


def _review_module():
    spec = importlib.util.spec_from_file_location("review_gold", ROOT / "scripts" / "review_gold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_page_renders_every_pair(tmp_path):
    out = tmp_path / "review.html"
    assert _review_module().main([str(PILOT), "-o", str(out)]) == 0
    page = out.read_text(encoding="utf-8")
    assert all(f'id="{pid}"' in page for pid in _ids(PAIRS))
    assert "<script src" not in page and "<link" not in page
    assert '<mark class="p">' in page and "<ins>" in page


def test_changed_words_mark_only_new_words():
    review = _review_module()
    after = "Each computer sent the packets."
    ranges = review.changed_ranges("The packets were forwarded.", after)
    assert [after[a:b] for a, b in ranges] == ["Each", "computer", "sent"]
