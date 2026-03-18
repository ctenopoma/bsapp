"""User-scoped data API: /api/data/...

Replaces client-side SQLite with server-side PostgreSQL.
All endpoints require an approved user.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from src.auth import require_approved
from src.database import get_db
from src.db_models import User, Persona, Task, Session, Message, SessionConfig
from src.db_models import PatentSession, PatentReport, PatentSummary

router = APIRouter()


# ─────────────────────────────────────────────
# Personas
# ─────────────────────────────────────────────

class PersonaIn(BaseModel):
    id: str
    name: str
    role: str
    pre_info: str = ""
    rag_config: str = ""   # JSON string


class PersonaOut(PersonaIn):
    pass


@router.get("/personas", response_model=list[PersonaOut])
async def list_personas(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(Persona).where(Persona.user_id == user.id).order_by(Persona.sort_order, Persona.created_at)
    )
    rows = result.scalars().all()
    return [PersonaOut(id=r.id, name=r.name, role=r.role, pre_info=r.pre_info, rag_config=r.rag_config) for r in rows]


@router.post("/personas", response_model=PersonaOut, status_code=201)
async def create_persona(
    body: PersonaIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    # assign sort_order = max + 1
    result = await db.execute(
        select(Persona).where(Persona.user_id == user.id).order_by(Persona.sort_order.desc())
    )
    last = result.scalars().first()
    next_order = (last.sort_order + 1) if last else 0

    p = Persona(
        id=body.id,
        user_id=user.id,
        name=body.name,
        role=body.role,
        pre_info=body.pre_info,
        rag_config=body.rag_config,
        sort_order=next_order,
    )
    db.add(p)
    await db.commit()
    return PersonaOut(id=p.id, name=p.name, role=p.role, pre_info=p.pre_info, rag_config=p.rag_config)


@router.put("/personas/{persona_id}", response_model=PersonaOut)
async def update_persona(
    persona_id: str,
    body: PersonaIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    p = await db.get(Persona, persona_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="Persona not found")
    p.name = body.name
    p.role = body.role
    p.pre_info = body.pre_info
    p.rag_config = body.rag_config
    await db.commit()
    return PersonaOut(id=p.id, name=p.name, role=p.role, pre_info=p.pre_info, rag_config=p.rag_config)


@router.delete("/personas/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    p = await db.get(Persona, persona_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="Persona not found")
    await db.delete(p)
    await db.commit()


# ─────────────────────────────────────────────
# Tasks
# ─────────────────────────────────────────────

class TaskIn(BaseModel):
    id: str
    description: str


class TaskOut(TaskIn):
    pass


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(Task).where(Task.user_id == user.id).order_by(Task.sort_order, Task.created_at)
    )
    return [TaskOut(id=r.id, description=r.description) for r in result.scalars().all()]


@router.post("/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    body: TaskIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(Task).where(Task.user_id == user.id).order_by(Task.sort_order.desc())
    )
    last = result.scalars().first()
    t = Task(id=body.id, user_id=user.id, description=body.description, sort_order=(last.sort_order + 1) if last else 0)
    db.add(t)
    await db.commit()
    return TaskOut(id=t.id, description=t.description)


@router.put("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    body: TaskIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    t = await db.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    t.description = body.description
    await db.commit()
    return TaskOut(id=t.id, description=t.description)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    t = await db.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(t)
    await db.commit()


# ─────────────────────────────────────────────
# Session Config (key-value)
# ─────────────────────────────────────────────

class ConfigItem(BaseModel):
    key: str
    value: str


@router.get("/config/{key}")
async def get_config(
    key: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(SessionConfig).where(SessionConfig.user_id == user.id, SessionConfig.key == key)
    )
    row = result.scalar_one_or_none()
    return {"key": key, "value": row.value if row else ""}


@router.put("/config/{key}")
async def save_config(
    key: str,
    body: ConfigItem,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(SessionConfig).where(SessionConfig.user_id == user.id, SessionConfig.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = body.value
    else:
        db.add(SessionConfig(user_id=user.id, key=key, value=body.value))
    await db.commit()
    return {"key": key, "value": body.value}


# ─────────────────────────────────────────────
# Sessions & Messages
# ─────────────────────────────────────────────

class SessionOut(BaseModel):
    id: str
    title: str
    created_at: str


class MessageIn(BaseModel):
    id: str
    theme: str
    agent_name: str
    content: str
    turn_order: int


class MessageOut(MessageIn):
    pass


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(Session).where(Session.user_id == user.id).order_by(Session.created_at.desc())
    )
    return [SessionOut(id=r.id, title=r.title, created_at=r.created_at.isoformat()) for r in result.scalars().all()]


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionOut,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    s = Session(id=body.id, user_id=user.id, title=body.title)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return SessionOut(id=s.id, title=s.title, created_at=s.created_at.isoformat())


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    s = await db.get(Session, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(s)
    await db.commit()


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    s = await db.get(Session, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.turn_order)
    )
    rows = result.scalars().all()
    return [MessageOut(id=r.id, theme=r.theme, agent_name=r.agent_name, content=r.content, turn_order=r.turn_order) for r in rows]


@router.post("/sessions/{session_id}/messages", response_model=MessageOut, status_code=201)
async def add_message(
    session_id: str,
    body: MessageIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    s = await db.get(Session, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    m = Message(
        id=body.id,
        session_id=session_id,
        theme=body.theme,
        agent_name=body.agent_name,
        content=body.content,
        turn_order=body.turn_order,
    )
    db.add(m)
    await db.commit()
    return MessageOut(id=m.id, theme=m.theme, agent_name=m.agent_name, content=m.content, turn_order=m.turn_order)


# ─────────────────────────────────────────────
# Patent Sessions
# ─────────────────────────────────────────────

class PatentSessionOut(BaseModel):
    id: str
    title: str
    created_at: str


class PatentReportIn(BaseModel):
    id: str
    company: str
    report: str
    sort_order: int = 0


class PatentReportOut(PatentReportIn):
    session_id: str


@router.get("/patent-sessions", response_model=list[PatentSessionOut])
async def list_patent_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(PatentSession).where(PatentSession.user_id == user.id).order_by(PatentSession.created_at.desc())
    )
    return [PatentSessionOut(id=r.id, title=r.title, created_at=r.created_at.isoformat()) for r in result.scalars().all()]


@router.post("/patent-sessions", response_model=PatentSessionOut, status_code=201)
async def create_patent_session(
    body: PatentSessionOut,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    ps = PatentSession(id=body.id, user_id=user.id, title=body.title)
    db.add(ps)
    await db.commit()
    await db.refresh(ps)
    return PatentSessionOut(id=ps.id, title=ps.title, created_at=ps.created_at.isoformat())


@router.delete("/patent-sessions/{session_id}", status_code=204)
async def delete_patent_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    ps = await db.get(PatentSession, session_id)
    if not ps or ps.user_id != user.id:
        raise HTTPException(status_code=404, detail="Patent session not found")
    await db.delete(ps)
    await db.commit()


@router.post("/patent-sessions/{session_id}/reports", response_model=PatentReportOut, status_code=201)
async def add_patent_report(
    session_id: str,
    body: PatentReportIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    ps = await db.get(PatentSession, session_id)
    if not ps or ps.user_id != user.id:
        raise HTTPException(status_code=404, detail="Patent session not found")
    r = PatentReport(id=body.id, session_id=session_id, company=body.company, report=body.report, sort_order=body.sort_order)
    db.add(r)
    await db.commit()
    return PatentReportOut(id=r.id, session_id=r.session_id, company=r.company, report=r.report, sort_order=r.sort_order)


@router.get("/patent-sessions/{session_id}/reports", response_model=list[PatentReportOut])
async def list_patent_reports(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    ps = await db.get(PatentSession, session_id)
    if not ps or ps.user_id != user.id:
        raise HTTPException(status_code=404, detail="Patent session not found")
    result = await db.execute(
        select(PatentReport).where(PatentReport.session_id == session_id).order_by(PatentReport.sort_order)
    )
    rows = result.scalars().all()
    return [PatentReportOut(id=r.id, session_id=r.session_id, company=r.company, report=r.report, sort_order=r.sort_order) for r in rows]


@router.put("/patent-sessions/{session_id}/summary")
async def save_patent_summary(
    session_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    ps = await db.get(PatentSession, session_id)
    if not ps or ps.user_id != user.id:
        raise HTTPException(status_code=404, detail="Patent session not found")
    summary_text: str = body.get("summary", "")
    result = await db.execute(
        select(PatentSummary).where(PatentSummary.session_id == session_id)
    )
    row = result.scalar_one_or_none()
    if row:
        row.summary = summary_text
    else:
        db.add(PatentSummary(id=str(uuid.uuid4()), session_id=session_id, summary=summary_text))
    await db.commit()
    return {"session_id": session_id, "summary": summary_text}


@router.get("/patent-sessions/{session_id}/summary")
async def get_patent_summary(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    ps = await db.get(PatentSession, session_id)
    if not ps or ps.user_id != user.id:
        raise HTTPException(status_code=404, detail="Patent session not found")
    result = await db.execute(
        select(PatentSummary).where(PatentSummary.session_id == session_id)
    )
    row = result.scalar_one_or_none()
    return {"session_id": session_id, "summary": row.summary if row else ""}
