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


class QueryRequest(BaseModel):
    user_query: str = Field(min_length=1)
    paper_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=3, le=12)
    language: Literal["zh", "en"] = "zh"


settings = get_settings()
store = FaissRagStore(settings)
llm = DeepSeekClient(settings)

app = FastAPI(title="Agentic RAG", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
V2_DEMO_DIR = PROJECT_ROOT / "测试"


@app.get("/")
def root() -> dict:
    return {
        "name": "Agentic RAG backend",
        "status": "running",
        "versions": {
            "v1": "literature_rag",
            "v2": "multimodal_report",
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
    if not llm.configured:
        return FinalResponseContract(
            request_id=f"req_{int(started * 1000)}",
            status=FinalStatus.FAILED_CONTRACT_VALIDATION,
            final_answer=FinalAnswer(
                answer_text="DeepSeek API 尚未配置。请设置 DEEPSEEK_API_KEY 后再发起真实生成。",
                summary_table=[],
            ),
            evidence_cards=[],
            confidence=Confidence(label="low", reason="missing_deepseek_api_key", score=0.0),
            system_trace=SystemTrace(
                retrieval_rounds=0,
                critic_pass=False,
                latency_ms=int((time.time() - started) * 1000),
                timeout_stage="none",
            ),
        )

    request = UserRequestContract(
        request_id=f"req_{int(started * 1000)}",
        user_query=payload.user_query,
        task_template="literature_comparison",
        uploaded_paper_ids=payload.paper_ids,
        language=Language(payload.language),
    )


@app.get("/api/v2/health")
def v2_health() -> dict:
    return {
        "ok": True,
        "version": "v2",
        "status": "shell_ready",
        "demo_dir": str(V2_DEMO_DIR),
        "demo_dir_exists": V2_DEMO_DIR.exists(),
    }


@app.get("/api/v2/demo/files")
def v2_demo_files() -> dict:
    files = []
    if V2_DEMO_DIR.exists():
        for path in sorted(V2_DEMO_DIR.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file():
                continue
            files.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "kind": _v2_file_kind(path),
                }
            )
    return {"demo_dir": str(V2_DEMO_DIR), "files": files}
    workflow = AgenticRagWorkflow(retriever_tool=store, llm=llm, top_k_override=payload.top_k)
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
    if suffix == ".skeleton":
        return "skeleton"
    if suffix in {".xlsx", ".xls", ".csv"}:
        return "imu_or_table"
    return suffix.lstrip(".") or "unknown"
