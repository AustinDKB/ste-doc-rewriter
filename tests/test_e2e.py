"""End-to-end protect → swap → lint on sample docs."""

from pathlib import Path

import pytest

from ste_doc_rewriter.cli import main
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


def test_rewrite_leaves_subject_dependent_phrase_and_lint_flags_it():
    text = "The CI pipeline currently allows you to obtain logs."
    result = rewrite(text, glossary_dir=GLOSSARY)
    assert result.text == "The continuous integration (CI) pipeline now allows you to get logs."
    flagged = [f for f in result.lint.findings if f.rule == "not_approved"]
    assert [(f.message, f.suggestion) for f in flagged] == [
        ("Not-approved word 'allows you to'", "you can"),
    ]


def test_rewrite_is_idempotent_and_keeps_link_targets():
    text = (SAMPLES / "messy_ops.md").read_text(encoding="utf-8") + "\nRead the [API](API.md) guide.\n"
    once = rewrite(text, glossary_dir=GLOSSARY).text
    assert "[application programming interface (API)](API.md)" in once
    assert rewrite(once, glossary_dir=GLOSSARY).text == once


def test_lint_treats_protected_spans_as_neutral():
    text = (SAMPLES / "messy_ops.md").read_text(encoding="utf-8")
    result = lint_text(text, glossary_dir=GLOSSARY)
    assert not [f for f in result.findings if f.rule == "noun_cluster"]
    rewritten = rewrite(text, glossary_dir=GLOSSARY)
    assert not [f for f in rewritten.lint.findings if f.rule == "noun_cluster"]

    fenced = "Run the check.\n\n```\n" + "kubectl get pods -n kube-system\n" * 7 + "```\n"
    result = lint_text(fenced, glossary_dir=GLOSSARY)
    assert result.sentence_count == 1
    assert result.findings == []


def test_identity_rows_do_not_fail_lint():
    result = lint_text("Enable the feature flag. Use authentication.", glossary_dir=GLOSSARY)
    assert result.score == 100.0


@pytest.mark.parametrize("command", [["lint"], ["rewrite"], ["glossary", "validate"]])
def test_missing_glossary_dir_fails(tmp_path: Path, command: list[str], capsys):
    doc = tmp_path / "doc.md"
    doc.write_text("Use the tool.\n", encoding="utf-8")
    argv = [*command, "-g", str(tmp_path / "missing")]
    if command[0] != "glossary":
        argv.append(str(doc))
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code != 0
    assert "glossary directory not found" in capsys.readouterr().err
