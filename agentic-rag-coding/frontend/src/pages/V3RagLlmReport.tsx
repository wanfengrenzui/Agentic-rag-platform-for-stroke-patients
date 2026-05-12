import { Database, Globe2, Sparkles } from "lucide-react";
import ReportViewer from "../components/ReportViewer";
import VersionNav from "../components/VersionNav";

export default function V3RagLlmReport() {
  return (
    <main className="shell systemShell">
      <section className="topbar systemTopbar">
        <div>
          <p className="eyebrow">V3 · RAG + LLM Report</p>
          <h1>多模态报告智能解释层</h1>
          <p>本地运动数据分析、本地文献 RAG 与可选 LLM 解释增强的整合版本</p>
        </div>
        <VersionNav active="v3" />
      </section>

      <section className="v3CapabilityStrip">
        <article>
          <Database size={20} />
          <div>
            <strong>本地数据</strong>
            <span>skeleton / IMU / EMG 特征提取</span>
          </div>
        </article>
        <article>
          <Globe2 size={20} />
          <div>
            <strong>文献 RAG</strong>
            <span>优先绑定本地 PDF 证据</span>
          </div>
        </article>
        <article>
          <Sparkles size={20} />
          <div>
            <strong>LLM 解释</strong>
            <span>配置 DeepSeek 后自动增强报告语言</span>
          </div>
        </article>
      </section>

      <section className="v2Layout reportViewerSection">
        <ReportViewer
          endpoint="http://127.0.0.1:8000/api/v3/report/generate"
          title="V3 RAG + LLM 康复评估报告"
          subtitle="先提取本地运动特征，再检索文献证据，最后由 LLM 生成专业解释层"
          kicker="RAG + LLM Interpretation"
        />
      </section>
    </main>
  );
}
