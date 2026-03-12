from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
import os

# host/.env を明示的に読み込む
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# プロキシをバイパスするホストを NO_PROXY / no_proxy に追加
# 対象: クライアント←→ホスト (localhost) と ホスト←→LLM (LLM_IP)
def _setup_no_proxy() -> None:
    llm_ip = os.environ.get("LLM_IP", "127.0.0.1")
    new_hosts = {"localhost", "127.0.0.1", llm_ip}
    existing = {h.strip() for h in os.environ.get("NO_PROXY", "").split(",") if h.strip()}
    merged = ",".join(sorted(existing | new_hosts))
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged

_setup_no_proxy()

from src.api import session, rag, settings

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
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])

@app.get("/")
def read_root():
    return {"status": "ok", "message": "BSapp Backend is running."}
