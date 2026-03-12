import Database from '@tauri-apps/plugin-sql';
import { Persona, TaskModel, MessageHistory } from '../types/api';

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
      role TEXT NOT NULL
    )
  `);
  
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
      sort_order INTEGER NOT NULL DEFAULT 0
    )
  `);
  return _db;
}

export async function getPersonas(): Promise<Persona[]> {
  const db = await getDb();
  return db.select<Persona[]>('SELECT id, name, role FROM personas ORDER BY rowid');
}

export async function addPersona(p: Persona): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO personas (id, name, role) VALUES ($1, $2, $3)',
    [p.id, p.name, p.role]
  );
}

export async function updatePersona(p: Persona): Promise<void> {
  const db = await getDb();
  await db.execute(
    'UPDATE personas SET name=$1, role=$2 WHERE id=$3',
    [p.name, p.role, p.id]
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
  sort_order: number;
}

export async function getThemeEntries(): Promise<ThemeEntry[]> {
  const db = await getDb();
  return db.select<ThemeEntry[]>('SELECT id, text, persona_ids, sort_order FROM theme_entries ORDER BY sort_order');
}

export async function saveThemeEntries(entries: ThemeEntry[]): Promise<void> {
  const db = await getDb();
  await db.execute('DELETE FROM theme_entries', []);
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    await db.execute(
      'INSERT INTO theme_entries (id, text, persona_ids, sort_order) VALUES ($1, $2, $3, $4)',
      [e.id, e.text, e.persona_ids, i]
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
    [crypto.randomUUID(), sessionId, theme, agentName, content, turnOrder]
  );
}
