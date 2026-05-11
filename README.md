# Agentic RAG Platform for Stroke Patients

Agentic RAG web MVP for local academic PDFs about stroke, gait analysis, IMU/EMG sensing, and clinical decision-support research.

The app uses:

- FastAPI backend
- React/Vite frontend
- FAISS local vector index
- sentence-transformers local embeddings
- DeepSeek OpenAI-compatible chat API
- Raw PDFs from the repository `Data/` directory

## Project Layout

```text
.
├── Data/                         # Raw PDF corpus
├── PRD_Agentic_RAG_Contracts_V1.1.md
└── agentic-rag-coding/
    ├── src/                      # Backend, RAG, contracts, agents
    ├── tests/
    └── frontend/                 # React/Vite app
```

Generated artifacts are intentionally ignored:

- `agentic-rag-coding/storage/`
- `agentic-rag-coding/frontend/node_modules/`
- `agentic-rag-coding/frontend/dist/`
- `Data/uploads/`

## Backend Setup

```powershell
cd agentic-rag-coding
py -m pip install -r requirements.txt
$env:DEEPSEEK_API_KEY="your_deepseek_key"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
py -m src.main rebuild
py -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Backend links:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/health`

## Frontend Setup

```powershell
cd agentic-rag-coding/frontend
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1
```

Open:

```text
http://127.0.0.1:5173
```

## Verification

```powershell
cd agentic-rag-coding
py -m compileall .
py -m pytest -q

cd frontend
npm.cmd run build
```

## Notes

- Do not commit real API keys. Use environment variables or a local `.env` file.
- Rebuild the FAISS index after changing PDFs in `Data/`.
- Uploaded PDFs are saved to `Data/uploads/` locally and ignored by git.
