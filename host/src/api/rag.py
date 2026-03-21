import uuid
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ..app_settings import get_settings
from ..rag_manager import rag_manager
from ..chunker import CHUNK_STRATEGIES

router = APIRouter()

# インメモリジョブ状態管理
_job_status: dict = {}


class RagAddRequest(BaseModel):
    tag: str
    text: str
    strategy: str = "recursive_semantic"
    chunk_size: int = 800
    overlap: int = 150
    window_size: int = 5
    overlap_sentences: int = 1
    breakpoint_percentile: int = 85


class RagInitRequest(BaseModel):
    tag: str


@router.get("/types")
def get_rag_types():
    """利用可能なRAG種別の一覧を返す。host の settings.json で管理される。"""
    settings = get_settings()
    return {"types": [t.model_dump() for t in settings.available_rag_types]}


@router.post("/init")
def init_rag(req: RagInitRequest):
    """Qdrantの該当タグコレクションを削除・再作成する"""
    try:
        rag_manager.init_collection(req.tag)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error_msg": str(e)}


@router.get("/chunk_strategies")
def get_chunk_strategies():
    """利用可能なチャンキング戦略の一覧を返す"""
    return {"strategies": CHUNK_STRATEGIES}


@router.post("/add")
def add_rag(req: RagAddRequest, background_tasks: BackgroundTasks):
    """テキストをチャンキング＆エンベディングしてQdrantに保存する（非同期）"""
    job_id = str(uuid.uuid4())
    _job_status[job_id] = {"status": "processing"}
    background_tasks.add_task(
        rag_manager.add_text_background,
        req.tag, req.text, job_id, _job_status,
        req.strategy, req.chunk_size, req.overlap,
        req.window_size, req.overlap_sentences, req.breakpoint_percentile,
    )
    return {"job_id": job_id}


@router.get("/status/{job_id}")
def get_rag_status(job_id: str):
    """追加処理のポーリング用"""
    info = _job_status.get(job_id, {"status": "error", "error_msg": "job not found"})
    return info


@router.get("/collections")
def list_collections():
    """登録済みタグコレクションの一覧とチャンク数を返す"""
    return {"collections": rag_manager.list_collections()}


@router.get("/chunks/{tag}")
def get_chunks(tag: str, limit: int = 200):
    """タグのチャンク一覧を返す"""
    return rag_manager.get_chunks(tag, limit=limit)


@router.get("/search")
def search_rag(tag: str, query: str, limit: int = 3):
    """Playground用: 本番と同じ検索処理をスコア付きで返す"""
    try:
        return rag_manager.search_with_scores(tag, query, limit=limit)
    except Exception as e:
        return {"results": [], "context": "", "error": str(e)}


@router.delete("/chunks/{tag}/{chunk_id}")
def delete_chunk(tag: str, chunk_id: str):
    """指定チャンクを1件削除する"""
    try:
        rag_manager.delete_chunk(tag, chunk_id)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error_msg": str(e)}
