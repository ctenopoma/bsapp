import { useEffect, useState } from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import { MessageSquare, Users, Database, PlayCircle } from "lucide-react";
import { initDb } from "./lib/db";

import PersonasScreen from './components/PersonasScreen';
import RagScreen from './components/RagScreen';
import SetupScreen from './components/SetupScreen';
import DiscussionScreen from './components/DiscussionScreen';

function App() {
  const [dbReady, setDbReady] = useState(false);
  const location = useLocation();

  useEffect(() => {
    initDb().then(() => {
      console.log("Database initialized");
      setDbReady(true);
    }).catch(err => {
      console.error("Failed to init database", err);
    });
  }, []);

  if (!dbReady) {
    return <div className="flex h-screen items-center justify-center bg-gray-50">Loading application...</div>;
  }

  const navItems = [
    { path: "/", label: "New Session", icon: <PlayCircle size={20} /> },
    { path: "/personas", label: "Personas", icon: <Users size={20} /> },
    { path: "/rag", label: "Data Base", icon: <Database size={20} /> },
  ];

  return (
    <div className="flex h-screen w-screen bg-gray-100 text-gray-800 font-sans overflow-hidden">
      {/* Sidebar Navigation */}
      <nav className="w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm hidden md:flex">
        <div className="p-6 border-b border-gray-100 flex items-center gap-3">
          <MessageSquare className="text-blue-600" size={28} />
          <h1 className="font-bold text-xl tracking-tight text-gray-900">AI Discuss</h1>
        </div>
        <div className="flex-1 py-4 flex flex-col gap-1 px-3">
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
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        <Routes>
          <Route path="/" element={<SetupScreen />} />
          <Route path="/discussion/:sessionId" element={<DiscussionScreen />} />
          <Route path="/personas" element={<PersonasScreen />} />
          <Route path="/rag" element={<RagScreen />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
