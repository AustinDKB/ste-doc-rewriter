"""Harvest a candidate pool of messy gold inputs from Hugging Face (Phase 2).

Streams a seeded sample from each license-clear dataset (never a full download),
cleans the text, drops rows with personal data, offensive words or no technical
subject, and writes one JSON line per candidate to data/raw/candidates.jsonl
(gitignored). Each line records the dataset id, the pinned revision (commit sha)
and the row id, so a gold pair can cite its exact source.

    uv sync --extra harvest
    uv run python scripts/harvest_inputs.py
"""

from __future__ import annotations

import argparse
import html
import itertools
import json
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ste_doc_rewriter.gold import BANDS, length_band
from ste_doc_rewriter.lint import word_count

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SEED = 20261021
BUFFER = 2000


TECH = re.compile(
    r"\b(?:api|server|database|deploy\w*|docker|kubernetes|cluster|cache|query|sql|"
    r"code|software|program\w*|compil\w*|algorithm\w*|network\w*|protocol|encrypt\w*|"
    r"model|dataset|data|regression|metric\w*|test\w*|bug|debug\w*|build|pipeline|"
    r"version|git|release|config\w*|latency|memory|cpu|thread\w*|function|interface|"
    r"user experience|ux|design\w*|layout|accessib\w*|dashboard|analytics|statistic\w*|"
    r"computer|comput\w*|internet|web|browser|operating system|linux|unix|kernel|"
    r"file|storage|cloud|security|password|automat\w*|engineer\w*|technolog\w*)\b",
    re.IGNORECASE,
)
# Personal data: emails, @mentions, phone numbers, US aircraft tail numbers.
PERSONAL = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.]+|(?<![\w`])@[A-Za-z0-9][\w-]{1,38}\b|"
    r"\+?\d{1,2}[ .-]?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}|\bN\d{1,5}[A-Z]{0,2}\b"
)
COMPUTING = re.compile(
    r"\b(?:software|computer|computing|programming language|algorithm|protocol|database|"
    r"operating system|compiler|encryption|cryptograph\w*|internet|web browser|server|"
    r"microprocessor|semiconductor|file format|source code|network)\b",
    re.IGNORECASE,
)
OFFENSIVE = re.compile(
    r"\b(?:fuck\w*|shit\w*|damn|crap|bitch\w*|bastard|idiot\w*|stupid|retard\w*|wtf)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Source:
    key: str
    dataset: str
    revision: str
    messiness: str
    load: dict[str, Any]
    rows: Callable[[dict[str, Any], str], Iterator[dict[str, Any]]]
    needs_tech: bool = True
    pool: int = 40


def excerpt(paragraphs: list[str]) -> str:
    """Leading paragraphs that fit a length band, longest fit first."""
    best = ""
    for n in range(1, len(paragraphs) + 1):
        text = "\n\n".join(paragraphs[:n])
        if word_count(text) > BANDS[-1][2]:
            break
        if length_band(text):
            best = text
    return best


def html_to_text(raw: str) -> str:
    """Stack Exchange HTML to light Markdown: code stays code, links keep their text."""
    text = re.sub(r"<pre[^>]*><code>([\s\S]*?)</code></pre>", lambda m: f"\n```\n{m.group(1).strip()}\n```\n", raw)
    text = re.sub(r"<code>([\s\S]*?)</code>", r"`\1`", text)
    text = re.sub(r"<a [^>]*>([\s\S]*?)</a>", r"\1", text)
    text = re.sub(r"<li>", "\n- ", text)
    text = re.sub(r"<br\s*/?>|</p>|</li>|</ul>|</ol>|</blockquote>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def paragraphs(text: str) -> list[str]:
    text = re.sub(r"<!--[\s\S]*?-->", "", text).replace("\r\n", "\n")
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _se_rows(row: dict[str, Any], site: str) -> Iterator[dict[str, Any]]:
    answers = [a for a in row["answers"] if not a["selected"]]
    for a in sorted(answers, key=lambda a: a["pm_score"])[:1]:
        if a["pm_score"] > 2:
            continue
        yield {
            "row_id": f"{site}/q{row['qid']}/a{a['answer_id']}",
            "text": excerpt(paragraphs(html_to_text(a["text"]))),
            "attribution": {
                "url": f"https://{site}/a/{a['answer_id']}",
                "question_url": f"https://{site}/questions/{row['qid']}",
                "author": a["author"],
                "author_url": a["author_profile"],
            },
        }


def _gh_rows(row: dict[str, Any], _: str) -> Iterator[dict[str, Any]]:
    if row["is_pull_request"] or not row["body"]:
        return
    yield {
        "row_id": f"{row['owner']}/{row['repo']}#{row['number']}",
        "text": excerpt(paragraphs(row["body"])),
        "attribution": {"url": f"https://github.com/{row['owner']}/{row['repo']}/issues/{row['number']}"},
    }


def _asrs_rows(row: dict[str, Any], _: str) -> Iterator[dict[str, Any]]:
    yield {
        "row_id": f"ACN {row['acn_num_ACN']}",
        "text": excerpt(paragraphs(row["Report 1_Narrative"] or "")),
        "attribution": {"url": "https://asrs.arc.nasa.gov/search/database.html"},
    }


def _wq_rows(row: dict[str, Any], _: str) -> Iterator[dict[str, Any]]:
    # 100k rows hold only 37 distinct texts; the dedupe in harvest() keeps one of each.
    yield {"row_id": row["id"], "text": excerpt(paragraphs(row["rejected"])), "attribution": {}}


def _coedit_rows(row: dict[str, Any], _: str) -> Iterator[dict[str, Any]]:
    # "src" starts with an edit instruction ("Fix grammar: ..."); keep the text after it.
    yield {"row_id": row["_id"], "text": row["src"].split(": ", 1)[-1].strip(), "attribution": {}}


def _wiki_rows(row: dict[str, Any], _: str) -> Iterator[dict[str, Any]]:
    art = row["normal"]
    content = art["normal_article_content"]
    paras: dict[str, list[str]] = {}
    for sid, sent in zip(content["normal_sentence_id"], content["normal_sentence"]):
        paras.setdefault(sid.rsplit("-", 1)[0], []).append(sent)
    texts = [" ".join(s) for s in paras.values()]
    # Most articles are places and people; keep computing articles only.
    if not texts or not COMPUTING.search(texts[0]):
        return
    attribution = {"url": art["normal_article_url"], "title": art["normal_article_title"]}
    row_id = f"example {row['example_id']} article {art['normal_article_id']}"
    yield {"row_id": row_id, "text": excerpt(texts), "attribution": attribution}
    # Plus one single-paragraph and one single-sentence candidate per article.
    single = [(f"paragraph {i}", t) for i, t in enumerate(texts) if length_band(t) in {"paragraph", "section"}]
    sentences = [
        (f"paragraph {i} sentence {j}", sent)
        for i, t in enumerate(texts) for j, sent in enumerate(re.split(r"(?<=\.) ", t))
        if length_band(sent) == "sentence"
    ]
    for ref, text in single[:1] + sentences[:1]:
        yield {"row_id": f"{row_id} {ref}", "text": text, "attribution": attribution}


SE_REV = "c7bda74048748f55749cd663c3d8d1025a841fd9"
GH_REV = "f7bdbac081d5c16af1bbd61b3d593dec5caf3b1e"
SOURCES = [
    *(
        Source(f"se:{site}", "HuggingFaceH4/stack-exchange-preferences", SE_REV, "ultra",
               {"data_files": f"data/{site}/{shard}"},
               lambda row, site=site: _se_rows(row, site), needs_tech=False)
        for site, shard in (
            ("devops.stackexchange.com", "*.parquet"),
            ("datascience.stackexchange.com", "*.parquet"),
            ("ux.stackexchange.com", "*.parquet"),
            ("stats.stackexchange.com", "train-00000-of-00003.parquet"),
            ("sqa.stackexchange.com", "*.parquet"),
            ("softwareengineering.stackexchange.com", "train-00000-of-00003.parquet"),
        )
    ),
    *(
        Source(f"gh:{repo}", "open-index/open-github-issues", GH_REV, "ultra",
               {"data_files": f"data/issues/{repo}/0.parquet"}, _gh_rows, needs_tech=False)
        for repo in ("etcd-io/etcd", "redis/redis", "duckdb/duckdb", "vuejs/docs", "mdn/content")
    ),
    Source("asrs", "elihoole/asrs-aviation-reports", "f1e681e92cddae20d01fc498d685f1cf6a052d34", "ultra",
           {"data_files": "asrs-aviation-reports-train.jsonl"}, _asrs_rows, needs_tech=False),
    Source("wq", "stindardlogic/writing-quality-dpo-100k", "c99d68adbd32cac74764a741e4b583ea2bcc20d6", "mid",
           {}, _wq_rows),
    Source("coedit", "grammarly/coedit", "e9a255c33ef910bc33a9d2b522653fa87521583e", "mid",
           {"data_files": "train.jsonl"}, _coedit_rows),
    # wiki_auto ships a loading script only; read the Hub's Parquet conversion of it.
    Source("wiki", "chaojiang06/wiki_auto", "51dbb2c60cfad6753609f005d3064e96546a1e66", "near",
           {"data_files": "auto/part_2/0000.parquet"}, _wiki_rows, pool=90),
]
# facebook/asset is not harvested: its card lists cc-by-sa-4.0 in the metadata but
# CC BY-NC 4.0 under "Licensing Information", so it is not clear for an MIT repo.


def keep(text: str, needs_tech: bool) -> bool:
    return bool(
        text
        and length_band(text)
        and not PERSONAL.search(text)
        and not OFFENSIVE.search(text)
        and (not needs_tech or TECH.search(text))
    )


def harvest(src: Source, per_source: int) -> Iterator[dict[str, Any]]:
    from datasets import load_dataset

    ds = load_dataset(src.dataset, revision=src.revision, split="train", streaming=True, **src.load)
    found = 0
    seen: set[str] = set()  # some datasets repeat the same text across rows
    for row in ds.shuffle(seed=SEED, buffer_size=BUFFER):
        for cand in src.rows(row, src.key.split(":", 1)[-1]):
            if cand["text"] in seen or not keep(cand["text"], src.needs_tech):
                continue
            seen.add(cand["text"])
            words = word_count(cand["text"])
            yield {
                "candidate": f"{src.key}:{cand['row_id']}",
                "dataset": src.dataset,
                "revision": src.revision,
                "row_id": cand["row_id"],
                "messiness": src.messiness,
                "words": words,
                "band": length_band(cand["text"]),
                "text": cand["text"],
                "attribution": cand["attribution"],
            }
            found += 1
        if found >= per_source:
            return


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--per-source", type=int, help="Candidates per source (default: each source's pool)")
    p.add_argument("--only", nargs="*", help="Source keys to harvest (default: all)")
    p.add_argument("-o", "--output", type=Path, default=RAW / "candidates.jsonl")
    args = p.parse_args(argv)
    os.environ.setdefault("HF_HOME", str(RAW / "hf"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        for src in SOURCES:
            if args.only and src.key not in args.only:
                continue
            n = 0
            pool = args.per_source or src.pool
            for cand in itertools.islice(harvest(src, pool), pool):
                out.write(json.dumps(cand, ensure_ascii=False) + "\n")
                n += 1
            print(f"{src.key}: {n} candidates")


if __name__ == "__main__":
    main()
