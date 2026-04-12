from typing import Dict, List, Optional
import uuid

from .models import Persona, MessageHistory, SessionStartRequest, ThemeConfig


class SessionMemory:
    def __init__(self, session_id: str, request: SessionStartRequest):
        self.session_id: str = session_id
        self.themes: List[ThemeConfig] = request.themes
        self.current_theme_index: int = 0
        self.personas: List[Persona] = request.personas
        self.tasks: List[any] = request.tasks # will be converted by pydantic automatically
        self.history: List[MessageHistory] = request.history
        self.turns_per_theme: int = request.turns_per_theme
        self.common_theme: str = request.common_theme
        self.pre_info: str = request.pre_info
        self.turn_count_in_theme: int = 0
        self.summaries: List[dict] = []  # {"theme": str, "summary": str} のリスト
        self.summary_memory = "" # 過去のテーマの要約情報
        # 前回の選択 (テーマ切り替え時にリセット)
        self.last_persona_id: Optional[str] = None
        self.last_task_id: Optional[str] = None
        # マクロフロー設定
        self.project_flow: str = request.project_flow
        self.flow_config: dict = request.flow_config or {}
        # 特許CSVパス（空の場合はAppSettings.patent_csv_pathを使用）
        self.patent_csv_path: str = request.patent_csv_path
        # 特許分析結果キャッシュ: theme_index → report text
        self.patent_context_cache: dict = {}

    @property
    def current_theme_config(self) -> ThemeConfig | None:
        if self.current_theme_index < len(self.themes):
            return self.themes[self.current_theme_index]
        return None

    @property
    def current_theme(self) -> str:
        cfg = self.current_theme_config
        return cfg.theme if cfg else ""

    @property
    def all_themes_done(self) -> bool:
        return self.current_theme_index >= len(self.themes)

    @property
    def current_turns_per_theme(self) -> int:
        """現在のテーマの発言回数を返す。テーマ個別設定があればそれを、なければセッションのデフォルトを使用。"""
        cfg = self.current_theme_config
        if cfg and cfg.turns_per_theme is not None:
            return cfg.turns_per_theme
        return self.turns_per_theme

    @property
    def active_personas(self) -> List[Persona]:
        """現在のテーマで有効なペルソナを返す。persona_ids が空の場合は全員。"""
        cfg = self.current_theme_config
        if cfg is None or not cfg.persona_ids:
            return self.personas
        id_set = set(cfg.persona_ids)
        return [p for p in self.personas if p.id in id_set]

    def advance_theme(self, summary_text: str):
        """現在のテーマの要約を保存して次のテーマへ進む。"""
        self.summaries.append({
            "theme": self.current_theme,
            "summary": summary_text,
        })
        # 過去テーマの要約をエージェントへ渡せるよう summary_memory を更新する
        self.summary_memory = "\n\n".join(
            f"[{s['theme']}]\n{s['summary']}" for s in self.summaries
        )
        self.current_theme_index += 1
        self.turn_count_in_theme = 0
        self.last_persona_id = None
        self.last_task_id = None


class SessionManager:
    def __init__(self):
        self.active_sessions: Dict[str, SessionMemory] = {}

    def start_session(self, request: SessionStartRequest) -> str:
        session_id = uuid.uuid4().hex
        self.active_sessions[session_id] = SessionMemory(session_id, request)
        return session_id

    def get_session(self, session_id: str) -> SessionMemory | None:
        return self.active_sessions.get(session_id)


# Global instance
session_manager = SessionManager()
