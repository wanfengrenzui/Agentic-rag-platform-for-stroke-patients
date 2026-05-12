import { ArrowRight, BookOpenCheck, Home, LineChart, Sparkles } from "lucide-react";
import V1LiteratureRag from "./pages/V1LiteratureRag";
import V2MultimodalReport from "./pages/V2MultimodalReport";
import V3RagLlmReport from "./pages/V3RagLlmReport";

type Route = "/" | "/v1" | "/v2" | "/v3";

const route = normalizeRoute(window.location.pathname);

export default function App() {
  if (route === "/v1") return <V1LiteratureRag />;
  if (route === "/v2") return <V2MultimodalReport />;
  if (route === "/v3") return <V3RagLlmReport />;
  return <VersionHome />;
}

function VersionHome() {
  return (
    <main className="versionShell">
      <header className="versionHero">
        <div>
          <p className="eyebrow">Agentic RAG Platform</p>
          <h1>中风康复研究与报告平台</h1>
          <p>
            V1 保留文献证据绑定问答能力，V2 独立发展多模态运动数据分析和专业报告生成能力。
          </p>
        </div>
      </header>

      <section className="versionGrid">
        <a className="versionCard available" href="/v1">
          <div className="versionIcon">
            <BookOpenCheck size={24} />
          </div>
          <div>
            <span>V1 · Literature RAG</span>
            <h2>科研 PDF 问答工作台</h2>
            <p>基于本地 PDF、FAISS 检索和 DeepSeek 生成，输出中文回答、对比表格和页级证据卡片。</p>
          </div>
          <ArrowRight size={20} />
        </a>

        <a className="versionCard planned" href="/v2">
          <div className="versionIcon">
            <LineChart size={24} />
          </div>
          <div>
            <span>V2 · Multimodal Report</span>
            <h2>运动数据分析报告</h2>
            <p>面向深度相机骨骼点、IMU 和后续 EMG 数据，生成患者康复训练的结构化分析报告。</p>
          </div>
          <ArrowRight size={20} />
        </a>

        <a className="versionCard available" href="/v3">
          <div className="versionIcon">
            <Sparkles size={24} />
          </div>
          <div>
            <span>V3 · RAG + LLM</span>
            <h2>多模态报告智能解释层</h2>
            <p>在 V2 数据分析基础上接入本地文献 RAG 与 DeepSeek 解释层，生成更专业、更可追溯的康复报告。</p>
          </div>
          <ArrowRight size={20} />
        </a>
      </section>

      <section className="versionNote">
        <Home size={18} />
        <span>当前首页只做版本选择，后续每个版本都可以独立迭代、独立演示。</span>
      </section>
    </main>
  );
}

function normalizeRoute(pathname: string): Route {
  if (pathname === "/v1" || pathname.startsWith("/v1/")) return "/v1";
  if (pathname === "/v2" || pathname.startsWith("/v2/")) return "/v2";
  if (pathname === "/v3" || pathname.startsWith("/v3/")) return "/v3";
  return "/";
}
