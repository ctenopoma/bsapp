import {
  SessionStartRequest,
  SessionStartResponse,
  TurnStartResponse,
  TurnStatusResponse,
  SummarizeStartResponse,
  SummarizeStatusResponse,
  SessionEndResponse,
  RagInitRequest,
  RagInitResponse,
  RagAddRequest,
  RagAddResponse,
  RagStatusResponse,
} from '../types/api';
import { fetch } from '@tauri-apps/plugin-http';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

async function request<T>(path: string, options?: any): Promise<T> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: options?.method || 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: options?.body,
    });
    
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API error ${res.status}: ${text}`);
    }
    
    return res.json() as Promise<T>;
  } catch (err: any) {
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
