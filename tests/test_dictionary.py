"""Dictionary swap behavior."""

from ste_doc_rewriter.dictionary import apply_swaps
from ste_doc_rewriter.protect import protect, restore


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
    assert out == "Collect (logs, metrics, and so on). Then restart."


def test_file_names_are_not_rewritten():
    entries = [
        {"term": "admin", "replace": "administrator", "kind": "prefer"},
        {"term": "API", "replace": "application programming interface (API)", "kind": "acronym_expand", "case_sensitive": True},
    ]
    text = "Copy admin.conf and edit API.md now."
    assert apply_swaps(text, entries) == (text, [])
    out, _ = apply_swaps("Ask the admin. Use the API.", entries)
    assert out == "Ask the administrator. Use the application programming interface (API)."


def test_hard_wrapped_dotted_terms_do_not_end_the_sentence():
    entries = [
        {"term": "e.g.", "replace": "for example", "kind": "prefer", "case_sensitive": True},
        {"term": "i.e.", "replace": "that is", "kind": "prefer", "case_sensitive": True},
        {"term": "etc.", "replace": "and so on", "kind": "prefer", "case_sensitive": True},
    ]
    text = (
        "Use a managed cloud such as Azure, e.g.\nGCP or AWS, for the cluster.\n"
        "Read the docs, i.e.\nthe README, before you start.\n"
        "Collect logs, metrics, etc.\nand send them to the store.\n\n"
        "Collect traces, etc.\n\nNext paragraph, etc."
    )
    out, _ = apply_swaps(text, entries)
    assert out == (
        "Use a managed cloud such as Azure, for example\nGCP or AWS, for the cluster.\n"
        "Read the docs, that is\nthe README, before you start.\n"
        "Collect logs, metrics, and so on\nand send them to the store.\n\n"
        "Collect traces, and so on.\n\nNext paragraph, and so on."
    )


def test_first_use_expansion_capitalized_at_sentence_or_heading_start():
    api = [{"term": "API", "replace": "application programming interface (API)", "kind": "acronym_expand", "case_sensitive": True}]
    cases = {
        "API keys must rotate. Use the API.": "Application programming interface (API) keys must rotate. Use the API.",
        "# API guide": "# Application programming interface (API) guide",
        "- API keys rotate.": "- Application programming interface (API) keys rotate.",
        "Keys rotate. API calls fail.": "Keys rotate. Application programming interface (API) calls fail.",
        "Call the API now.": "Call the application programming interface (API) now.",
    }
    for text, expected in cases.items():
        out, _ = apply_swaps(text, api)
        assert out == expected, text
        assert apply_swaps(out, api) == (out, [])


def test_first_use_expansion_not_capitalized_on_wrapped_lines():
    api = [{"term": "API", "replace": "application programming interface (API)", "kind": "acronym_expand", "case_sensitive": True}]
    cases = {
        "The service calls the\nAPI over HTTPS.": "The service calls the\napplication programming interface (API) over HTTPS.",
        "- Run the job and send\n  API calls to the store.": "- Run the job and send\n  application programming interface (API) calls to the store.",
        "Rotate the keys.\nAPI calls fail.": "Rotate the keys.\nApplication programming interface (API) calls fail.",
        "# Guide\nAPI calls fail.": "# Guide\nApplication programming interface (API) calls fail.",
        "| Key | Value |\nAPI calls fail.": "| Key | Value |\nApplication programming interface (API) calls fail.",
        "Intro text\n\nAPI calls fail.": "Intro text\n\nApplication programming interface (API) calls fail.",
    }
    for text, expected in cases.items():
        out, _ = apply_swaps(text, api)
        assert out == expected, text


def test_etc_keeps_period_before_list_item_and_after_final_paren():
    entries = [{"term": "etc.", "replace": "and so on", "kind": "prefer", "case_sensitive": True}]
    out, _ = apply_swaps("- Collect logs, metrics, etc.\n- Send traces.\n1. Keep logs, etc.\n2. Stop.", entries)
    assert out == "- Collect logs, metrics, and so on.\n- Send traces.\n1. Keep logs, and so on.\n2. Stop."
    out, _ = apply_swaps("Collect all data (logs, metrics, etc.)", entries)
    assert out == "Collect all data (logs, metrics, and so on)."
    out, _ = apply_swaps("Collect (logs, etc.)\nand send them.", entries)
    assert out == "Collect (logs, and so on)\nand send them."


def test_first_use_expansion_capitalized_after_code_block_and_in_quote():
    api = [{"term": "API", "replace": "application programming interface (API)", "kind": "acronym_expand", "case_sensitive": True}]
    def swap(text: str) -> str:
        protected = protect(text)
        return restore(apply_swaps(protected.text, api)[0], protected.spans)

    assert swap("Run this:\n```\nmake build\n```\nAPI calls fail.") == (
        "Run this:\n```\nmake build\n```\nApplication programming interface (API) calls fail."
    )
    assert swap("> API keys rotate.") == "> Application programming interface (API) keys rotate."
    assert swap("Run `make build`.\nAPI calls fail.") == (
        "Run `make build`.\nApplication programming interface (API) calls fail."
    )


def test_first_use_expansion_not_capitalized_mid_sentence_wraps():
    api = [{"term": "API", "replace": "application programming interface (API)", "kind": "acronym_expand", "case_sensitive": True}]

    def swap(text: str) -> str:
        protected = protect(text)
        return restore(apply_swaps(protected.text, api)[0], protected.spans)

    for text in (
        "> The service calls the\n> API over HTTPS.",
        "> **Note:** each pod calls the\n> API at start.",
        "Run the job and\n`make build`\nAPI calls fail.",
        "This was fixed in issue\n#123 API calls.",
    ):
        assert "application programming interface (API)" in swap(text), text


def test_first_use_expansion_skips_front_matter_and_follows_setext_heading():
    api = [{"term": "API", "replace": "application programming interface (API)", "kind": "acronym_expand", "case_sensitive": True}]

    def swap(text: str) -> str:
        protected = protect(text)
        return restore(apply_swaps(protected.text, api)[0], protected.spans)

    assert swap("---\ntitle: API guide\n---\nThe API returns JSON.") == (
        "---\ntitle: API guide\n---\nThe application programming interface (API) returns JSON."
    )
    assert swap("Install\n=======\nAPI keys rotate.") == (
        "Install\n=======\nApplication programming interface (API) keys rotate."
    )
    assert swap("Open docs/README.md. API calls fail.") == (
        "Open docs/README.md. Application programming interface (API) calls fail."
    )


def test_etc_keeps_period_before_rule_heading_and_table_row():
    entries = [{"term": "etc.", "replace": "and so on", "kind": "prefer", "case_sensitive": True}]
    out, _ = apply_swaps("Collect logs, metrics, etc.\n---\nNext.", entries)
    assert out == "Collect logs, metrics, and so on.\n---\nNext."
    out, _ = apply_swaps("Collect logs, etc.\n# Next\nBody.", entries)
    assert out == "Collect logs, and so on.\n# Next\nBody."
    out, _ = apply_swaps("Collect logs, etc.\n| a | b |", entries)
    assert out == "Collect logs, and so on.\n| a | b |"
    out, _ = apply_swaps("> Collect logs, etc.\n> - Send traces.\n> Keep logs, etc.\n>\n> next.", entries)
    assert out == "> Collect logs, and so on.\n> - Send traces.\n> Keep logs, and so on.\n>\n> next."
    out, _ = apply_swaps("Collect logs, etc.\n#123 fixed it.", entries)
    assert out == "Collect logs, and so on\n#123 fixed it."
