from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz


DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
NOISY_TITLE_PREFIXES = (
    "citation:",
    "academic editor",
    "ieee transactions",
    "5th international",
    "received:",
    "revised:",
    "accepted:",
    "published:",
    "publisher",
    "copyright",
    "licensee",
    "abstract",
    "keywords",
    "www.",
    "http",
    "doi",
)
NOISY_SENTENCE_STARTS = (
    "gait impairment,",
    "of rehabilitating walking function",
    "used to promote",
    "with regard to",
    "published maps",
    "this article",
    "distributed under",
    "conditions of the creative commons",
)
TITLE_KEYWORDS = (
    "gait",
    "stroke",
    "hemipleg",
    "imu",
    "inertial",
    "sensor",
    "wearable",
    "cane",
    "emg",
    "electromyographic",
    "rehabilitation",
    "patient",
    "analysis",
    "assessment",
)


def extract_text_by_page(pdf_path: Path) -> list[str]:
    doc = fitz.open(str(pdf_path))
    try:
        return [page.get_text("text") for page in doc]
    finally:
        doc.close()


def extract_metadata_from_pages(pdf_path: Path, pages: list[str]) -> dict[str, Any]:
    first_page = pages[0] if pages else ""
    lines = [_clean_line(line) for line in first_page.splitlines()]
    lines = [line for line in lines if line]

    title = _extract_title(lines) or _title_from_filename(pdf_path)
    authors = _extract_authors(lines, title)

    text_all = "\n".join(pages)
    doi_match = DOI_RE.search(text_all)
    year_match = re.search(r"(19|20)\d{2}", first_page)

    return {
        "paper_id": stable_paper_id(pdf_path),
        "title": title[:300],
        "authors": authors,
        "year": int(year_match.group(0)) if year_match else None,
        "doi": doi_match.group(0) if doi_match else None,
        "source_path": str(pdf_path.resolve()),
    }


def stable_paper_id(pdf_path: Path) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", pdf_path.stem).strip("_").lower()
    return normalized[:80] or "paper"


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _extract_title(lines: list[str]) -> str | None:
    if len(lines) >= 2 and _looks_like_title(lines[0]) and _looks_like_title_continuation(lines[1]):
        early_title = _clean_title(f"{lines[0]} {lines[1]}")
        if any(keyword in early_title.lower() for keyword in TITLE_KEYWORDS):
            return early_title

    candidates: list[tuple[int, str]] = []
    for index, line in enumerate(lines[:80]):
        if not _looks_like_title(line):
            continue
        score = 0
        low = line.lower()
        score += sum(3 for keyword in TITLE_KEYWORDS if keyword in low)
        score += 4 if 35 <= len(line) <= 180 else 0
        score += 2 if ":" in line else 0
        score -= index // 4

        line = _expand_title_candidate(lines, index)
        if len(line) > 80:
            score += 4
        if any(keyword in line.lower() for keyword in ("abstract", "keywords", "background and clinical")):
            score -= 8
        if line[:1].islower():
            score -= 4
        candidates.append((score, line))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return _clean_title(candidates[0][1])


def _looks_like_title(line: str) -> bool:
    low = line.lower()
    if len(line) < 12 or len(line) > 240:
        return False
    if any(low.startswith(prefix) for prefix in NOISY_TITLE_PREFIXES):
        return False
    if any(low.startswith(prefix) for prefix in NOISY_SENTENCE_STARTS):
        return False
    if ";" in line and not any(keyword in low for keyword in TITLE_KEYWORDS):
        return False
    if re.search(r"\bvol\.\s*\d+", low):
        return False
    if "congress" in low and "thailand" in low:
        return False
    if re.fullmatch(r"[\W\d_]+", line):
        return False
    letters = sum(char.isalpha() for char in line)
    if letters < 8:
        return False
    if low.count("@") or "creativecommons" in low:
        return False
    return True


def _looks_like_title_continuation(line: str) -> bool:
    if not _looks_like_title(line):
        return False
    low = line.lower()
    if low in {"review", "case report", "open"}:
        return True
    if ";" in line and not any(keyword in low for keyword in TITLE_KEYWORDS):
        return False
    if re.search(r"\b[A-Z]\.;", line):
        return False
    if "," in line and not any(keyword in low for keyword in TITLE_KEYWORDS):
        return False
    return True


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\.\s+(Healthcare|Sensors|Scientific Reports|Reports|IEEE).*$", ".", title)
    title = re.sub(r"^Review\s+", "", title)
    if title.lower().startswith("case report ") and title.lower().endswith("case report"):
        title = title[len("Case Report ") :]
    return title.strip(" .") or title


def _expand_title_candidate(lines: list[str], index: int) -> str:
    parts = [lines[index]]

    cursor = index - 1
    while cursor >= 0 and len(parts) < 3 and _looks_like_title_continuation(lines[cursor]):
        parts.insert(0, lines[cursor])
        cursor -= 1

    cursor = index + 1
    while cursor < len(lines) and len(parts) < 4 and _looks_like_title_continuation(lines[cursor]):
        parts.append(lines[cursor])
        cursor += 1

    combined = " ".join(parts)
    return combined[:240]


def _extract_authors(lines: list[str], title: str) -> list[str]:
    try:
        start = lines.index(title.split("  ")[0])
    except ValueError:
        start = 0
    for line in lines[start + 1 : start + 8]:
        if "@" in line or any(line.lower().startswith(prefix) for prefix in NOISY_TITLE_PREFIXES):
            continue
        if "," in line or " and " in line.lower():
            return [item.strip() for item in re.split(r",|;|\band\b", line) if item.strip()]
    return []


def _title_from_filename(pdf_path: Path) -> str:
    title = re.sub(r"[_-]+", " ", pdf_path.stem)
    title = re.sub(r"\s+", " ", title).strip()
    return title or pdf_path.stem
