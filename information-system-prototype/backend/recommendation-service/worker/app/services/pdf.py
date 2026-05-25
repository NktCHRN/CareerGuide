"""PDF → plain text extraction (pypdf)."""
from __future__ import annotations

import logging
from io import BytesIO

from pypdf import PdfReader

logger = logging.getLogger("recommendation-worker.pdf")


def extract_text(data: bytes) -> str:
    """Concatenate the text of every page. Pages that fail to parse are skipped."""
    reader = PdfReader(BytesIO(data))
    chunks: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            chunks.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 — a single bad page must not abort the rest
            logger.warning("Failed to extract text from PDF page %d", i)
    return "\n".join(chunks).strip()
