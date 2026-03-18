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
  theme_strategy?: string; // テーマ内ストラテジー（空=sequential）
  strategy_config?: Record<string, any>; // ストラテジー固有の設定
  persona_order?: string[]; // ペルソナIDの発言順序（空=ストラテジー任せ）
}

// テーマ内ストラテジーの定義
export interface ThemeStrategyOption {
  id: string;
  name: string;
  description: string;
  configFields: ThemeStrategyConfigField[];
}

export interface ThemeStrategyConfigField {
  key: string;
  label: string;
  type: 'number' | 'select' | 'text';
  default: any;
  min?: number;
  max?: number;
  options?: { value: any; label: string }[];
  placeholder?: string;
}

// 利用可能なストラテジー定義
export const THEME_STRATEGIES: ThemeStrategyOption[] = [
  {
    id: 'sequential',
    name: 'シーケンシャル（バトンリレー）',
    description: '各エージェントが順番に発言し、結果を次に渡します。',
    configFields: [],
  },
  {
    id: 'parallel',
    name: '並列独立（ブレスト）',
    description: '各エージェントが独立して意見を出し、ファシリテーターが集約します。',
    configFields: [
      {
        key: 'facilitator_index',
        label: 'ファシリテーター（先頭からの番号）',
        type: 'number',
        default: 0,
        min: 0,
      },
    ],
  },
  {
    id: 'round_robin_debate',
    name: 'ラウンドロビン（順番ディベート）',
    description: '全員が順番に発言するループを複数回回し、議論を深掘りします。',
    configFields: [
      {
        key: 'max_loops',
        label: '最大ループ数',
        type: 'number',
        default: 2,
        min: 1,
        max: 10,
      },
    ],
  },
  {
    id: 'hierarchical',
    name: '階層型（計画・実行・反省）',
    description: 'マネージャーが計画を立て、ワーカーが実行し、評価・修正を繰り返して品質を高めます。',
    configFields: [
      {
        key: 'manager_index',
        label: 'マネージャー（先頭からの番号）',
        type: 'number',
        default: 0,
        min: 0,
      },
      {
        key: 'max_revision_loops',
        label: '最大修正ループ数',
        type: 'number',
        default: 3,
        min: 1,
        max: 10,
      },
      {
        key: 'pass_condition',
        label: '合格判定の追加指示（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 実現可能性と具体性の両方が満たされていること',
      },
    ],
  },
  {
    id: 'adversarial',
    name: '敵対的・レッドチーム（生成・批判）',
    description: '生成役が提案し、批判役がダメ出し、修正を繰り返して提案の質を高めます。',
    configFields: [
      {
        key: 'generator_index',
        label: '生成役（先頭からの番号）',
        type: 'number',
        default: 0,
        min: 0,
      },
      {
        key: 'critic_index',
        label: '批判役（先頭からの番号）',
        type: 'number',
        default: 1,
        min: 0,
      },
      {
        key: 'max_rounds',
        label: '最大往復数',
        type: 'number',
        default: 3,
        min: 1,
        max: 10,
      },
      {
        key: 'critic_perspective',
        label: '批判の観点（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: セキュリティ面から、コスト面から',
      },
    ],
  },
  {
    id: 'judge_jury',
    name: '陪審員・裁判官（Judge & Jury）',
    description: 'ディベーター間で議論し、最後に裁判官が全履歴を読んで最終判定を下します。',
    configFields: [
      {
        key: 'judge_index',
        label: '裁判官（先頭からの番号、-1=最後）',
        type: 'number',
        default: -1,
      },
      {
        key: 'debate_turns',
        label: 'ディベートのターン数',
        type: 'number',
        default: 6,
        min: 1,
        max: 20,
      },
      {
        key: 'evaluation_criteria',
        label: '評価基準・観点（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 実現可能性・独自性・社会的インパクトの3点で評価',
      },
    ],
  },
];

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
