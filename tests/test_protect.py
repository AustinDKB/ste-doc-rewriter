"""Protect / restore round-trips."""

from ste_doc_rewriter.protect import protect, restore


def test_code_url_flag_path_number_round_trip():
    text = (
        "See `inline` and:\n"
        "```\ncode block\n```\n"
        "Visit https://example.com/a and path docs/PLAN_AND_SPEC.md "
        "with --dry-run and -f plus 10ms and 2.5 GB."
    )
    result = protect(text, product_names=["Kubernetes"])
    assert "`inline`" not in result.text
    assert "https://example.com/a" not in result.text
    assert "--dry-run" not in result.text
    assert "10ms" not in result.text
    restored = restore(result.text, result.spans)
    assert restored == text


def test_product_names_unchanged():
    text = "Deploy on Kubernetes and Docker today."
    result = protect(text, product_names=["Kubernetes", "Docker"])
    restored = restore(result.text, result.spans)
    assert restored == text
    assert "Kubernetes" not in result.text
    assert "Docker" not in result.text
