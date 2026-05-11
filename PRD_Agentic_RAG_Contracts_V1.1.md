# PRD: Agentic RAG Platform for Stroke Patients V1

## 1. 文档信息

- 项目名称：Agentic RAG Platform for Stroke Patients
- 版本：V1.0
- 日期：2026-05-11
- 当前状态：MVP 已实现，可本地运行，可推送到 GitHub，支持公开部署准备
- 代码仓库：https://github.com/wanfengrenzui/Agentic-rag-platform-for-stroke-patients

## 2. V1 产品目标

V1 的目标是交付一个面向中风、步态分析、IMU/EMG 与康复医学论文的 Agentic RAG Web MVP。

用户可以在网页中基于本地 PDF 文献库提问，系统完成：

1. 解析 `Data/` 目录中的 PDF 原始数据。
2. 建立本地 FAISS 向量索引。
3. 使用 hybrid retrieval 检索相关证据片段。
4. 调用 DeepSeek API 进行 Planner、Synthesizer、Critic 流程。
5. 输出中文回答、论文对比表格、证据卡片、页码引用与置信度。

V1 重点不是做完整生产 SaaS，而是做一个可演示、可迭代、可解释的研究型 Agentic RAG 原型。

## 3. 用户与使用场景

### 3.1 目标用户

- 康复医学、HCI、医学工程方向研究者
- 中风步态分析相关学生或科研助理
- 想快速比较多篇 IMU/EMG 论文方法和结论的用户

### 3.2 核心场景

- 上传或放置一批 PDF 文献。
- 重建索引。
- 提问，例如：  
  `请比较这些论文中的 IMU 步态事件检测方法，并给出关键证据。`
- 获得：
  - 4-6 句中文解释性回答
  - 按文献名称展示的对比表
  - evidence cards，包含标题、页码、章节、证据片段
  - confidence 与 system_trace

## 4. V1 已实现范围

### 4.1 前端

技术栈：React + Vite + TypeScript

已实现页面能力：

- 索引状态卡片
  - PDF 数量
  - chunk 数量
  - FAISS 是否就绪
- 文档列表
- 上传 PDF
- 重建索引
- 查询输入框
- 回答展示
  - answer_text
  - summary_table
  - evidence_cards
  - confidence
  - latency_ms

展示优化：

- 表格第一列优先显示 `paper_title`，避免直接展示内部 `paper_id`
- 长 evidence_id 缩略显示
- 表格固定布局，适配浏览器 100% 缩放
- 长文本自动换行，避免横向撑破页面

### 4.2 后端

技术栈：FastAPI + Pydantic

已实现接口：

| Method | Path | 说明 |
|---|---|---|
| GET | `/` | 后端状态入口 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/documents` | 返回 `Data/` 中 PDF 列表 |
| GET | `/api/index/status` | 返回索引状态 |
| POST | `/api/index/rebuild` | 重建 FAISS 索引 |
| POST | `/api/upload` | 上传 PDF 到 `Data/uploads/` |
| POST | `/api/query` | 执行 Agentic RAG 查询 |

### 4.3 数据与索引

默认原始数据目录：

```text
Data/
```

上传目录：

```text
Data/uploads/
```

生成文件：

```text
agentic-rag-coding/storage/faiss.index
agentic-rag-coding/storage/chunks.jsonl
```

生成文件不进入 Git。

### 4.4 RAG

V1 检索策略：

- PDF 解析：PyMuPDF
- Chunking：按页切分，保留 page_start/page_end
- Embedding：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 向量索引：FAISS `IndexFlatIP`
- Hybrid Search：
  - vector weight: 0.6
  - keyword/BM25-style weight: 0.4
  - min-max normalization

### 4.5 Agent 流程

V1 流程：

```text
User Query
-> Planner Agent
-> Retriever
-> Synthesizer Agent
-> Critic Agent
-> Final Response
```

LLM：

- Provider: DeepSeek API
- Base URL: `https://api.deepseek.com`
- Default model: `deepseek-v4-flash`
- 环境变量：`DEEPSEEK_API_KEY`

如果没有配置 `DEEPSEEK_API_KEY`：

- 后端仍可启动
- 查询返回清晰错误提示
- 不会崩溃

## 5. 核心数据合同

### 5.1 Query Request

接口：

```text
POST /api/query
```

请求体：

```json
{
  "user_query": "请比较这些论文中的 IMU 步态事件检测方法，并给出关键证据。",
  "paper_ids": [],
  "top_k": 8,
  "language": "zh"
}
```

字段约束：

- `user_query`: 必填
- `paper_ids`: 可选，为空表示检索全部文献
- `top_k`: 默认 8，范围 3-12
- `language`: `zh` 或 `en`，V1 默认 `zh`

### 5.2 Evidence

```json
{
  "evidence_id": "ev_healthcare_10_01210_methods_p04_c0003",
  "paper_id": "healthcare_10_01210",
  "title": "IMU-Based Monitoring for Assistive Diagnosis and Management of IoHT: A Review",
  "authors": ["Fan Bo", "Mustafa Yerebakan"],
  "year": 2022,
  "doi": "10.3390/healthcare10071210",
  "section": "methods",
  "chunk_index": 3,
  "page_start": 4,
  "page_end": 4,
  "text": "Retrieved evidence text...",
  "score_vector": 0.82,
  "score_bm25": 0.74,
  "score_final": 0.788,
  "source_type": "local_pdf"
}
```

规则：

- `page_start/page_end` 必须来自 PDF 解析结果。
- `score_final` 范围为 `[0, 1]`。
- `title` 用作文献名称展示，不应在最终回答中退化为内部文件名或 `paper_id`。

### 5.3 Summary Row

```json
{
  "paper_id": "healthcare_10_01210",
  "paper_title": "IMU-Based Monitoring for Assistive Diagnosis and Management of IoHT: A Review",
  "method": "使用机器学习处理 IMU 信号，用于疾病检测和管理。",
  "sensor_position": "未说明",
  "metrics": ["分类准确率", "疾病检测", "进展评估"],
  "main_finding": "IMU 可作为远程健康监测的重要传感器，但强噪声环境下需要 ML 提高鲁棒性。",
  "evidence_ids": ["ev_healthcare_10_01210_methods_p04_c0003"]
}
```

规则：

- 前端优先展示 `paper_title`。
- `paper_id` 仅用于内部追踪。
- `evidence_ids` 必须可在 evidence_list 中找到。

### 5.4 Final Response

```json
{
  "request_id": "req_1778466121269",
  "status": "completed",
  "final_answer": {
    "answer_text": "这些文献都围绕 IMU 或 IMU+EMG 的步态评估展开，但侧重点不同...",
    "summary_table": []
  },
  "evidence_cards": [
    {
      "evidence_id": "ev_healthcare_10_01210_methods_p04_c0003",
      "title": "IMU-Based Monitoring for Assistive Diagnosis and Management of IoHT: A Review",
      "page": "p.4",
      "section": "methods",
      "snippet": "..."
    }
  ],
  "confidence": {
    "label": "medium",
    "score": 0.72,
    "reason": "部分论文只提供综述级证据，方法细节有限。"
  },
  "system_trace": {
    "retrieval_rounds": 1,
    "critic_pass": true,
    "latency_ms": 78387,
    "timeout_stage": "over_15s"
  }
}
```

## 6. 生成规则

### 6.1 Synthesizer

V1 要求：

- 回答语言默认中文。
- `answer_text` 应为 4-6 句，不能过短。
- 回答中必须优先使用完整文献名称。
- 不应使用 `Healthcare 2022`、`Sensors 2022`、`s41598` 或内部 `paper_id` 代替文献名。
- `summary_table` 建议 6-8 行；如果证据覆盖更多论文或方法，最多可扩展到 10 行。
- 前端必须保证 10 行以内的表格在浏览器 100% 缩放下可读，不应横向撑破页面。
- 每行必须绑定至少一个 `evidence_id`。
- 不允许生成无证据支持的 claim。

### 6.2 Critic

V1 检查：

- claim 是否绑定 evidence_id
- evidence_id 是否存在
- 基础引用可回溯性

V1 未完全实现：

- 深度医学风险分类
- 多证据冲突检测
- 自动二次检索闭环

## 7. 错误与状态

### 7.1 Final Status

| 状态 | 说明 |
|---|---|
| `completed` | 正常完成 |
| `completed_with_warning` | 达到最大尝试次数或置信度有限 |
| `need_user_confirmation` | 超时需要用户确认 |
| `failed_no_evidence` | 没有检索到证据 |
| `failed_contract_validation` | 配置缺失或合同校验失败 |

### 7.2 关键错误场景

| 场景 | V1 行为 |
|---|---|
| 未配置 DeepSeek key | 返回 `failed_contract_validation`，提示设置 `DEEPSEEK_API_KEY` |
| 索引为空 | 返回 `failed_no_evidence` 或提示重建索引 |
| claim 引用不存在 | Critic 阻断 |
| 上传非 PDF | 返回 400 |

## 8. 验收结果

V1 已通过以下验证：

```powershell
py -m compileall .
py -m pytest -q
npm.cmd run build
py -m src.main rebuild
```

当前测试结果：

- Python 编译通过
- 前端 build 通过
- 单元测试：5 passed
- Data 目录索引构建成功
  - PDF 数量：9
  - Chunk 数量：196

## 9. V1 非目标

以下内容不纳入 V1：

- 多用户账号系统
- 云端生产部署自动化
- 权限管理
- 数据库持久化用户会话
- PDF 原文页内跳转
- 引用人工审核工作流
- 医疗建议合规审查
- Web Search 联合检索
- 多模型路由

## 10. V2 候选方向

V1 之后可讨论的方向：

1. 部署与公开访问
   - Cloudflare Tunnel 临时公开
   - VPS + Nginx + HTTPS 长期部署
   - 子域名：`rag.asta.net.cn`

2. 引用体验增强
   - 点击 evidence card 打开 PDF
   - 跳转到页码
   - 高亮证据句

3. 检索质量增强
   - 更强 BM25
   - reranker
   - section-aware retrieval
   - 去除 PRD 类非论文文档对论文问题的干扰

4. Agent 能力增强
   - 二次检索
   - 失败自修正
   - 查询意图分类
   - 医学风险识别

5. 产品化
   - 项目空间
   - 文献集合管理
   - 导出 Word/Markdown/PDF 报告
   - 人工反馈闭环
