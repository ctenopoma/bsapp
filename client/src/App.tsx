import { useEffect, useState } from "react";
import { Routes, Route, Link, useLocation, useNavigate } from "react-router-dom";
import { MessageSquare, Users, Database, PlayCircle, History, MessageCircle, Trash2, SlidersHorizontal, FlaskConical, ShieldCheck, LogOut, BookOpen } from "lucide-react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { setAuthToken } from "./lib/api";
import { getSessions, SessionData } from "./lib/server-db";

import LoginScreen from './components/LoginScreen';
import PersonasScreen from './components/PersonasScreen';
import TasksScreen from './components/TasksScreen';
import RagScreen from './components/RagScreen';
import SetupScreen from './components/SetupScreen';
import DiscussionScreen from './components/DiscussionScreen';
import SettingsScreen from './components/SettingsScreen';
import PatentResearchScreen from './components/PatentResearchScreen';
import AdminScreen from './components/AdminScreen';
import ManualScreen from './components/ManualScreen';

// ─── Inner app (needs auth context) ─────────────────────────────────────────
function AppShell() {
  const { ready, user, token, logout } = useAuth();
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const location = useLocation();
  const navigate = useNavigate();

  // Sync auth token to api.ts fetch helper
  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  // Load session history from server whenever location changes
  useEffect(() => {
    if (user?.is_approved) {
      getSessions().then(setSessions).catch(() => {});
    }
  }, [location.pathname, user]);

  if (!ready) {
    return <div className="flex h-screen items-center justify-center bg-gray-50">Loading...</div>;
  }

  // Not logged in
  if (!user) {
    return <LoginScreen />;
  }

  // Logged in but not yet approved
  if (!user.is_approved) {
    return <LoginScreen pending />;
  }

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("本当にこのセッションの履歴を削除しますか？")) return;
    try {
      const { deleteSession } = await import('./lib/server-db');
      await deleteSession(id);
      setSessions(prev => prev.filter(s => s.id !== id));
      if (location.pathname === `/discussion/${id}`) navigate('/');
    } catch (err) {
      console.error("Failed to delete session", err);
      alert("削除に失敗しました。");
    }
  };

  const navItems = [
    { path: "/", label: "New Session", icon: <PlayCircle size={20} /> },
    { path: "/personas", label: "Personas", icon: <Users size={20} /> },
    { path: "/tasks", label: "Tasks", icon: <MessageSquare size={20} /> },
    { path: "/rag", label: "Data Base", icon: <Database size={20} /> },
    { path: "/patent", label: "Patent Research", icon: <FlaskConical size={20} /> },
    { path: "/settings", label: "Settings", icon: <SlidersHorizontal size={20} /> },
    { path: "/manual", label: "Manual", icon: <BookOpen size={20} /> },
    ...(user.is_admin ? [{ path: "/admin", label: "Admin", icon: <ShieldCheck size={20} /> }] : []),
  ];

  return (
    <div className="flex h-screen w-screen bg-gray-100 text-gray-800 font-sans overflow-hidden">
      {/* Sidebar */}
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

        {/* History */}
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
                <Link to={`/discussion/${s.id}`} className="flex items-center gap-3 flex-1 overflow-hidden">
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

        {/* User info + logout */}
        <div className="p-3 border-t border-gray-100">
          <div className="flex items-center gap-2 px-2 py-2 rounded-lg">
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-gray-700 truncate">{user.display_name || user.email}</div>
              <div className="text-xs text-gray-400 truncate">{user.email}</div>
            </div>
            <button
              onClick={logout}
              className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors shrink-0"
              title="ログアウト"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </nav>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden bg-gray-50">
        <div className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<SetupScreen />} />
            <Route path="/discussion/:sessionId" element={<DiscussionScreen />} />
            <Route path="/personas" element={<PersonasScreen />} />
            <Route path="/tasks" element={<TasksScreen />} />
            <Route path="/rag" element={<RagScreen />} />
            <Route path="/patent" element={<PatentResearchScreen />} />
            <Route path="/settings" element={<SettingsScreen />} />
            <Route path="/manual" element={<ManualScreen />} />
            {user.is_admin && <Route path="/admin" element={<AdminScreen />} />}
          </Routes>
        </div>
      </main>
    </div>
  );
}

// ─── Root with AuthProvider ──────────────────────────────────────────────────
function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}

export default App;
