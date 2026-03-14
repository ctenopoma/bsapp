from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..app_settings import get_settings

router = APIRouter()


class RagAddRequest(BaseModel):
    tag: str
    text: str


class RagInitRequest(BaseModel):
    tag: str


@router.get("/types")
def get_rag_types():
    """利用可能なRAG種別の一覧を返す。host の settings.json で管理される。"""
    settings = get_settings()
    return {"types": [t.model_dump() for t in settings.available_rag_types]}


@router.post("/init")
def init_rag(req: RagInitRequest):
    # TODO: Qdrantの該当タグデータを全削除
    return {"status": "success"}


@router.post("/add")
def add_rag(req: RagAddRequest):
    # TODO: チャンキング＆エンベディング開始
    return {"job_id": "mock_job_id_rag_456"}


@router.get("/status/{job_id}")
def get_rag_status(job_id: str):
    # TODO: 追加処理のポーリング用
    return {"status": "completed"}
