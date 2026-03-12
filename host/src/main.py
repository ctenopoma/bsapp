from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

# host/.env を明示的に読み込む
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from src.api import session, rag

app = FastAPI(title="BSapp Backend", version="0.1.0")

# CORS設定 (Tauriからのアクセスを許可)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://tauri.localhost",
        "tauri://localhost"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIルーターの登録
app.include_router(session.router, prefix="/api/session", tags=["Session"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])

@app.get("/")
def read_root():
    return {"status": "ok", "message": "BSapp Backend is running."}
