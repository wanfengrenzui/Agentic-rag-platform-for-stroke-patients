from __future__ import annotations

import time
from typing import Protocol

from src.agents.critic_agent import CriticAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.synthesizer_agent import SynthesizerAgent
from src.contracts.rag_contract_models import (
    Confidence,
    CriticInputContract,
    Evidence,
    EvidenceCard,
    FinalAnswer,
    FinalResponseContract,
    FinalStatus,
    PlannerOutputContract,
    RetrieverFilters,
    RetrieverInputContract,
    RetrieverOutputContract,
    RetrievalDiagnostics,
    SynthesizerInputContract,
    SystemTrace,
    TimeoutNegotiationContract,
    UserRequestContract,
)
from src.llm.deepseek_client import DeepSeekClient


class RetrieverTool(Protocol):
    def run(self, payload: RetrieverInputContract) -> RetrieverOutputContract:
        raise NotImplementedError


class AgenticRagWorkflow:
    def __init__(
        self,
        retriever_tool: RetrieverTool,
        llm: DeepSeekClient | None = None,
        max_attempts: int = 3,
        top_k_override: int | None = None,
    ) -> None:
        self.retriever_tool = retriever_tool
        self.max_attempts = max_attempts
        self.top_k_override = top_k_override
        self.planner = PlannerAgent(llm=llm)
        self.synthesizer = SynthesizerAgent(llm=llm)
        self.critic = CriticAgent(llm=llm)

    def run(self, request: UserRequestContract) -> FinalResponseContract | TimeoutNegotiationContract:
        started = time.time()
        planner_output: PlannerOutputContract = self.planner.run(request)
        attempts = 0
        last_answer_text = ""
        last_evidence: list[Evidence] = []

        while attempts < self.max_attempts:
            attempts += 1
            latency_ms = int((time.time() - started) * 1000)
            if latency_ms > request.max_latency_ms and request.allow_timeout_confirm:
                return TimeoutNegotiationContract(
                    request_id=request.request_id,
                    status=FinalStatus.NEED_USER_CONFIRMATION,
                    timeout_stage="over_20s",
                    partial_answer=last_answer_text or "系统仍在生成中。",
                    current_evidence_count=len(last_evidence),
                    estimated_extra_ms=5000,
                    continue_token=f"cont_{request.request_id}_r{attempts}",
                )

            retriever_input = RetrieverInputContract(
                request_id=request.request_id,
                queries=[item.query for item in planner_output.rewritten_queries],
                filters=RetrieverFilters(
                    paper_ids=planner_output.retrieval_plan.paper_scope,
                    sections=planner_output.retrieval_plan.target_sections,
                    year_range=None,
                ),
                top_k=self.top_k_override or planner_output.retrieval_plan.top_k,
            )
            retriever_output = self.retriever_tool.run(retriever_input)
            last_evidence = retriever_output.evidence_list

            if not retriever_output.evidence_list:
                return self._final(
                    request=request,
                    status=FinalStatus.FAILED_NO_EVIDENCE,
                    answer_text="未检索到可靠证据，无法回答。请先重建索引，或换一个更具体的问题。",
                    summary_table=[],
                    evidence=[],
                    confidence=Confidence(label="low", reason="no_evidence", score=0.0),
                    attempts=attempts,
                    started=started,
                    critic_pass=False,
                )

            synth_input = SynthesizerInputContract(
                user_query=request.user_query,
                intent=planner_output.intent,
                evidence_list=retriever_output.evidence_list,
            )
            synth_output = self.synthesizer.run(synth_input)
            last_answer_text = synth_output.answer_text

            critic_input = CriticInputContract(
                user_query=request.user_query,
                answer_text=synth_output.answer_text,
                claims=synth_output.claims,
                evidence_list=retriever_output.evidence_list,
            )
            critic_output = self.critic.run(critic_input)

            if critic_output.passed:
                return self._final(
                    request=request,
                    status=FinalStatus.COMPLETED,
                    answer_text=synth_output.answer_text,
                    summary_table=[row.model_dump() for row in synth_output.summary_table],
                    evidence=retriever_output.evidence_list,
                    confidence=synth_output.confidence,
                    attempts=attempts,
                    started=started,
                    critic_pass=True,
                )

        return self._final(
            request=request,
            status=FinalStatus.COMPLETED_WITH_WARNING,
            answer_text=last_answer_text or "已达到最大尝试次数，返回当前最优结果。",
            summary_table=[],
            evidence=last_evidence,
            confidence=Confidence(label="medium", reason="max_attempts_reached", score=0.6),
            attempts=attempts,
            started=started,
            critic_pass=False,
        )

    @staticmethod
    def _final(
        request: UserRequestContract,
        status: FinalStatus,
        answer_text: str,
        summary_table: list[dict],
        evidence: list[Evidence],
        confidence: Confidence,
        attempts: int,
        started: float,
        critic_pass: bool,
    ) -> FinalResponseContract:
        latency_ms = int((time.time() - started) * 1000)
        cards = [
            EvidenceCard(
                evidence_id=item.evidence_id,
                title=item.title,
                page=f"p.{item.page_start}" if item.page_start == item.page_end else f"p.{item.page_start}-{item.page_end}",
                section=item.section,
                snippet=item.text[:240],
            )
            for item in evidence
        ]
        return FinalResponseContract(
            request_id=request.request_id,
            status=status,
            final_answer=FinalAnswer(answer_text=answer_text, summary_table=summary_table),
            evidence_cards=cards,
            confidence=confidence,
            system_trace=SystemTrace(
                retrieval_rounds=attempts,
                critic_pass=critic_pass,
                latency_ms=latency_ms,
                timeout_stage="over_15s" if latency_ms > 15000 else "none",
            ),
        )


class MockRetrieverTool:
    """Dev-only retriever to validate workflow wiring."""

    def run(self, payload: RetrieverInputContract) -> RetrieverOutputContract:
        del payload
        evidence = Evidence(
            evidence_id="ev_paper001_methods_p05_c02",
            paper_id="paper_001",
            title="Wearable IMU-Based Gait Event Detection in Stroke Patients",
            authors=["Author A", "Author B"],
            year=2023,
            doi="10.xxxx/xxxxx",
            section="methods",
            chunk_index=2,
            page_start=5,
            page_end=5,
            text="Initial contact was detected using the peak angular velocity of the shank.",
            score_vector=0.82,
            score_bm25=0.74,
            score_final=0.788,
            source_type="local_pdf",
        )
        return RetrieverOutputContract(
            retrieval_status="success",
            evidence_list=[evidence],
            retrieval_diagnostics=RetrievalDiagnostics(
                num_candidates_vector=30,
                num_candidates_bm25=30,
                num_merged=42,
                num_returned=1,
                low_confidence=False,
                norm_method="minmax",
                dedup_strategy="semantic_hash",
            ),
        )
