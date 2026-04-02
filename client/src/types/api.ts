export interface RagConfig {
  enabled: boolean;
  tag?: string;
  rag_type?: string; // RAGの種別ID (例: "qdrant")
  rag_query_prompt?: string; // RAG検索クエリ生成プロンプト (空=テーマをそのまま使用)
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
  flow_role_map?: Record<string, string | string[]>; // フロー役割マッピング（役割名 → ペルソナID or ID[]）
  task_assignment?: string; // タスク割り当てモード: random / round_robin / fixed（空=グローバル設定）
  persona_task_map?: Record<string, string>; // fixed時のペルソナID→タスクIDマッピング
  summarize?: boolean; // テーマ終了後に要約を生成するか（省略時=true）
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
  type: 'number' | 'select' | 'text' | 'role_map' | 'slot_prompts';
  default: any;
  min?: number;
  max?: number;
  options?: { value: any; label: string }[];
  placeholder?: string;
  roles?: string[]; // role_map / slot_prompts type 用: 利用可能な役割名リスト
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
      {
        key: 'role_map',
        label: '役割マッピング（ペルソナID → 役割）',
        type: 'role_map',
        default: {},
        roles: ['facilitator', 'member'],
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（役割ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['facilitator', 'member'],
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
      {
        key: 'role_map',
        label: '役割マッピング（ペルソナID → 役割）',
        type: 'role_map',
        default: {},
        roles: ['manager', 'worker'],
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（役割ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['manager', 'worker'],
      },
    ],
  },
  {
    id: 'adversarial',
    name: '敵対的・レッドチーム（生成・批判）',
    description: '生成役が提案し、批判役がJSON評価でダメ出し、修正を繰り返して提案の質を高めます。批判役が問題なしと判定すれば早期終了します。',
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
      {
        key: 'max_retry_per_phase',
        label: 'リトライ上限（上限到達で打ち切り）',
        type: 'number',
        default: 3,
        min: 1,
        max: 10,
      },
      {
        key: 'role_map',
        label: '役割マッピング（ペルソナID → 役割）',
        type: 'role_map',
        default: {},
        roles: ['generator', 'critic'],
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（役割ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['generator', 'critic'],
      },
    ],
  },
  {
    id: 'judge_jury',
    name: '陪審員・裁判官（Judge & Jury）',
    description: 'ディベーター間で議論し、最後に裁判官が全履歴を読んでJSON形式で最終判定を下します。',
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
      {
        key: 'role_map',
        label: '役割マッピング（ペルソナID → 役割）',
        type: 'role_map',
        default: {},
        roles: ['judge', 'debater'],
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（役割ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['judge', 'debater'],
      },
    ],
  },
  {
    id: 'dynamic_routing',
    name: '動的ルーティング（司会者主導）',
    description: '司会者が文脈を読んでJSONで次の発言者を動的に指名します。',
    configFields: [
      {
        key: 'router_index',
        label: '司会者（先頭からの番号）',
        type: 'number',
        default: 0,
        min: 0,
      },
      {
        key: 'max_turns',
        label: '最大ターン数',
        type: 'number',
        default: 10,
        min: 1,
        max: 30,
      },
      {
        key: 'end_condition',
        label: '終了条件の説明（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 全員が同意した場合、または3つ以上の具体案が出た場合',
      },
      {
        key: 'role_map',
        label: '役割マッピング（ペルソナID → 役割）',
        type: 'role_map',
        default: {},
        roles: ['router', 'speaker'],
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（役割ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['router', 'speaker'],
      },
    ],
  },
  {
    id: 'map_reduce',
    name: '分割統治（Map-Reduce）',
    description: 'プランナーがタスクを分割し、ワーカーが個別処理し、サマライザーが統合します。',
    configFields: [
      {
        key: 'planner_index',
        label: 'プランナー（先頭からの番号）',
        type: 'number',
        default: 0,
        min: 0,
      },
      {
        key: 'summarizer_index',
        label: 'サマライザー（先頭からの番号、-1=最後）',
        type: 'number',
        default: -1,
      },
      {
        key: 'max_subtasks',
        label: '最大サブタスク数',
        type: 'number',
        default: 5,
        min: 1,
        max: 10,
      },
      {
        key: 'role_map',
        label: '役割マッピング（ペルソナID → 役割）',
        type: 'role_map',
        default: {},
        roles: ['planner', 'worker', 'summarizer'],
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（役割ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['planner', 'worker', 'summarizer'],
      },
    ],
  },
  {
    id: 'dynamic_generation',
    name: '動的エージェント生成',
    description: 'メタエージェントが議題に最適なペルソナをその場で生成し、議論を実行します。',
    configFields: [
      {
        key: 'meta_agent_index',
        label: 'メタエージェント（先頭からの番号）',
        type: 'number',
        default: 0,
        min: 0,
      },
      {
        key: 'max_generated',
        label: '最大生成ペルソナ数',
        type: 'number',
        default: 3,
        min: 1,
        max: 10,
      },
      {
        key: 'generation_guideline',
        label: '編成指針（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 技術・法律・ビジネスの専門家を含めること',
      },
      {
        key: 'role_map',
        label: '役割マッピング（ペルソナID → 役割）',
        type: 'role_map',
        default: {},
        roles: ['meta_agent'],
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（役割ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['meta_agent'],
      },
    ],
  },
];

// マクロフロー（テーマ間の進行制御）定義
export interface ProjectFlowOption {
  id: string;
  name: string;
  description: string;
  configFields: ThemeStrategyConfigField[];
  flowRoles?: { name: string; multi: boolean }[]; // フロー内の役割（multi=true: 複数ペルソナ選択可）
}

export const PROJECT_FLOWS: ProjectFlowOption[] = [
  {
    id: 'waterfall',
    name: 'ウォーターフォール型（デフォルト）',
    description: 'テーマを定義順に1つずつ実行します。',
    configFields: [],
    flowRoles: [],
  },
  // NOTE: flowRoles format - { name: role_name, multi: true/false }
  //   multi=false → single persona dropdown (gatekeeper, judge, etc.)
  //   multi=true  → multiple persona chips (proponent camp, opponent camp, etc.)
  {
    id: 'stage_gate',
    name: 'ステージゲート型',
    description: '各テーマ完了後にゲートキーパーが品質チェックし、不合格なら差し戻します。',
    configFields: [
      {
        key: 'max_revisions',
        label: '最大差し戻し回数',
        type: 'number',
        default: 2,
        min: 0,
        max: 10,
      },
      {
        key: 'pass_condition',
        label: '通過条件（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 具体的なアクションアイテムが3つ以上含まれること',
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（役割ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['gatekeeper'],
      },
    ],
    flowRoles: [{ name: 'gatekeeper', multi: false }],
  },
  {
    id: 'agile_sprint',
    name: 'アジャイル/スプリント型',
    description: '全テーマをスプリントとして複数回繰り返し、完成判定者が仕上がりを評価します。',
    configFields: [
      {
        key: 'sprint_count',
        label: 'スプリント回数',
        type: 'number',
        default: 2,
        min: 1,
        max: 10,
      },
      {
        key: 'completion_criteria',
        label: '完成判定の基準（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 全テーマで実装可能な具体案が揃っていること',
      },
    ],
    flowRoles: [{ name: 'completion_judge', multi: false }],
  },
  {
    id: 'conditional',
    name: '条件分岐/ツリー型',
    description: 'テーマの結論によってルーターが次のテーマを動的に選択します。',
    configFields: [
      {
        key: 'max_total_themes',
        label: '最大実行テーマ総数（0=テーマ数×3）',
        type: 'number',
        default: 0,
        min: 0,
      },
      {
        key: 'routing_rules',
        label: '分岐条件ルール（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 問題が特定された場合は解決策テーマへ、合意が得られた場合は実装テーマへ',
      },
    ],
    flowRoles: [{ name: 'router', multi: false }],
  },
  {
    id: 'v_shape',
    name: 'V字型（実行＆逆順レビュー）',
    description: '全テーマを順番に実行した後、逆順でレビューして品質を担保します。',
    configFields: [
      {
        key: 'review_focus',
        label: 'レビューの観点（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 前半の要件定義と後半の実装内容の整合性を確認',
      },
    ],
    flowRoles: [{ name: 'reviewer', multi: false }],
  },
  {
    id: 'game_theory',
    name: 'ゲーム理論/対立型（陣営間ディベート）',
    description: '提案陣営と批判陣営が対立的に議論し、合意形成者が最終案を導きます。',
    configFields: [
      {
        key: 'rounds',
        label: 'ラウンド数',
        type: 'number',
        default: 2,
        min: 1,
        max: 10,
      },
      {
        key: 'agreement_criteria',
        label: '合意の基準（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 実装コストと効果のバランスが取れた案であること',
      },
      {
        key: 'slot_prompts',
        label: 'スタンスプロンプト（陣営ごとの立場・ミッション）',
        type: 'slot_prompts',
        default: {},
        roles: ['proponent', 'opponent', 'agreement_judge'],
      },
    ],
    flowRoles: [{ name: 'proponent', multi: true }, { name: 'opponent', multi: true }, { name: 'agreement_judge', multi: false }],
  },
  {
    id: 'blackboard',
    name: 'ブラックボード型（共有黒板）',
    description: 'コーディネーターが黒板状態を読み、次の担当エージェントを動的に指名します。',
    configFields: [
      {
        key: 'max_total_turns',
        label: '最大ターン数（0=自動）',
        type: 'number',
        default: 0,
        min: 0,
      },
      {
        key: 'goal_condition',
        label: '終了条件（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 全テーマについて具体的なアクションアイテムが出揃った時点',
      },
    ],
    flowRoles: [{ name: 'coordinator', multi: false }],
  },
  {
    id: 'tournament',
    name: 'トーナメント/進化型（並列コンペ）',
    description: '同じプロジェクトを複数回実行し、審査員が最良の成果物を選びます。',
    configFields: [
      {
        key: 'num_lanes',
        label: '並列レーン数',
        type: 'number',
        default: 2,
        min: 1,
        max: 5,
      },
      {
        key: 'evaluation_criteria',
        label: '審査基準（省略可）',
        type: 'text',
        default: '',
        placeholder: '例: 独自性・実現可能性・具体性の3点で評価',
      },
    ],
    flowRoles: [{ name: 'judge', multi: false }],
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
  project_flow?: string;
  flow_config?: Record<string, any>;
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

export interface ChunkStrategy {
  id: string;
  name: string;
  description: string;
}

export interface ChunkStrategiesResponse {
  strategies: ChunkStrategy[];
}

export interface RagAddRequest {
  tag: string;
  text: string;
  strategy?: string;
  chunk_size?: number;
  overlap?: number;
  window_size?: number;
  overlap_sentences?: number;
  breakpoint_percentile?: number;
}

export interface RagAddResponse {
  job_id: string;
}

export interface RagStatusResponse {
  status: 'processing' | 'completed' | 'error';
  error_msg?: string;
}

export interface RagCollectionInfo {
  tag: string;
  count: number;
}

export interface RagCollectionsResponse {
  collections: RagCollectionInfo[];
}

export interface RagChunk {
  id: string;
  text: string;
}

export interface RagChunksResponse {
  chunks: RagChunk[];
  total: number;
  error?: string;
}

export interface RagSearchHit {
  id: string;
  text: string;
  score: number;
}

export interface RagSearchResponse {
  results: RagSearchHit[];
  context: string;
  error?: string;
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

// ヘルパーエージェント API (ペルソナ・タスク入力支援)
export interface HelperMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface FieldSuggestion {
  field: string;   // "name" | "role" | "pre_info" | "description"
  value: string;
  label: string;   // 表示用ラベル ("名前", "ロール" 等)
}

export interface HelperAskRequest {
  context: 'persona' | 'task' | 'setup' | 'rag' | 'patent';
  question: string;
  history: HelperMessage[];
  current_input?: Record<string, string>;
}

export interface HelperAskResponse {
  answer: string;
  suggestions?: FieldSuggestion[];
}
