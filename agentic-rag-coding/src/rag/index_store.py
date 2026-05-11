from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import Settings
from src.contracts.rag_contract_models import Evidence, RetrieverInputContract, RetrieverOutputContract, RetrievalDiagnostics
from src.ingest.pdf_parser import extract_metadata_from_pages, extract_text_by_page
from src.rag.rag_chunking import RagChunk, RagSectionChunker


@dataclass
class ChunkRecord:
    evidence_id: str
    paper_id: str
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    section: str
    chunk_index: int
    page_start: int
    page_end: int
    text: str
    source_path: str


class EmbeddingModel:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype="float32")


class FaissRagStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedder = EmbeddingModel(settings.embedding_model)
        self.chunker = RagSectionChunker()
        self._index: faiss.Index | None = None
        self._records: list[ChunkRecord] | None = None

    def list_documents(self) -> list[dict[str, Any]]:
        documents = []
        for path in sorted(self.settings.data_dir.rglob("*.pdf")):
            documents.append(
                {
                    "paper_id": re.sub(r"[^A-Za-z0-9]+", "_", path.stem).strip("_").lower()[:80],
                    "filename": path.name,
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "uploaded": "uploads" in path.parts,
                }
            )
        return documents

    def status(self) -> dict[str, Any]:
        records = self._load_records_if_available()
        return {
            "data_dir": str(self.settings.data_dir),
            "storage_dir": str(self.settings.storage_dir),
            "index_exists": self.settings.faiss_index_path.exists(),
            "metadata_exists": self.settings.metadata_path.exists(),
            "document_count": len(self.list_documents()),
            "chunk_count": len(records),
            "embedding_model": self.settings.embedding_model,
        }

    def rebuild(self) -> dict[str, Any]:
        self.settings.storage_dir.mkdir(parents=True, exist_ok=True)
        records: list[ChunkRecord] = []

        for pdf_path in sorted(self.settings.data_dir.rglob("*.pdf")):
            pages = extract_text_by_page(pdf_path)
            metadata = extract_metadata_from_pages(pdf_path, pages)
            chunks = self.chunker.chunk_pages(metadata["paper_id"], pages)
            records.extend(self._records_from_chunks(metadata, chunks))

        if not records:
            self._index = None
            self._records = []
            self.settings.metadata_path.write_text("", encoding="utf-8")
            return self.status()

        vectors = self.embedder.encode([record.text for record in records])
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(self.settings.faiss_index_path))

        with self.settings.metadata_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

        self._index = index
        self._records = records
        return self.status()

    def retrieve(self, payload: RetrieverInputContract) -> RetrieverOutputContract:
        index, records = self._load()
        if index is None or not records:
            return RetrieverOutputContract(
                retrieval_status="empty_index",
                evidence_list=[],
                retrieval_diagnostics=RetrievalDiagnostics(norm_method=payload.norm_method),
            )

        query = " ".join(payload.queries)
        query_vector = self.embedder.encode([query])
        candidate_count = min(max(payload.top_k * 6, 20), len(records))
        vector_scores, vector_ids = index.search(query_vector, candidate_count)

        candidates: dict[int, float] = {}
        for idx, score in zip(vector_ids[0].tolist(), vector_scores[0].tolist()):
            if idx >= 0:
                candidates[idx] = max(float(score), 0.0)

        filtered_ids = [
            idx
            for idx in candidates
            if self._matches_filters(records[idx], payload)
        ]
        if not filtered_ids:
            filtered_ids = [idx for idx in range(len(records)) if self._matches_filters(records[idx], payload)]

        vector_raw = [candidates.get(idx, 0.0) for idx in filtered_ids]
        bm25_raw = [self._keyword_score(query, records[idx].text) for idx in filtered_ids]
        vector_norm = self._minmax(vector_raw)
        bm25_norm = self._minmax(bm25_raw)

        scored = []
        for pos, idx in enumerate(filtered_ids):
            final = payload.hybrid_weights.vector * vector_norm[pos] + payload.hybrid_weights.bm25 * bm25_norm[pos]
            scored.append((idx, vector_norm[pos], bm25_norm[pos], final))
        scored.sort(key=lambda item: item[3], reverse=True)

        evidence = [self._to_evidence(records[idx], vec, bm25, final) for idx, vec, bm25, final in scored[: payload.top_k]]
        return RetrieverOutputContract(
            retrieval_status="success" if evidence else "no_results",
            evidence_list=evidence,
            retrieval_diagnostics=RetrievalDiagnostics(
                num_candidates_vector=candidate_count,
                num_candidates_bm25=len(filtered_ids),
                num_merged=len(scored),
                num_returned=len(evidence),
                low_confidence=bool(evidence and evidence[0].score_final < 0.35),
                norm_method=payload.norm_method,
                dedup_strategy="evidence_id",
            ),
        )

    def run(self, payload: RetrieverInputContract) -> RetrieverOutputContract:
        return self.retrieve(payload)

    def _records_from_chunks(self, metadata: dict[str, Any], chunks: list[RagChunk]) -> list[ChunkRecord]:
        records = []
        for chunk in chunks:
            if len(chunk.text.strip()) < 80:
                continue
            records.append(
                ChunkRecord(
                    evidence_id=f"ev_{chunk.chunk_id}",
                    paper_id=metadata["paper_id"],
                    title=metadata["title"],
                    authors=metadata["authors"],
                    year=metadata["year"],
                    doi=metadata["doi"],
                    section=chunk.section.value,
                    chunk_index=chunk.chunk_index,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text=chunk.text,
                    source_path=metadata["source_path"],
                )
            )
        return records

    def _load(self) -> tuple[faiss.Index | None, list[ChunkRecord]]:
        records = self._load_records_if_available()
        if self._index is None and self.settings.faiss_index_path.exists():
            self._index = faiss.read_index(str(self.settings.faiss_index_path))
        return self._index, records

    def _load_records_if_available(self) -> list[ChunkRecord]:
        if self._records is not None:
            return self._records
        if not self.settings.metadata_path.exists():
            self._records = []
            return self._records
        records = []
        with self.settings.metadata_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(ChunkRecord(**json.loads(line)))
        self._records = records
        return records

    @staticmethod
    def _matches_filters(record: ChunkRecord, payload: RetrieverInputContract) -> bool:
        if payload.filters.paper_ids and record.paper_id not in payload.filters.paper_ids:
            return False
        if payload.filters.sections and record.section not in {section.value for section in payload.filters.sections}:
            return False
        return True

    @staticmethod
    def _keyword_score(query: str, text: str) -> float:
        query_terms = [term.lower() for term in re.findall(r"[\w-]+", query) if len(term) > 1]
        if not query_terms:
            return 0.0
        text_low = text.lower()
        hits = sum(1 for term in query_terms if term in text_low)
        coverage = hits / len(set(query_terms))
        density = min(sum(text_low.count(term) for term in set(query_terms)) / 20.0, 1.0)
        return 0.75 * coverage + 0.25 * density

    @staticmethod
    def _minmax(values: list[float]) -> list[float]:
        if not values:
            return []
        low = min(values)
        high = max(values)
        if math.isclose(high, low):
            return [1.0 for _ in values]
        return [(value - low) / (high - low) for value in values]

    @staticmethod
    def _to_evidence(record: ChunkRecord, score_vector: float, score_bm25: float, score_final: float) -> Evidence:
        return Evidence(
            evidence_id=record.evidence_id,
            paper_id=record.paper_id,
            title=record.title,
            authors=record.authors,
            year=record.year,
            doi=record.doi,
            section=record.section,
            chunk_index=record.chunk_index,
            page_start=record.page_start,
            page_end=record.page_end,
            text=record.text,
            score_vector=max(0.0, min(score_vector, 1.0)),
            score_bm25=max(0.0, min(score_bm25, 1.0)),
            score_final=max(0.0, min(score_final, 1.0)),
        )
