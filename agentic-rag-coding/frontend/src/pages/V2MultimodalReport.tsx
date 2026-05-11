import { Activity, Database, FileSpreadsheet, Gauge, Loader2, Upload } from "lucide-react";
import { ChangeEvent, useEffect, useState } from "react";
import VersionNav from "../components/VersionNav";

type V2File = {
  name: string;
  path: string;
  size_bytes: number;
  kind: string;
  source: string;
};

export default function V2MultimodalReport() {
  const [files, setFiles] = useState<V2File[]>([]);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    try {
      const [health, data] = await Promise.all([
        fetch("/api/v2/health").then((res) => res.json()),
        fetch("/api/v2/demo/files").then((res) => res.json())
      ]);
      setApiReady(Boolean(health.ok));
      setFiles(data.files ?? []);
    } catch {
      setApiReady(false);
    }
  }

  async function uploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMessage(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch("/api/v2/upload", { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setFiles(data.files ?? []);
      setMessage(`已上传：${data.filename}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "上传失败");
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">V2 · Multimodal Report</p>
          <h1>运动数据分析报告</h1>
          <p>面向深度相机骨骼点、IMU 与 EMG 数据的独立版本页面</p>
        </div>
        <VersionNav active="v2" />
      </section>

      <section className="v2Layout">
        <section className="v2Intro">
          <div>
            <h2>多模态康复数据工作台</h2>
            <p>
              上传患者运动数据后，系统会接收 skeleton、IMU 和 EMG 文件，围绕动作质量、稳定性、对称性、
              速度和活动范围等指标组织分析，并结合 V1 的文献证据生成专业报告。
            </p>
          </div>
          <label className="primaryButton v2UploadButton">
            {busy ? <Loader2 className="spin" size={18} /> : <Upload size={18} />}
            上传运动数据
            <input
              type="file"
              accept=".skeleton,.xlsx,.xls,.csv,.txt,.json,.mat"
              onChange={uploadFile}
              disabled={busy}
            />
          </label>
        </section>

        <section className="v2StageGrid">
          <div className="stageItem">
            <Database size={20} />
            <h3>数据接入</h3>
            <p>支持 Kinect/深度相机骨骼点文件、IMU 表格和 EMG 信号文件，按患者案例统一管理。</p>
          </div>
          <div className="stageItem">
            <Gauge size={20} />
            <h3>特征分析</h3>
            <p>抽取关节轨迹、角速度、加速度峰值、肌电强度、动作周期和左右差异等指标。</p>
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
            <h2>运动数据文件</h2>
          </div>
          <p className="mutedLine">后端状态：{apiReady === null ? "检查中" : apiReady ? "就绪" : "未连接"}</p>
          {message && <p className="statusLine">{message}</p>}
          <div className="demoFileList">
            {files.length === 0 && <p className="mutedLine">尚未发现运动数据文件。</p>}
            {files.map((file) => (
              <div className="demoFileItem" key={file.path}>
                <span>{file.name}</span>
                <small>{displayKind(file.kind)} · {file.source === "upload" ? "已上传" : "演示数据"} · {formatBytes(file.size_bytes)}</small>
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function displayKind(kind: string) {
  const labels: Record<string, string> = {
    skeleton: "骨骼点",
    imu: "IMU",
    emg: "EMG",
    sensor_table: "传感器表格",
    matlab_data: "MATLAB 数据"
  };
  return labels[kind] ?? kind;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
