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
from src.db_models import User, Persona, Task, Session, Message, SessionConfig, SessionPreset, PersonaPreset, TaskPreset
from src.db_models import PatentSession, PatentReport, PatentSummary, PatentPreset

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
# Session Presets (theme config only)
# ─────────────────────────────────────────────

class PresetIn(BaseModel):
    id: str
    name: str
    theme_entries: str = "[]"      # JSON string
    common_theme: str = ""
    pre_info: str = ""
    turns_per_theme: int = 5


class PresetOut(PresetIn):
    pass


@router.get("/presets", response_model=list[PresetOut])
async def list_presets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(SessionPreset).where(SessionPreset.user_id == user.id).order_by(SessionPreset.sort_order, SessionPreset.created_at)
    )
    rows = result.scalars().all()
    return [PresetOut(
        id=r.id, name=r.name, theme_entries=r.theme_entries, common_theme=r.common_theme,
        pre_info=r.pre_info, turns_per_theme=r.turns_per_theme,
    ) for r in rows]


@router.post("/presets", response_model=PresetOut, status_code=201)
async def create_preset(
    body: PresetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(SessionPreset).where(SessionPreset.user_id == user.id).order_by(SessionPreset.sort_order.desc())
    )
    last = result.scalars().first()
    next_order = (last.sort_order + 1) if last else 0
    p = SessionPreset(
        id=body.id, user_id=user.id, name=body.name,
        theme_entries=body.theme_entries, common_theme=body.common_theme,
        pre_info=body.pre_info,
        turns_per_theme=body.turns_per_theme, sort_order=next_order,
    )
    db.add(p)
    await db.commit()
    return PresetOut(
        id=p.id, name=p.name, theme_entries=p.theme_entries, common_theme=p.common_theme,
        pre_info=p.pre_info, turns_per_theme=p.turns_per_theme,
    )


@router.put("/presets/{preset_id}", response_model=PresetOut)
async def update_preset(
    preset_id: str,
    body: PresetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    p = await db.get(SessionPreset, preset_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="Preset not found")
    p.name = body.name
    p.theme_entries = body.theme_entries
    p.common_theme = body.common_theme
    p.pre_info = body.pre_info
    p.turns_per_theme = body.turns_per_theme
    await db.commit()
    return PresetOut(
        id=p.id, name=p.name, theme_entries=p.theme_entries, common_theme=p.common_theme,
        pre_info=p.pre_info, turns_per_theme=p.turns_per_theme,
    )


@router.delete("/presets/{preset_id}", status_code=204)
async def delete_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    p = await db.get(SessionPreset, preset_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="Preset not found")
    await db.delete(p)
    await db.commit()


# ─────────────────────────────────────────────
# Persona Presets
# ─────────────────────────────────────────────

class PersonaPresetIn(BaseModel):
    id: str
    name: str
    persona_ids: str = ""  # comma-separated


class PersonaPresetOut(PersonaPresetIn):
    pass


@router.get("/persona-presets", response_model=list[PersonaPresetOut])
async def list_persona_presets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(PersonaPreset).where(PersonaPreset.user_id == user.id).order_by(PersonaPreset.sort_order, PersonaPreset.created_at)
    )
    return [PersonaPresetOut(id=r.id, name=r.name, persona_ids=r.persona_ids) for r in result.scalars().all()]


@router.post("/persona-presets", response_model=PersonaPresetOut, status_code=201)
async def create_persona_preset(
    body: PersonaPresetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(PersonaPreset).where(PersonaPreset.user_id == user.id).order_by(PersonaPreset.sort_order.desc())
    )
    last = result.scalars().first()
    pp = PersonaPreset(id=body.id, user_id=user.id, name=body.name, persona_ids=body.persona_ids, sort_order=(last.sort_order + 1) if last else 0)
    db.add(pp)
    await db.commit()
    return PersonaPresetOut(id=pp.id, name=pp.name, persona_ids=pp.persona_ids)


@router.put("/persona-presets/{preset_id}", response_model=PersonaPresetOut)
async def update_persona_preset(
    preset_id: str,
    body: PersonaPresetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    pp = await db.get(PersonaPreset, preset_id)
    if not pp or pp.user_id != user.id:
        raise HTTPException(status_code=404, detail="Persona preset not found")
    pp.name = body.name
    pp.persona_ids = body.persona_ids
    await db.commit()
    return PersonaPresetOut(id=pp.id, name=pp.name, persona_ids=pp.persona_ids)


@router.delete("/persona-presets/{preset_id}", status_code=204)
async def delete_persona_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    pp = await db.get(PersonaPreset, preset_id)
    if not pp or pp.user_id != user.id:
        raise HTTPException(status_code=404, detail="Persona preset not found")
    await db.delete(pp)
    await db.commit()


# ─────────────────────────────────────────────
# Task Presets
# ─────────────────────────────────────────────

class TaskPresetIn(BaseModel):
    id: str
    name: str
    task_ids: str = ""  # comma-separated


class TaskPresetOut(TaskPresetIn):
    pass


@router.get("/task-presets", response_model=list[TaskPresetOut])
async def list_task_presets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(TaskPreset).where(TaskPreset.user_id == user.id).order_by(TaskPreset.sort_order, TaskPreset.created_at)
    )
    return [TaskPresetOut(id=r.id, name=r.name, task_ids=r.task_ids) for r in result.scalars().all()]


@router.post("/task-presets", response_model=TaskPresetOut, status_code=201)
async def create_task_preset(
    body: TaskPresetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(TaskPreset).where(TaskPreset.user_id == user.id).order_by(TaskPreset.sort_order.desc())
    )
    last = result.scalars().first()
    tp = TaskPreset(id=body.id, user_id=user.id, name=body.name, task_ids=body.task_ids, sort_order=(last.sort_order + 1) if last else 0)
    db.add(tp)
    await db.commit()
    return TaskPresetOut(id=tp.id, name=tp.name, task_ids=tp.task_ids)


@router.put("/task-presets/{preset_id}", response_model=TaskPresetOut)
async def update_task_preset(
    preset_id: str,
    body: TaskPresetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    tp = await db.get(TaskPreset, preset_id)
    if not tp or tp.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task preset not found")
    tp.name = body.name
    tp.task_ids = body.task_ids
    await db.commit()
    return TaskPresetOut(id=tp.id, name=tp.name, task_ids=tp.task_ids)


@router.delete("/task-presets/{preset_id}", status_code=204)
async def delete_task_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    tp = await db.get(TaskPreset, preset_id)
    if not tp or tp.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task preset not found")
    await db.delete(tp)
    await db.commit()


# ─────────────────────────────────────────────
# Sessions & Messages
# ─────────────────────────────────────────────

class SessionIn(BaseModel):
    id: str
    title: str
    common_theme: str = ""
    pre_info: str = ""


class SessionOut(BaseModel):
    id: str
    title: str
    common_theme: str
    pre_info: str
    created_at: str


class MessageIn(BaseModel):
    id: str
    theme: str
    agent_name: str
    content: str
    turn_order: int
    rag_context: str | None = None
    patent_context: str | None = None


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
    return [SessionOut(id=r.id, title=r.title, common_theme=r.common_theme, pre_info=r.pre_info, created_at=r.created_at.isoformat()) for r in result.scalars().all()]


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    s = Session(id=body.id, user_id=user.id, title=body.title, common_theme=body.common_theme, pre_info=body.pre_info)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return SessionOut(id=s.id, title=s.title, common_theme=s.common_theme, pre_info=s.pre_info, created_at=s.created_at.isoformat())


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    s = await db.get(Session, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut(id=s.id, title=s.title, common_theme=s.common_theme, pre_info=s.pre_info, created_at=s.created_at.isoformat())


class SessionUpdateBody(BaseModel):
    title: str


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: str,
    body: SessionUpdateBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    s = await db.get(Session, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    s.title = body.title
    await db.commit()
    await db.refresh(s)
    return SessionOut(id=s.id, title=s.title, common_theme=s.common_theme, pre_info=s.pre_info, created_at=s.created_at.isoformat())


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
    return [MessageOut(id=r.id, theme=r.theme, agent_name=r.agent_name, content=r.content, turn_order=r.turn_order, rag_context=getattr(r, "rag_context", None), patent_context=getattr(r, "patent_context", None)) for r in rows]


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
        rag_context=body.rag_context,
        patent_context=body.patent_context,
    )
    db.add(m)
    await db.commit()
    return MessageOut(id=m.id, theme=m.theme, agent_name=m.agent_name, content=m.content, turn_order=m.turn_order, rag_context=m.rag_context, patent_context=m.patent_context)


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


# ─────────────────────────────────────────────
# Patent Presets
# ─────────────────────────────────────────────

class PatentPresetIn(BaseModel):
    id: str
    name: str
    system_prompt: str = ""
    output_format: str = ""
    strategy: str = "bulk"
    chunk_size: int = 20
    max_companies: int = 20
    max_total_patents: int = 100
    patents_per_company: int = 10


class PatentPresetOut(PatentPresetIn):
    pass


@router.get("/patent-presets", response_model=list[PatentPresetOut])
async def list_patent_presets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(PatentPreset).where(PatentPreset.user_id == user.id).order_by(PatentPreset.sort_order, PatentPreset.created_at)
    )
    rows = result.scalars().all()
    return [PatentPresetOut(
        id=r.id, name=r.name, system_prompt=r.system_prompt, output_format=r.output_format,
        strategy=r.strategy, chunk_size=r.chunk_size, max_companies=r.max_companies,
        max_total_patents=r.max_total_patents, patents_per_company=r.patents_per_company,
    ) for r in rows]


@router.post("/patent-presets", response_model=PatentPresetOut, status_code=201)
async def create_patent_preset(
    body: PatentPresetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    result = await db.execute(
        select(PatentPreset).where(PatentPreset.user_id == user.id).order_by(PatentPreset.sort_order.desc())
    )
    last = result.scalars().first()
    pp = PatentPreset(
        id=body.id, user_id=user.id, name=body.name,
        system_prompt=body.system_prompt, output_format=body.output_format,
        strategy=body.strategy, chunk_size=body.chunk_size,
        max_companies=body.max_companies, max_total_patents=body.max_total_patents,
        patents_per_company=body.patents_per_company,
        sort_order=(last.sort_order + 1) if last else 0,
    )
    db.add(pp)
    await db.commit()
    return PatentPresetOut(
        id=pp.id, name=pp.name, system_prompt=pp.system_prompt, output_format=pp.output_format,
        strategy=pp.strategy, chunk_size=pp.chunk_size, max_companies=pp.max_companies,
        max_total_patents=pp.max_total_patents, patents_per_company=pp.patents_per_company,
    )


@router.put("/patent-presets/{preset_id}", response_model=PatentPresetOut)
async def update_patent_preset(
    preset_id: str,
    body: PatentPresetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    pp = await db.get(PatentPreset, preset_id)
    if not pp or pp.user_id != user.id:
        raise HTTPException(status_code=404, detail="Patent preset not found")
    pp.name = body.name
    pp.system_prompt = body.system_prompt
    pp.output_format = body.output_format
    pp.strategy = body.strategy
    pp.chunk_size = body.chunk_size
    pp.max_companies = body.max_companies
    pp.max_total_patents = body.max_total_patents
    pp.patents_per_company = body.patents_per_company
    await db.commit()
    return PatentPresetOut(
        id=pp.id, name=pp.name, system_prompt=pp.system_prompt, output_format=pp.output_format,
        strategy=pp.strategy, chunk_size=pp.chunk_size, max_companies=pp.max_companies,
        max_total_patents=pp.max_total_patents, patents_per_company=pp.patents_per_company,
    )


@router.delete("/patent-presets/{preset_id}", status_code=204)
async def delete_patent_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved),
):
    pp = await db.get(PatentPreset, preset_id)
    if not pp or pp.user_id != user.id:
        raise HTTPException(status_code=404, detail="Patent preset not found")
    await db.delete(pp)
    await db.commit()


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
