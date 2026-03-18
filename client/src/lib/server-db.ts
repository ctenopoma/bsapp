/**
 * server-db.ts – drop-in replacement for db.ts
 *
 * All data is now stored in PostgreSQL on the server.
 * The API functions mirror the same signatures as the old SQLite helpers.
 */
import { Persona, TaskModel, MessageHistory } from '../types/api';
import { request as _req } from './api-internal';

// Re-export types used by consumers
export interface ThemeEntry {
  id: string;
  text: string;
  persona_ids: string; // comma-separated
  output_format: string;
  turns_per_theme?: number | null; // テーマごとの発言回数（null=デフォルト）
  pre_info?: string; // テーマ固有の事前情報（テンプレート変数使用可）
  sort_order: number;
}

export interface SessionData {
  id: string;
  title: string;
  created_at: string;
}

export interface PatentSessionData {
  id: string;
  title: string;
  created_at: string;
}

export interface PatentReportData {
  id: string;
  session_id: string;
  company: string;
  report: string;
  sort_order: number;
}

// No-op: DB is initialised on the server
export async function initDb(): Promise<void> {}

// ─────────────────────────────────────────────
// Session Config
// ─────────────────────────────────────────────

export async function getSessionConfig(key: string): Promise<string> {
  const r = await _req<{ key: string; value: string }>(`/api/data/config/${encodeURIComponent(key)}`);
  return r.value;
}

export async function saveSessionConfig(key: string, value: string): Promise<void> {
  await _req(`/api/data/config/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify({ key, value }),
  });
}

// ─────────────────────────────────────────────
// Personas
// ─────────────────────────────────────────────

export async function getPersonas(): Promise<Persona[]> {
  const rows = await _req<{ id: string; name: string; role: string; pre_info: string; rag_config: string }[]>('/api/data/personas');
  return rows.map(r => ({
    id: r.id,
    name: r.name,
    role: r.role,
    pre_info: r.pre_info,
    rag_config: r.rag_config ? JSON.parse(r.rag_config) : undefined,
  }));
}

export async function addPersona(p: Persona): Promise<void> {
  await _req('/api/data/personas', {
    method: 'POST',
    body: JSON.stringify({
      id: p.id,
      name: p.name,
      role: p.role,
      pre_info: p.pre_info ?? '',
      rag_config: p.rag_config ? JSON.stringify(p.rag_config) : '',
    }),
  });
}

export async function updatePersona(p: Persona): Promise<void> {
  await _req(`/api/data/personas/${p.id}`, {
    method: 'PUT',
    body: JSON.stringify({
      id: p.id,
      name: p.name,
      role: p.role,
      pre_info: p.pre_info ?? '',
      rag_config: p.rag_config ? JSON.stringify(p.rag_config) : '',
    }),
  });
}

export async function deletePersona(id: string): Promise<void> {
  await _req(`/api/data/personas/${id}`, { method: 'DELETE' });
}

// ─────────────────────────────────────────────
// Tasks
// ─────────────────────────────────────────────

export async function getTasks(): Promise<TaskModel[]> {
  return _req<TaskModel[]>('/api/data/tasks');
}

export async function addTask(t: TaskModel): Promise<void> {
  await _req('/api/data/tasks', { method: 'POST', body: JSON.stringify(t) });
}

export async function updateTask(t: TaskModel): Promise<void> {
  await _req(`/api/data/tasks/${t.id}`, { method: 'PUT', body: JSON.stringify(t) });
}

export async function deleteTask(id: string): Promise<void> {
  await _req(`/api/data/tasks/${id}`, { method: 'DELETE' });
}

// ─────────────────────────────────────────────
// Theme Entries (stored in session_config as JSON for now)
// ─────────────────────────────────────────────

const THEME_CONFIG_KEY = 'theme_entries';

export async function getThemeEntries(): Promise<ThemeEntry[]> {
  const raw = await getSessionConfig(THEME_CONFIG_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as ThemeEntry[];
  } catch {
    return [];
  }
}

export async function saveThemeEntries(entries: ThemeEntry[]): Promise<void> {
  await saveSessionConfig(THEME_CONFIG_KEY, JSON.stringify(entries));
}

// ─────────────────────────────────────────────
// Session Presets
// ─────────────────────────────────────────────

export interface PresetData {
  id: string;
  name: string;
  theme_entries: string;   // JSON string
  common_theme: string;
  pre_info: string;
  turns_per_theme: number;
}

export async function getPresets(): Promise<PresetData[]> {
  return _req<PresetData[]>('/api/data/presets');
}

export async function createPreset(preset: PresetData): Promise<void> {
  await _req('/api/data/presets', { method: 'POST', body: JSON.stringify(preset) });
}

export async function updatePreset(preset: PresetData): Promise<void> {
  await _req(`/api/data/presets/${preset.id}`, { method: 'PUT', body: JSON.stringify(preset) });
}

export async function deletePreset(id: string): Promise<void> {
  await _req(`/api/data/presets/${id}`, { method: 'DELETE' });
}

// ─────────────────────────────────────────────
// Persona Presets
// ─────────────────────────────────────────────

export interface PersonaPresetData {
  id: string;
  name: string;
  persona_ids: string; // comma-separated
}

export async function getPersonaPresets(): Promise<PersonaPresetData[]> {
  return _req<PersonaPresetData[]>('/api/data/persona-presets');
}

export async function createPersonaPreset(preset: PersonaPresetData): Promise<void> {
  await _req('/api/data/persona-presets', { method: 'POST', body: JSON.stringify(preset) });
}

export async function updatePersonaPreset(preset: PersonaPresetData): Promise<void> {
  await _req(`/api/data/persona-presets/${preset.id}`, { method: 'PUT', body: JSON.stringify(preset) });
}

export async function deletePersonaPreset(id: string): Promise<void> {
  await _req(`/api/data/persona-presets/${id}`, { method: 'DELETE' });
}

// ─────────────────────────────────────────────
// Task Presets
// ─────────────────────────────────────────────

export interface TaskPresetData {
  id: string;
  name: string;
  task_ids: string; // comma-separated
}

export async function getTaskPresets(): Promise<TaskPresetData[]> {
  return _req<TaskPresetData[]>('/api/data/task-presets');
}

export async function createTaskPreset(preset: TaskPresetData): Promise<void> {
  await _req('/api/data/task-presets', { method: 'POST', body: JSON.stringify(preset) });
}

export async function updateTaskPreset(preset: TaskPresetData): Promise<void> {
  await _req(`/api/data/task-presets/${preset.id}`, { method: 'PUT', body: JSON.stringify(preset) });
}

export async function deleteTaskPreset(id: string): Promise<void> {
  await _req(`/api/data/task-presets/${id}`, { method: 'DELETE' });
}

// ─────────────────────────────────────────────
// Sessions & Messages
// ─────────────────────────────────────────────

export async function createSession(id: string, title: string): Promise<void> {
  await _req('/api/data/sessions', {
    method: 'POST',
    body: JSON.stringify({ id, title, created_at: new Date().toISOString() }),
  });
}

export async function getSessions(): Promise<SessionData[]> {
  return _req<SessionData[]>('/api/data/sessions');
}

export async function deleteSession(id: string): Promise<void> {
  await _req(`/api/data/sessions/${id}`, { method: 'DELETE' });
}

export async function getMessages(sessionId: string): Promise<MessageHistory[]> {
  return _req<MessageHistory[]>(`/api/data/sessions/${sessionId}/messages`);
}

export async function addMessage(
  sessionId: string,
  theme: string,
  agentName: string,
  content: string,
  turnOrder: number,
): Promise<void> {
  await _req(`/api/data/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({
      id: crypto.randomUUID(),
      theme,
      agent_name: agentName,
      content,
      turn_order: turnOrder,
    }),
  });
}

// ─────────────────────────────────────────────
// Patent Sessions
// ─────────────────────────────────────────────

export async function createPatentSession(id: string, title: string): Promise<void> {
  await _req('/api/data/patent-sessions', {
    method: 'POST',
    body: JSON.stringify({ id, title, created_at: new Date().toISOString() }),
  });
}

export async function getPatentSessions(): Promise<PatentSessionData[]> {
  return _req<PatentSessionData[]>('/api/data/patent-sessions');
}

export async function deletePatentSession(id: string): Promise<void> {
  await _req(`/api/data/patent-sessions/${id}`, { method: 'DELETE' });
}

export async function addPatentReport(
  sessionId: string,
  company: string,
  report: string,
  sortOrder: number,
): Promise<void> {
  await _req(`/api/data/patent-sessions/${sessionId}/reports`, {
    method: 'POST',
    body: JSON.stringify({ id: crypto.randomUUID(), company, report, sort_order: sortOrder }),
  });
}

export async function getPatentReports(sessionId: string): Promise<PatentReportData[]> {
  return _req<PatentReportData[]>(`/api/data/patent-sessions/${sessionId}/reports`);
}

export async function savePatentSummary(sessionId: string, summary: string): Promise<void> {
  await _req(`/api/data/patent-sessions/${sessionId}/summary`, {
    method: 'PUT',
    body: JSON.stringify({ summary }),
  });
}

export async function getPatentSummary(sessionId: string): Promise<string> {
  const r = await _req<{ summary: string }>(`/api/data/patent-sessions/${sessionId}/summary`);
  return r.summary;
}
