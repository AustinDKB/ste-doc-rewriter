"""Each Phase-1 lint rule."""

from ste_doc_rewriter.lint import lint, split_sentences


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
    result = lint("Please utilize the tool.", glossary=BANNED)
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


def test_identity_rows_are_not_flagged():
    glossary = [{"term": "feature", "replace": "feature", "kind": "prefer"}]
    result = lint("Enable the feature flag.", glossary=glossary)
    assert not [f for f in result.findings if f.rule == "not_approved"]


def test_not_approved_multi_word_and_dotted_terms():
    glossary = [
        {"term": "in order to", "replace": "to", "kind": "ste_swap"},
        {"term": "etc.", "replace": "and so on", "kind": "prefer", "case_sensitive": True},
        {"term": "allows you to", "replace": "you can", "kind": "avoid"},
    ]
    result = lint(
        "Do this in order to start. Collect logs, metrics, etc. "
        "The tool allows you to get logs.",
        glossary=glossary,
    )
    hits = [f.message for f in result.findings if f.rule == "not_approved"]
    assert hits == [
        "Not-approved word 'in order to'",
        "Not-approved word 'etc.'",
        "Not-approved word 'allows you to'",
    ]


def test_case_sensitive_not_approved():
    glossary = [{"term": "etc.", "replace": "and so on", "kind": "prefer", "case_sensitive": True}]
    result = lint("Use the ETC. tool.", glossary=glossary)
    assert not [f for f in result.findings if f.rule == "not_approved"]


def test_noun_cluster_skips_verbs_adverbs_and_acronyms():
    glossary = [
        {"term": "CI", "replace": "continuous integration (CI)", "kind": "acronym_expand", "case_sensitive": True},
        {"term": "CLI", "replace": "command-line interface (CLI)", "kind": "acronym_expand", "case_sensitive": True},
    ]
    for sentence in (
        "AWS help orchestrate workloads across an AZ.",
        "The CI pipeline currently allows you to get logs.",
        "Use the command-line interface (CLI) to start the deploy.",
        "The continuous integration (CI) pipeline now allows you to get logs.",
        "Restart failed pods immediately.",
    ):
        result = lint(sentence, glossary=glossary)
        assert not [f for f in result.findings if f.rule == "noun_cluster"], sentence


def test_placeholders_are_neutral_and_code_only_lines_are_not_sentences():
    text = "Run \x00P0\x00 with \x00P1\x00 and check \x00P2\x00 status now.\n\x00P3\x00\n\n\n"
    result = lint(text)
    assert result.sentence_count == 1
    assert result.findings == []


def test_approved_vocabulary_skipped_without_list():
    result = lint("Use the tool.")
    assert result.skipped == ["approved_vocabulary"]


def test_approved_vocabulary_flags_unknown_words():
    glossary = [
        {"term": w, "replace": w, "kind": "approved"}
        for w in ("use", "the", "tool")
    ]
    result = lint("Use the tool. Use the gizmo.", glossary=glossary)
    assert result.skipped == []
    hits = [f for f in result.findings if f.rule == "approved_vocabulary"]
    assert [f.message for f in hits] == ["Word 'gizmo' is not in the approved vocabulary"]
    assert result.score == 50.0


def test_nouns_inside_glossary_verb_phrases_still_count_as_nouns():
    glossary = [
        {"term": "containerize", "replace": "put in a container", "kind": "avoid", "pos": "verb"},
        {"term": "orchestrate", "replace": "control and coordinate", "kind": "ste_swap", "pos": "verb"},
    ]
    for sentence in (
        "Pull the container image registry mirror.",
        "Check the access control policy rule.",
    ):
        result = lint(sentence, glossary=glossary)
        assert [f for f in result.findings if f.rule == "noun_cluster"], sentence
    sentence = "Teams orchestrate workloads cluster nodes."
    assert [f for f in lint(sentence, glossary=[]).findings if f.rule == "noun_cluster"]
    result = lint(sentence, glossary=glossary)
    assert not [f for f in result.findings if f.rule == "noun_cluster"]


def test_list_markers_are_not_sentences():
    glossary = [{"term": "utilize", "replace": "use", "kind": "ste_swap"}]
    numbered = lint("1. Utilize the dashboard.\n2. Utilize the console.\n- Utilize the CLI.", glossary=glossary)
    assert numbered.sentence_count == 3
    assert numbered.score == 0.0


LONG_SENTENCE = (
    "When the operator deploys the new release to the production cluster, the controller "
    "checks every pod, restarts the failed ones, writes a report to the shared store and then "
    "sends a short message to the on-call engineer before the window closes tonight."
)


def test_wrapped_sentence_scores_like_one_line():
    words = LONG_SENTENCE.split()
    wrapped = " ".join(words[:12]) + "\n" + " ".join(words[12:24]) + "\n" + " ".join(words[24:])
    one_line = lint(LONG_SENTENCE)
    result = lint(wrapped)
    assert one_line.sentence_count == result.sentence_count == 1
    assert result.score == one_line.score == 0.0
    assert [f.rule for f in result.findings] == [f.rule for f in one_line.findings]
    assert "sentence_length" in [f.rule for f in result.findings]


def test_passive_split_over_line_break():
    result = lint("The new release was\ndeployed by the team.")
    assert any(f.rule == "passive_voice" for f in result.findings)


def test_heading_and_list_items_start_new_groups():
    result = lint("# Deploy the release\nUse the tool.\n1. Start the job and\n   check the status.\n2. Stop the job.")
    assert result.sentence_count == 4
    assert result.findings == []
    assert split_sentences("The fix shipped in\n2024. Then it broke.") == [
        "The fix shipped in 2024.", "Then it broke.",
    ]


def test_paragraph_length_counts_wrapped_sentences():
    four = "Use the tool to start\nthe job. Check the status\nafter the run. Keep the logs\nfor a week. Stop the job\nat the end."
    assert not [f for f in lint(four).findings if f.rule == "paragraph_length"]
    seven = "One. Two.\nThree. Four.\nFive. Six.\nSeven."
    hits = [f for f in lint(seven).findings if f.rule == "paragraph_length"]
    assert [f.message for f in hits] == ["Paragraph has 7 sentences (max 6)"]


def test_inline_code_and_issue_refs_do_not_split_wrapped_sentences():
    assert split_sentences("To install the tool, run\n\x00P0\x00\nfrom the repo root.") == [
        "To install the tool, run \x00P0\x00 from the repo root.",
    ]
    assert split_sentences("This was fixed in issue\n#123 when the team changed the build.") == [
        "This was fixed in issue #123 when the team changed the build.",
    ]
    assert split_sentences("Run this:\n\x00P0\x00\n\n\nThen stop.") == ["Run this:", "Then stop."]


def test_table_rows_and_front_matter_are_not_joined():
    text = (
        "---\ntitle: Ops guide for the platform team\nweight: 10\n---\n"
        "Set these keys.\n"
        "| Key | Default | Meaning |\n"
        "|---|---|---|\n"
        "| timeout | 30 | Wait time |\n"
        "| retries | 3 | Retry count |\n"
    )
    assert split_sentences(text) == [
        "Set these keys.",
        "| Key | Default | Meaning |",
        "| timeout | 30 | Wait time |",
        "| retries | 3 | Retry count |",
    ]
    assert not [f for f in lint(text).findings if f.rule == "sentence_length"]
