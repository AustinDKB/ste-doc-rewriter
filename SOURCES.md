# Sources and licenses

This repository is public (MIT). Glossary entries store **facts** (term → preferred
wording) plus a `source_url`. They are **not** a copy of any copyrighted dictionary.

| Source | What we use | License / terms | Local file |
|---|---|---|---|
| [ASD-STE100](https://www.asd-ste100.org/) | Rule *ideas* only (sentence length, voice, noun clusters). **No** ASD dictionary text is redistributed. | Copyright ASD / ASD-STE100. Full approved/not-approved dictionary is proprietary. | Optional overlay: `glossary/local/*.json` (gitignored). Load with the CLI when present. |
| [PlainLanguage.gov word tips](https://www.plainlanguage.gov/guidelines/words/) | Public-domain-aligned simple-word preferences used in `glossary/ste.json`. | U.S. government work (public domain). | `glossary/ste.json` |
| [Google developer style word list](https://developers.google.com/style/word-list) | Prefer/avoid pairs restated as `prefer` / `ste_swap` entries. | Google developer docs; follow Google terms when redistributing. We store short prefer/avoid facts with attribution, not full guide text. | `glossary/google_word_list.json` |
| [CNCF Glossary](https://glossary.cncf.io/) | Starter acronym / term expansions. | Creative Commons (see CNCF glossary site). | `glossary/domains/cncf.json` |
| [NIST Glossary](https://csrc.nist.gov/glossary) | Starter security term expansions. | U.S. government work. | `glossary/domains/nist.json` |
| [AWS Glossary](https://docs.aws.amazon.com/general/latest/gr/glos-chap.html) | Starter service acronym expansions. | AWS docs terms of use; short expansion facts only. | `glossary/domains/aws.json` |
| [Red Hat Glossary](https://docs.redhat.com/en/glossary) | Starter DevOps terms. | Red Hat docs terms; short facts only. | `glossary/domains/redhat.json` |
| [Google ML Glossary](https://developers.google.com/machine-learning/glossary) | Starter ML acronym expansions. | Google developer docs terms. | `glossary/domains/ml.json` |
| Product / brand names | Never rewritten. | Facts of common product names. | `glossary/protect.json` |

## Restricted STE dictionary overlay

If you have a licensed ASD-STE100 dictionary export, place schema-valid JSON arrays under:

```text
glossary/local/
```

That directory is gitignored. The CLI loads it automatically when present. Do **not**
commit ASD dictionary text to this public repository.
