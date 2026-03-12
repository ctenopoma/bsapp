export interface RagConfig {
  enabled: boolean;
  tag?: string;
}

export interface Persona {
  id: string;
  name: string;
  role: string;
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
}

// Session API Requests
export interface SessionStartRequest {
  themes: ThemeConfig[];
  personas: Persona[];
  tasks: TaskModel[];
  history: MessageHistory[];
  turns_per_theme?: number;
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
  is_theme_end?: boolean;
  error_msg?: string;
}

export interface SummarizeStatusResponse {
  status: 'processing' | 'completed' | 'error';
  summary_text?: string;
  error_msg?: string;
}

export interface SessionEndResponse {
  status: 'success';
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
