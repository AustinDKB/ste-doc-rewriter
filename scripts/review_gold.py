"""Render the gold pairs into one self-contained HTML page for review.

Each pair shows the input and the output side by side, with the protected spans
highlighted in both columns and the words that the output changed marked. Filters
select domain, messiness and length band; a toggle shows only the spot-check ids
(data/gold/spot_check.txt). The page has no external scripts, styles or fonts.

    uv run python scripts/review_gold.py          # or: make review
"""

from __future__ import annotations

import argparse
import difflib
import html
import json
import re
from pathlib import Path
from typing import Any

from ste_doc_rewriter.gold import BANDS, DATASET_LICENSES, GOLD_DIR, length_band, read_ids, read_pairs
from ste_doc_rewriter.lint import word_count

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "raw" / "review.html"
_TOKEN = re.compile(r"\S+")


def _key(token: str) -> str:
    return re.sub(r"\W+", "", token.lower())


def changed_ranges(before: str, after: str) -> list[tuple[int, int]]:
    """Character ranges of the words in after that are not matched in before."""
    old = [_key(m.group()) for m in _TOKEN.finditer(before)]
    new = list(_TOKEN.finditer(after))
    matcher = difflib.SequenceMatcher(None, old, [_key(m.group()) for m in new], autojunk=False)
    kept = {j for block in matcher.get_matching_blocks() for j in range(block.b, block.b + block.size)}
    return [(m.start(), m.end()) for j, m in enumerate(new) if j not in kept]


def span_ranges(text: str, spans: list[str]) -> list[tuple[int, int]]:
    out = []
    for span in spans:
        start = text.find(span)
        while start != -1:
            out.append((start, start + len(span)))
            start = text.find(span, start + len(span))
    return out


def marked(text: str, protected: list[tuple[int, int]], changed: list[tuple[int, int]]) -> str:
    """HTML for text with <mark class=p> on protected runs and <ins> on changed words."""
    flags = [0] * len(text)
    for bit, ranges in ((1, protected), (2, changed)):
        for start, end in ranges:
            for i in range(start, end):
                flags[i] |= bit
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and flags[j] == flags[i]:
            j += 1
        part = html.escape(text[i:j])
        if flags[i] & 2:
            part = f"<ins>{part}</ins>"
        if flags[i] & 1:
            part = f'<mark class="p">{part}</mark>'
        out.append(part)
        i = j
    return "".join(out)


def card(pair: dict[str, Any], spot: list[str], hard: set[str]) -> str:
    qc, source = pair["qc"], pair["source"]
    spans = [s["text"] for s in pair["protected_spans"]]
    band = length_band(pair["input"]) or "none"
    unapproved = qc.get("ste_strict_unapproved")
    technical = qc.get("ste_technical_terms", [])
    if unapproved is None:
        strict = '<span class="tag">strict STE: not checked</span>'
    elif unapproved:
        strict = f'<span class="tag bad">unapproved: {html.escape(", ".join(unapproved))}</span>'
    else:
        strict = '<span class="tag ok">unapproved: none</span>'
    tags = [
        f'<span class="tag">{pair["domain"]}</span>',
        f'<span class="tag">{pair["messiness"]}</span>',
        f'<span class="tag">{band}</span>',
        f'<span class="tag">lint {qc["ste_lint_score"]:.2f}</span>',
        strict,
    ]
    if pair["id"] in spot:
        tags.insert(0, f'<span class="tag spot">spot-check {spot.index(pair["id"]) + 1}</span>')
    if pair["id"] in hard:
        tags.insert(0, '<span class="tag hard">hard case</span>')
    license_ = DATASET_LICENSES.get(source["dataset"], "see SOURCES.md")
    tech = (
        f"<details><summary>Technical names and verbs ({len(technical)})</summary>"
        f"<p>{html.escape(', '.join(technical))}</p></details>"
        if technical
        else ""
    )
    return f"""
<section class="pair" data-domain="{pair['domain']}" data-messiness="{pair['messiness']}" data-band="{band}"
 data-spot="{int(pair['id'] in spot)}" id="{pair['id']}">
<h2>{pair['id']}</h2>
<p class="tags">{''.join(tags)}</p>
<p class="src">{html.escape(source['dataset'])} · {html.escape(source.get('ref', ''))} · {html.escape(license_)}</p>
<div class="cols">
<div><h3>Input <small>{word_count(pair['input'])} words</small></h3>
<pre>{marked(pair['input'], span_ranges(pair['input'], spans), [])}</pre></div>
<div><h3>Output <small>{word_count(pair['output'])} words</small></h3>
<pre>{marked(pair['output'], span_ranges(pair['output'], spans), changed_ranges(pair['input'], pair['output']))}</pre></div>
</div>
{tech}
</section>"""


def _options(name: str, values: list[str]) -> str:
    opts = "".join(f'<option value="{v}">{v}</option>' for v in values)
    return f'<label>{name} <select data-filter="{name}"><option value="">all</option>{opts}</select></label>'


STYLE = """
:root { --bg: #fff; --fg: #1d1d1f; --muted: #666; --line: #ddd; --card: #fafafa;
  --prot: #fff1b8; --ins: #d7f5dd; --bad: #fde2e1; --ok: #d7f5dd; --spot: #dbe8ff; }
@media (prefers-color-scheme: dark) { :root { --bg: #161618; --fg: #eee; --muted: #aaa;
  --line: #333; --card: #1f1f22; --prot: #5a4b00; --ins: #1e4d2b; --bad: #5c1f1c; --ok: #1e4d2b; --spot: #1f3560; } }
body { margin: 0 auto; max-width: 1400px; padding: 16px; background: var(--bg); color: var(--fg);
  font: 15px/1.5 system-ui, sans-serif; }
header { position: sticky; top: 0; background: var(--bg); padding: 8px 0; border-bottom: 1px solid var(--line); z-index: 1; }
header label { margin-right: 12px; white-space: nowrap; }
.pair { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 12px; margin: 16px 0; }
.pair h2 { margin: 0; font-size: 17px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 700px) { .cols { grid-template-columns: 1fr; } }
.cols > div { min-width: 0; }
h3 { margin: 8px 0 4px; font-size: 14px; } small, .src { color: var(--muted); font-size: 13px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; padding: 8px; border: 1px solid var(--line);
  border-radius: 4px; background: var(--bg); font: 13px/1.5 ui-monospace, monospace; }
mark.p { background: var(--prot); color: inherit; } ins { background: var(--ins); text-decoration: none; }
.tag { display: inline-block; border: 1px solid var(--line); border-radius: 10px; padding: 0 8px; margin: 2px 4px 2px 0; font-size: 12px; }
.tag.bad { background: var(--bad); } .tag.ok { background: var(--ok); } .tag.spot, .tag.hard { background: var(--spot); }
.legend mark, .legend ins { padding: 0 4px; }
"""

SCRIPT = """
const pairs = [...document.querySelectorAll('.pair')];
const controls = [...document.querySelectorAll('[data-filter]')];
function apply() {
  const want = Object.fromEntries(controls.map(c => [c.dataset.filter, c.type === 'checkbox' ? (c.checked ? '1' : '') : c.value]));
  let shown = 0;
  for (const p of pairs) {
    const ok = Object.entries(want).every(([k, v]) => !v || p.dataset[k] === v);
    p.hidden = !ok; shown += ok;
  }
  document.getElementById('count').textContent = shown + ' of ' + pairs.length + ' pairs';
}
controls.forEach(c => c.addEventListener('change', apply));
apply();
"""


def render(paths: list[Path], spot: list[str], hard: set[str]) -> str:
    pairs = [p for path in paths for p in read_pairs(path)]
    domains = sorted({p["domain"] for p in pairs})
    filters = (
        _options("domain", domains)
        + _options("messiness", ["ultra", "mid", "near"])
        + _options("band", [name for name, _, _ in BANDS])
        + f'<label><input type="checkbox" data-filter="spot"> spot-check {len(spot)}</label>'
    )
    cards = "".join(card(p, spot, hard) for p in pairs)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gold pair review</title><style>{STYLE}</style></head>
<body><header><strong>Gold pair review</strong> · <span id="count"></span><br>{filters}
<p class="legend"><mark class="p">protected span</mark> <ins>changed word</ins></p></header>
{cards}
<script>{SCRIPT}</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="gold JSONL files (default: data/gold/*.jsonl)")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    paths = args.files or sorted(GOLD_DIR.glob("*.jsonl"))
    spot = read_ids(GOLD_DIR / "spot_check.txt")
    hard = set(read_ids(GOLD_DIR / "hard_cases.txt"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(paths, spot, hard), encoding="utf-8")
    print(json.dumps({"pairs": sum(len(read_pairs(p)) for p in paths), "html": str(args.output.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
