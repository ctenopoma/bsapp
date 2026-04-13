import uuid
import json as _json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    SessionStartRequest,
    SessionStartResponse,
    TurnStartResponse,
    TurnStatusResponse,
    SummarizeStartResponse,
    SummarizeStatusResponse,
    FullSessionStatusResponse
)
from src.session_manager import session_manager
from src.agent_runner import agent_runner, create_llm, job_statuses
from src.database import get_db
from src.db_models import PatentCsv
from src.auth import require_approved
from src.db_models import User

logger = logging.getLogger("bsapp.session")

router = APIRouter()


class GenerateTitleRequest(BaseModel):
    themes: List[str]
    common_theme: str = ""


class GenerateTitleResponse(BaseModel):
    title: str


@router.post("/start", response_model=SessionStartResponse)
async def start_session(
    req: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    session_id = session_manager.start_session(req)
    session = session_manager.get_session(session_id)

    # csv_idが指定されていれば事前にDBからCSV行データをロードしてセッションにキャッシュ
    csv_ids_to_load: set[str] = set()
    if req.patent_csv_id:
        csv_ids_to_load.add(req.patent_csv_id)
    for theme in req.themes:
        if theme.patent_config and theme.patent_config.csv_id:
            csv_ids_to_load.add(theme.patent_config.csv_id)

    for csv_id in csv_ids_to_load:
        pc = await db.get(PatentCsv, csv_id)
        if pc and pc.user_id == user.id:
            rows = _json.loads(pc.rows_json)
            session.patent_csv_cache[csv_id] = rows
            # デフォルトCSVとして patent_rows にもセット（後方互換）
            if csv_id == req.patent_csv_id and not session.patent_rows:
                session.patent_rows = rows

    return SessionStartResponse(session_id=session_id)


@router.post("/{session_id}/turn/start", response_model=TurnStartResponse)
def start_turn(session_id: str, background_tasks: BackgroundTasks):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    job_id = f"job-turn-{uuid.uuid4().hex}"
    background_tasks.add_task(agent_runner.start_turn_background, session_id, job_id)
    return TurnStartResponse(job_id=job_id)


@router.get("/{session_id}/turn/status/{job_id}", response_model=TurnStatusResponse)
def get_turn_status(session_id: str, job_id: str):
    status_info = job_statuses.get(job_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="Job not found")
    return TurnStatusResponse(**status_info)


@router.post("/{session_id}/summarize/start", response_model=SummarizeStartResponse)
def start_summarize(session_id: str, background_tasks: BackgroundTasks):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    job_id = f"job-sum-{uuid.uuid4().hex}"
    background_tasks.add_task(agent_runner.summarize_background, session_id, job_id)
    return SummarizeStartResponse(job_id=job_id)


@router.get("/{session_id}/summarize/status/{job_id}", response_model=SummarizeStatusResponse)
def get_summarize_status(session_id: str, job_id: str):
    status_info = job_statuses.get(job_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="Job not found")
    return SummarizeStatusResponse(**status_info)


@router.post("/{session_id}/full/start", response_model=TurnStartResponse)
def start_full_session(session_id: str, background_tasks: BackgroundTasks):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    job_id = f"job-full-{uuid.uuid4().hex}"
    background_tasks.add_task(agent_runner.run_full_session_background, session_id, job_id)
    return TurnStartResponse(job_id=job_id)

@router.get("/{session_id}/full/status/{job_id}", response_model=FullSessionStatusResponse)
def get_full_session_status(session_id: str, job_id: str):
    status_info = job_statuses.get(job_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="Job not found")
    return FullSessionStatusResponse(**status_info)


@router.post("/generate-title", response_model=GenerateTitleResponse)
def generate_title(req: GenerateTitleRequest):
    """テーマ一覧からLLMに議論タイトルを生成させる。"""
    themes_text = "\n".join(f"- {t}" for t in req.themes)
    common = f"\n共通テーマ: {req.common_theme}" if req.common_theme else ""

    prompt = (
        "以下は議論セッションで扱うテーマの一覧です。\n"
        f"{themes_text}{common}\n\n"
        "この議論セッション全体を表す簡潔なタイトルを1つだけ生成してください。\n"
        "条件:\n"
        "- 20文字以内の日本語\n"
        "- テーマの本質を捉えた分かりやすい表現\n"
        "- タイトルのみを出力し、他の説明は不要"
    )

    try:
        llm = create_llm()
        result = llm.invoke(prompt)
        title = result.content.strip().strip("「」『』\"'")
        # 万が一長すぎる場合は切り詰め
        if len(title) > 50:
            title = title[:47] + "..."
        return GenerateTitleResponse(title=title)
    except Exception as e:
        logger.warning(f"タイトル生成に失敗、フォールバック使用: {e}")
        # フォールバック: 最初のテーマの先頭30文字
        fallback = req.themes[0][:30] + ("..." if len(req.themes[0]) > 30 else "") if req.themes else "Untitled"
        return GenerateTitleResponse(title=fallback)
