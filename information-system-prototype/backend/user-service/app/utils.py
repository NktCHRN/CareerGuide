"""Small utilities: parsing experience dates in the "M/YYYY" format."""
from __future__ import annotations

import re
from datetime import datetime, timezone

MONTH_YEAR_RE = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{4})\s*$")
CURRENT = "current"


def is_valid_month_year(value: str) -> bool:
    m = MONTH_YEAR_RE.match(value)
    if not m:
        return False
    month = int(m.group(1))
    return 1 <= month <= 12


def parse_month_year(value: str) -> tuple[int, int] | None:
    """Returns (month, year) or None if the string is not in the "M/YYYY" format."""
    m = MONTH_YEAR_RE.match(value)
    if not m:
        return None
    month, year = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    return month, year


def compute_months_of_experience(start: str | None, end: str | None) -> int | None:
    """Number of months between start and end ("current" → current month).

    Example: 5/2019 → 8/2021 = (2021-2019)*12 + (8-5) = 27.
    """
    if not start:
        return None
    start_parsed = parse_month_year(start)
    if not start_parsed:
        return None
    s_month, s_year = start_parsed

    if not end or end.strip().lower() == CURRENT:
        now = datetime.now(timezone.utc)
        e_month, e_year = now.month, now.year
    else:
        end_parsed = parse_month_year(end)
        if not end_parsed:
            return None
        e_month, e_year = end_parsed

    months = (e_year - s_year) * 12 + (e_month - s_month)
    return max(months, 0)
