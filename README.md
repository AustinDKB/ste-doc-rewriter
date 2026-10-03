# ste-doc-rewriter

Offload repetitive **ASD-STE100 + Google technical documentation style** rewrites from Cursor/Claude subscription tokens onto a small specialized model (**Qwen3.5-9B LoRA**) plus a **runtime dictionary** and **STE linter**.

This repo currently holds the **plan and planned spec**. Implementation comes next.

## Documents

| Doc | Purpose |
|---|---|
| [docs/PLAN_AND_SPEC.md](docs/PLAN_AND_SPEC.md) | Full plan, architecture, data recipe, training, CI offload, and planned technical spec |
| [schemas/glossary.schema.json](schemas/glossary.schema.json) | Planned JSON Schema for the hybrid glossary |

## One-line goal

Train once on ~10k messy→compliant pairs, ship LoRA + glossary + lint in CI, and keep subscription models for hard reasoning only.

## Status

- [x] Problem framed (quota offload, not dollar cost)
- [x] Dataset size target (~10k pairs, broad multi-domain)
- [x] Hybrid architecture (LoRA + dictionary + lint)
- [x] Source URL pack for dictionaries and messy inputs
- [ ] Harvest glossary entries
- [ ] Seed 500–1,000 gold pairs
- [ ] Expand to ~10k and train Qwen3.5-9B LoRA
- [ ] Wire CI rewrite hook

## License

MIT (see [LICENSE](LICENSE)). Dictionary sources retain their own licenses — harvest carefully.
