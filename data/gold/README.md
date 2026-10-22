# Gold pairs

Messy technical text (input) and a strict ASD-STE100 rewrite in Google developer
documentation style (output). One JSON object per line, as in section 11.1 of
[PLAN_AND_SPEC.md](../../docs/PLAN_AND_SPEC.md); the schema is
[schemas/pair.schema.json](../../schemas/pair.schema.json).

| File | Content |
|---|---|
| `pilot.jsonl` | Phase 2 pilot: 50 pairs |
| `batch-NN.jsonl` | Batches of 50 pairs after the pilot (pair_000051 and later) |
| `spot_check.txt` | Ids for human review (15%: 8 in the pilot, 7 or 8 in each batch), hard cases first |
| `hard_cases.txt` | Hard cases (10–15% of each file): dense jargon, code, logs, tables, long incident reports |
| `ATTRIBUTION.md` | Source row, link, author and license of each input |

To read the pairs side by side, run `make review`. It writes one self-contained
page to `data/raw/review.html` (gitignored), with protected spans and changed
words marked, and filters for domain, messiness, length band and the spot check.

## Pilot mix

| Length band (input words) | Pairs | Messiness | Pairs | Domain | Pairs |
|---|---|---|---|---|---|
| sentence (15–35) | 5 | ultra | 20 | other | 13 |
| paragraph (80–180) | 25 | mid | 20 | devops | 10 |
| section (180–250) | 10 | near | 10 | swe | 9 |
| chunk (250–400) | 10 | | | design | 6 |
| | | | | data_science | 5 |
| | | | | quality | 4 |
| | | | | analytics | 3 |

Aviation reports and other non-software text use the domain `other`.

## Batch mix

Each batch has the pilot's length bands (5 sentence, 25 paragraph, 10 section,
10 chunk) and messiness (20 ultra, 20 mid, 10 near).

| File | Domains | Lint min / median | Spot check | Hard |
|---|---|---|---|---|
| `batch-01.jsonl` | swe 13, other 11, devops 10, design 7, data_science 6, quality 2, analytics 1 | 0.8667 / 1.0 | 8 | 8 |
| `batch-02.jsonl` | swe 18, devops 17, other 6, data_science 5, design 3, quality 1 | 0.8 / 1.0 | 8 | 8 |
| `batch-03.jsonl` | devops 15, swe 12, other 10, data_science 9, quality 2, design 2 | 0.8333 / 1.0 | 7 | 8 |

## How the outputs were written

- Every output was written by hand in a Claude Code session. No model API made
  or changed any output.
- Outputs keep every fact, API, identifier, number and claim of the input.
  Each protected span of the input (code, URLs, paths, flags, numbers with
  units, product names) is in the output unchanged.
- Vocabulary is strict ASD-STE100 (Issue 9): each word is an approved word in
  its approved meaning and part of speech, or a technical name or technical
  verb. Sentences are at most 20 words in procedures and 25 in descriptions,
  in the active voice, with one instruction for each sentence.
- Google style is used where it agrees with STE: second person, present tense,
  sentence-case headings, numbered steps and code font.
- `qc.ste_lint_score` is the repo lint score (`ste-rewrite lint`, as a fraction).
  Pilot: min 0.9565, median 1.0, max 1.0. The glossary rows marked
  `ste_approved` (for example approximately → about) do not lower the score.
- `qc.ste_strict_unapproved` lists the output words that are neither approved
  nor technical. It is empty for all pairs. `qc.ste_technical_terms` lists
  the words that are accepted as technical names or verbs, for review.
  A technical name is the name of a specific thing in the domain (a product,
  component, command, unit, standard, protocol, metric or role). Everyday
  words (for example "simple", "years" or "two") must be approved words.
  The batches use this rule; the pilot lists come from an earlier, less strict
  check.
- The batch lists come from a check against the ASD-STE100 overlay that
  `ste-rewrite import-asd` writes to the gitignored `glossary/local/`. The
  approved-vocabulary lint with that overlay also runs on each batch output:
  each word that it flags is in `qc.ste_technical_terms`. The dictionary is
  not in this repository, so the tests do not recompute these lists.
- `qc.meaning_ok` and `qc.meaning_note` record the meaning check of each batch
  pair: the note lists the facts kept and the text dropped (for example a
  greeting). A pair that changes the meaning or adds a fact fails, and it is
  rewritten before it enters a batch.
- `qc.human_reviewed` is `false` until a person reviews the pair.

## Inputs

`scripts/harvest_inputs.py` streams a seeded sample (seed 20261021) from each
dataset at a pinned revision. It never downloads a full dataset, and it writes
the candidate pool to `data/raw/candidates.jsonl` (gitignored). It drops each
row that has offensive words or personal data (an email, an @mention, a phone
number or an aircraft tail number). It does not edit the text of a row to
remove personal data.
`source.ref` is `<row id>@<dataset revision>`.

```bash
uv sync --extra dev --extra harvest
uv run python scripts/harvest_inputs.py
```

Pilot deviations from the planned source mix:

- `facebook/asset` is not used. Its card metadata says CC BY-SA 4.0, but its
  "Licensing Information" section says CC BY-NC 4.0.
- `stindardlogic/writing-quality-dpo-100k` has only 37 distinct rejected texts
  in the sample, so 12 of the mid pairs come from it, 3 from `grammarly/coedit`,
  and 5 are Stack Exchange and GitHub excerpts marked `mid`.
- `chaojiang06/wiki_auto` has a loading script only; the harvest reads the Hub's
  Parquet conversion (`refs/convert/parquet`).

## Licenses

Gold inputs keep the license of their source dataset. The MIT license of this
repository covers the code, not the gold text. An output is a rewrite of its
input, so use each pair (input and output) under the input's license.

| Dataset | License | Pairs | Attribution |
|---|---|---|---|
| [HuggingFaceH4/stack-exchange-preferences](https://huggingface.co/datasets/HuggingFaceH4/stack-exchange-preferences) | CC BY-SA 4.0 | 14 | Name the author and link the answer (see `ATTRIBUTION.md`); share-alike |
| [open-index/open-github-issues](https://huggingface.co/datasets/open-index/open-github-issues) | ODC-By 1.0 | 7 | Name the dataset; the GitHub Terms of Service apply to the issue text |
| [elihoole/asrs-aviation-reports](https://huggingface.co/datasets/elihoole/asrs-aviation-reports) | Apache-2.0 | 4 | Keep the license notice; NASA ASRS reports are U.S. government work |
| [stindardlogic/writing-quality-dpo-100k](https://huggingface.co/datasets/stindardlogic/writing-quality-dpo-100k) | Apache-2.0 | 12 | Keep the license notice |
| [grammarly/coedit](https://huggingface.co/datasets/grammarly/coedit) | Apache-2.0 | 3 | Keep the license notice |
| [chaojiang06/wiki_auto](https://huggingface.co/datasets/chaojiang06/wiki_auto) | CC BY-SA 3.0 | 10 | Credit Wikipedia contributors and link the source; share-alike |

CC BY-SA is share-alike: if you share an adaptation of those pairs, you must
share it under the same license.
