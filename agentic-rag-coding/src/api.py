from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import get_settings
from src.contracts.rag_contract_models import (
    Confidence,
    FinalAnswer,
    FinalResponseContract,
    FinalStatus,
    Language,
    SystemTrace,
    UserRequestContract,
)
from src.llm.deepseek_client import DeepSeekClient
from src.orchestration.agentic_rag_workflow import AgenticRagWorkflow
from src.rag.index_store import FaissRagStore
from src.rag.web_search import WebAugmentedRetriever


class QueryRequest(BaseModel):
    user_query: str = Field(min_length=1)
    paper_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=3, le=12)
    language: Literal["zh", "en"] = "zh"
    allow_web_search: bool = False


settings = get_settings()
store = FaissRagStore(settings)
llm = DeepSeekClient(settings)

app = FastAPI(title="Agentic RAG", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
V2_DEMO_DIR = PROJECT_ROOT / "\u6d4b\u8bd5"
V2_UPLOAD_DIR = PROJECT_ROOT / "v2_data" / "cases" / "default"
V2_ALLOWED_SUFFIXES = {".skeleton", ".xlsx", ".xls", ".csv", ".txt", ".json", ".mat"}


@app.get("/")
def root() -> dict:
    return {
        "name": "Agentic RAG backend",
        "status": "running",
        "versions": {
            "v1": "literature_rag",
            "v2": "multimodal_report",
            "v3": "rag_llm_multimodal_report",
        },
        "frontend": "http://127.0.0.1:5173",
        "docs": "http://127.0.0.1:8000/docs",
        "health": "http://127.0.0.1:8000/api/health",
    }


@app.get("/api/health")
@app.get("/api/v1/health")
def health() -> dict:
    return {
        "ok": True,
        "version": "v1",
        "deepseek_configured": llm.configured,
        "deepseek_model": settings.deepseek_model,
        "data_dir": str(settings.data_dir),
    }


@app.get("/api/documents")
@app.get("/api/v1/documents")
def documents() -> dict:
    return {"documents": store.list_documents()}


@app.get("/api/index/status")
@app.get("/api/v1/index/status")
def index_status() -> dict:
    return store.status()


@app.post("/api/index/rebuild")
@app.post("/api/v1/index/rebuild")
def rebuild_index() -> dict:
    try:
        return store.rebuild()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to rebuild index: {exc}") from exc


@app.post("/api/upload")
@app.post("/api/v1/upload")
def upload_pdf(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = _safe_upload_path(settings.upload_dir, file.filename)
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return {"filename": target.name, "path": str(target), "documents": store.list_documents()}


@app.post("/api/query", response_model=FinalResponseContract)
@app.post("/api/v1/query", response_model=FinalResponseContract)
def query(payload: QueryRequest) -> FinalResponseContract:
    started = time.time()
    request = UserRequestContract(
        request_id=f"req_{int(started * 1000)}",
        user_query=payload.user_query,
        task_template="literature_comparison",
        uploaded_paper_ids=payload.paper_ids,
        language=Language(payload.language),
    )
    retriever_tool = WebAugmentedRetriever(store) if payload.allow_web_search else store
    workflow = AgenticRagWorkflow(retriever_tool=retriever_tool, llm=llm, top_k_override=payload.top_k)
    result = workflow.run(request)
    if isinstance(result, FinalResponseContract):
        return result
    return FinalResponseContract(
        request_id=result.request_id,
        status=FinalStatus.NEED_USER_CONFIRMATION,
        final_answer=FinalAnswer(answer_text=result.partial_answer, summary_table=[]),
        evidence_cards=[],
        confidence=Confidence(label="medium", reason="timeout_confirmation_required", score=0.5),
        system_trace=SystemTrace(
            retrieval_rounds=0,
            critic_pass=False,
            latency_ms=int((time.time() - started) * 1000),
            timeout_stage=result.timeout_stage,
        ),
    )


@app.get("/api/v2/health")
def v2_health() -> dict:
    return {
        "ok": True,
        "version": "v2",
        "status": "shell_ready",
        "demo_dir": str(V2_DEMO_DIR),
        "demo_dir_exists": V2_DEMO_DIR.exists(),
        "upload_dir": str(V2_UPLOAD_DIR),
    }


@app.get("/api/v3/health")
def v3_health() -> dict:
    return {
        "ok": True,
        "version": "v3",
        "status": "rag_llm_ready" if llm.configured else "rag_ready_llm_not_configured",
        "deepseek_configured": llm.configured,
        "local_rag_index": store.status().get("index_exists", False),
        "web_search": "available_on_v1_query",
    }


@app.get("/api/v2/demo/files")
def v2_demo_files() -> dict:
    return {"demo_dir": str(V2_DEMO_DIR), "upload_dir": str(V2_UPLOAD_DIR), "files": _v2_list_files()}


@app.post("/api/v2/upload")
def v2_upload_file(file: UploadFile = File(...)) -> dict:
    saved_file = _save_v2_upload(file)
    return {"filename": saved_file.name, "path": str(saved_file), "files": _v2_list_files()}


@app.post("/api/v2/uploads")
def v2_upload_files(files: list[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")
    saved_files = [_save_v2_upload(file) for file in files]
    return {
        "filenames": [path.name for path in saved_files],
        "count": len(saved_files),
        "files": _v2_list_files(),
    }


@app.post("/api/v2/report/generate")
def v2_generate_report() -> dict:
    files = _v2_list_files()
    if not files:
        raise HTTPException(status_code=400, detail="Please upload movement data files before generating a report.")

    modality_counts: dict[str, int] = {}
    total_bytes = 0
    for file in files:
        kind = str(file["kind"])
        modality_counts[kind] = modality_counts.get(kind, 0) + 1
        total_bytes += int(file["size_bytes"])

    file_summary = "、".join(f"{_v2_kind_label(kind)} {count} 个" for kind, count in modality_counts.items())
    has_skeleton = modality_counts.get("skeleton", 0) > 0
    has_imu = modality_counts.get("imu", 0) > 0 or modality_counts.get("sensor_table", 0) > 0
    has_emg = modality_counts.get("emg", 0) > 0

    observations = [
        f"本次报告接收 {len(files)} 个运动数据文件，合计 {_format_bytes(total_bytes)}，包含{file_summary}。",
        "已建立患者案例级文件清单，可用于后续同步解析、质量检查和特征提取。",
    ]
    if has_skeleton:
        observations.append("骨骼点数据可用于关节轨迹、活动范围、动作阶段和姿态稳定性分析。")
    if has_imu:
        observations.append("IMU/传感器表格数据可用于加速度、角速度、峰值变化和动作节律分析。")
    if has_emg:
        observations.append("EMG 数据可用于肌肉激活强度、激活时序和疲劳趋势分析。")

    recommendations = [
        "优先完成文件时间轴对齐，确保骨骼点、IMU 和 EMG 信号可以按动作阶段对应。",
        "对每个训练动作输出动作质量、稳定性、对称性、速度和活动范围五类指标。",
        "将异常指标与 V1 文献证据绑定，生成可追溯的康复训练解释。",
    ]

    return {
        "status": "completed",
        "title": "多模态康复运动数据初步分析报告",
        "summary": "系统已完成数据接收与报告草案生成。当前报告聚焦数据构成、可分析指标和下一步解释路径。",
        "file_count": len(files),
        "modalities": [_v2_kind_label(kind) for kind in modality_counts],
        "steps": [
            {"name": "数据文件检查", "status": "completed", "detail": f"识别到 {len(files)} 个运动数据文件。"},
            {"name": "模态类型归类", "status": "completed", "detail": f"包含{file_summary}。"},
            {"name": "可分析指标规划", "status": "completed", "detail": "已规划动作质量、稳定性、对称性、速度和活动范围指标。"},
            {"name": "报告草案生成", "status": "completed", "detail": "已生成初步分析报告。"},
        ],
        "observations": observations,
        "recommendations": recommendations,
        "files": files,
    }


def _save_v2_upload(file: UploadFile) -> Path:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in V2_ALLOWED_SUFFIXES:
        supported = ", ".join(sorted(V2_ALLOWED_SUFFIXES))
        raise HTTPException(status_code=400, detail=f"Unsupported V2 data file. Supported: {supported}")
    V2_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = _safe_upload_path(V2_UPLOAD_DIR, file.filename)
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return target


def _safe_upload_path(upload_dir: Path, filename: str) -> Path:
    raw_name = Path(filename).name
    target = upload_dir / raw_name
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = upload_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _v2_file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix == ".skeleton":
        return "skeleton"
    if "emg" in name:
        return "emg"
    if "imu" in name:
        return "imu"
    if suffix in {".xlsx", ".xls", ".csv"}:
        return "sensor_table"
    if suffix == ".mat":
        return "matlab_data"
    return suffix.lstrip(".") or "unknown"


def _v2_kind_label(kind: str) -> str:
    labels = {
        "skeleton": "骨骼点",
        "imu": "IMU",
        "emg": "EMG",
        "sensor_table": "传感器表格",
        "matlab_data": "MATLAB 数据",
    }
    return labels.get(kind, kind)


def _format_bytes(bytes_count: int) -> str:
    if bytes_count < 1024:
        return f"{bytes_count} B"
    if bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    return f"{bytes_count / 1024 / 1024:.1f} MB"


def _v2_list_files() -> list[dict]:
    files = []
    for source, directory in (("demo", V2_DEMO_DIR), ("upload", V2_UPLOAD_DIR)):
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file():
                continue
            files.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "kind": _v2_file_kind(path),
                    "source": source,
                }
            )
    return files


@app.post("/api/v2/report/analyze")
def v2_analyze_and_generate_report() -> dict:
    """Analyze uploaded data and generate rehabilitation report."""
    try:
        from src.multimodal.data_models import (
            AffectedSide,
            ConditionType,
            PatientCase,
        )
        from src.multimodal.feature_extractor import FeatureExtractorPipeline
        from src.multimodal.report_generator import RehabReportGenerator
        from src.multimodal.report_exporter import ReportExporter

        # Get uploaded files
        files = _v2_list_files()
        skeleton_file = None
        imu_file = None
        emg_file = None

        # If no files uploaded, try to use sample data
        if not files:
            sample_dir = PROJECT_ROOT / "sample_data"
            if (sample_dir / "skeleton_sample.csv").exists():
                skeleton_file = str(sample_dir / "skeleton_sample.csv")
            if (sample_dir / "imu_sample.csv").exists():
                imu_file = str(sample_dir / "imu_sample.csv")
            if (sample_dir / "emg_sample.csv").exists():
                emg_file = str(sample_dir / "emg_sample.csv")
        else:
            for f in files:
                if f["kind"] == "skeleton":
                    skeleton_file = f["path"]
                elif f["kind"] == "imu":
                    imu_file = f["path"]
                elif f["kind"] == "emg":
                    emg_file = f["path"]

        # Extract features from available files
        features, _ = FeatureExtractorPipeline.extract_all(
            skeleton_path=skeleton_file,
            imu_path=imu_file,
            emg_path=emg_file,
        )

        # Create patient case
        case = PatientCase(
            case_id=f"case_frontend_{int(time.time() * 1000)}",
            subject_code="S_Demo" if not files else "S_Custom",
            age=55,
            sex="male",
            condition=ConditionType.POST_STROKE,
            affected_side=AffectedSide.RIGHT,
            time_since_onset_months=12,
            assessment_date="2026-05-11",
            notes="Web frontend demo case" if not files else f"Custom case with {len(files)} files",
        )

        features.case_id = case.case_id

        # Generate report
        generator = RehabReportGenerator()
        report = generator.generate_report(case, features)

        # Export to multiple formats
        exporter = ReportExporter()
        markdown_content = exporter.to_markdown(report)
        json_content = exporter.to_json(report)
        import json as json_module
        json_payload = json_module.loads(json_content)

        # Save outputs
        output_dir = PROJECT_ROOT / "output"
        output_dir.mkdir(exist_ok=True)

        md_file = output_dir / f"{report.report_id}.md"
        json_file = output_dir / f"{report.report_id}.json"

        md_file.write_text(markdown_content, encoding="utf-8")
        json_file.write_text(json_content, encoding="utf-8")

        return {
            "status": "success",
            "report_id": report.report_id,
            "markdown_content": markdown_content,
            "json_content": json_payload,
            "metadata": {
                "case_id": case.case_id,
                "subject_code": case.subject_code,
                "confidence_level": report.confidence_level,
                "quality_score": report.overall_quality_score,
                "data_evidence_count": len(report.data_evidence_list),
                "claims_count": len(report.claims),
            },
        }

    except Exception as e:
        import traceback
        error_detail = f"Failed to generate report: {str(e)}"
        print(f"Error: {error_detail}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_detail) from e


@app.post("/api/v3/report/generate")
def v3_generate_rag_llm_report() -> dict:
    """Generate V3 report with local data, local literature RAG, and optional LLM interpretation."""
    try:
        return _generate_multimodal_report_response(
            version="v3",
            use_literature_rag=True,
            use_llm=True,
        )
    except Exception as e:
        import traceback
        error_detail = f"Failed to generate V3 report: {str(e)}"
        print(f"Error: {error_detail}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_detail) from e


def _generate_multimodal_report_response(version: str, use_literature_rag: bool, use_llm: bool) -> dict:
    from src.multimodal.data_models import (
        AffectedSide,
        ConditionType,
        PatientCase,
    )
    from src.multimodal.feature_extractor import FeatureExtractorPipeline
    from src.multimodal.report_generator import RehabReportGenerator
    from src.multimodal.report_exporter import ReportExporter

    files = _v2_list_files()
    skeleton_file = None
    imu_file = None
    emg_file = None

    if not files:
        sample_dir = PROJECT_ROOT / "sample_data"
        if (sample_dir / "skeleton_sample.csv").exists():
            skeleton_file = str(sample_dir / "skeleton_sample.csv")
        if (sample_dir / "imu_sample.csv").exists():
            imu_file = str(sample_dir / "imu_sample.csv")
        if (sample_dir / "emg_sample.csv").exists():
            emg_file = str(sample_dir / "emg_sample.csv")
    else:
        for f in files:
            if f["kind"] == "skeleton":
                skeleton_file = f["path"]
            elif f["kind"] == "imu":
                imu_file = f["path"]
            elif f["kind"] == "emg":
                emg_file = f["path"]

    features, _ = FeatureExtractorPipeline.extract_all(
        skeleton_path=skeleton_file,
        imu_path=imu_file,
        emg_path=emg_file,
    )

    case = PatientCase(
        case_id=f"case_{version}_{int(time.time() * 1000)}",
        subject_code="S_Demo" if not files else "S_Custom",
        age=55,
        sex="male",
        condition=ConditionType.POST_STROKE,
        affected_side=AffectedSide.RIGHT,
        time_since_onset_months=12,
        assessment_date="2026-05-11",
        notes=f"{version.upper()} case with {len(files)} files" if files else f"{version.upper()} demo case",
    )
    features.case_id = case.case_id

    generator = RehabReportGenerator(
        deepseek_client=llm if use_llm else None,
        rag_store=store if use_literature_rag else None,
    )
    report = generator.generate_report(case, features)

    exporter = ReportExporter()
    markdown_content = exporter.to_markdown(report)
    json_content = exporter.to_json(report)
    import json as json_module
    json_payload = json_module.loads(json_content)

    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    md_file = output_dir / f"{report.report_id}.md"
    json_file = output_dir / f"{report.report_id}.json"
    md_file.write_text(markdown_content, encoding="utf-8")
    json_file.write_text(json_content, encoding="utf-8")

    return {
        "status": "success",
        "version": version,
        "report_id": report.report_id,
        "markdown_content": markdown_content,
        "json_content": json_payload,
        "metadata": {
            "case_id": case.case_id,
            "subject_code": case.subject_code,
            "confidence_level": report.confidence_level,
            "quality_score": report.overall_quality_score,
            "data_evidence_count": len(report.data_evidence_list),
            "literature_evidence_count": len(report.literature_evidence_list),
            "claims_count": len(report.claims),
            "llm_enabled": bool(use_llm and llm.configured),
            "rag_enabled": use_literature_rag,
        },
    }


@app.get("/api/v2/report/{report_id}")
def v2_get_report(report_id: str) -> dict:
    """Get a previously generated report."""
    try:
        output_dir = PROJECT_ROOT / "output"
        md_file = output_dir / f"{report_id}.md"
        json_file = output_dir / f"{report_id}.json"

        if not md_file.exists():
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

        import json as json_module

        markdown_content = md_file.read_text(encoding="utf-8")
        json_content = json_module.loads(json_file.read_text(encoding="utf-8"))

        return {
            "status": "success",
            "report_id": report_id,
            "markdown_content": markdown_content,
            "json_content": json_content,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve report: {str(e)}") from e


@app.get("/api/v2/reports")
def v2_list_reports() -> dict:
    """List all generated reports."""
    output_dir = PROJECT_ROOT / "output"
    reports = []

    if output_dir.exists():
        for md_file in sorted(output_dir.glob("*.md"), reverse=True):
            report_id = md_file.stem
            json_file = output_dir / f"{report_id}.json"

            if json_file.exists():
                try:
                    import json as json_module

                    json_data = json_module.loads(json_file.read_text(encoding="utf-8"))
                    reports.append(
                        {
                            "report_id": report_id,
                            "generated_at": json_data.get("generated_at"),
                            "case_id": json_data.get("case_id"),
                            "confidence_level": json_data.get("confidence_level"),
                            "quality_score": json_data.get("overall_quality_score"),
                            "size_bytes": md_file.stat().st_size,
                        }
                    )
                except Exception:
                    pass

    return {
        "status": "success",
        "count": len(reports),
        "reports": reports,
    }
