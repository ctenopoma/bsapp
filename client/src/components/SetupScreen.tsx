import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Persona, ThemeConfig } from '../types/api';
import { getPersonas, createSession } from '../lib/db';
import { apiStartSession } from '../lib/api';
import { Settings, Play, Users } from 'lucide-react';

export default function SetupScreen() {
  const navigate = useNavigate();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<Set<string>>(new Set());
  const [themesInput, setThemesInput] = useState<string>('');
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getPersonas().then(data => {
      setPersonas(data);
    }).catch(console.error);
  }, []);

  const togglePersona = (id: string) => {
    const next = new Set(selectedPersonaIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedPersonaIds(next);
  };

  const handleStart = async () => {
    if (selectedPersonaIds.size === 0) {
      setError('Please select at least one persona.');
      return;
    }
    const themeStrings = themesInput.split('\n').map(s => s.trim()).filter(Boolean);
    if (themeStrings.length === 0) {
      setError('Please enter at least one theme.');
      return;
    }

    try {
      setIsStarting(true);
      setError('');

      const selectedPersonas = personas.filter(p => selectedPersonaIds.has(p.id));
      const themes: ThemeConfig[] = themeStrings.map(t => ({ theme: t, persona_ids: [] }));

      // Call host to start session
      const res = await apiStartSession({
        themes,
        personas: selectedPersonas,
        history: [] // New session
      });
      
      const sessionId = res.session_id;
      
      // Save session info to local SQLite
      const title = themes[0].substring(0, 30) + (themes[0].length > 30 ? '...' : '');
      await createSession(sessionId, title);
      
      // Navigate to discussion board
      navigate(`/discussion/${sessionId}`);
      
    } catch (e: any) {
      setError(e.message || 'Failed to start session');
      setIsStarting(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto flex flex-col h-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-2">
          <Settings className="text-blue-600" />
          Setup Discussion
        </h1>
        <p className="text-gray-600 mt-2">Configure the discussion themes and select participating agents.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        
        {/* Themes Column */}
        <div className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold text-gray-800 border-b border-gray-100 pb-2">1. Discussion Themes</h2>
          <p className="text-sm text-gray-500">Enter each theme or topic on a new line. The agents will discuss them in order.</p>
          <textarea
            value={themesInput}
            onChange={e => setThemesInput(e.target.value)}
            placeholder={"First Theme Example\nSecond Theme Example..."}
            rows={8}
            className="w-full border border-gray-300 rounded-lg p-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-none shadow-sm font-medium"
          />
        </div>

        {/* Personas Column */}
        <div className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold text-gray-800 border-b border-gray-100 pb-2 flex items-center gap-2">
            <Users size={18}/> 2. Select Personas
          </h2>
          <div className="flex flex-col gap-2 overflow-y-auto max-h-[250px] pr-2 custom-scrollbar">
            {personas.length === 0 ? (
              <p className="text-sm text-red-500">No personas found. Please create some in the Personas tab first.</p>
            ) : (
              personas.map(p => (
                <label 
                  key={p.id} 
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedPersonaIds.has(p.id) ? 'border-blue-500 bg-blue-50 shadow-sm' : 'border-gray-200 hover:bg-gray-50'}`}
                >
                  <input 
                    type="checkbox" 
                    className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-blue-500 cursor-pointer"
                    checked={selectedPersonaIds.has(p.id)}
                    onChange={() => togglePersona(p.id)}
                  />
                  <div>
                    <div className="font-semibold text-gray-900">{p.name}</div>
                    <div className="text-xs text-blue-600">{p.role}</div>
                  </div>
                </label>
              ))
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-6 bg-red-50 text-red-700 p-4 rounded-lg flex items-center border border-red-200">
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
          {isStarting ? 'Starting Server Session...' : 'Start Discussion Session'}
        </button>
      </div>
    </div>
  );
}
