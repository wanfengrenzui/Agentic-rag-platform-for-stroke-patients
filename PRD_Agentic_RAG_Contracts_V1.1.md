# PRD：Agentic RAG 输入输出契约（V1.1）

## 1. 文档信息
- 项目名称：Agentic RAG + 多Agent AI Coding 系统
- 版本：V1.1
- 日期：2026-05-10
- 目标：定义端到端输入输出契约，保证可控、可调试、可评估、可追溯

## 2. 适用范围
本契约覆盖以下流程：
User Request -> Planner Agent -> Retriever Tool -> Synthesizer Agent -> Critic Agent -> Final Response

本版本关键决策：
- 编排方式：LangChain 原生 tool-based
- 检索方式：Hybrid Search（向量 0.6 + BM25 0.4，标准化后线性加权）
- 分块方式：两层分块
  - L1：完整 section 保存
  - L2：用于向量化与检索的 chunk（500-800 tokens，overlap 80-120）
- 引用策略：页码只能来自检索结果，不允许模型编造
- 证据绑定：每条 claim 必须绑定 evidence_id
- 错误处理：V1 规则优先
- 性能策略：
  - 15 秒内目标返回
  - 15-20 秒继续执行
  - 超过 20 秒返回用户确认是否继续

## 3. 全局约定

### 3.1 字段命名
- 全部使用 snake_case
- 所有 ID 字段使用字符串

### 3.2 时间与数值
- latency_ms 单位为毫秒
- score 范围为 [0, 1]

### 3.3 枚举约束
- language: zh | en
- section_type: abstract | introduction | methods | results | discussion | conclusion
- final_status: completed | completed_with_warning | need_user_confirmation | failed_no_evidence | failed_contract_validation

### 3.4 通用错误对象
```json
{
  "error_code": "E1002",
  "error_message": "missing citation for at least one claim",
  "stage": "synthesizer",
  "retryable": true
}
```

## 4. 数据模型基础

### 4.1 Evidence 对象（统一）
```json
{
  "evidence_id": "ev_paper001_methods_p05_c02",
  "paper_id": "paper_001",
  "title": "Wearable IMU-Based Gait Event Detection in Stroke Patients",
  "authors": ["Author A", "Author B"],
  "year": 2023,
  "doi": "10.xxxx/xxxxx",
  "section": "methods",
  "chunk_index": 2,
  "page_start": 5,
  "page_end": 5,
  "text": "Initial contact was detected using the peak angular velocity ...",
  "score_vector": 0.82,
  "score_bm25": 0.74,
  "score_final": 0.788,
  "source_type": "local_pdf"
}
```

### 4.2 Claim 对象（统一）
```json
{
  "claim_id": "claim_001",
  "claim_text": "Paper 001 使用小腿角速度峰值检测 Initial Contact 和 Foot Off。",
  "claim_type": "method_detail",
  "evidence_ids": ["ev_paper001_methods_p05_c02"],
  "risk_level": "low"
}
```

## 5. Contract 1：User Request Contract

### 5.1 输入结构
```json
{
  "request_id": "req_20260510_001",
  "user_query": "请比较这三篇论文中的 IMU 步态事件检测方法",
  "task_template": "literature_comparison",
  "uploaded_paper_ids": ["paper_001", "paper_002", "paper_003"],
  "language": "zh",
  "response_mode": "normal",
  "max_latency_ms": 20000,
  "allow_timeout_confirm": true,
  "user_context": {
    "role": "hci_researcher",
    "output_preference": "table_first"
  }
}
```

### 5.2 字段约束
- 必填：request_id, user_query, language
- uploaded_paper_ids 最大长度：50
- max_latency_ms 默认：20000

## 6. Contract 2：Planner Output Contract

### 6.1 输出结构
```json
{
  "intent": "literature_comparison",
  "task_complexity": "medium",
  "planner_confidence": 0.86,
  "rewritten_queries": [
    {
      "query": "IMU gait event detection initial contact foot off method",
      "purpose": "retrieve_method_details",
      "priority": 1
    },
    {
      "query": "wearable IMU gait analysis evaluation metrics sensitivity precision",
      "purpose": "retrieve_evaluation_metrics",
      "priority": 2
    }
  ],
  "retrieval_plan": {
    "need_retrieval": true,
    "top_k": 8,
    "target_sections": ["methods", "results", "discussion"],
    "paper_scope": ["paper_001", "paper_002", "paper_003"],
    "allow_second_retrieval": true
  },
  "risk_flags": {
    "medical_advice": false,
    "requires_latest_guideline": false
  }
}
```

### 6.2 字段约束
- rewritten_queries 数量：1-3
- retrieval_plan.top_k 范围：3-12
- target_sections 必须为 section_type 枚举子集

## 7. Contract 3：Retriever Input Contract

### 7.1 输入结构
```json
{
  "request_id": "req_20260510_001",
  "queries": [
    "IMU gait event detection initial contact foot off method",
    "wearable IMU gait analysis evaluation metrics sensitivity precision"
  ],
  "filters": {
    "paper_ids": ["paper_001", "paper_002", "paper_003"],
    "sections": ["methods", "results", "discussion"],
    "year_range": null
  },
  "top_k": 8,
  "hybrid_weights": {
    "vector": 0.6,
    "bm25": 0.4
  },
  "norm_method": "minmax"
}
```

### 7.2 字段约束
- hybrid_weights.vector 固定 0.6
- hybrid_weights.bm25 固定 0.4
- 权重和必须等于 1.0

## 8. Contract 4：Retriever Output Contract

### 8.1 输出结构
```json
{
  "retrieval_status": "success",
  "evidence_list": [
    {
      "evidence_id": "ev_paper001_methods_p05_c02",
      "paper_id": "paper_001",
      "title": "Wearable IMU-Based Gait Event Detection in Stroke Patients",
      "authors": ["Author A", "Author B"],
      "year": 2023,
      "doi": "10.xxxx/xxxxx",
      "section": "methods",
      "chunk_index": 2,
      "page_start": 5,
      "page_end": 5,
      "text": "Initial contact was detected using the peak angular velocity ...",
      "score_vector": 0.82,
      "score_bm25": 0.74,
      "score_final": 0.788,
      "source_type": "local_pdf"
    }
  ],
  "retrieval_diagnostics": {
    "num_candidates_vector": 30,
    "num_candidates_bm25": 30,
    "num_merged": 42,
    "num_returned": 8,
    "low_confidence": false,
    "norm_method": "minmax",
    "dedup_strategy": "semantic_hash"
  }
}
```

### 8.2 规则约束
- page_start/page_end 必须来自检索管线解析结果
- score_final 计算规则：
  - s_vec_norm = normalize(score_vector)
  - s_bm25_norm = normalize(score_bm25)
  - score_final = 0.6 * s_vec_norm + 0.4 * s_bm25_norm

## 9. Contract 5：Synthesizer Input Contract

### 9.1 输入结构
```json
{
  "user_query": "请比较这三篇论文中的 IMU 步态事件检测方法",
  "intent": "literature_comparison",
  "evidence_list": [
    {
      "evidence_id": "ev_paper001_methods_p05_c02",
      "paper_id": "paper_001",
      "section": "methods",
      "page_start": 5,
      "page_end": 5,
      "text": "Initial contact was detected using the peak angular velocity ..."
    }
  ],
  "output_format": {
    "format": "comparison_table",
    "language": "zh",
    "require_citations": true
  }
}
```

### 9.2 规则约束
- evidence_list 为空时不得进入生成，直接错误分支 E1001
- require_citations 必须为 true

## 10. Contract 6：Synthesizer Output Contract

### 10.1 输出结构
```json
{
  "answer_text": "三篇论文均采用 IMU 信号进行步态事件检测，但在传感器位置、特征选择和事件识别规则上存在差异。",
  "summary_table": [
    {
      "paper_id": "paper_001",
      "method": "基于小腿角速度峰值检测 Initial Contact 和 Foot Off",
      "sensor_position": "shank",
      "metrics": ["sensitivity", "precision"],
      "main_finding": "该方法在规则步态中具有较高检测稳定性",
      "evidence_ids": ["ev_paper001_methods_p05_c02"]
    }
  ],
  "claims": [
    {
      "claim_id": "claim_001",
      "claim_text": "Paper 001 使用小腿角速度峰值检测 Initial Contact 和 Foot Off。",
      "claim_type": "method_detail",
      "evidence_ids": ["ev_paper001_methods_p05_c02"],
      "risk_level": "low"
    }
  ],
  "citations": [
    {
      "claim_id": "claim_001",
      "evidence_id": "ev_paper001_methods_p05_c02",
      "display_text": "[Wearable IMU-Based Gait Event Detection in Stroke Patients, p.5]"
    }
  ],
  "confidence": {
    "label": "medium",
    "reason": "方法证据较充分，但部分评价指标证据不足。"
  },
  "unsupported_claims": []
}
```

### 10.2 规则约束
- 每条 claim 必须绑定至少一个 evidence_id
- citations 必须可反查到 evidence_list

## 11. Contract 7：Critic Input Contract

### 11.1 输入结构
```json
{
  "user_query": "请比较这三篇论文中的 IMU 步态事件检测方法",
  "answer_text": "三篇论文均采用 IMU 信号进行步态事件检测...",
  "claims": [
    {
      "claim_id": "claim_001",
      "claim_text": "Paper 001 使用小腿角速度峰值检测 Initial Contact 和 Foot Off。",
      "evidence_ids": ["ev_paper001_methods_p05_c02"],
      "risk_level": "low"
    }
  ],
  "evidence_list": [
    {
      "evidence_id": "ev_paper001_methods_p05_c02",
      "text": "Initial contact was detected using the peak angular velocity ...",
      "page_start": 5,
      "page_end": 5
    }
  ]
}
```

### 11.2 检查范围
- 证据绑定完整性
- 证据支持度
- 引用可回溯性
- 风险标签完整性（医疗建议）

## 12. Contract 8：Critic Output Contract

### 12.1 输出结构
```json
{
  "pass": false,
  "overall_score": 0.72,
  "fail_reasons": [
    {
      "type": "unsupported_claim",
      "claim_id": "claim_003",
      "description": "该结论声称适用于中风患者，但证据片段中未出现对应人群信息。",
      "severity": "high"
    },
    {
      "type": "missing_citation",
      "claim_id": "claim_005",
      "description": "该结论未绑定 evidence_id。",
      "severity": "medium"
    }
  ],
  "retry_hint": {
    "need_retry": true,
    "retry_type": "second_retrieval",
    "suggested_queries": [
      "stroke patients IMU gait event detection validation"
    ],
    "target_sections": ["methods", "results"]
  },
  "blocking": true
}
```

### 12.2 fail_reasons.type 枚举
- missing_citation
- unsupported_claim
- evidence_conflict
- out_of_scope
- medical_risk_unlabeled

## 13. Contract 9：Timeout Negotiation Contract（新增）

### 13.1 触发规则
- latency_ms <= 15000：正常返回
- 15000 < latency_ms <= 20000：继续执行，不中断
- latency_ms > 20000：返回用户确认

### 13.2 输出结构
```json
{
  "request_id": "req_20260510_001",
  "status": "need_user_confirmation",
  "timeout_stage": "over_20s",
  "partial_answer": "当前已完成方法对比，评价指标仍在检索中。",
  "current_evidence_count": 6,
  "estimated_extra_ms": 5000,
  "continue_token": "cont_req_20260510_001_r2"
}
```

### 13.3 用户确认继续请求
```json
{
  "request_id": "req_20260510_001",
  "continue_token": "cont_req_20260510_001_r2",
  "user_decision": "continue"
}
```

## 14. Contract 10：Final Response Contract

### 14.1 输出结构
```json
{
  "request_id": "req_20260510_001",
  "status": "completed_with_warning",
  "final_answer": {
    "answer_text": "三篇论文均围绕 IMU 步态事件检测展开，但在传感器位置和事件识别策略上存在明显差异。",
    "summary_table": [
      {
        "paper": "paper_001",
        "method": "基于小腿角速度峰值检测 IC/FO",
        "sensor_position": "shank",
        "metrics": "sensitivity, precision",
        "citation": "[Paper 001, p.5]"
      }
    ]
  },
  "evidence_cards": [
    {
      "evidence_id": "ev_paper001_methods_p05_c02",
      "title": "Wearable IMU-Based Gait Event Detection in Stroke Patients",
      "page": "p.5",
      "section": "methods",
      "snippet": "Initial contact was detected using the peak angular velocity ..."
    }
  ],
  "confidence": {
    "label": "medium",
    "score": 0.72,
    "reason": "方法证据充分，部分评价指标证据不足。"
  },
  "system_trace": {
    "retrieval_rounds": 2,
    "critic_pass": true,
    "latency_ms": 12800,
    "timeout_stage": "none"
  }
}
```

## 15. 错误码表（V1）

| 错误码 | 名称 | 触发阶段 | 含义 | 是否可重试 |
|---|---|---|---|---|
| E1001 | no_evidence | retriever | 未检索到可用证据 | 是 |
| E1002 | citation_missing | synthesizer/critic | claim 无引用绑定 | 是 |
| E1003 | claim_unsupported | critic | 结论缺少证据支撑 | 是 |
| E1004 | timeout_confirmation_required | orchestrator | 超过 20 秒需用户确认 | 是 |
| E1005 | invalid_contract_field | any | 字段缺失或类型错误 | 否 |
| E1006 | evidence_conflict | critic | 证据间存在冲突 | 是 |
| E1007 | medical_risk_unlabeled | critic | 医疗风险内容缺失风险提示 | 是 |

## 16. 规则优先错误处理（V1）
- 检索为空：触发 query 改写 + 二次检索
- 置信度低：返回警告状态 completed_with_warning
- 引用缺失：critic 阻断并要求重生
- 用户质疑来源：返回 evidence_cards 明细
- 医疗建议风险：自动追加风险提示

## 17. 性能与停止条件
- 目标响应：15 秒内
- 最大尝试次数：3
- 停止条件：
  - critic pass
  - 达到最大尝试次数
  - 无相关证据
  - 超过 20 秒且用户拒绝继续

## 18. 验收标准（MVP）
- 引用正确率：人工抽样 30 条，目标 >= 90%
- claim-evidence 绑定率：100%
- 字段契约校验通过率：100%
- 15 秒内响应比例：>= 80%

## 19. 实施建议
- 在每个 Agent 入口/出口加 JSON Schema 校验
- 在 orchestrator 统一记录 system_trace
- 将错误码写入日志与前端可见状态
- 把本文件纳入 PRD 技术规格章节，作为联调基线
