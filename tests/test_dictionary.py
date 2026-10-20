"""Dictionary swap behavior."""

from ste_doc_rewriter.dictionary import apply_swaps


ENTRIES = [
    {"term": "utilize", "replace": "use", "kind": "ste_swap"},
    {"term": "CI", "replace": "continuous integration (CI)", "kind": "acronym_expand", "case_sensitive": True},
    {"term": "in order to", "replace": "to", "kind": "prefer"},
    {"term": "feature", "replace": "feature", "kind": "prefer"},  # identity skip
]


def test_ste_swap_and_phrase():
    text = "Please utilize logs in order to debug."
    out, applied = apply_swaps(text, ENTRIES)
    assert "utilize" not in out.lower()
    assert "in order to" not in out.lower()
    assert "use" in out
    assert any("utilize→use" == a for a in applied)


def test_acronym_expand_case_sensitive():
    text = "Enable CI now. Do not expand ci lowercase."
    out, applied = apply_swaps(text, ENTRIES)
    assert "continuous integration (CI)" in out
    assert "ci lowercase" in out
    assert any(a.startswith("CI→") for a in applied)


def test_skips_identity():
    text = "A feature flag."
    out, applied = apply_swaps(text, ENTRIES)
    assert out == text
    assert not any(a.startswith("feature→") for a in applied)
