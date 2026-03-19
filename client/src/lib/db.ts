import Database from '@tauri-apps/plugin-sql';
import { Persona, TaskModel, MessageHistory } from '../types/api';
import { generateUUID } from './uuid';

let _db: Database | null = null;

export async function initDb(): Promise<void> {
  await getDb();
}

async function getDb(): Promise<Database> {
  if (_db) return _db;
  _db = await Database.load('sqlite:bsapp.db');

  await _db.execute(`
    CREATE TABLE IF NOT EXISTS personas (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      role TEXT NOT NULL,
      pre_info TEXT NOT NULL DEFAULT '',
      rag_config TEXT NOT NULL DEFAULT ''
    )
  `);
  // マイグレーション: pre_info カラムが存在しない場合は追加
  try {
    await _db.execute(`ALTER TABLE personas ADD COLUMN pre_info TEXT NOT NULL DEFAULT ''`);
  } catch {
    // カラムが既に存在する場合は無視
  }
  // マイグレーション: rag_config カラムが存在しない場合は追加
  try {
    await _db.execute(`ALTER TABLE personas ADD COLUMN rag_config TEXT NOT NULL DEFAULT ''`);
  } catch {
    // カラムが既に存在する場合は無視
  }
  
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY,
      description TEXT NOT NULL
    )
  `);
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      session_id TEXT NOT NULL,
      theme TEXT NOT NULL,
      agent_name TEXT NOT NULL,
      content TEXT NOT NULL,
      turn_order INTEGER NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )
  `);
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS theme_entries (
      id TEXT PRIMARY KEY,
      text TEXT NOT NULL,
      persona_ids TEXT NOT NULL DEFAULT '',
      output_format TEXT NOT NULL DEFAULT '',
      sort_order INTEGER NOT NULL DEFAULT 0
    )
  `);
  // マイグレーション: output_format カラムが存在しない場合は追加
  try {
    await _db.execute(`ALTER TABLE theme_entries ADD COLUMN output_format TEXT NOT NULL DEFAULT ''`);
  } catch {
    // カラムが既に存在する場合は無視
  }
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS session_config (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL DEFAULT ''
    )
  `);

  // 特許調査テーブル
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS patent_sessions (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS patent_reports (
      id TEXT PRIMARY KEY,
      session_id TEXT NOT NULL,
      company TEXT NOT NULL,
      report TEXT NOT NULL,
      sort_order INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY (session_id) REFERENCES patent_sessions(id) ON DELETE CASCADE
    )
  `);
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS patent_summaries (
      id TEXT PRIMARY KEY,
      session_id TEXT NOT NULL UNIQUE,
      summary TEXT NOT NULL,
      FOREIGN KEY (session_id) REFERENCES patent_sessions(id) ON DELETE CASCADE
    )
  `);

  return _db;
}

export async function getSessionConfig(key: string): Promise<string> {
  const db = await getDb();
  const rows = await db.select<{ value: string }[]>(
    'SELECT value FROM session_config WHERE key = $1', [key]
  );
  return rows[0]?.value ?? '';
}

export async function saveSessionConfig(key: string, value: string): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO session_config (key, value) VALUES ($1, $2) ON CONFLICT(key) DO UPDATE SET value = $2',
    [key, value]
  );
}

export async function getPersonas(): Promise<Persona[]> {
  const db = await getDb();
  const rows = await db.select<{ id: string; name: string; role: string; pre_info: string; rag_config: string }[]>(
    'SELECT id, name, role, pre_info, rag_config FROM personas ORDER BY rowid'
  );
  return rows.map(r => ({
    id: r.id,
    name: r.name,
    role: r.role,
    pre_info: r.pre_info,
    rag_config: r.rag_config ? JSON.parse(r.rag_config) : undefined,
  }));
}

export async function addPersona(p: Persona): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO personas (id, name, role, pre_info, rag_config) VALUES ($1, $2, $3, $4, $5)',
    [p.id, p.name, p.role, p.pre_info ?? '', p.rag_config ? JSON.stringify(p.rag_config) : '']
  );
}

export async function updatePersona(p: Persona): Promise<void> {
  const db = await getDb();
  await db.execute(
    'UPDATE personas SET name=$1, role=$2, pre_info=$3, rag_config=$4 WHERE id=$5',
    [p.name, p.role, p.pre_info ?? '', p.rag_config ? JSON.stringify(p.rag_config) : '', p.id]
  );
}

export async function deletePersona(id: string): Promise<void> {
  const db = await getDb();
  await db.execute('DELETE FROM personas WHERE id=$1', [id]);
}

export async function getTasks(): Promise<TaskModel[]> {
  const db = await getDb();
  return db.select<TaskModel[]>('SELECT id, description FROM tasks ORDER BY rowid');
}

export async function addTask(t: TaskModel): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO tasks (id, description) VALUES ($1, $2)',
    [t.id, t.description]
  );
}

export async function updateTask(t: TaskModel): Promise<void> {
  const db = await getDb();
  await db.execute(
    'UPDATE tasks SET description=$1 WHERE id=$2',
    [t.description, t.id]
  );
}

export async function deleteTask(id: string): Promise<void> {
  const db = await getDb();
  await db.execute('DELETE FROM tasks WHERE id=$1', [id]);
}

export interface ThemeEntry {
  id: string;
  text: string;
  persona_ids: string; // comma-separated persona IDs
  output_format: string;
  sort_order: number;
}

export async function getThemeEntries(): Promise<ThemeEntry[]> {
  const db = await getDb();
  return db.select<ThemeEntry[]>('SELECT id, text, persona_ids, output_format, sort_order FROM theme_entries ORDER BY sort_order');
}

export async function saveThemeEntries(entries: ThemeEntry[]): Promise<void> {
  const db = await getDb();
  await db.execute('DELETE FROM theme_entries', []);
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    await db.execute(
      'INSERT INTO theme_entries (id, text, persona_ids, output_format, sort_order) VALUES ($1, $2, $3, $4, $5)',
      [e.id, e.text, e.persona_ids, e.output_format, i]
    );
  }
}

export async function createSession(id: string, title: string): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO sessions (id, title) VALUES ($1, $2)',
    [id, title]
  );
}

export interface SessionData {
  id: string;
  title: string;
  created_at: string;
}

export async function getSessions(): Promise<SessionData[]> {
  const db = await getDb();
  return db.select<SessionData[]>('SELECT id, title, created_at FROM sessions ORDER BY created_at DESC');
}

export async function deleteSession(id: string): Promise<void> {
  const db = await getDb();
  await db.execute('DELETE FROM sessions WHERE id=$1', [id]);
}

export async function getMessages(sessionId: string): Promise<MessageHistory[]> {
  const db = await getDb();
  return db.select<MessageHistory[]>(
    'SELECT id, theme, agent_name, content, turn_order FROM messages WHERE session_id=$1 ORDER BY turn_order',
    [sessionId]
  );
}

export async function addMessage(
  sessionId: string,
  theme: string,
  agentName: string,
  content: string,
  turnOrder: number
): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO messages (id, session_id, theme, agent_name, content, turn_order) VALUES ($1, $2, $3, $4, $5, $6)',
    [generateUUID(), sessionId, theme, agentName, content, turnOrder]
  );
}

// -------------------------------------------------------------------
// 特許調査 CRUD
// -------------------------------------------------------------------
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

export interface PatentSummaryData {
  id: string;
  session_id: string;
  summary: string;
}

export async function createPatentSession(id: string, title: string): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO patent_sessions (id, title) VALUES ($1, $2)',
    [id, title]
  );
}

export async function getPatentSessions(): Promise<PatentSessionData[]> {
  const db = await getDb();
  return db.select<PatentSessionData[]>(
    'SELECT id, title, created_at FROM patent_sessions ORDER BY created_at DESC'
  );
}

export async function deletePatentSession(id: string): Promise<void> {
  const db = await getDb();
  await db.execute('DELETE FROM patent_sessions WHERE id=$1', [id]);
}

export async function addPatentReport(
  sessionId: string,
  company: string,
  report: string,
  sortOrder: number
): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO patent_reports (id, session_id, company, report, sort_order) VALUES ($1, $2, $3, $4, $5)',
    [generateUUID(), sessionId, company, report, sortOrder]
  );
}

export async function getPatentReports(sessionId: string): Promise<PatentReportData[]> {
  const db = await getDb();
  return db.select<PatentReportData[]>(
    'SELECT id, session_id, company, report, sort_order FROM patent_reports WHERE session_id=$1 ORDER BY sort_order',
    [sessionId]
  );
}

export async function savePatentSummary(sessionId: string, summary: string): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO patent_summaries (id, session_id, summary) VALUES ($1, $2, $3) ON CONFLICT(session_id) DO UPDATE SET summary=$3',
    [generateUUID(), sessionId, summary]
  );
}

export async function getPatentSummary(sessionId: string): Promise<string> {
  const db = await getDb();
  const rows = await db.select<{ summary: string }[]>(
    'SELECT summary FROM patent_summaries WHERE session_id=$1',
    [sessionId]
  );
  return rows[0]?.summary ?? '';
}
