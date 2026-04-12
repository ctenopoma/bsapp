import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { writeText } from '@tauri-apps/plugin-clipboard-manager';
import { getMessages, addMessage, getSession } from '../lib/server-db';
import { MessageHistory } from '../types/api';
import { apiStartTurn, apiGetTurnStatus, apiStartSummarize, apiGetSummarizeStatus } from '../lib/api';
import { Loader2, Play, FileText, CheckCircle2, Copy, Check, Minimize2, ChevronDown, ChevronRight, ClipboardList, Database, FlaskConical } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

interface ThemeGroup {
  theme: string;
  messages: MessageHistory[];
}

function buildThemeGroups(messages: MessageHistory[]): ThemeGroup[] {
  const groups: ThemeGroup[] = [];
  for (const m of messages) {
    const isSystemMsg = m.agent_name === 'Summary' || m.agent_name === '[会話圧縮]';
    const themeKey = isSystemMsg
      ? (groups.length > 0 ? groups[groups.length - 1].theme : 'System')
      : m.theme;
    if (groups.length === 0 || groups[groups.length - 1].theme !== themeKey) {
      groups.push({ theme: themeKey, messages: [m] });
    } else {
      groups[groups.length - 1].messages.push(m);
    }
  }
  return groups;
}

function agentMessages(group: ThemeGroup) {
  return group.messages.filter(m => m.agent_name !== 'Summary' && m.agent_name !== '[会話圧縮]');
}

function shortThemeName(theme: string): string {
  const firstLine = theme.split('\n')[0].trim();
  if (firstLine.length <= 35) return firstLine;
  return firstLine.slice(0, 35) + '…';
}

export default function DiscussionScreen() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef(false);

  const [messages, setMessages] = useState<MessageHistory[]>([]);
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [currentAction, setCurrentAction] = useState<string>('');
  const [copiedState, setCopiedState] = useState<null | string>(null);
  const [commonTheme, setCommonTheme] = useState('');
  const [preInfo, setPreInfo] = useState('');

  const [openThemes, setOpenThemes] = useState<Set<string>>(new Set());
  const [openMessages, setOpenMessages] = useState<Set<string>>(new Set());
  const [openThemeTexts, setOpenThemeTexts] = useState<Set<string>>(new Set());
  const [openSummaries, setOpenSummaries] = useState<Set<string>>(new Set());
  const [openRagContexts, setOpenRagContexts] = useState<Set<string>>(new Set());
  const [openPatentContexts, setOpenPatentContexts] = useState<Set<string>>(new Set());
  // テーマ単位の特許分析結果（theme → patent_context）
  const [themePatentContexts, setThemePatentContexts] = useState<Record<string, string>>({});
  const initializedRef = useRef(false);

  useEffect(() => {
    if (sessionId) {
      getMessages(sessionId).then(msgs => {
        setMessages(msgs);
        // 履歴からテーマ単位のpatent_contextを復元
        const patentMap: Record<string, string> = {};
        for (const m of msgs) {
          if (m.patent_context && !patentMap[m.theme]) {
            patentMap[m.theme] = m.patent_context;
          }
        }
        if (Object.keys(patentMap).length > 0) {
          setThemePatentContexts(patentMap);
        }
      }).catch(console.error);
      getSession(sessionId).then(sess => {
        setCommonTheme(sess.common_theme || '');
        setPreInfo(sess.pre_info || '');
      }).catch(console.error);
    }
  }, [sessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, status]);

  // テーマ・メッセージの開閉状態管理
  useEffect(() => {
    if (messages.length === 0) return;
    const groups = buildThemeGroups(messages);
    if (groups.length === 0) return;
    const lastGroup = groups[groups.length - 1];
    const lastTheme = lastGroup.theme;
    const lastAgents = agentMessages(lastGroup);
    const lastMsg = lastAgents[lastAgents.length - 1];

    if (!initializedRef.current) {
      initializedRef.current = true;
      setOpenThemes(new Set([lastTheme]));
      setOpenMessages(lastMsg ? new Set([lastMsg.id]) : new Set());
    } else {
      setOpenThemes(prev => new Set([...prev, lastTheme]));
      if (lastMsg) setOpenMessages(prev => new Set([...prev, lastMsg.id]));
    }
  }, [messages]);

  const toggleTheme = (theme: string) => {
    setOpenThemes(prev => {
      const next = new Set(prev);
      if (next.has(theme)) next.delete(theme); else next.add(theme);
      return next;
    });
  };

  const toggleMessage = (id: string) => {
    setOpenMessages(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleThemeText = (theme: string) => {
    setOpenThemeTexts(prev => {
      const next = new Set(prev);
      if (next.has(theme)) next.delete(theme); else next.add(theme);
      return next;
    });
  };

  const toggleSummary = (id: string) => {
    setOpenSummaries(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleRagContext = (id: string) => {
    setOpenRagContexts(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const togglePatentContext = (theme: string) => {
    setOpenPatentContexts(prev => {
      const next = new Set(prev);
      if (next.has(theme)) next.delete(theme); else next.add(theme);
      return next;
    });
  };

  const handleStart = async () => {
    if (!sessionId) return;
    abortRef.current = false;
    setStatus('running');

    try {
      while (!abortRef.current) {
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
              notifyDone();
              return;
            }
            isThemeEnd = turnRes.is_theme_end ?? false;
            theme = turnRes.theme || 'Theme';
            // 特許分析結果をテーマ単位で保存（最初のターンのみ）
            if (turnRes.patent_context) {
              setThemePatentContexts(prev => ({ ...prev, [theme]: turnRes.patent_context! }));
            }
            if (turnRes.agent_name && turnRes.message) {
              const current = await getMessages(sessionId);
              if (turnRes.history_compressed) {
                await addMessage(sessionId, theme, '[会話圧縮]', '会話履歴が長くなったため、古い部分を要約圧縮しました。', current.length);
              }
              const afterCompress = turnRes.history_compressed ? await getMessages(sessionId) : current;
              await addMessage(sessionId, theme, turnRes.agent_name, turnRes.message, afterCompress.length, turnRes.rag_context, turnRes.patent_context);
              const updated = await getMessages(sessionId);
              setMessages(updated);
            }
            break;
          } else if (turnRes.status === 'error') {
            throw new Error(turnRes.error_msg || 'Turn failed');
          }
        }

        if (abortRef.current) break;

        if (isThemeEnd) {
          setCurrentAction('テーマの要約を生成しています...');
          const sumJob = await apiStartSummarize(sessionId);

          let allThemesDone = false;
          while (!abortRef.current) {
            await sleep(3000);
            const sumRes = await apiGetSummarizeStatus(sessionId, sumJob.job_id);

            if (sumRes.status === 'completed') {
              allThemesDone = sumRes.all_themes_done ?? false;
              if (sumRes.summary_text) {
                const current = await getMessages(sessionId);
                await addMessage(sessionId, 'System', 'Summary', sumRes.summary_text, current.length);
                setMessages(await getMessages(sessionId));
              }
              break;
            } else if (sumRes.status === 'error') {
              throw new Error(sumRes.error_msg || 'Summary failed');
            }
          }

          if (allThemesDone) {
            setStatus('done');
            setCurrentAction('全テーマの議論が完了しました。');
            notifyDone();
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

  const notifyDone = async () => {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
      await Notification.requestPermission();
    }
    if (Notification.permission === 'granted') {
      new Notification('AI Discuss', { body: '全テーマの議論が完了しました。' });
    }
  };

  const triggerCopied = (key: string) => {
    setCopiedState(key);
    setTimeout(() => setCopiedState(null), 2000);
  };

  const safeCopyToClipboard = async (text: string, key: string) => {
    const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
    
    if (isTauri) {
      try {
        await writeText(text);
        triggerCopied(key);
        return;
      } catch (err) {
        console.warn('Tauri clipboard copy failed, falling back to browser API:', err);
      }
    }

    if (navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(text);
        triggerCopied(key);
        return;
      } catch (fallbackErr) {
        console.warn('navigator.clipboard failed, trying execCommand:', fallbackErr);
      }
    }

    // HTTP環境など非セキュアコンテキスト向けフォールバック
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const success = document.execCommand('copy');
      document.body.removeChild(textarea);
      if (success) {
        triggerCopied(key);
      } else {
        console.error('execCommand copy failed.');
      }
    } catch (execErr) {
      console.error('No clipboard API available in this environment.', execErr);
    }
  };

  const handleCopyAll = async () => {
    const groups = buildThemeGroups(messages);
    const sections: string[] = [];
    if (commonTheme) sections.push(`# 共通テーマ\n${commonTheme}`);
    if (preInfo) sections.push(`## 事前情報\n${preInfo}`);
    for (const group of groups) {
      if (sections.length > 0) sections.push(`---`);
      sections.push(`## テーマ: ${group.theme}`);
      if (themePatentContexts[group.theme]) {
        sections.push(`### 特許分析結果\n${themePatentContexts[group.theme]}`);
      }
      for (const m of group.messages) {
        if (m.agent_name === '[会話圧縮]') continue;
        if (m.agent_name === 'Summary') {
          sections.push(`### 要約\n${m.content}`);
        } else {
          sections.push(`### ${m.agent_name}\n${m.content}`);
        }
      }
    }
    await safeCopyToClipboard(sections.join('\n\n'), 'all');
  };

  const handleCopyTheme = async (group: ThemeGroup) => {
    const sections: string[] = [`## テーマ: ${group.theme}`];
    if (themePatentContexts[group.theme]) {
      sections.push(`### 特許分析結果\n${themePatentContexts[group.theme]}`);
    }
    for (const m of group.messages) {
      if (m.agent_name === '[会話圧縮]') continue;
      if (m.agent_name === 'Summary') {
        sections.push(`### 要約\n${m.content}`);
      } else {
        sections.push(`### ${m.agent_name}\n${m.content}`);
      }
    }
    await safeCopyToClipboard(sections.join('\n\n'), `theme:${group.theme}`);
  };

  const handleCopyAllSummaries = async () => {
    const groups = buildThemeGroups(messages);
    const sections: string[] = [];
    if (commonTheme) sections.push(`# 共通テーマ\n${commonTheme}`);
    if (preInfo) sections.push(`## 事前情報\n${preInfo}`);
    let firstTheme = true;
    for (const group of groups) {
      const summary = group.messages.find(m => m.agent_name === 'Summary');
      if (summary) {
        if (!firstTheme || sections.length > 0) sections.push(`---`);
        sections.push(`## テーマ: ${group.theme}\n\n### 要約\n${summary.content}`);
        firstTheme = false;
      }
    }
    if (sections.length === 0) return;
    await safeCopyToClipboard(sections.join('\n\n'), 'summaries');
  };

  const hasSummaries = messages.some(m => m.agent_name === 'Summary');
  const groups = buildThemeGroups(messages);

  return (
    <div className="flex flex-col h-full bg-slate-50 relative">
      <div className="bg-white px-6 py-4 flex items-center justify-between border-b border-gray-200 shadow-sm z-10">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2"><FileText className="text-blue-600"/> Discussion Session</h1>
          <p className="text-xs text-gray-400 mt-1 font-mono">{sessionId}</p>
        </div>
        <div className="flex gap-2">
          {hasSummaries && (
            <button
              onClick={handleCopyAllSummaries}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors border text-sm ${
                copiedState === 'summaries'
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-amber-50 hover:bg-amber-100 text-amber-700 border-amber-200'
              }`}
            >
              {copiedState === 'summaries' ? <Check size={15} /> : <ClipboardList size={15} />}
              {copiedState === 'summaries' ? 'コピーしました' : '全要約コピー'}
            </button>
          )}

          {messages.length > 0 && (
            <button
              onClick={handleCopyAll}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors border text-sm ${
                copiedState === 'all'
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-gray-50 hover:bg-gray-100 text-gray-600 border-gray-200'
              }`}
            >
              {copiedState === 'all' ? <Check size={15} /> : <Copy size={15} />}
              {copiedState === 'all' ? 'コピーしました' : '全コピー'}
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

        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 scroll-smooth">
        <div className="w-full flex flex-col gap-4 pb-12">
          {messages.length === 0 && status === 'idle' && (
            <div className="text-center py-20 text-gray-400 bg-white rounded-2xl border border-dashed border-gray-300">
              <p className="text-lg">No messages yet.</p>
              <p className="text-sm">Click "Start Discussion" to begin.</p>
            </div>
          )}

          {groups.map((group) => {
            const isThemeOpen = openThemes.has(group.theme);
            const isThemeTextOpen = openThemeTexts.has(group.theme);
            const themeKey = `theme:${group.theme}`;
            const themeCopied = copiedState === themeKey;
            const shortName = shortThemeName(group.theme);
            const hasLongTheme = group.theme.length > shortName.replace('…', '').length + 1;

            return (
              <div key={group.theme} className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
                {/* テーマヘッダー */}
                <div className="bg-gray-50 border-b border-gray-200">
                  <div className="flex items-center gap-2 px-5 py-3">
                    <button
                      onClick={() => toggleTheme(group.theme)}
                      className="flex items-center gap-2 flex-1 text-left hover:text-blue-700 transition-colors min-w-0"
                    >
                      {isThemeOpen
                        ? <ChevronDown size={16} className="text-gray-400 shrink-0" />
                        : <ChevronRight size={16} className="text-gray-400 shrink-0" />}
                      <span className="font-bold text-gray-800 truncate">{shortName}</span>
                      {!isThemeOpen && (
                        <span className="text-xs text-gray-400 ml-2 shrink-0">
                          {agentMessages(group).length} 件の発言
                          {group.messages.some(m => m.agent_name === 'Summary') ? ' · 要約あり' : ''}
                        </span>
                      )}
                    </button>
                    {hasLongTheme && (
                      <button
                        onClick={() => toggleThemeText(group.theme)}
                        className={`shrink-0 text-xs px-2 py-1 rounded transition-colors border ${
                          isThemeTextOpen
                            ? 'bg-blue-50 text-blue-600 border-blue-200'
                            : 'bg-white text-gray-500 border-gray-200 hover:bg-gray-100'
                        }`}
                      >
                        {isThemeTextOpen ? 'テーマを閉じる' : 'テーマ全文'}
                      </button>
                    )}
                    <button
                      onClick={() => handleCopyTheme(group)}
                      className={`shrink-0 flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-colors border ${
                        themeCopied
                          ? 'bg-green-50 text-green-700 border-green-200'
                          : 'bg-white hover:bg-gray-100 text-gray-500 border-gray-200'
                      }`}
                    >
                      {themeCopied ? <Check size={12} /> : <Copy size={12} />}
                      {themeCopied ? 'コピー済' : 'コピー'}
                    </button>
                  </div>
                  {isThemeTextOpen && (
                    <div className="px-5 pb-4 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap border-t border-gray-200 bg-white py-4">
                      {group.theme}
                    </div>
                  )}
                </div>

                {/* テーマ本文 */}
                {isThemeOpen && (
                  <div className="flex flex-col gap-0">
                    {/* 特許分析結果（テーマ単位で表示） */}
                    {themePatentContexts[group.theme] && (() => {
                      const patentCtx = themePatentContexts[group.theme];
                      const isPatentOpen = openPatentContexts.has(group.theme);
                      return (
                        <div className="mx-5 mt-4 bg-purple-50 border border-purple-200 rounded-xl overflow-hidden">
                          <button
                            onClick={() => togglePatentContext(group.theme)}
                            className="w-full flex items-center gap-2 px-5 py-3 text-purple-800 font-bold hover:bg-purple-100 transition-colors"
                          >
                            {isPatentOpen
                              ? <ChevronDown size={16} className="shrink-0" />
                              : <ChevronRight size={16} className="shrink-0" />}
                            <FlaskConical size={16} className="shrink-0" />
                            <span>特許分析結果</span>
                            <span className="ml-auto text-xs text-purple-400 font-normal">
                              {patentCtx.length.toLocaleString()} 文字
                            </span>
                            <button
                              onClick={e => { e.stopPropagation(); safeCopyToClipboard(patentCtx, `patent:${group.theme}`); }}
                              className={`ml-2 flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-colors border ${
                                copiedState === `patent:${group.theme}`
                                  ? 'bg-green-100 text-green-700 border-green-300'
                                  : 'bg-white text-purple-600 border-purple-200 hover:bg-purple-100'
                              }`}
                            >
                              {copiedState === `patent:${group.theme}` ? <Check size={11} /> : <Copy size={11} />}
                              {copiedState === `patent:${group.theme}` ? 'コピー済' : 'コピー'}
                            </button>
                          </button>
                          {isPatentOpen && (
                            <div className="px-5 pb-5 pt-1">
                              <div className="prose prose-sm prose-purple max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{patentCtx}</ReactMarkdown>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                    {group.messages.map((m) => {
                      if (m.agent_name === '[会話圧縮]') {
                        return (
                          <div key={m.id} className="mx-5 my-3 flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-200 rounded-lg text-blue-700 text-xs">
                            <Minimize2 size={14} className="shrink-0" />
                            <span>{m.content}</span>
                          </div>
                        );
                      }

                      if (m.agent_name === 'Summary') {
                        const isSummaryOpen = openSummaries.has(m.id);
                        return (
                          <div key={m.id} className="mx-5 my-4 bg-yellow-50 border border-yellow-200 rounded-xl overflow-hidden">
                            <button
                              onClick={() => toggleSummary(m.id)}
                              className="w-full flex items-center gap-2 px-5 py-3 text-yellow-800 font-bold hover:bg-yellow-100 transition-colors"
                            >
                              {isSummaryOpen
                                ? <ChevronDown size={16} className="shrink-0" />
                                : <ChevronRight size={16} className="shrink-0" />}
                              <CheckCircle2 size={16} className="shrink-0" />
                              <span>Theme Summary</span>
                            </button>
                            {isSummaryOpen && (
                              <div className="px-5 pb-5 pt-1">
                                <div className="prose prose-sm prose-yellow max-w-none">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      }

                      const isEven = m.agent_name.length % 2 === 0;
                      const isMsgOpen = openMessages.has(m.id);
                      const preview = m.content.replace(/\n/g, ' ').slice(0, 80);
                      const hasMore = m.content.length > 80;
                      const ragContext = m.rag_context;
                      const isRagOpen = openRagContexts.has(m.id);

                      return (
                        <div
                          key={m.id}
                          className="border-t border-gray-100 first:border-t-0"
                        >
                          <button
                            onClick={() => toggleMessage(m.id)}
                            className="w-full flex items-center gap-3 px-5 py-3 hover:bg-gray-50 transition-colors text-left"
                          >
                            <span className={`w-7 h-7 rounded-full flex items-center justify-center text-white font-bold text-xs shrink-0 ${isEven ? 'bg-indigo-500' : 'bg-pink-500'}`}>
                              {m.agent_name.substring(0, 2).toUpperCase()}
                            </span>
                            <span className="text-sm font-semibold text-gray-700 shrink-0">{m.agent_name}</span>
                            {!isMsgOpen && (
                              <span className="text-sm text-gray-400 truncate flex-1">
                                {preview}{hasMore ? '…' : ''}
                              </span>
                            )}
                            {ragContext && (
                              <span className="shrink-0 flex items-center gap-1 text-xs text-teal-600 bg-teal-50 border border-teal-200 rounded px-1.5 py-0.5">
                                <Database size={11} />
                                RAG
                              </span>
                            )}
                            <span className="ml-auto shrink-0">
                              {isMsgOpen
                                ? <ChevronDown size={15} className="text-gray-400" />
                                : <ChevronRight size={15} className="text-gray-400" />}
                            </span>
                          </button>
                          {isMsgOpen && (
                            <div className="px-5 pb-5 pt-1 flex flex-col gap-2">
                              <div className="bg-white border border-gray-200 p-5 rounded-xl shadow-sm text-gray-800 text-[15px] leading-relaxed">
                                <div className="prose prose-sm max-w-none">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                                </div>
                              </div>
                              {ragContext && (
                                <div className="bg-teal-50 border border-teal-200 rounded-xl overflow-hidden">
                                  <button
                                    onClick={() => toggleRagContext(m.id)}
                                    className="w-full flex items-center gap-2 px-4 py-2.5 text-teal-800 font-semibold text-sm hover:bg-teal-100 transition-colors"
                                  >
                                    {isRagOpen
                                      ? <ChevronDown size={14} className="shrink-0" />
                                      : <ChevronRight size={14} className="shrink-0" />}
                                    <Database size={14} className="shrink-0" />
                                    <span>RAG 参照コンテキスト</span>
                                  </button>
                                  {isRagOpen && (
                                    <div className="px-4 pb-4 pt-1">
                                      <div className="text-xs text-teal-900 whitespace-pre-wrap leading-relaxed bg-white border border-teal-100 rounded-lg p-3 overflow-x-auto prose prose-sm max-w-none prose-teal">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{ragContext}</ReactMarkdown>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          {status === 'running' && (
            <div className="flex items-center gap-3 px-5 py-4 bg-white rounded-2xl border border-gray-200 shadow-sm animate-pulse">
              <span className="w-7 h-7 rounded-full bg-gray-300 shrink-0" />
              <span className="text-sm font-semibold text-gray-400">Agent typing...</span>
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
