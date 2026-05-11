from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RagScoredChunk:
    evidence_id: str
    score_vector_raw: float
    score_bm25_raw: float
    score_vector_norm: float = 0.0
    score_bm25_norm: float = 0.0
    score_final: float = 0.0


class RagHybridScorer:
    """Standardize scores then apply weighted linear fusion."""

    def __init__(self, vector_weight: float = 0.6, bm25_weight: float = 0.4) -> None:
        if round(vector_weight + bm25_weight, 6) != 1.0:
            raise ValueError("vector_weight + bm25_weight must equal 1.0")
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

    @staticmethod
    def _minmax(values: list[float]) -> list[float]:
        if not values:
            return []
        low = min(values)
        high = max(values)
        if high == low:
            return [1.0 for _ in values]
        return [(value - low) / (high - low) for value in values]

    def score(self, chunks: list[RagScoredChunk]) -> list[RagScoredChunk]:
        vector_norm = self._minmax([item.score_vector_raw for item in chunks])
        bm25_norm = self._minmax([item.score_bm25_raw for item in chunks])

        for idx, chunk in enumerate(chunks):
            chunk.score_vector_norm = vector_norm[idx]
            chunk.score_bm25_norm = bm25_norm[idx]
            chunk.score_final = (
                self.vector_weight * chunk.score_vector_norm
                + self.bm25_weight * chunk.score_bm25_norm
            )

        return sorted(chunks, key=lambda item: item.score_final, reverse=True)
