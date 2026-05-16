
"""
Add `summary_i` columns to train/validation/test CSVs, one per experience.

For every row with `number_of_experiences = n`, this writes columns
`summary_0, summary_1, ..., summary_{n-1}`. Each `summary_i` is generated
by a local Ollama LLM (default `gemma4:e4b`) prompted with the
experiences `0..i` of that row, concatenated as:

    Title: {title_0}
    Description: {description_0}

    Title: {title_1}
    Description: {description_1}

    ...

    Title: {title_i}
    Description: {description_i}

The model is asked to write a short professional-summary paragraph (the
kind of "Summary" section that opens a resume) reflecting the candidate
as of experience `i`.

Per-(row, i) progress is mirrored to a sidecar
`<split>.summary_i.progress.jsonl` so a crash mid-run resumes from where
it left off on restart. Failed generations (None) are not persisted, so
they get retried.

Install:
    pip install -U "ollama>=0.4" pandas tqdm

Then install Ollama (https://ollama.com) and pull the model:
    ollama pull gemma4:e4b

Usage:
    python map_summary_i.py
    python map_summary_i.py --model gemma4:e4b
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

import ollama
import pandas as pd
from tqdm.auto import tqdm

SPLIT_FILES = ("train.csv", "validation.csv", "test.csv")
DEFAULT_LLM_MODEL = "gemma4:e4b"

# Cap on the joined experiences passed to the LLM. The number of
# experiences is small (max 17 in this dataset) but a single description
# can be long; this guards against blowing the context window.
EXPERIENCES_CHAR_BUDGET = 12000

# Generation knobs. The summary is short.
NUM_PREDICT_TOKENS = 220
TEMPERATURE = 0.2

PROMPT_TEMPLATE = """\
You are writing the "Professional Summary" section of a resume on behalf of \
its owner. Below are the candidate's work experiences so far, in reverse \
chronological order (most recent first). Produce a concise 2-4 sentence \
summary that highlights the candidate's current role, years of experience, \
core strengths, and notable accomplishments based ONLY on the experiences \
listed, leading with what the most recent role establishes about them. Write in the first-person-implicit style \
typical of resume summaries (no "I" / "the candidate" / "this person" - just \
direct statements like "Dedicated chef with..."). Do NOT include section \
headers, bullet points, or quotes. Return only the summary text.

Experiences:
{experiences}

Summary:"""


# -----------------------------------------------------------------------------
# Experience formatting
# -----------------------------------------------------------------------------

def _str_or_empty(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def build_experiences_block(row, upto_i: int) -> Optional[str]:
    """Concatenate experiences 0..upto_i (inclusive) into the prompt block.

    Returns None if every experience in the range is empty (no title and
    no description), in which case there is nothing meaningful to summarize.
    """
    chunks: list[str] = []
    for i in range(upto_i, -1, -1):
        title = _str_or_empty(row.get(f"title_{i}"))
        description = _str_or_empty(row.get(f"description_{i}"))
        if not title and not description:
            continue
        chunks.append(f"Title: {title}\nDescription: {description}")
    if not chunks:
        return None
    block = "\n\n".join(chunks)
    if len(block) > EXPERIENCES_CHAR_BUDGET:
        block = block[:EXPERIENCES_CHAR_BUDGET]
    return block


# -----------------------------------------------------------------------------
# Ollama
# -----------------------------------------------------------------------------

def generate_summary(
    experiences_block: str,
    client: ollama.Client,
    model_name: str,
) -> Optional[str]:
    """Call the LLM to write a summary. Returns None on Ollama failure."""
    prompt = PROMPT_TEMPLATE.format(experiences=experiences_block)
    try:
        response = client.generate(
            model=model_name,
            prompt=prompt,
            think=False,
            options={"temperature": TEMPERATURE, "num_predict": NUM_PREDICT_TOKENS},
        )
    except Exception as e:
        if "ollama" not in type(e).__module__:
            raise
        print(f"  ollama error: {e!r}", file=sys.stderr)
        return None

    raw = response.get("response", "") if isinstance(response, dict) \
        else getattr(response, "response", "")
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.lower().startswith("summary:"):
        raw = raw.split(":", 1)[1].strip()
    return raw or None


# -----------------------------------------------------------------------------
# Sidecar progress
# -----------------------------------------------------------------------------

def _sidecar_path(split_path: Path) -> Path:
    return split_path.parent / (split_path.name + ".summary_i.progress.jsonl")


def _load_progress(sidecar_path: Path) -> dict[tuple[str, int], str]:
    """Returns {(identifier, i) -> summary}. Null/empty entries are skipped
    so they get retried on the next run."""
    if not sidecar_path.exists():
        return {}
    progress: dict[tuple[str, int], str] = {}
    with open(sidecar_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ident = rec.get("identifier")
            i = rec.get("i")
            summary = rec.get("summary")
            if ident is None or not isinstance(i, int):
                continue
            if not isinstance(summary, str) or not summary.strip():
                continue
            progress[(str(ident), i)] = summary
    return progress


def _record_progress(
    sidecar_f, identifier: str, i: int, summary: Optional[str],
) -> None:
    sidecar_f.write(json.dumps(
        {"identifier": identifier, "i": i, "summary": summary},
        ensure_ascii=False,
    ) + "\n")
    sidecar_f.flush()


def _row_identifier(idx: int, row) -> str:
    raw = row.get("identifier")
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return f"_row_{idx}"
    return str(raw)


# -----------------------------------------------------------------------------
# Split enrichment
# -----------------------------------------------------------------------------

def enrich_split(
    split_path: Path,
    client: ollama.Client,
    model_name: str,
) -> None:
    df = pd.read_csv(split_path)

    if "number_of_experiences" not in df.columns:
        print(
            f"  {split_path.name}: missing 'number_of_experiences' column; skipping",
            file=sys.stderr,
        )
        return

    # Determine the maximum number of experiences in this split so we can
    # pre-allocate output columns of the right width.
    max_n = int(pd.to_numeric(df["number_of_experiences"], errors="coerce")
                .fillna(0).max())
    if max_n <= 0:
        print(f"  {split_path.name}: no experiences anywhere; skipping",
              file=sys.stderr)
        return

    # Output columns (one per experience slot). Strings, missing as None.
    out_cols: list[list[Optional[str]]] = [
        [None] * len(df) for _ in range(max_n)
    ]

    sidecar_path = _sidecar_path(split_path)
    progress = _load_progress(sidecar_path)

    n_resumed = 0
    n_generated = 0
    n_failed = 0
    n_empty = 0  # experience slot had no title/description -> nothing to summarize

    # Total summary_i units across the whole split, so the progress bar
    # reflects work, not rows.
    n_units = int(pd.to_numeric(df["number_of_experiences"], errors="coerce")
                  .fillna(0).clip(lower=0).sum())

    t0 = time.time()
    sidecar_f = open(sidecar_path, "a", encoding="utf-8")
    try:
        pbar = tqdm(total=n_units, desc=split_path.name,
                    unit="summary", leave=True)
        for idx, row in df.iterrows():
            ident = _row_identifier(idx, row)
            try:
                n = int(row["number_of_experiences"])
            except (TypeError, ValueError):
                n = 0
            if n <= 0:
                continue

            for i in range(n):
                cached = progress.get((ident, i))
                if cached is not None:
                    out_cols[i][idx] = cached
                    n_resumed += 1
                    pbar.update(1)
                    continue

                block = build_experiences_block(row, i)
                if block is None:
                    out_cols[i][idx] = None
                    n_empty += 1
                    pbar.update(1)
                    continue

                generated = generate_summary(block, client, model_name)
                out_cols[i][idx] = generated
                if generated is not None:
                    _record_progress(sidecar_f, ident, i, generated)
                    n_generated += 1
                else:
                    n_failed += 1
                pbar.set_postfix_str(
                    f"gen={n_generated} resumed={n_resumed} "
                    f"fail={n_failed} empty={n_empty}"
                )
                pbar.update(1)
        pbar.close()
    finally:
        sidecar_f.close()

    for i in range(max_n):
        df[f"summary_{i}"] = out_cols[i]
    df.to_csv(split_path, index=False)
    print(
        f"  {split_path.name}: done in {time.time()-t0:.0f}s — "
        f"generated={n_generated}, resumed={n_resumed}, "
        f"failed={n_failed}, empty={n_empty}, max_n={max_n}",
        file=sys.stderr,
    )


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits-dir", type=Path,
                    default=Path("data/output"),
                    help="Directory containing train/validation/test CSVs")
    ap.add_argument("--model", default=DEFAULT_LLM_MODEL,
                    help="Ollama model tag (default: gemma4:e4b)")
    ap.add_argument("--ollama-host", default=None,
                    help="Override Ollama host, e.g. http://localhost:11434")
    args = ap.parse_args()

    client = ollama.Client(host=args.ollama_host) if args.ollama_host \
        else ollama.Client()
    try:
        client.show(args.model)
    except Exception as e:
        print(
            f"Error: Ollama model '{args.model}' is not available ({e!r}).\n"
            f"       Pull it first: ollama pull {args.model}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Ollama model: {args.model}", file=sys.stderr)

    for name in SPLIT_FILES:
        split_path = args.splits_dir / name
        if not split_path.exists():
            print(f"  skipping {name}: not found", file=sys.stderr)
            continue
        enrich_split(split_path, client, args.model)


if __name__ == "__main__":
    main()
