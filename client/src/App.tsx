import { useEffect, useState } from "react";
import { Routes, Route, Link, useLocation, useNavigate } from "react-router-dom";
import { MessageSquare, Users, Database, PlayCircle, History, MessageCircle, Trash2, SlidersHorizontal } from "lucide-react";
import { initDb, getSessions, SessionData, deleteSession } from "./lib/db";

import PersonasScreen from './components/PersonasScreen';
import TasksScreen from './components/TasksScreen';
import RagScreen from './components/RagScreen';
import SetupScreen from './components/SetupScreen';
import DiscussionScreen from './components/DiscussionScreen';
import SettingsScreen from './components/SettingsScreen';

function App() {
  const [dbReady, setDbReady] = useState(false);
  const [dbError, setDbError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    initDb().then(() => {
      console.log("Database initialized");
      setDbReady(true);
      loadSessions();
    }).catch(err => {
      console.error("Failed to init database", err);
      setDbError(String(err));
    });
  }, []);

  useEffect(() => {
    if (dbReady) {
      loadSessions();
    }
  }, [location.pathname, dbReady]);

  const loadSessions = async () => {
    try {
      const data = await getSessions();
      setSessions(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.preventDefault(); // 親のLinkナビゲーションを防ぐ
    e.stopPropagation();
    
    if (confirm("本当にこのセッションの履歴を削除しますか？")) {
      try {
        await deleteSession(id);
        await loadSessions();
        // もし今開いているセッションを消した場合、初期画面に戻す
        if (location.pathname === `/discussion/${id}`) {
          navigate('/');
        }
      } catch (err) {
        console.error("Failed to delete session", err);
        alert("削除に失敗しました。");
      }
    }
  };

  if (dbError) {
    return <div className="flex h-screen items-center justify-center bg-gray-50 text-red-600 font-bold">Failed to load database: {dbError}</div>;
  }

  if (!dbReady) {
    return <div className="flex h-screen items-center justify-center bg-gray-50">Loading application...</div>;
  }

  const navItems = [
    { path: "/", label: "New Session", icon: <PlayCircle size={20} /> },
    { path: "/personas", label: "Personas", icon: <Users size={20} /> },
    { path: "/tasks", label: "Tasks", icon: <MessageSquare size={20} /> },
    { path: "/rag", label: "Data Base", icon: <Database size={20} /> },
    { path: "/settings", label: "Settings", icon: <SlidersHorizontal size={20} /> },
  ];

  return (
    <div className="flex h-screen w-screen bg-gray-100 text-gray-800 font-sans overflow-hidden">
      {/* Sidebar Navigation */}
      <nav className="w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm hidden md:flex">
        <div className="p-6 border-b border-gray-100 flex items-center gap-3">
          <MessageSquare className="text-blue-600" size={28} />
          <h1 className="font-bold text-xl tracking-tight text-gray-900">AI Discuss</h1>
        </div>
        <div className="flex-none py-4 flex flex-col gap-1 px-3 border-b border-gray-100">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                location.pathname === item.path
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              }`}
            >
              {item.icon}
              {item.label}
            </Link>
          ))}
        </div>

        {/* History Section */}
        <div className="flex-1 overflow-y-auto py-4 px-3 flex flex-col gap-1">
          <div className="px-4 text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-2">
            <History size={14} /> Recent Sessions
          </div>
          {sessions.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-400 italic">No history yet.</div>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                className={`group flex items-center justify-between px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  location.pathname === `/discussion/${s.id}`
                    ? "bg-blue-50 text-blue-700 font-medium"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                <Link
                  to={`/discussion/${s.id}`}
                  className="flex items-center gap-3 flex-1 overflow-hidden"
                >
                  <MessageCircle size={16} className="text-gray-400 shrink-0" />
                  <span className="truncate">{s.title || "Untitled Session"}</span>
                </Link>
                <button
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md opacity-0 group-hover:opacity-100 transition-all focus:opacity-100"
                  title="Delete Session"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        <Routes>
          <Route path="/" element={<SetupScreen />} />
          <Route path="/discussion/:sessionId" element={<DiscussionScreen />} />
          <Route path="/personas" element={<PersonasScreen />} />
          <Route path="/tasks" element={<TasksScreen />} />
          <Route path="/rag" element={<RagScreen />} />
          <Route path="/settings" element={<SettingsScreen />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
