"""CLI: lint, rewrite, glossary validate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ste_doc_rewriter.glossary import DEFAULT_GLOSSARY_DIR, validate_glossary_dir
from ste_doc_rewriter.lint import format_text_report
from ste_doc_rewriter.pipeline import lint_text, rewrite


def _read_input(path: str | None) -> str:
    if path is None or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def cmd_lint(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    result = lint_text(
        text,
        glossary_dir=Path(args.glossary) if args.glossary else None,
        mode=args.mode,
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_text_report(result))
    threshold = args.threshold
    if threshold is not None and result.score < threshold:
        return 1
    return 0


def cmd_rewrite(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    result = rewrite(
        text,
        glossary_dir=Path(args.glossary) if args.glossary else None,
        mode=args.mode,
        expand_acronyms=not args.no_expand,
    )
    if args.output:
        Path(args.output).write_text(result.text, encoding="utf-8")
    else:
        sys.stdout.write(result.text)
        if not result.text.endswith("\n"):
            sys.stdout.write("\n")

    report = {
        "expansions_applied": result.expansions_applied,
        "lint": result.lint.to_dict(),
    }
    if args.report:
        Path(args.report).write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    elif args.format == "json":
        # Full JSON payload to stderr so stdout stays the rewritten text
        print(json.dumps(report, indent=2), file=sys.stderr)
    else:
        print(format_text_report(result.lint), file=sys.stderr)
        if result.expansions_applied:
            print(
                "Swaps: " + ", ".join(result.expansions_applied),
                file=sys.stderr,
            )

    threshold = args.threshold
    if threshold is not None and result.lint.score < threshold:
        return 1
    return 0


def cmd_glossary_validate(args: argparse.Namespace) -> int:
    root = Path(args.glossary) if args.glossary else DEFAULT_GLOSSARY_DIR
    errors = validate_glossary_dir(root)
    if errors:
        print(f"Glossary validation failed ({len(errors)} error(s)):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    n_files = len(list(root.rglob("*.json"))) if root.is_dir() else 0
    print(f"OK: {n_files} glossary file(s) under {root}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ste-rewrite",
        description="Phase 1 STE protect → dictionary rewrite → lint",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "-g", "--glossary",
            help="Glossary directory (default: ./glossary)",
        )
        sp.add_argument(
            "--mode",
            choices=["descriptive", "procedure"],
            default="descriptive",
            help="Sentence length limit: descriptive=25, procedure=20",
        )
        sp.add_argument(
            "--threshold",
            type=float,
            default=None,
            help="Exit 1 if lint score (percent) is below this value",
        )
        sp.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Report format",
        )

    lint_p = sub.add_parser("lint", help="Lint text for STE-oriented rules")
    add_common(lint_p)
    lint_p.add_argument(
        "input", nargs="?", default="-",
        help="Input file (default: stdin)",
    )
    lint_p.set_defaults(func=cmd_lint)

    rw = sub.add_parser(
        "rewrite",
        help="Protect → dictionary swaps → restore; print lint report",
    )
    add_common(rw)
    rw.add_argument(
        "input", nargs="?", default="-",
        help="Input file (default: stdin)",
    )
    rw.add_argument("-o", "--output", help="Write rewritten text to file")
    rw.add_argument(
        "--report",
        help="Write JSON lint/swap report to file",
    )
    rw.add_argument(
        "--no-expand",
        action="store_true",
        help="Skip acronym/abbreviation expansion",
    )
    rw.set_defaults(func=cmd_rewrite)

    gv = sub.add_parser(
        "glossary",
        help="Glossary operations",
    )
    gv_sub = gv.add_subparsers(dest="glossary_command", required=True)
    gv_val = gv_sub.add_parser("validate", help="Validate glossary against schema")
    gv_val.add_argument(
        "-g", "--glossary",
        help="Glossary directory (default: ./glossary)",
    )
    gv_val.set_defaults(func=cmd_glossary_validate)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
