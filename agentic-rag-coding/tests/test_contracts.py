from __future__ import annotations

import pytest

from src.contracts.rag_contract_models import Claim, Evidence, validate_claim_evidence_binding


def make_evidence(evidence_id: str = "ev_1") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        paper_id="paper_1",
        title="Title",
        section="methods",
        chunk_index=0,
        page_start=1,
        page_end=1,
        text="Evidence text",
        score_vector=0.8,
        score_bm25=0.7,
        score_final=0.76,
    )


def test_claim_evidence_binding_passes_for_known_ids() -> None:
    claim = Claim(claim_id="claim_1", claim_text="Supported claim", claim_type="method", evidence_ids=["ev_1"])
    validate_claim_evidence_binding([claim], [make_evidence()])


def test_claim_evidence_binding_rejects_unknown_ids() -> None:
    claim = Claim(claim_id="claim_1", claim_text="Unsupported claim", claim_type="method", evidence_ids=["missing"])
    with pytest.raises(ValueError):
        validate_claim_evidence_binding([claim], [make_evidence()])
