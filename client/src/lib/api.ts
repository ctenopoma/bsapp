import {
  SessionStartRequest,
  SessionStartResponse,
  TurnStartResponse,
  TurnStatusResponse,
  SummarizeStartResponse,
  SummarizeStatusResponse,
  SessionEndResponse,
  AppSettings,
  HealthResponse,
  UpdateInfoResponse,
  RagInitRequest,
  RagInitResponse,
  RagAddRequest,
  RagAddResponse,
  RagStatusResponse,
  RagTypesResponse,
  PatentAnalyzeRequest,
  PatentAnalyzeResponse,
  PatentSummaryRequest,
  PatentSummaryResponse,
} from '../types/api';
import { fetch } from '@tauri-apps/plugin-http';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

// Viteのビルド時定数: vite build (リリース) では false に置換されコードごと削除される
const IS_DEV = import.meta.env.DEV;

function vlog(message: string, ...args: unknown[]): void {
  if (IS_DEV) console.log(message, ...args);
}

function vlogError(message: string, ...args: unknown[]): void {
  if (IS_DEV) console.error(message, ...args);
}

async function request<T>(path: string, options?: any): Promise<T> {
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

  const startMs = Date.now();
  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
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
    vlogError(`  ブラウザで確認: ${url}`);
    if (!BASE_URL.includes('localhost') && !BASE_URL.includes('127.0.0.1')) {
      vlogError(`  capabilities確認: src-tauri/capabilities/default.json の allow に ${BASE_URL}/** があるか確認`);
    }

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

export function apiEndSession(sessionId: string): Promise<SessionEndResponse> {
  return request(`/api/session/${sessionId}/end`, { method: 'POST' });
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

export function apiPatentSummary(req: PatentSummaryRequest): Promise<PatentSummaryResponse> {
  return request('/api/patent/summary', { method: 'POST', body: JSON.stringify(req) });
}
