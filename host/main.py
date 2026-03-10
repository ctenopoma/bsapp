import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

from src.models import (
    SessionStartRequest, SessionStartResponse, 
    TurnStartResponse, TurnStatusResponse,
    SummarizeStartResponse, SummarizeStatusResponse, SessionEndResponse,
    RagInitRequest, RagInitResponse, 
    RagAddRequest, RagAddResponse, RagStatusResponse
)
from src.session_manager import session_manager
from src.rag_manager import rag_manager
from src.agent_runner import agent_runner, job_statuses

app = FastAPI(title="AI Discussion App Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Since Tauri runs on localhost/custom protocol
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Session Management API ---

@app.post("/api/session/start", response_model=SessionStartResponse)
def start_session(request: SessionStartRequest):
    session_id = session_manager.start_session(request)
    return SessionStartResponse(session_id=session_id)

@app.post("/api/session/{session_id}/turn/start", response_model=TurnStartResponse)
def start_turn(session_id: str, background_tasks: BackgroundTasks):
    if not session_manager.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
        
    job_id = f"turn-{uuid.uuid4().hex}"
    background_tasks.add_task(agent_runner.start_turn_background, session_id, job_id)
    return TurnStartResponse(job_id=job_id)

@app.get("/api/session/{session_id}/turn/status/{job_id}", response_model=TurnStatusResponse)
def get_turn_status(session_id: str, job_id: str):
    status_data = job_statuses.get(job_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Job not found")
    return TurnStatusResponse(**status_data)

@app.post("/api/session/{session_id}/summarize/start", response_model=SummarizeStartResponse)
def start_summarize(session_id: str, background_tasks: BackgroundTasks):
    if not session_manager.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
        
    job_id = f"sum-{uuid.uuid4().hex}"
    background_tasks.add_task(agent_runner.summarize_background, session_id, job_id)
    return SummarizeStartResponse(job_id=job_id)

@app.get("/api/session/{session_id}/summarize/status/{job_id}", response_model=SummarizeStatusResponse)
def get_summarize_status(session_id: str, job_id: str):
    status_data = job_statuses.get(job_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Job not found")
    return SummarizeStatusResponse(**status_data)

@app.post("/api/session/{session_id}/end", response_model=SessionEndResponse)
def end_session(session_id: str):
    success = session_manager.end_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionEndResponse(status="success")


# --- RAG Management API ---

@app.post("/api/rag/init", response_model=RagInitResponse)
def init_rag(request: RagInitRequest):
    try:
        success = rag_manager.init_collection(request.tag)
        return RagInitResponse(status="success" if success else "error")
    except Exception as e:
        return RagInitResponse(status="error", error_msg=str(e))

@app.post("/api/rag/add", response_model=RagAddResponse)
def add_rag_text(request: RagAddRequest, background_tasks: BackgroundTasks):
    job_id = f"rag-{uuid.uuid4().hex}"
    background_tasks.add_task(rag_manager.add_text_background, request.tag, request.text, job_id, job_statuses)
    return RagAddResponse(job_id=job_id)

@app.get("/api/rag/status/{job_id}", response_model=RagStatusResponse)
def get_rag_status(job_id: str):
    status_data = job_statuses.get(job_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Handle cases where backend added 'status' generically
    status = status_data.get("status", "error")
    error_msg = status_data.get("error_msg")
    
    return RagStatusResponse(status=status, error_msg=error_msg)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
