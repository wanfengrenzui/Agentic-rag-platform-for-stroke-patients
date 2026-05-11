from __future__ import annotations

from src.rag.rag_hybrid_search import RagHybridScorer, RagScoredChunk


def test_hybrid_scoring_sorts_and_bounds_scores() -> None:
    scorer = RagHybridScorer()
    chunks = [
        RagScoredChunk(evidence_id="low", score_vector_raw=0.1, score_bm25_raw=0.1),
        RagScoredChunk(evidence_id="high", score_vector_raw=0.9, score_bm25_raw=0.8),
    ]

    scored = scorer.score(chunks)

    assert scored[0].evidence_id == "high"
    assert all(0.0 <= item.score_final <= 1.0 for item in scored)
