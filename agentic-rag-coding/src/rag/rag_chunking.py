from __future__ import annotations

from dataclasses import dataclass
import re

from src.contracts.rag_contract_models import SectionType


@dataclass
class RagChunk:
    chunk_id: str
    paper_id: str
    section: SectionType
    chunk_index: int
    page_start: int
    page_end: int
    text: str


class RagSectionChunker:
    """Two-layer chunking: section-level first, then token-window chunking."""

    def __init__(self, chunk_size_tokens: int = 700, overlap_tokens: int = 100) -> None:
        if chunk_size_tokens < 500 or chunk_size_tokens > 800:
            raise ValueError("chunk_size_tokens must be in [500, 800]")
        if overlap_tokens < 80 or overlap_tokens > 120:
            raise ValueError("overlap_tokens must be in [80, 120]")
        self.chunk_size_tokens = chunk_size_tokens
        self.overlap_tokens = overlap_tokens

    @staticmethod
    def _rough_tokenize(text: str) -> list[str]:
        return re.findall(r"[\w-]+|[^\s\w]", text, flags=re.UNICODE)

    @staticmethod
    def detect_section(line: str, current: SectionType) -> SectionType:
        low = line.strip().lower()
        if re.match(r"^\d*\.?\s*abstract\b", low):
            return SectionType.ABSTRACT
        if re.match(r"^\d*\.?\s*introduction\b", low):
            return SectionType.INTRODUCTION
        if re.match(r"^\d*\.?\s*(methods?|materials and methods)\b", low):
            return SectionType.METHODS
        if re.match(r"^\d*\.?\s*results?\b", low):
            return SectionType.RESULTS
        if re.match(r"^\d*\.?\s*discussion\b", low):
            return SectionType.DISCUSSION
        if re.match(r"^\d*\.?\s*conclusions?\b", low):
            return SectionType.CONCLUSION
        return current

    def chunk_pages(self, paper_id: str, pages: list[str]) -> list[RagChunk]:
        chunks: list[RagChunk] = []
        section = SectionType.INTRODUCTION
        chunk_index = 0

        for page_number, page_text in enumerate(pages, start=1):
            page_lines = []
            for line in page_text.splitlines():
                section = self.detect_section(line, section)
                page_lines.append(line)
            for chunk_text in self._window_text("\n".join(page_lines)):
                chunks.append(
                    RagChunk(
                        chunk_id=f"{paper_id}_{section.value}_p{page_number:03d}_c{chunk_index:04d}",
                        paper_id=paper_id,
                        section=section,
                        chunk_index=chunk_index,
                        page_start=page_number,
                        page_end=page_number,
                        text=chunk_text,
                    )
                )
                chunk_index += 1
        return chunks

    def chunk_section(self, paper_id: str, section: str, section_text: str) -> list[RagChunk]:
        section_type = SectionType(section) if section in SectionType._value2member_map_ else SectionType.INTRODUCTION
        return [
            RagChunk(
                chunk_id=f"{paper_id}_{section_type.value}_c{idx:03d}",
                paper_id=paper_id,
                section=section_type,
                chunk_index=idx,
                page_start=1,
                page_end=1,
                text=text,
            )
            for idx, text in enumerate(self._window_text(section_text))
        ]

    def _window_text(self, text: str) -> list[str]:
        tokens = self._rough_tokenize(text)
        if not tokens:
            return []

        chunks: list[str] = []
        start = 0

        while start < len(tokens):
            end = min(start + self.chunk_size_tokens, len(tokens))
            text = " ".join(tokens[start:end])
            chunks.append(text)
            if end == len(tokens):
                break
            start = max(end - self.overlap_tokens, start + 1)

        return chunks
