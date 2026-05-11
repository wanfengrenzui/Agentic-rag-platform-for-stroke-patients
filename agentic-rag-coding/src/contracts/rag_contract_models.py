from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class SectionType(str, Enum):
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"


class FinalStatus(str, Enum):
    COMPLETED = "completed"
    COMPLETED_WITH_WARNING = "completed_with_warning"
    NEED_USER_CONFIRMATION = "need_user_confirmation"
    FAILED_NO_EVIDENCE = "failed_no_evidence"
    FAILED_CONTRACT_VALIDATION = "failed_contract_validation"


class Language(str, Enum):
    ZH = "zh"
    EN = "en"


class UserContext(BaseModel):
    role: str | None = None
    output_preference: str | None = None


class UserRequestContract(BaseModel):
    request_id: str
    user_query: str
    task_template: str | None = None
    uploaded_paper_ids: list[str] = Field(default_factory=list, max_length=50)
    language: Language
    response_mode: str = "normal"
    max_latency_ms: int = 20000
    allow_timeout_confirm: bool = True
    user_context: UserContext | None = None


class RewrittenQuery(BaseModel):
    query: str
    purpose: str
    priority: int = Field(ge=1, le=3)


class RetrievalPlan(BaseModel):
    need_retrieval: bool = True
    top_k: int = Field(default=8, ge=3, le=12)
    target_sections: list[SectionType] = Field(default_factory=list)
    paper_scope: list[str] = Field(default_factory=list)
    allow_second_retrieval: bool = True


class RiskFlags(BaseModel):
    medical_advice: bool = False
    requires_latest_guideline: bool = False


class PlannerOutputContract(BaseModel):
    intent: str
    task_complexity: str = "medium"
    planner_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    rewritten_queries: list[RewrittenQuery] = Field(min_length=1, max_length=3)
    retrieval_plan: RetrievalPlan
    risk_flags: RiskFlags


class HybridWeights(BaseModel):
    vector: float = 0.6
    bm25: float = 0.4

    @model_validator(mode="after")
    def validate_sum(self) -> "HybridWeights":
        total = round(self.vector + self.bm25, 6)
        if total != 1.0:
            raise ValueError("hybrid_weights must sum to 1.0")
        return self


class RetrieverFilters(BaseModel):
    paper_ids: list[str] = Field(default_factory=list)
    sections: list[SectionType] = Field(default_factory=list)
    year_range: list[int] | None = None


class RetrieverInputContract(BaseModel):
    request_id: str
    queries: list[str] = Field(min_length=1)
    filters: RetrieverFilters
    top_k: int = Field(default=8, ge=3, le=12)
    hybrid_weights: HybridWeights = Field(default_factory=HybridWeights)
    norm_method: str = "minmax"


class Evidence(BaseModel):
    evidence_id: str
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    section: SectionType
    chunk_index: int = Field(ge=0)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    text: str
    score_vector: float = Field(ge=0.0, le=1.0)
    score_bm25: float = Field(ge=0.0, le=1.0)
    score_final: float = Field(ge=0.0, le=1.0)
    source_type: str = "local_pdf"

    @model_validator(mode="after")
    def validate_page_range(self) -> "Evidence":
        if self.page_end < self.page_start:
            raise ValueError("page_end must be >= page_start")
        return self


class RetrievalDiagnostics(BaseModel):
    num_candidates_vector: int = 0
    num_candidates_bm25: int = 0
    num_merged: int = 0
    num_returned: int = 0
    low_confidence: bool = False
    norm_method: str = "minmax"
    dedup_strategy: str = "semantic_hash"


class RetrieverOutputContract(BaseModel):
    retrieval_status: str
    evidence_list: list[Evidence] = Field(default_factory=list)
    retrieval_diagnostics: RetrievalDiagnostics


class OutputFormat(BaseModel):
    format: str = "comparison_table"
    language: Language = Language.ZH
    require_citations: bool = True


class SynthesizerInputContract(BaseModel):
    user_query: str
    intent: str
    evidence_list: list[Evidence] = Field(min_length=1)
    output_format: OutputFormat = Field(default_factory=OutputFormat)


class SummaryRow(BaseModel):
    paper_id: str
    paper_title: str | None = None
    method: str
    sensor_position: str | None = None
    metrics: list[str] = Field(default_factory=list)
    main_finding: str
    evidence_ids: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: str
    evidence_ids: list[str] = Field(min_length=1)
    risk_level: str = "low"


class Citation(BaseModel):
    claim_id: str
    evidence_id: str
    display_text: str


class Confidence(BaseModel):
    label: str
    reason: str
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class SynthesizerOutputContract(BaseModel):
    answer_text: str
    summary_table: list[SummaryRow] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: Confidence
    unsupported_claims: list[str] = Field(default_factory=list)


class CriticInputContract(BaseModel):
    user_query: str
    answer_text: str
    claims: list[Claim] = Field(default_factory=list)
    evidence_list: list[Evidence] = Field(default_factory=list)


class FailReason(BaseModel):
    type: str
    claim_id: str | None = None
    description: str
    severity: str


class RetryHint(BaseModel):
    need_retry: bool = False
    retry_type: str | None = None
    suggested_queries: list[str] = Field(default_factory=list)
    target_sections: list[SectionType] = Field(default_factory=list)


class CriticOutputContract(BaseModel):
    passed: bool = Field(alias="pass")
    overall_score: float = Field(ge=0.0, le=1.0)
    fail_reasons: list[FailReason] = Field(default_factory=list)
    retry_hint: RetryHint = Field(default_factory=RetryHint)
    blocking: bool = False

    model_config = {"populate_by_name": True}


class TimeoutNegotiationContract(BaseModel):
    request_id: str
    status: FinalStatus
    timeout_stage: str
    partial_answer: str
    current_evidence_count: int = Field(ge=0)
    estimated_extra_ms: int = Field(ge=0)
    continue_token: str


class FinalAnswer(BaseModel):
    answer_text: str
    summary_table: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceCard(BaseModel):
    evidence_id: str
    title: str
    page: str
    section: SectionType
    snippet: str


class SystemTrace(BaseModel):
    retrieval_rounds: int = 1
    critic_pass: bool = False
    latency_ms: int = 0
    timeout_stage: str = "none"


class FinalResponseContract(BaseModel):
    request_id: str
    status: FinalStatus
    final_answer: FinalAnswer
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)
    confidence: Confidence
    system_trace: SystemTrace


def validate_claim_evidence_binding(claims: list[Claim], evidence_list: list[Evidence]) -> None:
    evidence_ids = {item.evidence_id for item in evidence_list}
    for claim in claims:
        for evidence_id in claim.evidence_ids:
            if evidence_id not in evidence_ids:
                raise ValueError(f"claim {claim.claim_id} binds unknown evidence_id {evidence_id}")
