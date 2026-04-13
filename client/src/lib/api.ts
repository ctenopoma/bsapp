import {
  SessionStartRequest,
  SessionStartResponse,
  TurnStartResponse,
  TurnStatusResponse,
  SummarizeStartResponse,
  SummarizeStatusResponse,
  AppSettings,
  HealthResponse,
  UpdateInfoResponse,
  RagInitRequest,
  RagInitResponse,
  RagAddRequest,
  RagAddResponse,
  RagStatusResponse,
  RagTypesResponse,
  RagCollectionsResponse,
  RagChunksResponse,
  RagSearchResponse,
  ChunkStrategiesResponse,
  PatentAnalyzeRequest,
  PatentAnalyzeResponse,
  PatentSummaryRequest,
  PatentSummaryResponse,
  PatentCompressRequest,
  PatentCompressResponse,
  PatentChunkedAnalyzeRequest,
  PatentChunkedAnalyzeResponse,
  PatentStatsRequest,
  PatentStatsResponse,
  StatProcessorInfo,
  HelperAskRequest,
  HelperAskResponse,
} from '../types/api';

// Use native fetch (works in both Tauri webview and plain browser)
const _fetch: typeof fetch = window.fetch.bind(window);

export const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

// Viteのビルド時定数: vite build (リリース) では false に置換されコードごと削除される
const IS_DEV = import.meta.env.DEV;
const DEV_AUTH_BYPASS = import.meta.env.VITE_DEV_AUTH_BYPASS === 'true';

// Auth token store – set by AuthContext after login
let _authToken: string | undefined;
export function setAuthToken(token: string | undefined) {
  _authToken = token;
}

// Dev session ID: persists in localStorage so the same browser always maps to the same dev user
// Note: uses a polyfill fallback for HTTP (non-secure) contexts where crypto.randomUUID() is unavailable
function _generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try { return crypto.randomUUID(); } catch (_) {}
  }
  // Fallback for HTTP non-secure context (LAN access via http://192.168.x.x/...)
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

function getDevSessionId(): string {
  const KEY = 'dev_session_id';
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = _generateUUID();
    localStorage.setItem(KEY, id);
  }
  return id;
}

// Windows username: used as stable user identifier in DEV_AUTH_BYPASS mode.
// Tauri: auto-detected via Rust command. Browser: prompted once and stored in localStorage.
const _WIN_USER_KEY = 'bsapp_winuser';

function _shouldInitWindowsUsername(): boolean {
  return DEV_AUTH_BYPASS;
}

export function getWindowsUsername(): string {
  return localStorage.getItem(_WIN_USER_KEY) ?? '';
}

export async function initAuth(): Promise<void> {
  if (!_shouldInitWindowsUsername()) return;
  if (localStorage.getItem(_WIN_USER_KEY)) return;
  // Tauri environment: auto-detect via Rust %USERNAME%
  if ((window as any).__TAURI__) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const name: string = await invoke('get_windows_username');
      if (name) {
        localStorage.setItem(_WIN_USER_KEY, name);
        return;
      }
    } catch (_) {}
  }
  // Browser fallback: prompt once
  const name = (prompt('Windowsアカウント名を入力してください（例: tanaka.taro）\n※ 以降は自動的に使用されます') ?? '').trim();
  if (name) localStorage.setItem(_WIN_USER_KEY, name);
}

export function buildRequestHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  headers['X-Dev-Session-Id'] = getDevSessionId();

  const winUser = getWindowsUsername();
  if (winUser) headers['X-Windows-Username'] = winUser;

  return headers;
}

function vlog(message: string, ...args: unknown[]): void {
  if (IS_DEV) console.log(message, ...args);
}

function vlogError(message: string, ...args: unknown[]): void {
  if (IS_DEV) console.error(message, ...args);
}

export async function request<T>(path: string, options?: any): Promise<T> {
  const method = options?.method || 'GET';
  const url = `${BASE_URL}${path}`;

  vlog(`[→Host] ${method} ${url}`);
  if (IS_DEV && options?.body) {
    try {
      vlog('  body:', JSON.parse(options.body));
    } catch {
      vlog('  body:', options.body);
    }
  }

  const headers = buildRequestHeaders(_authToken);

  const startMs = Date.now();
  try {
    const res = await _fetch(url, {
      method,
      headers,
      body: options?.body,
    });

    const elapsed = Date.now() - startMs;
    vlog(`[Host→] ${res.status} ${url}  (${elapsed}ms)`);

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API error ${res.status}: ${text}`);
    }

    return res.json() as Promise<T>;
  } catch (err: any) {
    const elapsed = Date.now() - startMs;
    vlogError(`[Fetch ERROR] ${method} ${url}  (${elapsed}ms)`);
    vlogError(`  ${err.message || err}`);

    let detail = String(err);
    if (typeof err === 'object' && err !== null) {
      try {
        detail = JSON.stringify(err);
      } catch (e) {}
    }
    throw new Error(`[Fetch Failed] ${err.message || ''} | Detail: ${detail}`);
  }
}

export function apiStartSession(req: SessionStartRequest): Promise<SessionStartResponse> {
  return request('/api/session/start', { method: 'POST', body: JSON.stringify(req) });
}

export function apiGenerateTitle(themes: string[], commonTheme: string): Promise<{ title: string }> {
  return request('/api/session/generate-title', {
    method: 'POST',
    body: JSON.stringify({ themes, common_theme: commonTheme }),
  });
}

export function apiStartTurn(sessionId: string): Promise<TurnStartResponse> {
  return request(`/api/session/${sessionId}/turn/start`, { method: 'POST' });
}

export function apiGetTurnStatus(sessionId: string, jobId: string): Promise<TurnStatusResponse> {
  return request(`/api/session/${sessionId}/turn/status/${jobId}`);
}

export function apiStartSummarize(sessionId: string): Promise<SummarizeStartResponse> {
  return request(`/api/session/${sessionId}/summarize/start`, { method: 'POST' });
}

export function apiGetSummarizeStatus(sessionId: string, jobId: string): Promise<SummarizeStatusResponse> {
  return request(`/api/session/${sessionId}/summarize/status/${jobId}`);
}

export function apiGetSettings(): Promise<AppSettings> {
  return request('/api/settings/');
}

export function apiSaveSettings(s: AppSettings): Promise<AppSettings> {
  return request('/api/settings/', { method: 'PUT', body: JSON.stringify(s) });
}

export function apiGetHealth(): Promise<HealthResponse> {
  return request('/api/settings/health');
}

export function apiRagInit(req: RagInitRequest): Promise<RagInitResponse> {
  return request('/api/rag/init', { method: 'POST', body: JSON.stringify(req) });
}
export const apiInitRag = apiRagInit;

export function apiRagAdd(req: RagAddRequest): Promise<RagAddResponse> {
  return request('/api/rag/add', { method: 'POST', body: JSON.stringify(req) });
}
export const apiAddRag = apiRagAdd;

export function apiRagStatus(jobId: string): Promise<RagStatusResponse> {
  return request(`/api/rag/status/${jobId}`);
}
export const apiGetRagStatus = apiRagStatus;

export function apiGetRagTypes(): Promise<RagTypesResponse> {
  return request('/api/rag/types');
}

export function apiGetRagCollections(): Promise<RagCollectionsResponse> {
  return request('/api/rag/collections');
}

export function apiGetChunkStrategies(): Promise<ChunkStrategiesResponse> {
  return request('/api/rag/chunk_strategies');
}

export function apiGetRagChunks(tag: string, limit = 200): Promise<RagChunksResponse> {
  return request(`/api/rag/chunks/${encodeURIComponent(tag)}?limit=${limit}`);
}

export function apiDeleteRagChunk(tag: string, chunkId: string): Promise<{ status: string; error_msg?: string }> {
  return request(`/api/rag/chunks/${encodeURIComponent(tag)}/${encodeURIComponent(chunkId)}`, { method: 'DELETE' });
}

export function apiSearchRag(tag: string, query: string, limit: number = 3): Promise<RagSearchResponse> {
  return request(`/api/rag/search?tag=${encodeURIComponent(tag)}&query=${encodeURIComponent(query)}&limit=${limit}`);
}

// アップデート確認 API
export function apiCheckUpdate(currentVersion: string, platform: string = 'windows'): Promise<UpdateInfoResponse> {
  return request(`/api/update/info?current=${encodeURIComponent(currentVersion)}&platform=${platform}`);
}

// インストーラーの絶対ダウンロードURLを構築する
export function getDownloadUrl(relativePath: string): string {
  return `${BASE_URL}${relativePath}`;
}

// 特許調査 API
export function apiPatentAnalyze(req: PatentAnalyzeRequest): Promise<PatentAnalyzeResponse> {
  return request('/api/patent/analyze', { method: 'POST', body: JSON.stringify(req) });
}

export function apiPatentCompress(req: PatentCompressRequest): Promise<PatentCompressResponse> {
  return request('/api/patent/compress', { method: 'POST', body: JSON.stringify(req) });
}

export function apiPatentAnalyzeChunked(req: PatentChunkedAnalyzeRequest): Promise<PatentChunkedAnalyzeResponse> {
  return request('/api/patent/analyze_chunked', { method: 'POST', body: JSON.stringify(req) });
}

export function apiPatentSummary(req: PatentSummaryRequest): Promise<PatentSummaryResponse> {
  return request('/api/patent/summary', { method: 'POST', body: JSON.stringify(req) });
}

export function apiPatentStats(req: PatentStatsRequest): Promise<PatentStatsResponse> {
  return request('/api/patent/stats', { method: 'POST', body: JSON.stringify(req) });
}

export function apiPatentStatsProcessors(): Promise<StatProcessorInfo[]> {
  return request('/api/patent/stats/processors', { method: 'GET' });
}

// ヘルパーエージェント API
export function apiHelperAsk(req: HelperAskRequest): Promise<HelperAskResponse> {
  return request('/api/helper/ask', { method: 'POST', body: JSON.stringify(req) });
}
