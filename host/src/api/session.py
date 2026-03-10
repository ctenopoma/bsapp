from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Dict

router = APIRouter()


class Persona(BaseModel):
    id: str
    name: str
    role: str
    task: str


class MessageHistory(BaseModel):
    id: str
    session_id: str
    theme: str
    agent_name: str
    content: str
    turn_order: int


class SessionStartRequest(BaseModel):
    themes: List[str]
    personas: List[Persona]
    history: List[MessageHistory] = []


@router.post("/start")
def start_session(req: SessionStartRequest):
    # TODO: オンメモリにセッション空間を作成
    return {"session_id": "mock_session_id_123"}


@router.post("/{session_id}/turn/start")
def start_turn(session_id: str):
    # TODO: バックグラウンドで生成開始
    return {"job_id": "mock_job_id_turn_456"}


@router.get("/{session_id}/turn/status/{job_id}")
def get_turn_status(session_id: str, job_id: str):
    # TODO: ポーリング用状態取得
    return {
        "status": "completed",
        "agent_name": "Mock Agent",
        "message": "This is a mock response from the agent.",
        "is_theme_end": False,
    }


@router.post("/{session_id}/summarize/start")
def start_summarize(session_id: str):
    # TODO: テーマ終了時のまとめ生成
    return {"job_id": "mock_job_id_sum_789"}


@router.get("/{session_id}/summarize/status/{job_id}")
def get_summarize_status(session_id: str, job_id: str):
    # TODO: まとめポーリング用状態取得
    return {
        "status": "completed",
        "summary_text": "This is a mock summary of the discussion.",
    }


@router.post("/{session_id}/end")
def end_session(session_id: str):
    # TODO: オンメモリのセッションを破棄
    return {"status": "success"}
