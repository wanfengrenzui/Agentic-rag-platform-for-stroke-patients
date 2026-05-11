from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz


DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)


def extract_text_by_page(pdf_path: Path) -> list[str]:
    doc = fitz.open(str(pdf_path))
    try:
        return [page.get_text("text") for page in doc]
    finally:
        doc.close()


def extract_metadata_from_pages(pdf_path: Path, pages: list[str]) -> dict[str, Any]:
    first_page = pages[0] if pages else ""
    lines = [line.strip() for line in first_page.splitlines() if line.strip()]
    title = lines[0] if lines else pdf_path.stem
    authors = ""

    if len(lines) >= 2:
        authors = lines[1] if "," in lines[1] or " and " in lines[1].lower() else " ".join(lines[1:3])

    text_all = "\n".join(pages)
    doi_match = DOI_RE.search(text_all)
    year_match = re.search(r"(19|20)\d{2}", first_page)

    return {
        "paper_id": stable_paper_id(pdf_path),
        "title": title[:300],
        "authors": [item.strip() for item in re.split(r",|;|\band\b", authors) if item.strip()],
        "year": int(year_match.group(0)) if year_match else None,
        "doi": doi_match.group(0) if doi_match else None,
        "source_path": str(pdf_path.resolve()),
    }


def stable_paper_id(pdf_path: Path) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", pdf_path.stem).strip("_").lower()
    return normalized[:80] or "paper"
