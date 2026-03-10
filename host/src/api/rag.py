from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class RagAddRequest(BaseModel):
    tag: str
    text: str


class RagInitRequest(BaseModel):
    tag: str


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
