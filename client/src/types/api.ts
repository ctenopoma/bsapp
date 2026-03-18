export interface RagConfig {
  enabled: boolean;
  tag?: string;
  rag_type?: string; // RAGの種別ID (例: "qdrant")
}

export interface AvailableRagType {
  id: string;
  name: string;
  description?: string;
}

export interface RagTypesResponse {
  types: AvailableRagType[];
}

export interface Persona {
  id: string;
  name: string;
  role: string;
  pre_info?: string;
  rag_config?: RagConfig;
}

export interface TaskModel {
  id: string;
  description: string;
}

export interface MessageHistory {
  id: string;
  theme: string;
  agent_name: string;
  content: string;
  turn_order: number;
}

export interface ThemeConfig {
  theme: string;
  persona_ids: string[];  // 空=全ペルソナが有効
  output_format?: string; // 空=デフォルトフォーマットを使用
  turns_per_theme?: number; // テーマごとの発言回数（未指定=セッションのデフォルト値）
  pre_info?: string; // テーマ固有の事前情報（テンプレート変数使用可）
}

// Session API Requests
export interface SessionStartRequest {
  themes: ThemeConfig[];
  personas: Persona[];
  tasks: TaskModel[];
  history: MessageHistory[];
  turns_per_theme?: number;
  common_theme?: string;
  pre_info?: string;
}

export interface SessionStartResponse {
  session_id: string;
}

export interface TurnStartResponse {
  job_id: string;
}

export interface SummarizeStartResponse {
  job_id: string;
}

export interface JobResponse {
  job_id: string;
}

export interface TurnStatusResponse {
  status: 'processing' | 'completed' | 'error';
  agent_name?: string;
  message?: string;
  theme?: string;
  is_theme_end?: boolean;
  all_themes_done?: boolean;
  history_compressed?: boolean;
  error_msg?: string;
}

export interface SummarizeStatusResponse {
  status: 'processing' | 'completed' | 'error';
  summary_text?: string;
  all_themes_done?: boolean;
  error_msg?: string;
}

export interface SessionEndResponse {
  status: 'success';
}

// App Settings (LLM接続情報はサーバー側のみで管理・非公開)
export interface AppSettings {
  turns_per_theme: number;
  default_output_format: string;
  agent_prompt_template: string;
  summary_prompt_template: string;
  max_history_tokens: number;
  recent_history_count: number;
  // 利用可能なRAG種別
  available_rag_types: AvailableRagType[];
  // 特許調査設定
  patent_company_column: string;
  patent_content_column: string;
  patent_date_column: string;
}

export interface HealthResponse {
  server: 'ok';
  llm: 'ok' | 'error';
  llm_error?: string;
}

// アップデート API
export interface UpdateInfoResponse {
  latest_version: string;
  current_version: string;
  has_update: boolean;
  release_notes: string;
  download_url: string;   // 相対パス (/api/update/download/filename)
  filename: string;
}

// RAG API Requests
export interface RagInitRequest {
  tag: string;
}

export interface RagInitResponse {
  status: 'success' | 'error';
  error_msg?: string;
}

export interface RagAddRequest {
  tag: string;
  text: string;
}

export interface RagAddResponse {
  job_id: string;
}

export interface RagStatusResponse {
  status: 'processing' | 'completed' | 'error';
  error_msg?: string;
}

// 特許調査 API
export interface PatentItem {
  content: string;
  date?: string;
}

export interface PatentAnalyzeRequest {
  company: string;
  patents: PatentItem[];
  system_prompt: string;
  output_format: string;
}

export interface PatentAnalyzeResponse {
  company: string;
  report: string;
}

export interface PatentSummaryRequest {
  company_reports: PatentAnalyzeResponse[];
  system_prompt: string;
}

export interface PatentSummaryResponse {
  summary: string;
}
