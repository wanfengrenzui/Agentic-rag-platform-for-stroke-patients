from __future__ import annotations

import json

from src.contracts.rag_contract_models import (
    CriticInputContract,
    CriticOutputContract,
    FailReason,
    RetryHint,
    validate_claim_evidence_binding,
)
from src.llm.deepseek_client import DeepSeekClient


class CriticAgent:
    """Rule-first critic with optional DeepSeek support check."""

    def __init__(self, llm: DeepSeekClient | None = None) -> None:
        self.llm = llm

    def run(self, payload: CriticInputContract) -> CriticOutputContract:
        fail_reasons: list[FailReason] = []
        try:
            validate_claim_evidence_binding(payload.claims, payload.evidence_list)
        except ValueError as exc:
            fail_reasons.append(
                FailReason(
                    type="missing_citation",
                    claim_id=None,
                    description=str(exc),
                    severity="high",
                )
            )

        if not fail_reasons and self.llm and self.llm.configured:
            try:
                llm_result = self._run_llm(payload)
                if not llm_result.passed:
                    return llm_result
            except Exception:
                pass

        passed = len(fail_reasons) == 0
        return CriticOutputContract(
            **{"pass": passed},
            overall_score=0.9 if passed else 0.6,
            fail_reasons=fail_reasons,
            retry_hint=RetryHint(
                need_retry=not passed,
                retry_type="second_retrieval" if not passed else None,
                suggested_queries=[payload.user_query] if not passed else [],
            ),
            blocking=not passed,
        )

    def _run_llm(self, payload: CriticInputContract) -> CriticOutputContract:
        assert self.llm is not None
        evidence = [
            {
                "evidence_id": item.evidence_id,
                "text": item.text[:1200],
                "page_start": item.page_start,
                "page_end": item.page_end,
            }
            for item in payload.evidence_list
        ]
        system = (
            "你是 RAG Critic。只输出 JSON，不要 Markdown。检查 claim 是否被 evidence 支持。"
            "如果发现无证据、引用不存在、证据冲突，pass=false。"
        )
        user = {
            "user_query": payload.user_query,
            "answer_text": payload.answer_text,
            "claims": [claim.model_dump() for claim in payload.claims],
            "evidence_list": evidence,
            "required_schema": {
                "pass": True,
                "overall_score": 0.9,
                "fail_reasons": [],
                "retry_hint": {"need_retry": False, "retry_type": None, "suggested_queries": [], "target_sections": []},
                "blocking": False,
            },
        }
        data = self.llm.chat_json(system, json.dumps(user, ensure_ascii=False))
        return CriticOutputContract.model_validate(data)
