export interface RagConfig {
  enabled: boolean;
  tag?: string;
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
}

export interface HealthResponse {
  server: 'ok';
  llm: 'ok' | 'error';
  llm_error?: string;
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
