.PHONY: install test lint-glossary rewrite-sample ste-lint

install:
	uv sync --extra dev

test:
	uv run pytest

lint-glossary:
	uv run ste-rewrite glossary validate

ste-lint:
	uv run ste-rewrite lint --threshold 80 samples/messy_ops.md

rewrite-sample:
	uv run ste-rewrite rewrite samples/messy_ops.md -o /tmp/ste-rewrite-out.md --threshold 0
