import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any

from src.models import (
    SessionStartRequest,
    SessionStartResponse,
    TurnStartResponse,
    TurnStatusResponse,
    SummarizeStartResponse,
    SummarizeStatusResponse,
    SessionEndResponse,
    FullSessionStatusResponse
)
from src.session_manager import session_manager
from src.agent_runner import agent_runner, job_statuses

router = APIRouter()


@router.post("/start", response_model=SessionStartResponse)
def start_session(req: SessionStartRequest):
    session_id = session_manager.start_session(req)
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


@router.post("/{session_id}/end", response_model=SessionEndResponse)
def end_session(session_id: str):
    success = session_manager.end_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionEndResponse(status="success")

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
