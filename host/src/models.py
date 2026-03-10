from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# -------------------------------------------------------------------
# RAG設定 (ペルソナごとに持つ)
# -------------------------------------------------------------------
class RagConfig(BaseModel):
    enabled: bool = False
    tag: Optional[str] = None  # 使用するRAGコレクションのタグ名


# -------------------------------------------------------------------
# Common
# -------------------------------------------------------------------
class Persona(BaseModel):
    id: str
    name: str
    role: str
    task: str
    rag_config: RagConfig = Field(default_factory=RagConfig)


class MessageHistory(BaseModel):
    id: str
    theme: str
    agent_name: str
    content: str
    turn_order: int


# -------------------------------------------------------------------
# エージェント1回の実行に渡す入力をまとめた構造体
# -------------------------------------------------------------------
class AgentInput(BaseModel):
    persona: Persona
    task: str           # persona.task と同値だが、将来的に動的上書きできるよう分離
    query: str          # 今回のターンで考えさせる問い (現状はテーマをそのまま渡す)
    history: List[MessageHistory]
    rag_context: str = ""  # RAGが有効な場合に事前取得して渡す


# -------------------------------------------------------------------
# Session API
# -------------------------------------------------------------------
class SessionStartRequest(BaseModel):
    themes: List[str]
    personas: List[Persona]
    history: List[MessageHistory] = Field(default_factory=list)


class SessionStartResponse(BaseModel):
    session_id: str


class TurnStartResponse(BaseModel):
    job_id: str


class TurnStatusResponse(BaseModel):
    status: Literal["processing", "completed", "error"]
    agent_name: Optional[str] = None
    message: Optional[str] = None
    is_theme_end: Optional[bool] = None
    error_msg: Optional[str] = None


class SummarizeStartResponse(BaseModel):
    job_id: str


class SummarizeStatusResponse(BaseModel):
    status: Literal["processing", "completed", "error"]
    summary_text: Optional[str] = None
    error_msg: Optional[str] = None


class SessionEndResponse(BaseModel):
    status: Literal["success"]


# -------------------------------------------------------------------
# RAG API
# -------------------------------------------------------------------
class RagInitRequest(BaseModel):
    tag: str


class RagInitResponse(BaseModel):
    status: Literal["success", "error"]
    error_msg: Optional[str] = None


class RagAddRequest(BaseModel):
    tag: str
    text: str


class RagAddResponse(BaseModel):
    job_id: str


class RagStatusResponse(BaseModel):
    status: Literal["processing", "completed", "error"]
    error_msg: Optional[str] = None
