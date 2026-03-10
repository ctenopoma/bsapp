import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getMessages, addMessage } from '../lib/db';
import { MessageHistory } from '../types/api';
import { apiStartTurn, apiGetTurnStatus, apiStartSummarize, apiGetSummarizeStatus, apiEndSession } from '../lib/api';
import { Loader2, Play, Square, FileText, CheckCircle2 } from 'lucide-react';

export default function DiscussionScreen() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<MessageHistory[]>([]);
  const [status, setStatus] = useState<'idle' | 'generating' | 'summarizing' | 'ended' | 'error'>('idle');
  const [currentAction, setCurrentAction] = useState<string>('');
  const [abortFlag, setAbortFlag] = useState(false);

  useEffect(() => {
    if (sessionId) {
      getMessages(sessionId).then(setMessages).catch(console.error);
    }
  }, [sessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, status]);

  const handleNextTurn = async () => {
    if (!sessionId || abortFlag) return;
    try {
      setStatus('generating');
      setCurrentAction('Waiting for agent response...');
      
      const res = await apiStartTurn(sessionId);
      
      const poll = setInterval(async () => {
        if (abortFlag) {
          clearInterval(poll);
          setStatus('idle');
          return;
        }

        try {
          const statusRes = await apiGetTurnStatus(sessionId, res.job_id);
          
          if (statusRes.status === 'completed') {
            clearInterval(poll);
            
            // Save to DB
            const turnOrder = messages.length;
            const theme = "Current Theme"; // Ideally fetch actual theme from backend/DB if stored
            
            if (statusRes.agent_name && statusRes.message) {
              await addMessage(sessionId, theme, statusRes.agent_name, statusRes.message, turnOrder);
              const updatedMessages = await getMessages(sessionId);
              setMessages(updatedMessages);
            }

            if (statusRes.is_theme_end) {
              handleSummarize();
            } else {
              setStatus('idle');
              // Automatically proceed? Spec implies user action or looped. 
              // We'll leave it to user click for debugging, or we can auto-trigger.
            }
          } else if (statusRes.status === 'error') {
            clearInterval(poll);
            setStatus('error');
            setCurrentAction(`Error: ${statusRes.error_msg}`);
          }
        } catch (e: any) {
          clearInterval(poll);
          setStatus('error');
          setCurrentAction('Failed to poll status.');
        }
      }, 3000);
      
    } catch (e: any) {
      setStatus('error');
      setCurrentAction(e.message || 'Failed to start turn.');
    }
  };

  const handleSummarize = async () => {
    if (!sessionId || abortFlag) return;
    try {
      setStatus('summarizing');
      setCurrentAction('Generating theme summary...');
      const res = await apiStartSummarize(sessionId);
      
      const poll = setInterval(async () => {
         if (abortFlag) {
          clearInterval(poll);
          setStatus('idle');
          return;
        }

        try {
          const statusRes = await apiGetSummarizeStatus(sessionId, res.job_id);
          if (statusRes.status === 'completed') {
            clearInterval(poll);
            setStatus('idle');
            
            // Save summary as a system message
            await addMessage(sessionId, "System", "Summary", statusRes.summary_text || "Summarized.", messages.length);
            const updatedMessages = await getMessages(sessionId);
            setMessages(updatedMessages);
          } else if (statusRes.status === 'error') {
            clearInterval(poll);
            setStatus('error');
            setCurrentAction(`Summary Error: ${statusRes.error_msg}`);
          }
        } catch(e) {
          clearInterval(poll);
          setStatus('error');
          setCurrentAction('Failed to poll summary status.');
        }
      }, 3000);
    } catch (e: any) {
      setStatus('error');
      setCurrentAction(e.message || 'Failed to start summarize.');
    }
  };

  const handleEndSession = async () => {
    if (!sessionId) return;
    setAbortFlag(true);
    setStatus('ended');
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
          {status === 'idle' && (
            <button 
              onClick={handleNextTurn}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg font-semibold transition-colors shadow-sm"
            >
              <Play size={18} fill="currentColor" />
              Next Turn
            </button>
          )}
          
          {(status === 'generating' || status === 'summarizing') && (
            <div className="flex items-center gap-3 bg-blue-50 text-blue-800 px-5 py-2.5 rounded-lg font-medium border border-blue-200">
              <Loader2 size={18} className="animate-spin" />
              {currentAction}
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
                <p className="text-sm">Click "Next Turn" to start the discussion.</p>
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
                  <div className="prose prose-sm prose-yellow max-w-none whitespace-pre-wrap">{m.content}</div>
                </div>
              );
            }

            // Alternating avatar colors for different agents
            const isEven = m.agent_name.length % 2 === 0;
            
            return (
              <div key={m.id} className={`flex flex-col gap-1 w-full max-w-3xl ${idx % 2 === 0 ? 'self-start' : 'self-end'}`}>
                <div className={`flex items-center gap-2 ${idx % 2 === 0 ? 'ml-4' : 'mr-4 justify-end flex-row-reverse'}`}>
                  <span className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs ${isEven ? 'bg-indigo-500' : 'bg-pink-500'}`}>
                    {m.agent_name.substring(0,2).toUpperCase()}
                  </span>
                  <span className="text-sm font-semibold text-gray-700">{m.agent_name}</span>
                </div>
                <div className={`${idx % 2 === 0 ? 'mr-12 ml-4 rounded-tl-sm' : 'ml-12 mr-4 rounded-tr-sm bg-blue-50 border-blue-100'} bg-white border border-gray-200 p-5 rounded-2xl shadow-sm text-gray-800 text-[15px] leading-relaxed whitespace-pre-wrap`}>
                  {m.content}
                </div>
              </div>
            );
          })}
          
          {(status === 'generating' || status === 'summarizing') && (
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
