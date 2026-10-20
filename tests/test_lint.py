"""Each Phase-1 lint rule."""

from ste_doc_rewriter.lint import lint


BANNED = [{"term": "utilize", "replace": "use", "kind": "ste_swap"}]


def test_sentence_length_descriptive():
    words = " ".join(["word"] * 26)
    result = lint(f"{words}.", mode="descriptive")
    assert any(f.rule == "sentence_length" for f in result.findings)
    assert result.score < 100


def test_sentence_length_procedure():
    words = " ".join(["word"] * 21)
    result = lint(f"{words}.", mode="procedure")
    assert any(f.rule == "sentence_length" for f in result.findings)


def test_paragraph_length():
    text = "One. Two. Three. Four. Five. Six. Seven."
    result = lint(text)
    assert any(f.rule == "paragraph_length" for f in result.findings)


def test_not_approved():
    result = lint("Please utilize the tool.", not_approved=BANNED)
    hit = [f for f in result.findings if f.rule == "not_approved"]
    assert hit
    assert hit[0].suggestion == "use"


def test_passive_voice():
    result = lint("The file was written by the agent.")
    assert any(f.rule == "passive_voice" for f in result.findings)


def test_noun_cluster():
    result = lint("The system architecture design document overview helps.")
    assert any(f.rule == "noun_cluster" for f in result.findings)


def test_ing_verb():
    result = lint("The agent is writing the report now.")
    assert any(f.rule == "ing_verb" for f in result.findings)


def test_clean_scores_high():
    result = lint("Use the tool. Start the job.")
    assert result.score == 100.0
    assert result.findings == []
