# STE Doc Rewriter — Plan & Planned Spec

**Repo:** `ste-doc-rewriter`  
**Date:** 2026-10-03  
**Status:** Phase 1 implemented (dictionary + protect + lint CLI; no model)  
**Owner intent:** Offload STE100 + Google style documentation rewrites from subscription LLM tokens onto a small specialist model + dictionary + linter.

---

## 1. Problem

Subscription models (Cursor / Claude-class) are used for:

1. Hard work — architecture, debugging, design judgment  
2. Mechanical work — rewrite docs toward ASD-STE100 + Google technical writing style, expand abbreviations/acronyms, keep technical meaning  

Task (2) is high-volume (CI / bulk corpus), checkable, and repetitive. Burning subscription quota on it reduces capacity for task (1).

**Goal:** Make STE/Google rewrite **infrastructure**, not a chat task.

---

## 2. Success criteria

| Metric | Target |
|---|---|
| STE lint pass on held-out docs | **≥ ~80%** |
| Concept / fact retention (APIs, numbers, claims) | **≥ ~95%** on spot-check |
| Domains covered | DevOps, Data Science, Software Engineering, Design, Data Analytics, Style/linters/quality (broad) |
| Inference home | Cloud/API (CI continuous); optional later CPU quantized |
| Subscription role after ship | Authoring, review, hard meaning — **never** bulk style rewrite |
| Train method | LoRA / QLoRA on **Qwen3.5-9B** (or closest hosted twin), not full FT |

---

## 3. Recommended solution (hybrid)

Pure fine-tuning will not memorize ASD-STE100 (~2,000 dictionary entries + ~53 rules) reliably. Use three layers:

```
raw text
  → protect code / API / flag / number spans
  → LoRA rewrite (sentence shape, Google clarity, concept retention)
  → dictionary expand / STE word↔phrase swap
  → STE + Google lint pass
  → optional second micro-rewrite only on flagged sentences
  → restore protected spans
```

| Layer | Job | Consistency |
|---|---|---|
| Dictionary / STE lexicon | Hard word → approved word or fixed 2–3 STE words; abbrev → full form | Near-100% when keyed |
| Acronym glossary | Domain-tagged expansions | High with disambiguation tags |
| LoRA model | Structure, voice, clarity, keep meaning | ~80% with good data |
| Post-lint | Score / fail CI | Catches misses |

**Programmatic conversion works** for vocabulary (`utilize` → `use`, one complicated word → a fixed STE phrase). It does **not** replace sentence rules (short sentences, active voice, one instruction per sentence) — that is the model + lint.

---

## 4. Model sweet spot

| Size | Fit |
|---|---|
| 3B–4B | Often too weak on multi-domain technical meaning — skip for v1 breadth |
| **Qwen3.5-9B** | **Pick this** — smart enough, cheap LoRA, fine for CI/API |
| 27B+ | Only if 9B fails the 80% bar after dictionary + lint |

CPU note: 9B quantized *can* run on CPU but will be slow. Day-to-day load is **cloud/API CI**, so size for that.

---

## 5. Dataset plan

### 5.1 Size tiers

| Tier | Paired samples | Expectation |
|---|---|---|
| MVP | 2,000–3,000 | Style starts to stick; STE often ~50–65% |
| **Sweet spot** | **8,000–12,000** | Realistic shot at ~80% with hybrid |
| Strong | 15,000–25,000 | Diminishing returns after ~20k if quality is high |

**Default: ~10,000 high-quality pairs.**

Each sample:

- **input:** normal / messy technical prose (acronym-heavy OK)  
- **output:** STE-leaning + Google-style rewrite, **same facts / APIs / numbers**

### 5.2 Manual gold length (recommended mix)

Write gold by hand mostly as **short paragraphs / short sections**, not one-liner chips and not whole chapters.

| Unit | Input length | Share of gold |
|---|---|---|
| Hard single sentence | 15–35 words | ~10% |
| Paragraph | **80–180 words** | ~50% |
| Short section | **180–250 words** (2–4 paras) | ~20% |
| Longer CI-realistic chunk | **250–400 words** | ~20% |

**Hand-write sweet spot: ~100–200 words per pair** (default ~120–180).

**Output sentence rules (STE-leaning):**

- Procedures: ~5–20 words/sentence (prefer under ~25)  
- Descriptions: up to ~20–25 words; split if longer  
- One main idea / one instruction per sentence  
- Paragraphs: usually 2–6 short sentences  

Cadence: ~5–15 min/pair → **500 gold ≈ focused week**; **1,000** if a stronger seed is wanted.

### 5.3 Messiness spectrum (inputs)

| Band | Share | Sources |
|---|---|---|
| Ultra messy | ~40% | Forums, bad READMEs, acronym soup |
| Little / mid messy | ~40% | Verbose LLM dumps, jargon-heavy but coherent docs |
| Near-compliant | ~20% | Clear prose that still fails STE word rules |

**There is no public STE parallel corpus.** Harvest messy **inputs**; manufacture compliant **targets** (cheap model + dictionary + lint). Do not treat HF “chosen/good” columns as STE truth.

### 5.4 Seed → expand recipe

1. **500–1,000** human gold pairs (subscription OK here — quality of examples only)  
2. Expand to **~10k off-subscription** with few-shot + cheap hosted model  
3. Dictionary pass on targets  
4. Auto-filter: protected-token drift, STE lint score, embedding/meaning similarity  
5. Human spot-check **~10–15%** (hard cases first)  
6. Hold out **800–1,000** pairs for eval  

Hard-case budget inside the set: **~20–30%** nested conditionals, API names, metrics, acronym soup.

---

## 6. Dictionary & term sources (harvest pack)

Prioritized for a **full multi-domain** glossary. Respect each source’s license when copying text.

### 6.1 STE / controlled English / style word choice

1. https://www.asd-ste100.org/ — ASD-STE100 home (rules + controlled vocabulary product)  
2. https://github.com/dfch/biz.dfch.AsdSte100Vocab — STE vocabulary tooling  
3. https://github.com/dfch/biz.dfch.AsdSte100Nlp — STE NLP helpers  
4. https://github.com/dfensgmbh/biz.dfch.AsdSte100Parser — STE parse / lint-oriented tooling  
5. https://developers.google.com/style — Google developer documentation style guide  
6. https://developers.google.com/style/word-list — Google word list (prefer/avoid)  
7. https://developers.google.com/style/abbreviations — Abbreviations / acronyms guidance  
8. https://www.plainlanguage.gov/guidelines/words/ — Plain language word guidance (US)

### 6.2 Domain glossaries (DevOps / cloud / security / SWE)

9. https://glossary.cncf.io/ — CNCF cloud-native glossary  
10. https://csrc.nist.gov/glossary — NIST glossary  
11. https://docs.aws.amazon.com/general/latest/gr/glos-chap.html — AWS glossary  
12. https://docs.redhat.com/en/glossary — Red Hat glossary  
13. https://learn.microsoft.com/en-us/dotnet/standard/glossary — .NET / Microsoft glossary patterns  

### 6.3 Data / analytics / design / quality

14. https://developers.google.com/machine-learning/glossary — ML glossary  
15. https://www.tableau.com/learn/articles/data-glossary — Analytics vocabulary (cross-check terms)  
16. https://www.nngroup.com/articles/ — NN/g UX writing concepts (design language; curate carefully)  
17. https://eslint.org/docs/latest/use/core-concepts/ — Linter / quality concepts  
18. https://semgrep.dev/docs/ — Static analysis / quality terminology  

**Dictionary size target:** ~1,500–5,000 domain entries + STE controlled vocab (separate). Update glossary without retraining.

---

## 7. Messy-input sources (Hugging Face & related)

### 7.1 Ultra messy

1. https://huggingface.co/datasets/marin-community/stackexchange-markdown  
2. https://huggingface.co/datasets/stanfordnlp/SHP-2 — prefer **worse** side as input  
3. https://huggingface.co/datasets/HuggingFaceH4/stack-exchange-preferences  
4. https://huggingface.co/datasets/bigcode/the-stack — filter Markdown / READMEs  
5. https://huggingface.co/datasets/HuggingFaceCode/stack-v3-train — stream Markdown docs  

### 7.2 Little / mid messy (LLM dumps, weak writing)

6. https://huggingface.co/datasets/stindardlogic/writing-quality-dpo-100k — use **rejected** side  
7. https://huggingface.co/datasets/RedMod/finetuning_rephrasing_data  
8. https://huggingface.co/datasets/Exgentic/agent-llm-traces-v2  
9. https://huggingface.co/datasets/GasaiAI/Chat-Agent-1M — filter technical topics  
10. https://huggingface.co/datasets/sayan-03/blogai-style-data — fluffy blog prose  

### 7.3 Simplification scaffolds (pairing patterns, not STE targets)

11. https://huggingface.co/datasets/facebook/asset  
12. https://huggingface.co/datasets/chaojiang06/wiki_auto  
13. https://huggingface.co/datasets/eilamc14/wikilarge-clean  
14. https://huggingface.co/datasets/MichaelR207/MultiSimV2  
15. https://huggingface.co/datasets/mjbommar/opengloss-v1.3-encyclopedia-variants  
16. https://github.com/martiansideofthemoon/style-transfer-paraphrase  

HF search keywords: `text simplification`, `style transfer`, `formality`, `writing quality dpo`, `stackexchange`. Prefer **rejected / complex / informal / source** columns as inputs.

---

## 8. Training plan (semi-quick)

| Item | Choice |
|---|---|
| Base | Qwen3.5-9B-Instruct (or closest hosted twin) |
| Method | LoRA / QLoRA |
| Epochs | 2–3 |
| Approx train tokens | ~10k × ~500 × 3 ≈ **15M** |
| Hosted train ballpark | Often ~$5–25 compute (data QC is the real effort) |
| Eval holdout | 800–1,000 pairs |

Instruction template (planned):

```text
Rewrite the following technical text for ASD-STE100 Simplified Technical English
and Google developer documentation style. Keep all technical meaning, APIs,
identifiers, numbers, and claims. Prefer short active sentences. Expand glossary
terms when the dictionary provides an expansion. Do not invent facts.
```

Ship together: **LoRA adapter + `glossary.json` + protect rules + linter config**.

---

## 9. Subscription offload / CI plan

### Hard boundary

| Small model + dict + lint | Subscription |
|---|---|
| Style / STE compliance | Ambiguous technical meaning |
| Acronym expansion via dictionary | New architecture / design |
| Bulk / CI rewrite | Hard debugging |
| Consistent word → phrase swaps | Deciding what docs should say |

### CI triggers (planned)

- PR opened/updated on `docs/**`, `*.md`, ADR paths  
- Nightly bulk corpus pass  
- `make ste-rewrite` / pre-merge check failing below STE lint threshold  

Subscription agents **read results and fix real content bugs**; they do not perform the rewrite.

### Retrain triggers

- Glossary/acronym changes → **update JSON only**  
- Sentence-shape / compliance drifts below ~80% → retrain LoRA  

---

## 10. Phased delivery plan

### Phase 0 — Boundary

Document: Cursor/subscription = authoring & review; specialist = STE/Google rewrite.

### Phase 1 — Dictionary first (no fine-tune)

- STE approved / not-approved lexicon  
- Domain glossary from sources in §6  
- Protect list: code, APIs, flags, numbers, product names  
- Programmatic swaps live before any LoRA  

### Phase 2 — Seed gold (500–1,000)

- Manual pairs at lengths in §5.2  
- Even domain mix; acronym-heavy examples included  

### Phase 3 — Expand to ~10k off-subscription

- Few-shot from gold  
- Dictionary + lint filters  
- Spot-check 10–15%  

### Phase 4 — Train once

- Qwen3.5-9B LoRA, 2–3 epochs  
- Holdout eval  

### Phase 5 — Inference hybrid

Pipeline in §3.

### Phase 6 — CI hook

PR + nightly + local make target.

### Phase 7 — Operate

Subscription for high-value only; glossary updates without retrain.

---

## 11. Planned technical spec

### 11.1 Pair record (JSONL)

Each training line:

```json
{
  "id": "pair_000123",
  "domain": "devops",
  "messiness": "ultra",
  "input": "Messy technical prose...",
  "output": "STE-leaning Google-style rewrite...",
  "protected_spans": [
    {"text": "kubectl apply -f", "kind": "cli"}
  ],
  "source": {
    "dataset": "stackexchange-markdown",
    "ref": "optional external id"
  },
  "qc": {
    "ste_lint_score": 0.91,
    "concept_check": "pass",
    "human_reviewed": false
  }
}
```

**Constraints:**

- `input` and `output` must preserve the same protected tokens (after restore)  
- `messiness` ∈ `ultra | mid | near`  
- `domain` ∈ `devops | data_science | swe | design | analytics | quality | other`  
- Gold set: `human_reviewed: true`  

### 11.2 Glossary record

See also [`schemas/glossary.schema.json`](../schemas/glossary.schema.json).

```json
{
  "term": "orchestrate",
  "replace": "control and coordinate",
  "kind": "ste_swap",
  "pos": "verb",
  "domains": ["devops"],
  "protect_if": ["proper_noun", "code_span"],
  "source_url": "https://example.com/glossary#orchestrate",
  "notes": "Use only as verb meaning coordinate systems"
}
```

Kinds:

| `kind` | Behavior |
|---|---|
| `ste_swap` | Disallowed / verbose → STE approved word or fixed phrase |
| `abbrev_expand` | Abbreviation → full words |
| `acronym_expand` | Acronym → full concept (domain-tagged) |
| `prefer` | Google-style preferred wording |
| `avoid` | Lint flags it with `replace` as the suggestion; rewrite leaves it (needs sentence context, for example `allows you to`) |
| `protect` | Never rewrite (product names, brands) |
| `approved` | Approved STE word (`replace` = `term`); turns on the approved-vocabulary lint check. Only in the gitignored `glossary/local/` overlay |

### 11.3 Protect rules (planned)

Protect before model/dictionary:

- Fenced code / inline code  
- CLI flags (`--foo`, `-f`)  
- Version numbers, URLs, file paths  
- Known API symbols from a project allowlist (optional)  
- Numbers tied to metrics when listed in protect spans  

Restore after lint.

### 11.4 Inference API (planned)

`POST /v1/rewrite`

```json
{
  "text": "...",
  "domain_hint": "devops",
  "expand_acronyms": true,
  "strict_ste": true
}
```

Response:

```json
{
  "text": "...",
  "ste_lint_score": 0.86,
  "expansions_applied": ["CI→continuous integration"],
  "warnings": []
}
```

### 11.5 Eval suite (planned)

| Check | Method | Gate |
|---|---|---|
| STE compliance | Rule / STE linter on holdout | ≥ 0.80 mean pass |
| Glossary coverage | Known acronyms expanded correctly | ≥ 0.90 when `expand_acronyms` |
| Concept fidelity | Human or LLM-judge vs input facts | ≥ 0.95 spot-check |
| Over-rewrite | Near-compliant band should change minimally | Qualitative + edit-distance band |

### 11.6 CI job sketch (planned)

```yaml
# conceptual — not wired yet
on:
  pull_request:
    paths: ["docs/**", "**/*.md"]
jobs:
  ste-rewrite:
    steps:
      - checkout
      - run protect → 9B LoRA → dictionary → lint
      - fail if ste_lint_score < 0.80 on changed docs
      - upload rewritten artifact / optional PR comment
```

### 11.7 Repo layout (Phase 1 + planned later)

```text
ste-doc-rewriter/
  README.md
  SOURCES.md                     # source licenses (ASD dict not redistributed)
  docs/PLAN_AND_SPEC.md          # this document
  schemas/glossary.schema.json
  pyproject.toml                 # ste-rewrite CLI entry point
  Makefile
  samples/                       # small docs for lint / rewrite checks
  data/                          # Phase 2+
    gold/                        # 500–1000 human pairs
    train.jsonl
    holdout.jsonl
  glossary/
    ste.json                     # plain-language / STE-aligned swaps (not ASD text)
    google_word_list.json
    protect.json
    domains/*.json
    local/                       # gitignored optional licensed STE overlay
  src/ste_doc_rewriter/
    protect.py
    dictionary.py
    lint.py
    glossary.py
    pipeline.py
    cli.py
  train/                         # Phase 4
    sft_config.yaml
    prepare_jsonl.py
  ci/                            # Phase 6
    ste-rewrite.yml
```

---

## 12. Out of scope (v1)

- Full ASD-STE100 certification / aerospace compliance claims  
- Training a 27B+ model  
- Running day-1 inference only on laptop CPU  
- Using subscription tokens to synthesize the full 10k corpus  
- Replacing human judgment on *what* the documentation should say  

---

## 13. Immediate next actions

1. Harvest STE + Google word list + CNCF/NIST/AWS into `glossary/` using the schema  
2. Write 50 pilot gold pairs (validate length mix and lint loop)  
3. Scale gold to 500–1,000  
4. Build protect → rewrite → dictionary → lint CLI  
5. Expand to ~10k; train Qwen3.5-9B LoRA; wire CI  

---

## 14. Decision log

| Decision | Choice | Why |
|---|---|---|
| Primary goal | Subscription quota offload | Mechanical rewrite should not consume frontier tokens |
| Architecture | Hybrid LoRA + dictionary + lint | STE vocab needs deterministic swaps |
| Base model | Qwen3.5-9B class | Sweet spot for broad tech + CI |
| Dataset size | ~10k pairs | Shot at ~80% with hybrid |
| Gold length | Mostly 100–200 words | Context without burnout |
| Messiness mix | 40/40/20 ultra/mid/near | Robustness across real inputs |
| Inference | Cloud/API CI first | Continuous / bulk load |
| Public repo name | `ste-doc-rewriter` | Clear product intent |
| Phase 1 package layout | `src/ste_doc_rewriter/` + `ste-rewrite` CLI (argparse) | Spec asked for a Python package + CLI; hatchling/uv is enough |
| STE dictionary in git | Starter plain-language / STE-aligned swaps only; full ASD dict via `glossary/local/` (gitignored) | Public repo must not redistribute copyrighted ASD dictionary text |
| Filler deletion (`please`, `simply`) | Not in Phase 1 glossary | Schema requires non-empty `replace`; empty delete would violate schema |
| Sentence length modes | `--mode descriptive` (25) / `procedure` (20) | Spec lists both limits; default descriptive |
| Lint score | Percent of sentences with zero findings | Matches “percent of sentences passing”; CI uses `--threshold` |
| Identity glossary rows | Allowed for domain coverage; dictionary and lint skip term==replace | Lets starter domain files record terms without no-op churn |
| Sentence splitting | Join wrapped lines inside a paragraph, then split on `.!?`; an ATX heading, list item, table row, `===` / `---` line (setext underline or rule) or fenced code block starts a new group (inline code on its own line does not); front matter is protected as one span; strip `#` / list markers at the start of a group | A hard-wrapped sentence must count as one sentence for `sentence_length`, passive and paragraph checks; headings still do not join the next line |
| Acronym expansion | Expand only the first unprotected hit per document; expand none when the text already has `(ACR)` | Google abbreviations guidance (first use); a second rewrite run changes nothing |
