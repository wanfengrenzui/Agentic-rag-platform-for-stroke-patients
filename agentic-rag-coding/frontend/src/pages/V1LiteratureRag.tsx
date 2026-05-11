import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { Database, FileText, Loader2, RefreshCw, Search, Upload } from "lucide-react";
import VersionNav from "../components/VersionNav";

type DocumentItem = {
  paper_id: string;
  filename: string;
  path: string;
  size_bytes: number;
  uploaded: boolean;
};

type IndexStatus = {
  index_exists: boolean;
  document_count: number;
  chunk_count: number;
};

type FinalResponse = {
  status: string;
  final_answer: {
    answer_text: string;
    summary_table: Array<Record<string, unknown>>;
  };
  evidence_cards: Array<{
    evidence_id: string;
    title: string;
    page: string;
    section: string;
    snippet: string;
  }>;
  confidence: {
    label: string;
    reason: string;
    score?: number;
  };
  system_trace: {
    retrieval_rounds: number;
    critic_pass: boolean;
    latency_ms: number;
    timeout_stage: string;
  };
};

const API = "";
const TABLE_COLUMNS = [
  { key: "paper_title", label: "文献名称" },
  { key: "method", label: "方法" },
  { key: "sensor_position", label: "传感器位置" },
  { key: "metrics", label: "指标" },
  { key: "main_finding", label: "主要发现" },
  { key: "evidence_ids", label: "证据" }
];

export default function V1LiteratureRag() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [question, setQuestion] = useState("请比较这些论文中的 IMU 步态事件检测方法，并给出关键证据。");
  const [answer, setAnswer] = useState<FinalResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ready = Boolean(status?.index_exists && status?.chunk_count);
  const sortedDocs = useMemo(() => [...documents].sort((a, b) => a.filename.localeCompare(b.filename)), [documents]);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setError(null);
    const [statusRes, docsRes] = await Promise.all([fetch(`${API}/api/v1/index/status`), fetch(`${API}/api/v1/documents`)]);
    setStatus(await statusRes.json());
    const docsJson = await docsRes.json();
    setDocuments(docsJson.documents ?? []);
  }

  async function rebuild() {
    setBusy("rebuild");
    setError(null);
    try {
      const res = await fetch(`${API}/api/v1/index/rebuild`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      setStatus(await res.json());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "索引重建失败");
    } finally {
      setBusy(null);
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API}/api/v1/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setBusy(null);
      event.target.value = "";
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    setBusy("query");
    setError(null);
    setAnswer(null);
    try {
      const res = await fetch(`${API}/api/v1/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: question, top_k: 8, language: "zh" })
      });
      if (!res.ok) throw new Error(await res.text());
      setAnswer(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "查询失败");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">V1 · Literature RAG</p>
          <h1>Agentic RAG</h1>
          <p>面向本地科研 PDF 的证据绑定问答工作台</p>
        </div>
        <div className="topbarActions">
          <VersionNav active="v1" />
          <button onClick={refresh} className="iconButton" title="刷新状态">
            <RefreshCw size={18} />
          </button>
        </div>
      </section>

      <section className="layout">
        <aside className="sidebar">
          <div className="panel">
            <div className="panelTitle">
              <Database size={18} />
              <h2>索引状态</h2>
            </div>
            <dl className="metrics">
              <div><dt>PDF</dt><dd>{status?.document_count ?? "-"}</dd></div>
              <div><dt>Chunks</dt><dd>{status?.chunk_count ?? "-"}</dd></div>
              <div><dt>FAISS</dt><dd>{ready ? "就绪" : "未就绪"}</dd></div>
            </dl>
            <button onClick={rebuild} disabled={busy === "rebuild"} className="primaryButton">
              {busy === "rebuild" ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />}
              重建索引
            </button>
            <label className="uploadButton">
              {busy === "upload" ? <Loader2 className="spin" size={18} /> : <Upload size={18} />}
              上传 PDF
              <input type="file" accept="application/pdf" onChange={upload} />
            </label>
          </div>

          <div className="panel documentPanel">
            <div className="panelTitle">
              <FileText size={18} />
              <h2>文档</h2>
            </div>
            <div className="documentList">
              {sortedDocs.map((doc) => (
                <div className="documentItem" key={doc.path} title={doc.filename}>
                  <span>{doc.filename}</span>
                  <small>{doc.uploaded ? "上传" : "Data"}</small>
                </div>
              ))}
            </div>
          </div>
        </aside>

        <section className="workspace">
          <form className="queryBox" onSubmit={ask}>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
            <button disabled={busy === "query" || !question.trim()} className="primaryButton">
              {busy === "query" ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
              查询
            </button>
          </form>

          {error && <div className="errorBox">{error}</div>}

          {answer && (
            <article className="answer">
              <div className="answerHeader">
                <div>
                  <h2>回答</h2>
                  <p>{answer.status} · 置信度 {answer.confidence.label} · {answer.system_trace.latency_ms} ms</p>
                </div>
              </div>
              <p className="answerText">{answer.final_answer.answer_text}</p>

              {answer.final_answer.summary_table.length > 0 && (
                <div className="tableWrap">
                  <table>
                    <thead>
                      <tr>
                        {TABLE_COLUMNS.map((column) => <th key={column.key}>{column.label}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {answer.final_answer.summary_table.map((row, index) => (
                        <tr key={index}>
                          {TABLE_COLUMNS.map((column) => (
                            <td key={column.key} className={`cell-${column.key}`}>
                              {formatCell(row[column.key] ?? row.paper_id, column.key)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="evidenceGrid">
                {answer.evidence_cards.map((card) => (
                  <section className="evidenceCard" key={card.evidence_id}>
                    <div className="citationLine">
                      <span>{card.page}</span>
                      <span>{card.section}</span>
                    </div>
                    <h3>{card.title}</h3>
                    <p>{card.snippet}</p>
                    <code>{shorten(card.evidence_id, 72)}</code>
                  </section>
                ))}
              </div>
            </article>
          )}
        </section>
      </section>
    </main>
  );
}

function formatCell(value: unknown, key: string) {
  if (Array.isArray(value)) {
    const joined = value.join(", ");
    return key === "evidence_ids" ? shorten(joined, 92) : shorten(joined, 92);
  }
  const text = String(value ?? "");
  if (key === "paper_title") return shorten(text, 110);
  return shorten(text, 150);
}

function shorten(value: string, maxLength: number) {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 1))}…`;
}
