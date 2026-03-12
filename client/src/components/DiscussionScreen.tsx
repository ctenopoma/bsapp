import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getMessages, addMessage, getSessionConfig } from '../lib/db';
import { MessageHistory } from '../types/api';
import { apiStartTurn, apiGetTurnStatus, apiStartSummarize, apiGetSummarizeStatus, apiEndSession } from '../lib/api';
import { Loader2, Play, Square, FileText, CheckCircle2, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

export default function DiscussionScreen() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef(false);

  const [messages, setMessages] = useState<MessageHistory[]>([]);
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [currentAction, setCurrentAction] = useState<string>('');
  const [copied, setCopied] = useState(false);
  const [commonTheme, setCommonTheme] = useState('');

  useEffect(() => {
    if (sessionId) {
      getMessages(sessionId).then(setMessages).catch(console.error);
    }
    getSessionConfig('common_theme').then(setCommonTheme).catch(console.error);
  }, [sessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, status]);

  const handleStart = async () => {
    if (!sessionId) return;
    abortRef.current = false;
    setStatus('running');

    try {
      while (!abortRef.current) {
        // --- ターン実行 ---
        setCurrentAction('エージェントの応答を待っています...');
        const turnJob = await apiStartTurn(sessionId);

        let isThemeEnd = false;
        let theme = 'Theme';
        while (!abortRef.current) {
          await sleep(3000);
          const turnRes = await apiGetTurnStatus(sessionId, turnJob.job_id);

          if (turnRes.status === 'completed') {
            if (turnRes.all_themes_done) {
              setStatus('done');
              setCurrentAction('全テーマの議論が完了しました。');
              return;
            }
            isThemeEnd = turnRes.is_theme_end ?? false;
            theme = turnRes.theme || 'Theme';
            if (turnRes.agent_name && turnRes.message) {
              const current = await getMessages(sessionId);
              await addMessage(sessionId, theme, turnRes.agent_name, turnRes.message, current.length);
              setMessages(await getMessages(sessionId));
            }
            break;
          } else if (turnRes.status === 'error') {
            throw new Error(turnRes.error_msg || 'Turn failed');
          }
        }

        if (abortRef.current) break;

        // --- テーマ終了 → 要約 ---
        if (isThemeEnd) {
          setCurrentAction('テーマの要約を生成しています...');
          const sumJob = await apiStartSummarize(sessionId);

          let allThemesDone = false;
          while (!abortRef.current) {
            await sleep(3000);
            const sumRes = await apiGetSummarizeStatus(sessionId, sumJob.job_id);

            if (sumRes.status === 'completed') {
              allThemesDone = sumRes.all_themes_done ?? false;
              const current = await getMessages(sessionId);
              await addMessage(sessionId, 'System', 'Summary', sumRes.summary_text || 'Summarized.', current.length);
              setMessages(await getMessages(sessionId));
              break;
            } else if (sumRes.status === 'error') {
              throw new Error(sumRes.error_msg || 'Summary failed');
            }
          }

          if (allThemesDone) {
            setStatus('done');
            setCurrentAction('全テーマの議論が完了しました。');
            return;
          }
        }
      }

      if (abortRef.current) {
        setStatus('idle');
        setCurrentAction('');
      }
    } catch (e: any) {
      setStatus('error');
      setCurrentAction(e.message || 'エラーが発生しました。');
    }
  };

  const handleCopy = async () => {
    // テーマ順を保ちつつグループ化
    const themeOrder: string[] = [];
    const themeMap: Record<string, MessageHistory[]> = {};
    for (const m of messages) {
      if (m.agent_name === 'Summary') continue;
      if (!themeMap[m.theme]) {
        themeOrder.push(m.theme);
        themeMap[m.theme] = [];
      }
      themeMap[m.theme].push(m);
    }
    // Summaryはテーマ名で紐付け
    const summaryMap: Record<string, string> = {};
    for (const m of messages) {
      if (m.agent_name === 'Summary') summaryMap[m.theme] = m.content;
    }

    const sections: string[] = [];
    if (commonTheme) sections.push(`# ${commonTheme}`);

    for (const theme of themeOrder) {
      sections.push(`## ${theme}`);
      for (const m of themeMap[theme]) {
        sections.push(`### ${m.agent_name}\n${m.content}`);
      }
      if (summaryMap[theme]) {
        sections.push(`### Summary\n${summaryMap[theme]}`);
      }
    }

    await navigator.clipboard.writeText(sections.join('\n\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleEndSession = async () => {
    if (!sessionId) return;
    abortRef.current = true;
    setStatus('done');
    try {
      await apiEndSession(sessionId);
      alert('Session Ended and memory cleared on host.');
      navigate('/');
    } catch (e) {
      console.error(e);
      alert('Failed to end session on host. It might already be cleared.');
      navigate('/');
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 relative">
      <div className="bg-white px-6 py-4 flex items-center justify-between border-b border-gray-200 shadow-sm z-10">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2"><FileText className="text-blue-600"/> Discussion Session</h1>
          <p className="text-xs text-gray-400 mt-1 font-mono">{sessionId}</p>
        </div>
        <div className="flex gap-3">
          {messages.length > 0 && (
            <button
              onClick={handleCopy}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors border ${
                copied
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-gray-50 hover:bg-gray-100 text-gray-600 border-gray-200'
              }`}
            >
              {copied ? <Check size={16} /> : <Copy size={16} />}
              {copied ? 'コピーしました' : 'コピー'}
            </button>
          )}

          {status === 'idle' && (
            <button
              onClick={handleStart}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg font-semibold transition-colors shadow-sm"
            >
              <Play size={18} fill="currentColor" />
              Start Discussion
            </button>
          )}

          {status === 'running' && (
            <div className="flex items-center gap-3 bg-blue-50 text-blue-800 px-5 py-2.5 rounded-lg font-medium border border-blue-200">
              <Loader2 size={18} className="animate-spin" />
              {currentAction}
            </div>
          )}

          {status === 'done' && (
            <div className="flex items-center gap-2 bg-green-50 text-green-700 px-5 py-2.5 rounded-lg font-medium border border-green-200">
              <CheckCircle2 size={18} />
              完了
            </div>
          )}

          <button
            onClick={handleEndSession}
            className="flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-700 px-5 py-2.5 rounded-lg font-semibold transition-colors border border-red-200"
          >
            <Square size={18} fill="currentColor" />
            End Session
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 scroll-smooth">
        <div className="max-w-4xl mx-auto flex flex-col gap-6 pb-12">
          {messages.length === 0 && status === 'idle' && (
             <div className="text-center py-20 text-gray-400 bg-white rounded-2xl border border-dashed border-gray-300">
                <p className="text-lg">No messages yet.</p>
                <p className="text-sm">Click "Start Discussion" to begin.</p>
             </div>
          )}

          {messages.map((m, idx) => {
            const isSystem = m.agent_name === 'Summary';

            if (isSystem) {
              return (
                <div key={m.id} className="my-8 mx-auto w-full max-w-3xl bg-yellow-50 border border-yellow-200 p-6 rounded-2xl shadow-sm">
                  <div className="flex items-center gap-2 text-yellow-800 font-bold mb-3">
                    <CheckCircle2 size={20} /> Theme Summary
                  </div>
                  <div className="prose prose-sm prose-yellow max-w-none"><ReactMarkdown>{m.content}</ReactMarkdown></div>
                </div>
              );
            }

            const isEven = m.agent_name.length % 2 === 0;

            return (
              <div key={m.id} className={`flex flex-col gap-1 w-full max-w-3xl ${idx % 2 === 0 ? 'self-start' : 'self-end'}`}>
                <div className={`flex items-center gap-2 ${idx % 2 === 0 ? 'ml-4' : 'mr-4 justify-end flex-row-reverse'}`}>
                  <span className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs ${isEven ? 'bg-indigo-500' : 'bg-pink-500'}`}>
                    {m.agent_name.substring(0,2).toUpperCase()}
                  </span>
                  <span className="text-sm font-semibold text-gray-700">{m.agent_name}</span>
                </div>
                <div className={`${idx % 2 === 0 ? 'mr-12 ml-4 rounded-tl-sm' : 'ml-12 mr-4 rounded-tr-sm bg-blue-50 border-blue-100'} bg-white border border-gray-200 p-5 rounded-2xl shadow-sm text-gray-800 text-[15px] leading-relaxed`}>
                  <div className="prose prose-sm max-w-none"><ReactMarkdown>{m.content}</ReactMarkdown></div>
                </div>
              </div>
            );
          })}

          {status === 'running' && (
            <div className="flex flex-col gap-1 w-full max-w-3xl self-start mt-4 animate-pulse">
               <div className="flex items-center gap-2 ml-4">
                  <span className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center"></span>
                  <span className="text-sm font-semibold text-gray-400">Agent typing...</span>
               </div>
               <div className="mr-12 ml-4 bg-gray-100 border border-gray-200 p-6 rounded-2xl rounded-tl-sm w-48 h-16">
               </div>
            </div>
          )}
        </div>
      </div>

      {status === 'error' && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-red-600 text-white px-6 py-3 rounded-full shadow-lg font-medium tracking-wide">
          {currentAction}
        </div>
      )}
    </div>
  );
}
