import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Database,
  Download,
  FileText,
  Gauge,
  Loader2,
  UserRound
} from "lucide-react";
import { useState } from "react";
import "../styles.css";

interface ReportContent {
  report_id: string;
  markdown_content: string;
  json_content: Record<string, any>;
}

type ReportViewerProps = {
  endpoint?: string;
  title?: string;
  subtitle?: string;
  kicker?: string;
};

export default function ReportViewer({
  endpoint = "http://127.0.0.1:8000/api/v2/report/analyze",
  title = "康复运动数据分析报告",
  subtitle = "面向骨骼点、IMU 与 EMG 数据的横向评估看板",
  kicker = "Multimodal Assessment"
}: ReportViewerProps) {
  const [report, setReport] = useState<ReportContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateReport = async () => {
    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}: Failed to generate report`);
      }

      const jsonContent =
        typeof data.json_content === "string" ? JSON.parse(data.json_content) : data.json_content ?? {};

      setReport({
        report_id: data.report_id,
        markdown_content: data.markdown_content,
        json_content: jsonContent
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
    } finally {
      setLoading(false);
    }
  };

  const downloadMarkdown = () => {
    if (!report) return;
    const element = document.createElement("a");
    element.setAttribute("href", `data:text/markdown;charset=utf-8,${encodeURIComponent(report.markdown_content)}`);
    element.setAttribute("download", `${report.report_id}.md`);
    element.style.display = "none";
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const confidenceLevel = getNumber(report?.json_content?.confidence_level);
  const qualityScore = getNumber(report?.json_content?.overall_quality_score);
  const dataEvidence = getArray(report?.json_content?.data_evidence_list);
  const claims = getArray(report?.json_content?.claims);
  const basicInfo = report?.json_content?.basic_info ?? {};
  const analysisCards = report ? buildAnalysisCards(report.json_content) : [];
  const recommendations = report ? summarizeText(report.json_content.follow_up_recommendations, 4) : [];
  const limitations = report ? summarizeText(report.json_content.risk_and_limitation, 4) : [];

  return (
    <div className="reportViewer">
      <div className="reportControl">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>

        <button onClick={generateReport} disabled={loading} className="generateBtn">
          {loading ? (
            <>
              <Loader2 size={18} className="icon-spin" />
              生成中...
            </>
          ) : (
            <>
              <FileText size={18} />
              生成报告
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="alert error">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {report && (
        <div className="reportContainer">
          <div className="reportDashboardHeader">
            <div>
              <p className="reportKicker">{kicker}</p>
              <h2>{title}</h2>
              <span className="reportId">报告编号: {report.report_id}</span>
              <div className="reportMetrics">
                <MetricCard icon={<Gauge size={20} />} label="置信度" value={`${(confidenceLevel * 100).toFixed(1)}%`} tone="blue" />
                <MetricCard icon={<Activity size={20} />} label="数据质量" value={`${(qualityScore * 100).toFixed(1)}%`} tone="green" />
                <MetricCard icon={<Database size={20} />} label="证据数量" value={String(dataEvidence.length)} tone="orange" />
                <MetricCard icon={<CheckCircle2 size={20} />} label="分析结论" value={String(claims.length)} tone="red" />
              </div>
            </div>
            <button onClick={downloadMarkdown} className="downloadBtn" title="下载 Markdown 报告">
              <Download size={18} />
              下载
            </button>
          </div>

          <div className="reportDashboard">
            <section className="reportCard reportSubjectCard">
              <div className="reportCardTitle">
                <UserRound size={20} />
                <h3>个体信息</h3>
              </div>
              <div className="subjectGrid">
                <InfoCell label="对象" value={basicInfo.subject_code ?? "未知"} />
                <InfoCell label="年龄/性别" value={`${basicInfo.age ?? "未知"} / ${basicInfo.sex ?? "未知"}`} />
                <InfoCell label="诊断" value={basicInfo.condition ?? "未知"} />
                <InfoCell label="患侧" value={basicInfo.affected_side ?? "未知"} />
              </div>
            </section>

            <section className="reportCard reportFindingsCard">
              <div className="reportCardTitle">
                <Activity size={20} />
                <h3>核心分析概览</h3>
              </div>
              <div className="analysisGrid">
                {analysisCards.map((item) => (
                  <article className="analysisCard" key={item.title}>
                    <span>{item.title}</span>
                    <p>{item.text}</p>
                  </article>
                ))}
              </div>
            </section>

            <section className="reportCard reportEvidenceCard">
              <div className="reportCardTitle">
                <Database size={20} />
                <h3>数据证据</h3>
              </div>
              <div className="evidenceTable">
                {dataEvidence.slice(0, 5).map((item: any) => (
                  <div className="evidenceRow" key={item.data_evidence_id ?? item.feature_name}>
                    <strong>{formatFeatureName(item.feature_name)}</strong>
                    <span>{formatEvidenceValue(item.value, item.unit)}</span>
                    <small>{item.interpretation ?? "暂无解释"}</small>
                  </div>
                ))}
                {dataEvidence.length === 0 && <p className="mutedLine">暂无可展示的数据证据。</p>}
              </div>
            </section>

            <section className="reportCard reportAdviceCard">
              <div className="reportCardTitle">
                <FileText size={20} />
                <h3>建议与限制</h3>
              </div>
              <div className="compactList">
                {[...recommendations, ...limitations].slice(0, 6).map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            </section>
          </div>

          {claims.length > 0 && (
            <div className="reportClaims">
              <h3>专业分析结论</h3>
              <div className="claimsList">
                {claims.map((claim: any, idx: number) => (
                  <div key={idx} className={`claimItem risk-${claim.risk_level || "medium"}`}>
                    <CheckCircle2 size={18} className="claimIcon" />
                    <div className="claimContent">
                      <p>{claim.claim_text || claim.text || String(claim)}</p>
                      {claim.risk_level && <span className="riskBadge">{claim.risk_level.toUpperCase()}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <details className="fullReportDetails">
            <summary>查看完整 Markdown 报告</summary>
            <div className="reportContent">
              <ReportRenderer markdown={report.markdown_content} />
            </div>
          </details>
        </div>
      )}

      {!report && !error && !loading && (
        <div className="reportEmpty">
          <FileText size={48} />
          <p>点击“生成报告”查看横向评估看板</p>
          <p style={{ fontSize: "13px", color: "#6b7a90", marginTop: "8px" }}>
            支持示例数据或上传的自定义数据
          </p>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  tone
}: {
  icon: JSX.Element;
  label: string;
  value: string;
  tone: "blue" | "green" | "orange" | "red";
}) {
  return (
    <div className={`metric metric-${tone}`}>
      {icon}
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

function InfoCell({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="infoCell">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function buildAnalysisCards(json: Record<string, any>) {
  return [
    { title: "步态时空", text: firstMeaningfulLine(json.gait_spatiotemporal_analysis) },
    { title: "骨骼关节", text: firstMeaningfulLine(json.skeleton_joint_analysis) },
    { title: "IMU 信号", text: firstMeaningfulLine(json.imu_signal_analysis) },
    { title: "EMG 肌电", text: firstMeaningfulLine(json.emg_muscle_analysis) }
  ].filter((item) => item.text);
}

function firstMeaningfulLine(value: unknown) {
  return summarizeText(value, 1)[0] ?? "";
}

function summarizeText(value: unknown, limit: number) {
  if (typeof value !== "string") return [];
  return value
    .split("\n")
    .filter((line) => !line.trim().startsWith("#"))
    .map((line) =>
      line
        .replace(/^\d+\.\s*/, "")
        .replace(/^-\s*/, "")
        .replace(/\*\*/g, "")
        .trim()
    )
    .filter((line) => line && line !== "---")
    .slice(0, limit);
}

function getNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function getArray(value: unknown) {
  return Array.isArray(value) ? value : [];
}

function formatFeatureName(name: unknown) {
  const labels: Record<string, string> = {
    left_right_step_symmetry: "左右步态对称",
    cadence_steps_per_min: "步频",
    left_right_peak_asymmetry: "IMU 不对称",
    co_activation_proxy: "肌肉协同激活"
  };
  return typeof name === "string" ? labels[name] ?? name : "指标";
}

function formatEvidenceValue(value: unknown, unit: unknown) {
  const numeric = typeof value === "number" ? value.toFixed(Math.abs(value) >= 10 ? 1 : 2) : String(value ?? "N/A");
  return `${numeric}${unit ? ` ${unit}` : ""}`;
}

function ReportRenderer({ markdown }: { markdown: string }) {
  const lines = markdown.split("\n");
  const elements: JSX.Element[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i++;
      continue;
    }

    if (line.startsWith("# ")) {
      elements.push(<h1 key={i}>{line.slice(2)}</h1>);
      i++;
    } else if (line.startsWith("## ")) {
      elements.push(<h2 key={i}>{line.slice(3)}</h2>);
      i++;
    } else if (line.startsWith("### ")) {
      elements.push(<h3 key={i}>{line.slice(4)}</h3>);
      i++;
    } else if (line.startsWith("**") && line.endsWith("**")) {
      elements.push(
        <p key={i}>
          <strong>{line.slice(2, -2)}</strong>
        </p>
      );
      i++;
    } else if (line.includes("**")) {
      const parts = line.split(/\*\*([^*]+)\*\*/);
      const jsxParts = parts.map((part, idx) => (idx % 2 === 1 ? <strong key={idx}>{part}</strong> : part));
      elements.push(<p key={i}>{jsxParts}</p>);
      i++;
    } else if (line.startsWith("- ")) {
      const listItems: JSX.Element[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) {
        listItems.push(<li key={i}>{lines[i].slice(2)}</li>);
        i++;
      }
      elements.push(<ul key={`ul-${i}`}>{listItems}</ul>);
    } else if (line.match(/^\d+\.\s/)) {
      const listItems: JSX.Element[] = [];
      while (i < lines.length && lines[i].match(/^\d+\.\s/)) {
        const content = lines[i].replace(/^\d+\.\s/, "");
        listItems.push(<li key={i}>{content}</li>);
        i++;
      }
      elements.push(<ol key={`ol-${i}`}>{listItems}</ol>);
    } else if (line.trim() === "---") {
      elements.push(<hr key={i} />);
      i++;
    } else {
      elements.push(<p key={i}>{line}</p>);
      i++;
    }
  }

  return <>{elements}</>;
}
