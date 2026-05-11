from __future__ import annotations

from src.contracts.rag_contract_models import SectionType
from src.rag.rag_chunking import RagSectionChunker


def test_chunk_pages_keeps_page_metadata_and_stable_ids() -> None:
    chunker = RagSectionChunker(chunk_size_tokens=500, overlap_tokens=80)
    pages = [
        "Methods\n" + "Initial contact was detected from shank angular velocity. " * 80,
        "Results\n" + "Sensitivity and precision were reported for gait events. " * 80,
    ]

    chunks = chunker.chunk_pages("paper_001", pages)

    assert chunks
    assert chunks[0].paper_id == "paper_001"
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert chunks[0].section == SectionType.METHODS
    assert chunks[0].chunk_id.startswith("paper_001_methods_p001_c")
    assert any(chunk.section == SectionType.RESULTS and chunk.page_start == 2 for chunk in chunks)
