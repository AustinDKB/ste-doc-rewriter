# ste-doc-rewriter

Offload repetitive **ASD-STE100 + Google technical documentation style** rewrites from Cursor/Claude subscription tokens onto a small specialized model (**Qwen3.5-9B LoRA**) plus a **runtime dictionary** and **STE linter**.

**Phase 1 (this release):** protect → deterministic dictionary swaps → STE-oriented lint. No model, no training.

## Documents

| Doc | Purpose |
|---|---|
| [docs/PLAN_AND_SPEC.md](docs/PLAN_AND_SPEC.md) | Full plan, architecture, data recipe, training, CI offload, and technical spec |
| [schemas/glossary.schema.json](schemas/glossary.schema.json) | JSON Schema for glossary entries |
| [SOURCES.md](SOURCES.md) | Dictionary sources and licenses (ASD dictionary is **not** redistributed) |

## One-line goal

Train once on ~10k messy→compliant pairs, ship LoRA + glossary + lint in CI, and keep subscription models for hard reasoning only. Phase 1 ships the dictionary + protect + lint CLI first.

## Status

- [x] Problem framed (quota offload, not dollar cost)
- [x] Dataset size target (~10k pairs, broad multi-domain)
- [x] Hybrid architecture (LoRA + dictionary + lint)
- [x] Source URL pack for dictionaries and messy inputs
- [x] Harvest glossary entries (starter STE-aligned + Google + CNCF/NIST/AWS/…)
- [x] Protect → rewrite → dictionary → lint CLI
- [ ] Seed 500–1,000 gold pairs
- [ ] Expand to ~10k and train Qwen3.5-9B LoRA
- [ ] Wire CI rewrite hook

## Install

```bash
uv sync --extra dev
# or: make install
```

Phase 1 runs from a repo checkout only (`uv sync` / `uv run`, or the `make` targets). The CLI reads `glossary/` and `schemas/` from the checkout; a built wheel does not include them. Packaging them is Phase 6 (CI hook) work.

## Usage

```bash
# Validate glossary against schemas/glossary.schema.json
uv run ste-rewrite glossary validate
# make lint-glossary

# Lint a file (text report). Exit 1 if score < threshold (for CI later).
uv run ste-rewrite lint samples/messy_ops.md
uv run ste-rewrite lint --format json --threshold 80 samples/clean_short.md

# Procedure mode: max 20 words/sentence (descriptive default: 25)
uv run ste-rewrite lint --mode procedure path/to/doc.md

# Protect → dictionary swaps → restore; lint report on stderr
uv run ste-rewrite rewrite samples/messy_ops.md
uv run ste-rewrite rewrite samples/messy_ops.md -o /tmp/out.md --report /tmp/report.json

# Optional ASD-STE100 Issue 9 overlay (gitignored; do not commit the dictionary):
#   uv run ste-rewrite import-asd ISSUE9.pdf --out glossary/local/
#   glossary/local/*.json  ("approved" rows turn on the approved-vocabulary check)
```

## What Phase 1 protects

YAML front matter, fenced/inline code, URLs, markdown link targets, file paths, CLI flags, numbers with units, and product names from `glossary/protect.json` (plus any `kind: protect` entries). Lint sees each protected span as one neutral word.

## Layout

```text
glossary/           # schema-valid entry arrays (+ optional local/ overlay)
src/ste_doc_rewriter/
samples/            # small docs for manual / e2e checks
tests/
```

## License

MIT (see [LICENSE](LICENSE)). Dictionary sources retain their own licenses — see [SOURCES.md](SOURCES.md).
