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


def test_preserves_case_of_match():
    entries = [
        {"term": "commence", "replace": "start", "kind": "ste_swap"},
        {"term": "prior to", "replace": "before", "kind": "ste_swap"},
    ]
    out, _ = apply_swaps("Commence the deploy. Prior to the run, commence it.", entries)
    assert out == "Start the deploy. Before the run, start it."


def test_dotted_term_keeps_sentence_end():
    entries = [
        {"term": "etc.", "replace": "and so on", "kind": "prefer", "case_sensitive": True},
        {"term": "e.g.", "replace": "for example", "kind": "prefer", "case_sensitive": True},
    ]
    out, _ = apply_swaps("Collect logs, metrics, etc. Then restart.\nUse tools, e.g. kubectl.", entries)
    assert out == "Collect logs, metrics, and so on. Then restart.\nUse tools, for example kubectl."


def test_acronym_expansion_is_first_use_only_and_idempotent():
    text = "Enable CI now. The CI job runs."
    once, applied = apply_swaps(text, ENTRIES)
    assert once == "Enable continuous integration (CI) now. The CI job runs."
    assert applied == ["CI→continuous integration (CI)"]
    twice, applied_again = apply_swaps(once, ENTRIES)
    assert twice == once
    assert applied_again == []


def test_avoid_kind_is_not_rewritten():
    entries = [{"term": "allows you to", "replace": "you can", "kind": "avoid"}]
    text = "The CI pipeline currently allows you to obtain logs."
    assert apply_swaps(text, entries) == (text, [])


def test_eg_ie_before_capital_do_not_gain_a_period():
    entries = [
        {"term": "e.g.", "replace": "for example", "kind": "prefer", "case_sensitive": True},
        {"term": "i.e.", "replace": "that is", "kind": "prefer", "case_sensitive": True},
    ]
    out, _ = apply_swaps("Use a managed cloud, e.g. Azure or GCP. Pick one, i.e. The one you own.", entries)
    assert out == "Use a managed cloud, for example Azure or GCP. Pick one, that is The one you own."


def test_etc_keeps_period_before_placeholder_and_after_paren():
    entries = [{"term": "etc.", "replace": "and so on", "kind": "prefer", "case_sensitive": True}]
    out, _ = apply_swaps("Collect logs, metrics, etc. \x00P0\x00 stores them.", entries)
    assert out == "Collect logs, metrics, and so on. \x00P0\x00 stores them."
    out, _ = apply_swaps("Collect (logs, metrics, etc.) Then restart.", entries)
    assert out == "Collect (logs, metrics, and so on.) Then restart."


def test_file_names_are_not_rewritten():
    entries = [
        {"term": "admin", "replace": "administrator", "kind": "prefer"},
        {"term": "API", "replace": "application programming interface (API)", "kind": "acronym_expand", "case_sensitive": True},
    ]
    text = "Copy admin.conf and edit API.md now."
    assert apply_swaps(text, entries) == (text, [])
    out, _ = apply_swaps("Ask the admin. Use the API.", entries)
    assert out == "Ask the administrator. Use the application programming interface (API)."
