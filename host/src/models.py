from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# -------------------------------------------------------------------
# RAG種別 (ホスト側で設定可能)
# -------------------------------------------------------------------
class AvailableRagType(BaseModel):
    id: str           # 種別ID (例: "qdrant")
    name: str         # 表示名 (例: "Qdrant (ベクトル検索)")
    description: str = ""


# -------------------------------------------------------------------
# RAG設定 (ペルソナごとに持つ)
# -------------------------------------------------------------------
class RagConfig(BaseModel):
    enabled: bool = False
    tag: Optional[str] = None      # 使用するRAGコレクションのタグ名
    rag_type: Optional[str] = None # RAGの種別ID (例: "qdrant")
    rag_query_prompt: str = ""     # RAG検索クエリ生成プロンプト (空=テーマをそのまま使用)
                                   # 使用可能変数: {theme}, {common_theme}, {history}


# -------------------------------------------------------------------
# Common
# -------------------------------------------------------------------
class Persona(BaseModel):
    id: str
    name: str
    role: str
    pre_info: str = ""           # ペルソナ固有の事前情報
    rag_config: Optional[RagConfig] = Field(default_factory=RagConfig)

class TaskModel(BaseModel):
    id: str
    description: str


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
    task: str           # The randomly assigned task description
    query: str          # 今回のターンで考えさせる問い (現状はテーマをそのまま渡す)
    history: List[MessageHistory]
    rag_context: str = ""        # RAGが有効な場合に事前取得して渡す
    pre_info: str = ""           # セッション共通の事前情報
    previous_summaries: str = ""   # これまでの要約を結合したもの
    stance_prompt: str = ""      # ストラテジ内の役割に応じたスタンス（立場・ミッション）プロンプト
    output_format: str = ""      # 出力フォーマット指定 (空の場合はデフォルト挙動)
    history_compressed: bool = False  # このターンで履歴圧縮が発生したか


# -------------------------------------------------------------------
# Session API
# -------------------------------------------------------------------
class PatentConfig(BaseModel):
    """テーマに設定する特許分析設定。"""
    preset_id: str = ""           # PatentPresetのID（空=直接設定を使用）
    system_prompt: str = ""
    output_format: str = ""
    strategy: str = "bulk"
    chunk_size: int = 20
    max_companies: int = 20
    max_total_patents: int = 100
    patents_per_company: int = 10
    pre_info_sources: List[str] = Field(default_factory=list)  # 事前情報に含めるソース ("summary:N", "messages:N", etc.)


class ThemeConfig(BaseModel):
    theme: str
    persona_ids: List[str] = Field(default_factory=list)  # 空=全ペルソナが有効
    output_format: str = ""  # 空=デフォルトフォーマットを使用
    turns_per_theme: Optional[int] = None  # None=セッション全体のデフォルト値を使用
    pre_info: str = ""  # テーマ固有の事前情報 (テンプレート変数使用可)
    theme_strategy: str = ""  # テーマ内ストラテジー (空=sequential)
    strategy_config: Optional[dict] = None  # ストラテジー固有の設定
    persona_order: List[str] = Field(default_factory=list)  # ペルソナIDの発言順序 (空=ストラテジー任せ)
    flow_role_map: dict = Field(default_factory=dict)  # フロー役割マッピング {persona_id: role_name} テーマ×立場のペルソナ割当
    task_assignment: str = ""  # タスク割り当てモード: random / round_robin / fixed (空=グローバル設定)
    persona_task_map: dict = Field(default_factory=dict)  # fixed時のペルソナID→タスクIDマッピング
    summarize: bool = True  # テーマ終了後に要約を生成するか
    patent_config: Optional[PatentConfig] = None  # 特許分析設定（テーマ前に特許分析を実行）


class SessionStartRequest(BaseModel):
    themes: List[ThemeConfig]
    personas: List[Persona]
    tasks: List[TaskModel]
    history: List[MessageHistory] = Field(default_factory=list)
    turns_per_theme: int = 5     # テーマ1つあたりのターン数
    common_theme: str = ""       # 全テーマ共通の上位テーマ
    pre_info: str = ""           # 事前情報 (ファイル内容等)
    project_flow: str = ""       # マクロフロータイプ (空=waterfall)
    flow_config: Optional[dict] = None  # フロー固有の設定
    patent_rows: List[dict] = Field(default_factory=list)  # クライアントがアップロードしたCSVの行データ


class SessionStartResponse(BaseModel):
    session_id: str


class TurnStartResponse(BaseModel):
    job_id: str


class TurnStatusResponse(BaseModel):
    status: Literal["processing", "completed", "error"]
    agent_name: Optional[str] = None
    message: Optional[str] = None
    theme: Optional[str] = None
    is_theme_end: Optional[bool] = None
    all_themes_done: Optional[bool] = None
    history_compressed: Optional[bool] = None  # 履歴圧縮が発生したか
    rag_context: Optional[str] = None  # RAGで取得したコンテキスト
    patent_context: Optional[str] = None  # 特許分析結果（Discussion内でテーマ前に実行）
    error_msg: Optional[str] = None


class SummarizeStartResponse(BaseModel):
    job_id: str


class SummarizeStatusResponse(BaseModel):
    status: Literal["processing", "completed", "error"]
    summary_text: Optional[str] = None
    all_themes_done: Optional[bool] = None
    error_msg: Optional[str] = None


# 全テーマ終了後の最終結果
class ThemeSummary(BaseModel):
    theme: str
    summary: str


class FullSessionResult(BaseModel):
    theme_summaries: List[ThemeSummary]
    final_report: str   # 全要約を結合したもの


class FullSessionStatusResponse(BaseModel):
    status: Literal["processing", "completed", "error"]
    result: Optional[FullSessionResult] = None
    error_msg: Optional[str] = None



# -------------------------------------------------------------------
# アプリ設定 (公開API経由で取得・変更できる設定のみ。LLM接続情報は含まない)
# -------------------------------------------------------------------
class AppSettings(BaseModel):
    turns_per_theme: int = 5
    default_output_format: str = ""   # 空=prompt_builder.pyのデフォルト値を使用
    agent_prompt_template: str = ""   # 空=prompt_builder.pyのデフォルト値を使用
    summary_prompt_template: str = "" # 空=prompt_builder.pyのデフォルト値を使用
    max_history_tokens: int = 50000   # 会話履歴の最大トークン数 (0=無制限)
    recent_history_count: int = 5     # 圧縮しない直近の会話数
    # 利用可能なRAG種別 (ホスト管理者がsettings.jsonで明示的に設定する。未設定時は空=RAG選択不可)
    available_rag_types: List[AvailableRagType] = Field(default_factory=list)
    # 特許調査設定
    patent_company_column: str = "出願人"   # CSV内の企業名列名
    patent_content_column: str = "請求項"  # CSV内の特許内容列名
    patent_date_column: str = "出願日"      # CSV内の日付列名 (最新N件ソート用)
    # 特許調査 トークン上限 (0=無制限)
    patent_max_prompt_tokens: int = 0
    # 特許圧縮プロンプト
    patent_compress_per_patent_prompt: str = ""   # 空=デフォルト
    patent_compress_per_company_prompt: str = ""  # 空=デフォルト
    # チャンク分割Reduce プロンプト
    patent_chunk_analyze_prompt: str = ""  # Map フェーズ: 各チャンクの分析プロンプト (空=デフォルト)
    patent_chunk_reduce_prompt: str = ""   # Reduce フェーズ: 中間レポート統合プロンプト (空=デフォルト)


# -------------------------------------------------------------------
# 特許調査 API
# -------------------------------------------------------------------
class PatentItem(BaseModel):
    content: str   # 特許タイトル・概要など
    date: str = "" # 日付文字列 (クライアント側でソート済み)


class PatentAnalyzeRequest(BaseModel):
    company: str
    patents: List[PatentItem]   # クライアントが絞り込み済み
    system_prompt: str
    output_format: str
    # トークン上限（0=サーバーデフォルト上限を使用）
    max_prompt_tokens: int = 0


class PatentAnalyzeResponse(BaseModel):
    company: str
    report: str


class PatentSummaryRequest(BaseModel):
    company_reports: List[PatentAnalyzeResponse]  # 全企業のレポート
    system_prompt: str


class PatentSummaryResponse(BaseModel):
    summary: str


class PatentCompressRequest(BaseModel):
    """特許リストを圧縮して返す（トークン削減用）。"""
    patents: List[PatentItem]
    mode: str  # "per_patent" | "per_company"
    company: str = ""  # per_company モード時に使用
    compress_prompt: str = ""  # 空=デフォルトプロンプト


class PatentCompressResponse(BaseModel):
    patents: List[PatentItem]  # 圧縮後の特許リスト
    original_count: int
    compressed_count: int


class PatentChunkedAnalyzeRequest(BaseModel):
    """チャンク分割Reduceによる特許分析リクエスト。"""
    company: str
    patents: List[PatentItem]
    system_prompt: str
    output_format: str
    chunk_size: int = 20          # 1チャンクあたりの特許数
    max_prompt_tokens: int = 0    # 0=サーバーデフォルト上限


class PatentChunkedAnalyzeResponse(BaseModel):
    company: str
    report: str                   # Reduce後の最終レポート
    chunk_count: int              # 実行したチャンク数
    intermediate_reports: List[str]  # 各チャンクの中間レポート（デバッグ用）


class PatentPresetModel(BaseModel):
    id: str
    name: str
    system_prompt: str = ""
    output_format: str = ""
    strategy: str = "bulk"
    chunk_size: int = 20
    max_companies: int = 20
    max_total_patents: int = 100
    patents_per_company: int = 10


class HealthResponse(BaseModel):
    server: Literal["ok"] = "ok"
    llm: Literal["ok", "error"]
    llm_error: Optional[str] = None


# -------------------------------------------------------------------
# アップデート API
# -------------------------------------------------------------------
class UpdateInfoResponse(BaseModel):
    latest_version: str
    current_version: str
    has_update: bool
    release_notes: str = ""
    download_url: str = ""   # 相対パス (/api/update/download/filename)
    filename: str = ""


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


# -------------------------------------------------------------------
# ヘルパーエージェント API (ペルソナ・タスク入力支援)
# -------------------------------------------------------------------
class HelperMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class FieldSuggestion(BaseModel):
    field: str    # フィールド名 (例: "name", "role", "pre_info", "description")
    value: str    # 提案値
    label: str    # 表示ラベル (例: "名前", "ロール")


class HelperAskRequest(BaseModel):
    context: Literal["persona", "task", "setup", "rag", "patent"]
    question: str
    history: List[HelperMessage] = Field(default_factory=list)
    current_input: Optional[dict] = None  # 現在の入力値 {"name": "...", "role": "..."}


class HelperAskResponse(BaseModel):
    answer: str
    suggestions: Optional[List[FieldSuggestion]] = None
