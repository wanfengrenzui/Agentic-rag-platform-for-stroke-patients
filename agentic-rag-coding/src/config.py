from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    upload_dir: Path
    storage_dir: Path
    faiss_index_path: Path
    metadata_path: Path
    embedding_model: str
    deepseek_api_key: str | None
    deepseek_model: str
    deepseek_base_url: str


def get_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", REPO_DIR / "Data")).resolve()
    storage_dir = Path(os.getenv("STORAGE_DIR", PROJECT_DIR / "storage")).resolve()
    return Settings(
        data_dir=data_dir,
        upload_dir=(data_dir / "uploads").resolve(),
        storage_dir=storage_dir,
        faiss_index_path=storage_dir / "faiss.index",
        metadata_path=storage_dir / "chunks.jsonl",
        embedding_model=os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
