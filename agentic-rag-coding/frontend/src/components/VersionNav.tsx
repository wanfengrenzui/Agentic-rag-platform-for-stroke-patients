import { Activity, BookOpenCheck, Home, Sparkles } from "lucide-react";

export default function VersionNav({ active }: { active: "v1" | "v2" | "v3" }) {
  return (
    <nav className="versionNav" aria-label="版本导航">
      <a className={active === "v1" ? "active" : ""} href="/v1">
        <BookOpenCheck size={16} />
        V1 文献 RAG
      </a>
      <a className={active === "v2" ? "active" : ""} href="/v2">
        <Activity size={16} />
        V2 多模态报告
      </a>
      <a className={active === "v3" ? "active" : ""} href="/v3">
        <Sparkles size={16} />
        V3 RAG + LLM
      </a>
      <a href="/">
        <Home size={16} />
        版本首页
      </a>
    </nav>
  );
}
