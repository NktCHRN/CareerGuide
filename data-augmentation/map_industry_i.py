"""
Add `industry_i` columns to train/validation/test CSVs, one per experience.

For every row with `number_of_experiences = n`, this writes columns
`industry_0, industry_1, ..., industry_{n-1}`. Assignment walks from the
most-recent experience (highest index) down to the oldest:

  - `industry_{n-1}` is copied verbatim from the row's `industry` column.
  - For `i < n-1`, if the first 2 digits of the ISCO group of
    `ESCO_uri_i` match those of `ESCO_uri_{i+1}`, the value of
    `industry_{i+1}` is propagated to `industry_i`. Otherwise we fall
    back to a cosine top-1 match between just experience `i` (its
    title + description, no surrounding context) and the `processed`
    column of `data/input/livecareer_resume_categories.csv`, mapped
    back to the `original` column.

ISCO groups are looked up in `data/input/occupations_en.csv` via the
`conceptUri` → `iscoGroup` mapping.

Embeddings come from `google/embeddinggemma-300m`. EmbeddingGemma uses
task-specific prefixes (asymmetric retrieval) — applied here for both
the query (experience block) and the document (category).

Install:
    pip install -U "sentence-transformers>=3.2" pandas numpy tqdm

EmbeddingGemma is a gated model — accept its license at
https://huggingface.co/google/embeddinggemma-300m and authenticate:
    huggingface-cli login    # or set HF_TOKEN env var

Usage:
    python map_industry_i.py
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from tqdm.auto import tqdm

SPLIT_FILES = ("train.csv", "validation.csv", "test.csv")
EMBED_MODEL = "google/embeddinggemma-300m"

# EmbeddingGemma asymmetric-retrieval prefixes.
# Source: https://huggingface.co/google/embeddinggemma-300m
EMBED_QUERY_PREFIX = "task: search result | query: "
EMBED_DOC_PREFIX = "title: none | text: "

# Same cap as map_summary_i.py — guards against blowing the embedder's
# context window on long descriptions.
EXPERIENCES_CHAR_BUDGET = 12000

EMBED_BATCH_SIZE = 32


# -----------------------------------------------------------------------------
# Experience formatting (same convention as map_summary_i.py)
# -----------------------------------------------------------------------------

def _str_or_empty(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def build_experience_block(row, i: int) -> Optional[str]:
    """Title + description of experience `i` only — no surrounding context.

    Returns None when both fields are empty.
    """
    title = _str_or_empty(row.get(f"title_{i}"))
    description = _str_or_empty(row.get(f"description_{i}"))
    if not title and not description:
        return None
    block = f"Title: {title}\nDescription: {description}"
    if len(block) > EXPERIENCES_CHAR_BUDGET:
        block = block[:EXPERIENCES_CHAR_BUDGET]
    return block


# -----------------------------------------------------------------------------
# Categories
# -----------------------------------------------------------------------------

# Augmented descriptions per category. Bare labels like "human resources"
# or "finance" embed too generically and pull unrelated experiences (HR
# absorbs anything that mentions training/scheduling staff; FINANCE loses
# to ACCOUNTANT because both share "financial"). These descriptions list
# the canonical activities/roles that define the category, biasing cosine
# similarity toward experiences that actually belong to it.
#
# Keyed by the `original` column from livecareer_resume_categories.csv.
# Categories without an entry fall back to the `processed` column.
CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "ACCOUNTANT": (
        "accountant: bookkeeping, general ledger, accounts payable and "
        "receivable, journal entries, bank reconciliation, tax preparation, "
        "audit support, month-end close, financial statement preparation"
    ),
    "ADVOCATE": (
        "advocate, attorney, lawyer: legal practice, litigation, court "
        "representation, drafting contracts and pleadings, client counsel, "
        "law firm associate, paralegal support"
    ),
    "AGRICULTURE": (
        "agriculture: farming, crop production, livestock and dairy, "
        "agronomy, irrigation, harvesting, agricultural equipment operation, "
        "ranch and farm operations"
    ),
    "APPAREL": (
        "apparel, clothing and fashion industry: garment manufacturing, "
        "textile production, fashion merchandising and buying, apparel "
        "designer, tailor and seamstress, clothing brand merchandiser, "
        "fashion house, footwear and accessories"
    ),
    "ARMY": (
        "army and military service: armed forces, soldier, infantry, "
        "non-commissioned officer, military officer, deployment and combat "
        "operations, military training and drill, defense and national "
        "security, navy, air force, marines, veteran service member"
    ),
    "ARTS": (
        "fine arts: visual artist, painter, sculptor, gallery exhibitions, "
        "creative artistic production, performing artist, art studio "
        "practice, art curation"
    ),
    "AUTOMOBILE": (
        "automobile and automotive industry: car dealership, vehicle "
        "sales, auto mechanic, motor mechanic, electrical mechanic on "
        "cars and trucks, automotive technician, vehicle technician, "
        "motor vehicle service technician, automotive repair shop, auto "
        "body technician, auto manufacturer, parts and service "
        "department, tire technician, motorcycle mechanic"
    ),
    "AVIATION": (
        "aviation: aircraft and airline operations, pilot, flight crew, "
        "cabin crew, airport ground handling, aerospace, air traffic, "
        "aviation maintenance"
    ),
    "BANKING": (
        "banking: retail and commercial bank branch, bank teller, personal "
        "banker, loan officer, mortgage origination, deposit accounts, "
        "consumer lending, branch operations"
    ),
    "BPO": (
        "business process outsourcing (BPO): outsourced call center agent, "
        "contact center customer support representative, inbound and "
        "outbound call handling, back-office process services for external "
        "clients"
    ),
    "BUSINESS-DEVELOPMENT": (
        "business development: strategic partnerships, lead generation, new "
        "market expansion, account growth, deal sourcing, building pipeline, "
        "B2B partnership management"
    ),
    "CHEF": (
        "chef and professional cook: kitchen brigade, line cook, sous chef, "
        "executive chef, menu development, food preparation in restaurant "
        "and hotel kitchens, culinary arts"
    ),
    "CONSTRUCTION": (
        "construction: residential and commercial building, general "
        "contractor, site superintendent, carpentry, masonry, framing, "
        "concrete, civil construction projects"
    ),
    "CONSULTANT": (
        "consultant: management and strategy consulting, client advisory "
        "engagements, professional services consulting firm, project-based "
        "advisory deliverables"
    ),
    "DESIGNER": (
        "designer of visual identity and physical artefacts: graphic "
        "designer, visual designer, brand and identity designer, "
        "typography, illustrator, print and packaging design, industrial "
        "and product designer of physical goods, interior designer, "
        "design studio work. Not software, not UI/UX engineering, not "
        "web development"
    ),
    "DIGITAL-MEDIA": (
        "digital media: digital marketing, social media management, online "
        "content creation, web content production, digital advertising, "
        "SEO, video and multimedia production for online channels"
    ),
    "ENGINEERING": (
        "engineering of physical systems and infrastructure: mechanical "
        "engineer, electrical engineer (power systems, not software), "
        "civil engineer, structural engineer, chemical engineer, "
        "industrial engineer, manufacturing engineer, process engineer, "
        "aerospace engineer, R&D engineer, product engineer working on "
        "hardware. Not software engineering, not IT, not web development"
    ),
    "FINANCE": (
        "finance: corporate finance, investment analysis, financial "
        "planning and analysis (FP&A), capital markets, treasury, equity "
        "research, M&A, portfolio management, investment banking"
    ),
    "FITNESS": (
        "fitness and physical exercise industry: personal fitness "
        "trainer at a gym, gym and fitness club instructor, group "
        "exercise class instructor at a fitness center, strength and "
        "conditioning specialist, yoga and pilates studio instructor, "
        "athletic training in a sports club, fitness center operations. "
        "Not corporate training, not vocational teaching, not classroom "
        "instruction"
    ),
    "HEALTHCARE": (
        "healthcare: medical care delivery, nursing, hospital and clinic "
        "operations, physician, patient care, clinical practice, allied "
        "health, medical assistant"
    ),
    "HR": (
        "human resources (HR): recruiting and hiring, talent acquisition, "
        "payroll administration, benefits administration, employee "
        "relations, HR generalist, onboarding new hires, HRIS"
    ),
    "INFORMATION-TECHNOLOGY": (
        "information technology (IT) and software: software developer, "
        "software engineer, software architect, programmer, web developer, "
        "frontend and backend developer, full-stack developer, mobile app "
        "developer, user interface developer, devops engineer, system "
        "administrator, network engineer, database administrator, "
        "cybersecurity, IT support and helpdesk"
    ),
    "PUBLIC-RELATIONS": (
        "public relations (PR): media relations, press releases, corporate "
        "communications, PR campaigns, publicist, spokesperson, "
        "communications strategy, crisis communications"
    ),
    "SALES": (
        "sales: sales representative, account executive, B2B and retail "
        "selling, sales quota attainment, prospecting and closing deals, "
        "territory sales"
    ),
    "TEACHER": (
        "teacher and educator employed by a school, college or "
        "university to deliver instruction in a classroom or lecture "
        "hall: lesson planning, curriculum delivery, grading and "
        "assessment, classroom management, pedagogy, faculty member, "
        "school staff, vocational teacher and vocational instructor at "
        "a vocational school, K-12 classroom teacher, secondary school "
        "teacher, high school teacher, university lecturer, college "
        "professor, education administrator, school principal, tutor, "
        "special education, early childhood education"
    ),
}


def load_categories(path: Path) -> tuple[list[str], list[str]]:
    """Returns (originals, embed_texts) aligned by row order.

    embed_texts is the augmented description from CATEGORY_DESCRIPTIONS
    when present, else the bare `processed` value as a fallback.
    """
    df = pd.read_csv(path)
    if "original" not in df.columns or "processed" not in df.columns:
        raise ValueError(
            f"{path} must have 'original' and 'processed' columns"
        )
    originals = [str(x).strip() for x in df["original"].tolist()]
    processed = [str(x).strip() for x in df["processed"].tolist()]
    embed_texts: list[str] = []
    n_aug = 0
    for orig, proc in zip(originals, processed):
        desc = CATEGORY_DESCRIPTIONS.get(orig)
        if desc:
            embed_texts.append(desc)
            n_aug += 1
        else:
            embed_texts.append(proc)
    print(
        f"  augmented descriptions for {n_aug}/{len(originals)} categories",
        file=sys.stderr,
    )
    return originals, embed_texts


def embed_categories(
    embed_texts: list[str], model: SentenceTransformer,
) -> np.ndarray:
    prefixed = [EMBED_DOC_PREFIX + t for t in embed_texts]
    return model.encode(
        prefixed,
        normalize_embeddings=True,
        batch_size=EMBED_BATCH_SIZE,
        show_progress_bar=False,
        convert_to_numpy=True,
    ).astype(np.float32)


# -----------------------------------------------------------------------------
# ESCO ISCO-group lookup
# -----------------------------------------------------------------------------

def load_isco_map(path: Path) -> dict[str, str]:
    """Build conceptUri → iscoGroup map from ESCO occupations CSV."""
    df = pd.read_csv(path, usecols=["conceptUri", "iscoGroup"])
    out: dict[str, str] = {}
    for uri, code in zip(df["conceptUri"], df["iscoGroup"]):
        if pd.isna(uri) or pd.isna(code):
            continue
        out[str(uri).strip()] = str(code).strip()
    return out


def isco_prefix(uri, isco_map: dict[str, str]) -> Optional[str]:
    """First 2 digits of the ISCO group for an ESCO URI, or None."""
    if uri is None:
        return None
    if isinstance(uri, float) and pd.isna(uri):
        return None
    code = isco_map.get(str(uri).strip())
    if not code or len(code) < 2:
        return None
    return code[:2]


# -----------------------------------------------------------------------------
# Split enrichment
# -----------------------------------------------------------------------------

def enrich_split(
    split_path: Path,
    embed_model: SentenceTransformer,
    cat_emb: np.ndarray,
    originals: list[str],
    isco_map: dict[str, str],
) -> None:
    df = pd.read_csv(split_path)

    if "number_of_experiences" not in df.columns:
        print(
            f"  {split_path.name}: missing 'number_of_experiences' column; skipping",
            file=sys.stderr,
        )
        return
    if "industry" not in df.columns:
        print(
            f"  {split_path.name}: missing 'industry' column; skipping",
            file=sys.stderr,
        )
        return

    max_n = int(pd.to_numeric(df["number_of_experiences"], errors="coerce")
                .fillna(0).max())
    if max_n <= 0:
        print(
            f"  {split_path.name}: no experiences anywhere; skipping",
            file=sys.stderr,
        )
        return

    # Pass 1 — walk every row from i=n-1 down to i=0 deciding which
    # cells need a cosine fallback. industry_{n-1} always copies from
    # the `industry` column. For i<n-1, if ESCO_uri_i and ESCO_uri_{i+1}
    # share the first 2 ISCO digits, the cell will copy from i+1;
    # otherwise it falls back to cosine on experience i alone.
    queries: list[str] = []
    coords: list[tuple[int, int]] = []  # (row_idx, i) for cosine queries
    n_copy = 0
    n_empty = 0

    for idx, row in df.iterrows():
        try:
            n = int(row["number_of_experiences"])
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            continue
        for i in range(n - 2, -1, -1):
            curr = isco_prefix(row.get(f"ESCO_uri_{i}"), isco_map)
            prev = isco_prefix(row.get(f"ESCO_uri_{i+1}"), isco_map)
            if curr is not None and prev is not None and curr == prev:
                n_copy += 1
                continue
            block = build_experience_block(row, i)
            if block is None:
                n_empty += 1
                continue
            queries.append(EMBED_QUERY_PREFIX + block)
            coords.append((idx, i))

    cosine_results: dict[tuple[int, int], str] = {}
    t0 = time.time()
    if queries:
        chunks: list[np.ndarray] = []
        pbar = tqdm(total=len(queries), desc=split_path.name,
                    unit="exp", leave=True)
        for start in range(0, len(queries), EMBED_BATCH_SIZE):
            batch = queries[start:start + EMBED_BATCH_SIZE]
            emb = embed_model.encode(
                batch,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).astype(np.float32)
            chunks.append(emb)
            pbar.update(len(batch))
        pbar.close()
        query_emb = np.vstack(chunks)

        # Cosine similarity (both sides L2-normalized) → matrix multiply.
        sims = query_emb @ cat_emb.T
        top1 = sims.argmax(axis=1)
        for (row_idx, i), cat_idx in zip(coords, top1):
            cosine_results[(row_idx, i)] = originals[int(cat_idx)]

    # Pass 2 — assemble output columns walking backwards per row,
    # propagating the "previous" (more recent) value through ISCO matches.
    out_cols: list[list[Optional[str]]] = [
        [None] * len(df) for _ in range(max_n)
    ]

    for idx, row in df.iterrows():
        try:
            n = int(row["number_of_experiences"])
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            continue
        industry_val = row.get("industry")
        if isinstance(industry_val, float) and pd.isna(industry_val):
            industry_val = None
        prev_value = industry_val
        out_cols[n - 1][idx] = prev_value
        for i in range(n - 2, -1, -1):
            curr = isco_prefix(row.get(f"ESCO_uri_{i}"), isco_map)
            prev = isco_prefix(row.get(f"ESCO_uri_{i+1}"), isco_map)
            if curr is not None and prev is not None and curr == prev:
                # Copy from the more recent neighbour.
                pass
            elif (idx, i) in cosine_results:
                prev_value = cosine_results[(idx, i)]
            else:
                # Cosine was wanted but the experience block was empty.
                prev_value = None
            out_cols[i][idx] = prev_value

    for i in range(max_n):
        df[f"industry_{i}"] = out_cols[i]
    df.to_csv(split_path, index=False)
    print(
        f"  {split_path.name}: done in {time.time()-t0:.1f}s — "
        f"cosine={len(queries)}, copied={n_copy}, empty={n_empty}, "
        f"max_n={max_n}",
        file=sys.stderr,
    )


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories-csv", type=Path,
                    default=Path("data/input/livecareer_resume_categories.csv"),
                    help="CSV with 'original' and 'processed' columns")
    ap.add_argument("--occupations-csv", type=Path,
                    default=Path("data/input/occupations_en.csv"),
                    help="ESCO occupations CSV with conceptUri/iscoGroup")
    ap.add_argument("--splits-dir", type=Path,
                    default=Path("data/output"),
                    help="Directory containing train/validation/test CSVs")
    ap.add_argument("--embed-model", default=EMBED_MODEL)
    args = ap.parse_args()

    print(f"Loading categories from {args.categories_csv}...", file=sys.stderr)
    originals, embed_texts = load_categories(args.categories_csv)
    print(f"  {len(originals)} categories", file=sys.stderr)

    print(f"Loading ESCO occupations from {args.occupations_csv}...",
          file=sys.stderr)
    isco_map = load_isco_map(args.occupations_csv)
    print(f"  {len(isco_map)} URI→ISCO entries", file=sys.stderr)

    print(f"Loading embedding model {args.embed_model}...", file=sys.stderr)
    embed_model = SentenceTransformer(args.embed_model)

    print("Embedding categories...", file=sys.stderr)
    t0 = time.time()
    cat_emb = embed_categories(embed_texts, embed_model)
    print(
        f"  done in {time.time()-t0:.1f}s, shape={cat_emb.shape}",
        file=sys.stderr,
    )

    for name in SPLIT_FILES:
        split_path = args.splits_dir / name
        if not split_path.exists():
            print(f"  skipping {name}: not found", file=sys.stderr)
            continue
        enrich_split(split_path, embed_model, cat_emb, originals, isco_map)


if __name__ == "__main__":
    main()
