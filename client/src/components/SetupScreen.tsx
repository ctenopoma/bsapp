import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Persona, ThemeConfig } from '../types/api';
import { getPersonas, createSession } from '../lib/db';
import { apiStartSession } from '../lib/api';
import { Settings, Play, Plus, Trash2 } from 'lucide-react';

interface ThemeEntry {
  localId: string;
  text: string;
  personaIds: Set<string>; // 空 = 全ペルソナ参加
}

function newEntry(): ThemeEntry {
  return { localId: crypto.randomUUID(), text: '', personaIds: new Set() };
}

export default function SetupScreen() {
  const navigate = useNavigate();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [themeEntries, setThemeEntries] = useState<ThemeEntry[]>([newEntry()]);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getPersonas().then(setPersonas).catch(console.error);
  }, []);

  const addTheme = () => setThemeEntries(prev => [...prev, newEntry()]);

  const removeTheme = (localId: string) =>
    setThemeEntries(prev => prev.filter(e => e.localId !== localId));

  const updateText = (localId: string, text: string) =>
    setThemeEntries(prev => prev.map(e => e.localId === localId ? { ...e, text } : e));

  const togglePersona = (localId: string, personaId: string) => {
    setThemeEntries(prev => prev.map(e => {
      if (e.localId !== localId) return e;
      const next = new Set(e.personaIds);
      // 空（全員）の状態でトグルした場合は、全員を選択してから1人除外
      if (next.size === 0) personas.forEach(p => next.add(p.id));
      if (next.has(personaId)) next.delete(personaId);
      else next.add(personaId);
      // 再び全員になったら空（全員）に正規化
      if (next.size === personas.length) next.clear();
      return { ...e, personaIds: next };
    }));
  };

  const isActive = (entry: ThemeEntry, personaId: string) =>
    entry.personaIds.size === 0 || entry.personaIds.has(personaId);

  const handleStart = async () => {
    const valid = themeEntries.filter(e => e.text.trim());
    if (valid.length === 0) { setError('テーマを1つ以上入力してください。'); return; }

    // 全テーマで使われるペルソナのunionを送信
    const usedIds = new Set<string>();
    valid.forEach(e => {
      if (e.personaIds.size === 0) personas.forEach(p => usedIds.add(p.id));
      else e.personaIds.forEach(id => usedIds.add(id));
    });
    const usedPersonas = personas.filter(p => usedIds.has(p.id));
    if (usedPersonas.length === 0) { setError('参加するペルソナがありません。'); return; }

    const themes: ThemeConfig[] = valid.map(e => ({
      theme: e.text.trim(),
      persona_ids: [...e.personaIds],
    }));

    try {
      setIsStarting(true);
      setError('');
      const res = await apiStartSession({ themes, personas: usedPersonas, history: [] });
      const sessionId = res.session_id;
      const title = themes[0].theme.substring(0, 30) + (themes[0].theme.length > 30 ? '...' : '');
      await createSession(sessionId, title);
      navigate(`/discussion/${sessionId}`);
    } catch (e: any) {
      setError(e.message || 'Failed to start session');
      setIsStarting(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto flex flex-col h-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-2">
          <Settings className="text-blue-600" />
          Setup Discussion
        </h1>
        <p className="text-gray-600 mt-2">テーマごとに参加するペルソナを設定してください。</p>
      </div>

      <div className="flex flex-col gap-3">
        {themeEntries.map((entry, idx) => (
          <div key={entry.localId} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            {/* テーマ入力行 */}
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xs font-bold text-gray-400 uppercase tracking-wide w-16 shrink-0">
                Theme {idx + 1}
              </span>
              <input
                type="text"
                value={entry.text}
                onChange={e => updateText(entry.localId, e.target.value)}
                placeholder="テーマを入力..."
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              <button
                onClick={() => removeTheme(entry.localId)}
                disabled={themeEntries.length === 1}
                className="p-1.5 text-gray-300 hover:text-red-500 disabled:opacity-20 transition-colors"
              >
                <Trash2 size={15} />
              </button>
            </div>

            {/* ペルソナ選択チップ */}
            <div className="flex items-center gap-2 flex-wrap pl-[4.75rem]">
              <span className="text-xs text-gray-400">参加:</span>
              {personas.length === 0 ? (
                <span className="text-xs text-red-400">ペルソナがありません</span>
              ) : (
                personas.map(p => {
                  const active = isActive(entry, p.id);
                  return (
                    <button
                      key={p.id}
                      onClick={() => togglePersona(entry.localId, p.id)}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                        active
                          ? 'bg-blue-100 border-blue-400 text-blue-700'
                          : 'bg-gray-100 border-gray-200 text-gray-400 line-through'
                      }`}
                    >
                      {p.name}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={addTheme}
        className="mt-3 flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium self-start transition-colors"
      >
        <Plus size={15} /> テーマを追加
      </button>

      {error && (
        <div className="mt-6 bg-red-50 text-red-700 p-4 rounded-lg border border-red-200">
          <span className="font-medium">{error}</span>
        </div>
      )}

      <div className="mt-8 flex justify-end">
        <button
          onClick={handleStart}
          disabled={isStarting || personas.length === 0}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-md transition-all transform hover:scale-[1.02]"
        >
          <Play size={24} />
          {isStarting ? 'Starting...' : 'Start Discussion'}
        </button>
      </div>
    </div>
  );
}
