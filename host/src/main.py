import logging
import time
import urllib.request
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
import os

# host/.env を明示的に読み込む
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bsapp.host")


# プロキシをバイパスするホストを NO_PROXY / no_proxy に追加
# 対象: クライアント←→ホスト (localhost)、ホスト←→LLM / Embedding / Rerank / Qdrant
def _setup_no_proxy() -> None:
    from urllib.parse import urlparse

    def _host_from_url(url: str) -> str:
        """URL からホスト部分だけ返す。パース失敗時は空文字。"""
        try:
            return urlparse(url).hostname or ""
        except Exception:
            return ""

    new_hosts: set[str] = {
        "localhost",
        "127.0.0.1",
        os.environ.get("LLM_IP", "127.0.0.1"),
        os.environ.get("EMBEDDING_IP", "127.0.0.1"),
        os.environ.get("RERANK_IP", "127.0.0.1"),
        _host_from_url(os.environ.get("QDRANT_URL", "http://localhost:6333")),
    }
    new_hosts.discard("")  # パース失敗の空文字を除外

    # NO_PROXY / no_proxy どちらか存在する方をベースにマージ
    existing_raw = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    existing = {h.strip() for h in existing_raw.split(",") if h.strip()}
    merged = ",".join(sorted(existing | new_hosts))
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged


def _log_startup_proxy_status() -> None:
    """起動時にプロキシ設定と各サービスのバイパス状況をログ出力する。"""
    from urllib.parse import urlparse

    logger.info("=" * 60)
    logger.info("HOST STARTUP")
    logger.info("=" * 60)

    # プロキシ環境変数を表示
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"]
    any_proxy = False
    for var in proxy_vars:
        val = os.environ.get(var)
        if val:
            logger.info(f"  {var}={val}")
            if var.upper() in ("HTTP_PROXY", "HTTPS_PROXY"):
                any_proxy = True
    if not any_proxy:
        logger.info("  (プロキシ環境変数なし)")

    # 各サービスのプロキシバイパス確認
    logger.info("--- Service proxy bypass check ---")
    services = {
        "LLM":       (os.environ.get("LLM_IP", ""),       os.environ.get("LLM_PORT", "")),
        "Embedding": (os.environ.get("EMBEDDING_IP", ""), os.environ.get("EMBEDDING_PORT", "")),
        "Rerank":    (os.environ.get("RERANK_IP", ""),    os.environ.get("RERANK_PORT", "")),
    }
    for name, (ip, port) in services.items():
        if not ip or ip in ("127.0.0.1", "localhost"):
            continue
        url = f"http://{ip}:{port}/" if port else f"http://{ip}/"
        bypassed = urllib.request.proxy_bypass(ip)
        if bypassed:
            logger.info(f"  {name}: {url}  proxy=BYPASS (OK)")
        else:
            logger.warning(f"  [WARNING] {name}: {url}  proxy=VIA PROXY")
            logger.warning(f"            Fix: NO_PROXY に {ip} を追加してください")

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant_host = urlparse(qdrant_url).hostname or ""
    if qdrant_host and qdrant_host not in ("127.0.0.1", "localhost"):
        bypassed = urllib.request.proxy_bypass(qdrant_host)
        if bypassed:
            logger.info(f"  Qdrant: {qdrant_url}  proxy=BYPASS (OK)")
        else:
            logger.warning(f"  [WARNING] Qdrant: {qdrant_url}  proxy=VIA PROXY")
            logger.warning(f"            Fix: NO_PROXY に {qdrant_host} を追加してください")

    logger.info("=" * 60)


_setup_no_proxy()
_log_startup_proxy_status()

from src.api import session, rag, settings, patent, update, auth, admin, user_data
from src.database import init_db

app = FastAPI(title="BSapp Backend", version="0.1.0")

# CORS設定 (Tauri + Web ブラウザからのアクセスを許可)
_extra_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://tauri.localhost",
        "tauri://localhost",
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        *_extra_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await init_db()
    logger.info("PostgreSQL tables ready")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """全HTTPリクエスト/レスポンスをログ出力する。"""
    start = time.time()
    client_host = request.client.host if request.client else "unknown"
    client_port = request.client.port if request.client else 0
    logger.info(f"[→Host] {request.method} {request.url.path}  from {client_host}:{client_port}")

    response = await call_next(request)

    elapsed_ms = (time.time() - start) * 1000
    logger.info(f"[Host→] {response.status_code} {request.url.path}  ({elapsed_ms:.1f}ms)")
    return response


# APIルーターの登録
app.include_router(session.router, prefix="/api/session", tags=["Session"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(patent.router, prefix="/api/patent", tags=["Patent"])
app.include_router(update.router, prefix="/api/update", tags=["Update"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(user_data.router, prefix="/api/data", tags=["UserData"])

@app.get("/")
def read_root():
    return {"status": "ok", "message": "BSapp Backend is running."}
