from __future__ import annotations

import json

from src.contracts.rag_contract_models import (
    PlannerOutputContract,
    RetrievalPlan,
    RewrittenQuery,
    RiskFlags,
    SectionType,
    UserRequestContract,
)
from src.llm.deepseek_client import DeepSeekClient


class PlannerAgent:
    """DeepSeek-backed planner with deterministic fallback."""

    def __init__(self, llm: DeepSeekClient | None = None) -> None:
        self.llm = llm

    def run(self, request: UserRequestContract) -> PlannerOutputContract:
        if self.llm and self.llm.configured:
            try:
                return self._run_llm(request)
            except Exception:
                pass

        query = request.user_query.strip()
        return PlannerOutputContract(
            intent=request.task_template or "literature_comparison",
            task_complexity="medium",
            planner_confidence=0.82,
            rewritten_queries=[
                RewrittenQuery(query=query, purpose="retrieve_relevant_evidence", priority=1),
            ],
            retrieval_plan=RetrievalPlan(
                need_retrieval=True,
                top_k=8,
                target_sections=[SectionType.METHODS, SectionType.RESULTS, SectionType.DISCUSSION],
                paper_scope=request.uploaded_paper_ids,
                allow_second_retrieval=True,
            ),
            risk_flags=RiskFlags(
                medical_advice=("建议" in query or "治疗" in query or "临床" in query),
                requires_latest_guideline=False,
            ),
        )

    def _run_llm(self, request: UserRequestContract) -> PlannerOutputContract:
        assert self.llm is not None
        system = (
            "你是 Agentic RAG 的 Planner。只输出 JSON，不要 Markdown。"
            "根据用户问题改写 1-3 条检索 query，并选择目标章节。"
        )
        user = {
            "user_query": request.user_query,
            "task_template": request.task_template or "literature_comparison",
            "uploaded_paper_ids": request.uploaded_paper_ids,
            "allowed_sections": [item.value for item in SectionType],
            "schema": {
                "intent": "string",
                "task_complexity": "low|medium|high",
                "planner_confidence": 0.85,
                "rewritten_queries": [{"query": "string", "purpose": "string", "priority": 1}],
                "retrieval_plan": {
                    "need_retrieval": True,
                    "top_k": 8,
                    "target_sections": ["methods", "results", "discussion"],
                    "paper_scope": request.uploaded_paper_ids,
                    "allow_second_retrieval": True,
                },
                "risk_flags": {"medical_advice": False, "requires_latest_guideline": False},
            },
        }
        data = self.llm.chat_json(system, json.dumps(user, ensure_ascii=False))
        return PlannerOutputContract.model_validate(data)
