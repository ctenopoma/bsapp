from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import session, rag

app = FastAPI(title="BSapp Backend", version="0.1.0")

# CORS設定 (Tauriからのアクセスを許可)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発用。本番では変更を検討
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
