from typing import Dict, List
import uuid

from .models import Persona, MessageHistory, SessionStartRequest

class SessionMemory:
    def __init__(self, session_id: str, request: SessionStartRequest):
        self.session_id: str = session_id
        self.themes: List[str] = request.themes
        self.current_theme_index: int = 0
        self.personas: List[Persona] = request.personas
        self.history: List[MessageHistory] = request.history
        self.turn_count_in_theme: int = 0
        # Placeholder for LangChain ConversationSummaryMemory
        self.summary_memory = None 

class SessionManager:
    def __init__(self):
        self.active_sessions: Dict[str, SessionMemory] = {}

    def start_session(self, request: SessionStartRequest) -> str:
        session_id = f"sess-{uuid.uuid4().hex}"
        self.active_sessions[session_id] = SessionMemory(session_id, request)
        return session_id

    def get_session(self, session_id: str) -> SessionMemory | None:
        return self.active_sessions.get(session_id)

    def end_session(self, session_id: str) -> bool:
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            return True
        return False

# Global instance
session_manager = SessionManager()
