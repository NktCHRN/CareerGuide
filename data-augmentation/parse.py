"""
Resume parser for the Bhawal/Kaggle Resume.csv dataset.

Extracts four fields from each resume's Resume_html column:
  - summary         (str | None)
  - additionalInfo  (str | None)
  - education       (str | None)  — Education + Certifications combined
  - skills          (list[str])

Parses HTML deterministically using section ID prefixes which are
stable across the dataset (e.g. SECTION_SUMM*, SECTION_EDUC*, SECTION_SKLL*).

Enriches the split CSVs (train/validation/test) under ./data/ with
four new columns — summary, additional_info, education, skills — by joining
each split's ``identifier`` against ``ID`` in ./data/Resume.csv.

Usage:
    python main.py
    python main.py --resume-csv data/Resume.csv --splits-dir data
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from bs4 import BeautifulSoup, Tag

# -----------------------------------------------------------------------------
# Section classification
# -----------------------------------------------------------------------------
# Primary signal: heading text matched against synonym sets.
# Fallback signal: section ID prefix (used only when no heading is present).
#
# Why heading text wins:
#   - Some users repurpose template slots: a HILT-prefixed section may be
#     titled "Skills" because the user renamed it. Heading text catches this.
#   - Some users rename SUMM-prefixed sections to "Position Applying" or
#     "Objective" (108 cases). These should NOT be treated as summary.
#   - The original spec was heading-text based; this aligns with intent.

# Map normalized (lowercased, stripped) heading text → output field name.
HEADING_TO_FIELD: dict[str, str] = {
    # summary
    "summary":                   "summary",
    "professional summary":      "summary",
    "career overview":           "summary",
    "career summary":            "summary",
    "executive summary":         "summary",
    "profile":                   "summary",
    "professional profile":      "summary",
    "executive profile":         "summary",
    "career profile":            "summary",
    # extended set — empirically derived from SUMM-prefixed sections
    # whose headings were renamed by users
    "career focus":              "summary",
    "objective":                 "summary",
    "career objective":          "summary",
    "objective statement":       "summary",
    "professional overview":     "summary",
    "professional background":   "summary",
    "professional objective":    "summary",
    "personal summary":          "summary",
    "summary of qualifications": "summary",
    "overview":                  "summary",
    "about":                     "summary",

    # education (also includes certifications/licenses per spec)
    "education":                   "education",
    "education and training":      "education",
    "academic background":         "education",
    "educational background":      "education",
    "certifications":              "education",
    "certificates":                "education",
    "licenses":                    "education",
    "licenses and certifications": "education",

    # skills
    "skills":             "skills",
    "core skills":        "skills",
    "key skills":         "skills",
    "technical skills":   "skills",
    "core competencies":  "skills",
    "computer skills":    "skills",
    "skill highlights":   "skills",

    # additional information
    "additional information":  "additionalInfo",
    "interests":               "additionalInfo",
    "hobbies":                 "additionalInfo",
    "activities":              "additionalInfo",
    "personal interests":      "additionalInfo",
    "affiliations":            "additionalInfo",
    "professional affiliations": "additionalInfo",
    "activities and honors":   "additionalInfo",

        # highlights — content that is summary-like in some resumes and
    # skill-like in others. Routed to BOTH summary (appended) and skills
    # (deduped against existing skills).
    "highlights":                "highlights",
    "core qualifications":       "highlights",
    "qualifications":            "highlights",
    "core strengths":            "highlights",
    "summary of skills":         "highlights",
    "summary of qualifications": "highlights",
    "areas of expertise":        "highlights",
    "professional highlights":   "highlights",
    "competencies":              "highlights",
}

# Fallback when a section has no heading at all.
PREFIX_TO_FIELD: dict[str, str] = {
    "SUMM": "summary",
    "EDUC": "education",
    "CERT": "education",
    "SKLL": "skills",
    "TSKL": "skills",
    "HILT": "highlights",
    "ADDI": "additionalInfo",
    "INTR": "additionalInfo",
    "AFIL": "additionalInfo",
}

SECTION_ID_RE = re.compile(r"SECTION_([A-Z]+)")


def get_section_prefix(section: Tag) -> Optional[str]:
    """Return the type prefix from a section's id attribute, or None."""
    sec_id = section.get("id", "") or ""
    m = SECTION_ID_RE.match(sec_id)
    return m.group(1) if m else None


def classify_section(section: Tag) -> Optional[str]:
    """
    Classify a section into one of: summary, education, skills,
    additionalInfo, or None (meaning: don't include).

    Heading text wins. Prefix is consulted only when no heading exists.
    A heading that doesn't match any known field returns None — this is
    intentional, so e.g. a SUMM-prefixed section titled "Position Applying"
    is correctly excluded.
    """
    title_el = section.find("div", class_="sectiontitle")
    if title_el:
        heading = title_el.get_text(strip=True).lower()
        if heading:
            return HEADING_TO_FIELD.get(heading)
    # No heading text → fall back to prefix
    prefix = get_section_prefix(section)
    if prefix:
        return PREFIX_TO_FIELD.get(prefix)
    return None


def get_section_body(section: Tag) -> Tag:
    """
    Return the content node of a section, excluding the heading.
    The heading is always in <div class="heading">; everything else is body.
    """
    heading = section.find("div", class_="heading")
    if heading:
        # Clone the section without the heading
        body_parts = []
        for child in section.find_all(recursive=False):
            if child is not heading:
                body_parts.append(child)
        # Wrap into a fresh container for uniform downstream handling
        body_soup = BeautifulSoup("<div></div>", "html.parser")
        container = body_soup.div
        for part in body_parts:
            container.append(part)
        return container
    return section


def get_section_text(section: Tag) -> str:
    """Extract the visible text of a section's body, normalized."""
    body = get_section_body(section)
    text = body.get_text(separator=" ", strip=True)
    # Collapse internal whitespace runs but preserve single spaces
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


# -----------------------------------------------------------------------------
# Skills extraction — leverages HTML structure
# -----------------------------------------------------------------------------

def extract_skills(section: Tag) -> list[str]:
    """
    Extract individual skills from a Skills section.

    Strategy: identify structural chunks (one per <li>, one per <td>, or
    one whole text block as fallback), then split each chunk further on
    bullets/commas/newlines. This handles both clean lists and "messy"
    cases where a <td> or <li> contains multiple bullet-separated items.
    """
    body = get_section_body(section)

    # Identify structural chunks
    list_items = body.find_all("li")
    if list_items:
        chunks = [li.get_text(separator="\n", strip=True) for li in list_items]
    elif body.find_all("td"):
        chunks = [td.get_text(separator="\n", strip=True)
                  for td in body.find_all("td")]
    else:
        chunks = [body.get_text(separator="\n", strip=True)]

    skills: list[str] = []
    for chunk in chunks:
        skills.extend(_split_chunk(chunk))
    return skills


# Bullet glyphs that may appear in plain-text skill listings
_BULLET_CHARS = "\u2022\u25E6\u25AA\u25CF•◦▪●·"
_BULLET_OR_COMMA = re.compile(rf"[,{_BULLET_CHARS}]\s*")
_NEWLINE_OR_SEMI = re.compile(r"[;\n]+")


def _split_chunk(chunk: str) -> list[str]:
    """Split a single text chunk into individual skills."""
    chunk = re.sub(r"[ \t]+", " ", chunk).strip()
    if not chunk:
        return []
    if _BULLET_OR_COMMA.search(chunk):
        parts = _BULLET_OR_COMMA.split(chunk)
    else:
        parts = _NEWLINE_OR_SEMI.split(chunk)
    return [s for s in (_clean_skill(p) for p in parts) if s]


def _clean_skill(s: str) -> str:
    """Remove leading bullets/whitespace and collapse internal spaces."""
    s = s.strip()
    s = re.sub(rf"^[{_BULLET_CHARS}*\-]+\s*", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


# -----------------------------------------------------------------------------
# Main parser
# -----------------------------------------------------------------------------

def parse_resume_html(html: str) -> dict:
    """Parse a single resume HTML into the four-field dict."""
    result = {
        "summary":        None,
        "additionalInfo": None,
        "education":      None,
        "skills":         [],
    }

    education_parts: list[str] = []
    additional_info_parts: list[str] = []
    # Highlights are kept separate so they can be merged into both
    # summary (as text) and skills (as deduped items) at the end.
    highlights_text_parts: list[str] = []
    highlights_skill_items: list[str] = []

    soup = BeautifulSoup(html, "html.parser")

    for section in soup.find_all("div", class_="section"):
        field = classify_section(section)
        if field is None:
            continue

        if field == "skills":
            result["skills"].extend(extract_skills(section))
            continue

        if field == "highlights":
            text = get_section_text(section)
            if text:
                highlights_text_parts.append(text)
            highlights_skill_items.extend(extract_skills(section))
            continue

        # For text-valued fields: extract body text and skip if empty
        text = get_section_text(section)
        if not text:
            continue

        if field == "summary":
            if result["summary"] is None:
                result["summary"] = text
        elif field == "education":
            education_parts.append(text)
        elif field == "additionalInfo":
            additional_info_parts.append(text)

    if education_parts:
        result["education"] = "\n".join(education_parts)
    if additional_info_parts:
        result["additionalInfo"] = "\n".join(additional_info_parts)

    # Merge highlights into summary (appended) and skills (deduped)
    if highlights_text_parts:
        highlights_text = "\n".join(highlights_text_parts)
        if result["summary"]:
            result["summary"] = result["summary"] + "\n" + highlights_text
        else:
            result["summary"] = highlights_text

    if highlights_skill_items:
        existing = {s.lower() for s in result["skills"]}
        for item in highlights_skill_items:
            key = item.lower()
            if key not in existing:
                result["skills"].append(item)
                existing.add(key)

    return result


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

SPLIT_FILES = ("train.csv", "validation.csv", "test.csv")
NEW_COLUMNS = ("summary", "additional_info", "education", "skills")


def build_resume_index(resume_csv: Path) -> dict[int, dict]:
    """Parse every row of Resume.csv once, return {ID: parsed_fields}."""
    df = pd.read_csv(resume_csv)
    print(f"Loaded {len(df)} resumes from {resume_csv}", file=sys.stderr)

    t0 = time.time()
    index: dict[int, dict] = {}
    for _, row in df.iterrows():
        index[int(row["ID"])] = parse_resume_html(row["Resume_html"])
    elapsed = time.time() - t0
    print(f"Parsed {len(index)} resumes in {elapsed:.1f}s "
          f"({len(index) / elapsed:.0f}/sec)", file=sys.stderr)
    return index


def enrich_split(split_path: Path, index: dict[int, dict]) -> None:
    """Add the four resume-derived columns to a split CSV in-place."""
    df = pd.read_csv(split_path)

    summaries: list[Optional[str]] = []
    add_infos: list[Optional[str]] = []
    educations: list[Optional[str]] = []
    skills_col: list[Optional[str]] = []

    n_matched = 0
    for ident in df["identifier"]:
        parsed = index.get(int(ident))
        if parsed is None:
            summaries.append(None)
            add_infos.append(None)
            educations.append(None)
            skills_col.append(None)
            continue
        n_matched += 1
        summaries.append(parsed["summary"])
        add_infos.append(parsed["additionalInfo"])
        educations.append(parsed["education"])
        # Serialize skills as JSON so commas/quotes inside skill names
        # round-trip cleanly through CSV.
        skills_col.append(json.dumps(parsed["skills"], ensure_ascii=False)
                          if parsed["skills"] else None)

    df["summary"] = summaries
    df["additional_info"] = add_infos
    df["education"] = educations
    df["skills"] = skills_col

    df.to_csv(split_path, index=False)
    print(f"  {split_path.name}: matched {n_matched}/{len(df)} identifiers",
          file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume-csv", type=Path,
                    default=Path("data/Resume.csv"),
                    help="Path to Resume.csv")
    ap.add_argument("--splits-dir", type=Path,
                    default=Path("data"),
                    help="Directory containing train/validation/test CSVs")
    args = ap.parse_args()

    index = build_resume_index(args.resume_csv)

    print(f"Enriching splits in {args.splits_dir}...", file=sys.stderr)
    for name in SPLIT_FILES:
        enrich_split(args.splits_dir / name, index)


if __name__ == "__main__":
    main()
