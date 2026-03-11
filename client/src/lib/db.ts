import Database from '@tauri-apps/plugin-sql';
import { Persona, MessageHistory } from '../types/api';

let _db: Database | null = null;

export async function initDb(): Promise<void> {
  await getDb();
}

async function getDb(): Promise<Database> {
  if (_db) return _db;
  _db = await Database.load('sqlite:bsapp.db');
  // スキーマ初期化
  await _db.execute(`
    CREATE TABLE IF NOT EXISTS personas (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      role TEXT NOT NULL,
      task TEXT NOT NULL
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
  return _db;
}

export async function getPersonas(): Promise<Persona[]> {
  const db = await getDb();
  return db.select<Persona[]>('SELECT id, name, role, task FROM personas ORDER BY rowid');
}

export async function addPersona(p: Persona): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO personas (id, name, role, task) VALUES ($1, $2, $3, $4)',
    [p.id, p.name, p.role, p.task]
  );
}

export async function updatePersona(p: Persona): Promise<void> {
  const db = await getDb();
  await db.execute(
    'UPDATE personas SET name=$1, role=$2, task=$3 WHERE id=$4',
    [p.name, p.role, p.task, p.id]
  );
}

export async function deletePersona(id: string): Promise<void> {
  const db = await getDb();
  await db.execute('DELETE FROM personas WHERE id=$1', [id]);
}

export async function createSession(id: string, title: string): Promise<void> {
  const db = await getDb();
  await db.execute(
    'INSERT INTO sessions (id, title) VALUES ($1, $2)',
    [id, title]
  );
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
