import { Activity, Database, FileSpreadsheet, Gauge, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import VersionNav from "../components/VersionNav";

type DemoFile = {
  name: string;
  path: string;
  size_bytes: number;
  kind: string;
};

export default function V2MultimodalReport() {
  const [files, setFiles] = useState<DemoFile[]>([]);
  const [apiReady, setApiReady] = useState<boolean | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/v2/health").then((res) => res.json()),
      fetch("/api/v2/demo/files").then((res) => res.json())
    ]).then(([health, demo]) => {
      setApiReady(Boolean(health.ok));
      setFiles(demo.files ?? []);
    }).catch(() => {
      setApiReady(false);
    });
  }, []);

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">V2 · Multimodal Report</p>
          <h1>运动数据分析报告</h1>
          <p>面向深度相机骨骼点、IMU 与后续 EMG 数据的独立版本页面</p>
        </div>
        <VersionNav active="v2" />
      </section>

      <section className="v2Layout">
        <section className="v2Intro">
          <div>
            <h2>V2 的第一步</h2>
            <p>
              这里会从“上传患者运动数据”开始，先解析 skeleton 与 IMU 文件，提取动作质量、稳定性、对称性、
              速度和活动范围等指标，再结合 V1 的文献证据生成专业报告。
            </p>
          </div>
          <button className="primaryButton disabledButton" type="button" disabled>
            <Upload size={18} />
            上传入口待开发
          </button>
        </section>

        <section className="v2StageGrid">
          <div className="stageItem">
            <Database size={20} />
            <h3>数据接入</h3>
            <p>支持 Kinect/深度相机骨骼点文件、IMU 表格，后续预留 EMG 文件。</p>
          </div>
          <div className="stageItem">
            <Gauge size={20} />
            <h3>特征分析</h3>
            <p>抽取关节轨迹、角速度、加速度峰值、动作周期和左右差异等指标。</p>
          </div>
          <div className="stageItem">
            <Activity size={20} />
            <h3>报告生成</h3>
            <p>生成面向康复训练的摘要、风险提示、证据解释和建议，不替代医生诊断。</p>
          </div>
        </section>

        <section className="panel">
          <div className="panelTitle">
            <FileSpreadsheet size={18} />
            <h2>演示数据探测</h2>
          </div>
          <p className="mutedLine">后端状态：{apiReady === null ? "检查中" : apiReady ? "就绪" : "未连接"}</p>
          <div className="demoFileList">
            {files.length === 0 && <p className="mutedLine">尚未发现演示数据文件。</p>}
            {files.map((file) => (
              <div className="demoFileItem" key={file.path}>
                <span>{file.name}</span>
                <small>{file.kind} · {formatBytes(file.size_bytes)}</small>
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
