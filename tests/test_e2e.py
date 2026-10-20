"""End-to-end protect → swap → lint on sample docs."""

from pathlib import Path

from ste_doc_rewriter.pipeline import lint_text, rewrite

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
GLOSSARY = ROOT / "glossary"


def test_rewrite_protects_code_and_swaps_words():
    text = (SAMPLES / "messy_ops.md").read_text(encoding="utf-8")
    result = rewrite(text, glossary_dir=GLOSSARY)
    assert "`kubectl apply -f deploy.yaml`" in result.text
    assert "--dry-run=client" in result.text
    assert "https://example.com/status" in result.text
    assert "10ms" in result.text
    assert "Kubernetes" in result.text
    assert "AWS" in result.text
    assert "utilize" not in result.text.lower()
    assert "use" in result.text.lower()
    assert result.expansions_applied
    assert result.lint.sentence_count > 0


def test_clean_sample_lints_well():
    text = (SAMPLES / "clean_short.md").read_text(encoding="utf-8")
    result = lint_text(text, glossary_dir=GLOSSARY)
    assert result.score >= 80


def test_lint_fail_sample_has_findings():
    text = (SAMPLES / "lint_fail.md").read_text(encoding="utf-8")
    result = lint_text(text, glossary_dir=GLOSSARY)
    rules = {f.rule for f in result.findings}
    assert "sentence_length" in rules or "noun_cluster" in rules
    assert "paragraph_length" in rules
    assert result.score < 80
