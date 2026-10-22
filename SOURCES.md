# Sources and licenses

This repository is public (MIT). Glossary entries store **facts** (term → preferred
wording) plus a `source_url`. They are **not** a copy of any copyrighted dictionary.

| Source | What we use | License / terms | Local file |
|---|---|---|---|
| [ASD-STE100](https://www.asd-ste100.org/) Issue 9 | Optional local overlay built by `ste-rewrite import-asd` from a copy of the Issue 9 PDF you already have. The committed glossary still has rule *ideas* only (sentence length, voice, noun clusters). **No** ASD dictionary text is committed. | Free of charge to all writers and users. Unauthorized distribution is strictly prohibited. Copyright ASD / ASD-STE100. | `glossary/local/*.json` (gitignored). The CLI loads it when present. |
| [dfch/biz.dfch.AsdSte100Vocab](https://github.com/dfch/biz.dfch.AsdSte100Vocab) | **Not harvested.** Checked 2026-10-20: code is AGPL-3.0 and the README states the ASD-STE100 vocabulary is copyright ASD, so it does not clearly allow redistribution in this MIT repo. | AGPL-3.0 + ASD copyright | — |
| [PlainLanguage.gov word tips](https://www.plainlanguage.gov/guidelines/words/) | Every row in `glossary/ste.json`. These are plain-language swaps in STE style, **not** ASD-STE100 dictionary entries; each row's `notes` says so. | U.S. government work (public domain). | `glossary/ste.json` |
| [Google developer style word list](https://developers.google.com/style/word-list) | Prefer/avoid pairs restated as `prefer` / `ste_swap` entries. | Google developer docs; follow Google terms when redistributing. We store short prefer/avoid facts with attribution, not full guide text. | `glossary/google_word_list.json` |
| [CNCF Glossary](https://glossary.cncf.io/) | Starter acronym / term expansions. | Creative Commons (see CNCF glossary site). | `glossary/domains/cncf.json` |
| [NIST Glossary](https://csrc.nist.gov/glossary) | Starter security term expansions. | U.S. government work. | `glossary/domains/nist.json` |
| [AWS Glossary](https://docs.aws.amazon.com/general/latest/gr/glos-chap.html) | Starter service acronym expansions. | AWS docs terms of use; short expansion facts only. | `glossary/domains/aws.json` |
| [Red Hat Glossary](https://docs.redhat.com/en/glossary) | Starter DevOps terms. | Red Hat docs terms; short facts only. | `glossary/domains/redhat.json` |
| [Google ML Glossary](https://developers.google.com/machine-learning/glossary) | Starter ML acronym expansions. | Google developer docs terms. | `glossary/domains/ml.json` |
| Product / brand names | Never rewritten. | Facts of common product names. | `glossary/protect.json` |

## Restricted STE dictionary overlay

Build the overlay from your own copy of the ASD-STE100 Issue 9 PDF. The importer
calls `pdftotext -layout` (poppler) for a PDF, or reads a layout dump directly:

```text
uv run ste-rewrite import-asd /path/to/ASD-STE100_ISSUE9.pdf
```

Issue 9 is free of charge to all writers and users. Unauthorized distribution is
strictly prohibited. The command writes schema-valid JSON to
`glossary/local/asd-ste100.json` (term, part of speech, and replacement only) and
that directory is gitignored. It refuses an `--out` directory outside `glossary/local/`.
Approved nouns also get their regular plural (`valve`, `valves`). A not-approved
word gets no swap row when the same spelling is approved in any part of speech.
The CLI loads it automatically when present. Do **not** commit ASD dictionary
text to this public repository.

Approved words use `"kind": "approved"` with `replace` equal to `term`, one row per
approved spelling (for example `start`, `starts`, `started`). When any `approved` row
is loaded, lint also flags words that are not approved words, glossary replacements,
or protected spans. Without them, the lint report says the approved-vocabulary check
was skipped.
