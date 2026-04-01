"""SQLAlchemy ORM models for PostgreSQL."""
from datetime import datetime
from sqlalchemy import (
    String, Boolean, Integer, Text, DateTime, ForeignKey,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    azure_oid: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_known_ip: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)

    personas: Mapped[list["Persona"]] = relationship("Persona", back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    session_presets: Mapped[list["SessionPreset"]] = relationship("SessionPreset", back_populates="user", cascade="all, delete-orphan")
    persona_presets: Mapped[list["PersonaPreset"]] = relationship("PersonaPreset", back_populates="user", cascade="all, delete-orphan")
    task_presets: Mapped[list["TaskPreset"]] = relationship("TaskPreset", back_populates="user", cascade="all, delete-orphan")
    patent_sessions: Mapped[list["PatentSession"]] = relationship("PatentSession", back_populates="user", cascade="all, delete-orphan")


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pre_info: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rag_config: Mapped[str] = mapped_column(Text, nullable=False, default="")  # JSON string
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="personas")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="tasks")


class SessionConfig(Base):
    __tablename__ = "session_config"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    theme: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["Session"] = relationship("Session", back_populates="messages")


class SessionPreset(Base):
    """Saved session configuration presets (themes, common_theme, pre_info, turns)."""
    __tablename__ = "session_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    theme_entries: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON
    common_theme: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pre_info: Mapped[str] = mapped_column(Text, nullable=False, default="")
    turns_per_theme: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="session_presets")


class PersonaPreset(Base):
    """Named set of personas."""
    __tablename__ = "persona_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    persona_ids: Mapped[str] = mapped_column(Text, nullable=False, default="")  # comma-separated
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="persona_presets")


class TaskPreset(Base):
    """Named set of tasks."""
    __tablename__ = "task_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_ids: Mapped[str] = mapped_column(Text, nullable=False, default="")  # comma-separated
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="task_presets")


class PatentSession(Base):
    __tablename__ = "patent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="patent_sessions")
    reports: Mapped[list["PatentReport"]] = relationship("PatentReport", back_populates="session", cascade="all, delete-orphan")
    summary: Mapped["PatentSummary | None"] = relationship("PatentSummary", back_populates="session", cascade="all, delete-orphan", uselist=False)


class PatentReport(Base):
    __tablename__ = "patent_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("patent_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    report: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    session: Mapped["PatentSession"] = relationship("PatentSession", back_populates="reports")


class PatentSummary(Base):
    __tablename__ = "patent_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("patent_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped["PatentSession"] = relationship("PatentSession", back_populates="summary")
