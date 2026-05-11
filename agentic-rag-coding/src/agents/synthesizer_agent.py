from __future__ import annotations

import json

from src.contracts.rag_contract_models import (
    Citation,
    Claim,
    Confidence,
    SummaryRow,
    SynthesizerInputContract,
    SynthesizerOutputContract,
)
from src.llm.deepseek_client import DeepSeekClient


class SynthesizerAgent:
    """Generate structured output only from retrieved evidence."""

    def __init__(self, llm: DeepSeekClient | None = None) -> None:
        self.llm = llm

    def run(self, payload: SynthesizerInputContract) -> SynthesizerOutputContract:
        if self.llm and self.llm.configured:
            try:
                return self._run_llm(payload)
            except Exception:
                pass

        top = payload.evidence_list[0]
        claim = Claim(
            claim_id="claim_001",
            claim_text=f"《{top.title}》在 {top.section.value} 部分给出了与问题相关的方法或结果。",
            claim_type="method_detail",
            evidence_ids=[top.evidence_id],
            risk_level="low",
        )
        citation = Citation(
            claim_id=claim.claim_id,
            evidence_id=top.evidence_id,
            display_text=f"[{top.title}, p.{top.page_start}]",
        )
        summary_row = SummaryRow(
            paper_id=top.paper_id,
            paper_title=top.title,
            method="见证据片段",
            main_finding=top.text[:160],
            evidence_ids=[top.evidence_id],
        )
        return SynthesizerOutputContract(
            answer_text="已基于检索证据生成结构化回答。",
            summary_table=[summary_row],
            claims=[claim],
            citations=[citation],
            confidence=Confidence(label="medium", reason="当前证据数量有限", score=0.72),
            unsupported_claims=[],
        )

    def _run_llm(self, payload: SynthesizerInputContract) -> SynthesizerOutputContract:
        assert self.llm is not None
        evidence = [
            {
                "evidence_id": item.evidence_id,
                "paper_id": item.paper_id,
                "paper_title": item.title,
                "section": item.section.value,
                "page_start": item.page_start,
                "page_end": item.page_end,
                "text": item.text[:1800],
            }
            for item in payload.evidence_list
        ]
        system = (
            "你是科研论文 RAG Synthesizer。只输出 JSON，不要 Markdown。"
            "必须只根据 evidence_list 回答，每条 claim 必须绑定至少一个 evidence_id。"
            "回答要有解释性，不要过短：answer_text 用中文写 4-6 句，先给总体比较，再点出关键差异。"
            "必须优先使用 evidence_list 中的 paper_title 称呼文献，不要用 Healthcare 2022、Sensors 2022、s41598 或 paper_id 代替文献名称。"
            "summary_table 建议 6-8 行；如果证据覆盖更多论文或方法，最多可扩展到 10 行。"
            "paper_title 字段必须填写完整文献名；method/main_finding 每格保持 1-2 个短句。"
            "metrics 最多 4 个短词；sensor_position 不确定就写 未说明。"
            "不要把长 evidence_id 复制进正文，只放到 evidence_ids 字段。"
        )
        user = {
            "user_query": payload.user_query,
            "intent": payload.intent,
            "evidence_list": evidence,
            "required_schema": {
                "answer_text": "中文，4-6句，使用文献名进行比较",
                "summary_table": [
                    {
                        "paper_id": "string",
                        "paper_title": "完整文献名，来自 evidence.paper_title",
                        "method": "1-2个短句说明方法",
                        "sensor_position": "短中文短语或未说明",
                        "metrics": ["短词，最多4个"],
                        "main_finding": "1-2个短句说明主要发现",
                        "evidence_ids": ["evidence_id"],
                    }
                ],
                "claims": [
                    {
                        "claim_id": "claim_001",
                        "claim_text": "string",
                        "claim_type": "method_detail|metric|finding|limitation",
                        "evidence_ids": ["evidence_id"],
                        "risk_level": "low|medium|high",
                    }
                ],
                "citations": [{"claim_id": "claim_001", "evidence_id": "evidence_id", "display_text": "[Title, p.1]"}],
                "confidence": {"label": "low|medium|high", "reason": "string", "score": 0.0},
                "unsupported_claims": [],
            },
        }
        data = self.llm.chat_json(system, json.dumps(user, ensure_ascii=False))
        return SynthesizerOutputContract.model_validate(data)
