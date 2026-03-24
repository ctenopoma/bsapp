import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageCircleQuestion, X, Send, Copy, Check, ClipboardPaste, Zap, ChevronDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { apiHelperAsk } from '../lib/api';
import type { HelperMessage, FieldSuggestion } from '../types/api';

interface ChatEntry {
  role: 'user' | 'assistant';
  content: string;
  suggestions?: FieldSuggestion[];
}

interface Props {
  /** どの画面で使用されているか */
  context: 'persona' | 'task' | 'setup' | 'rag' | 'patent';
  /** 現在のフォーム入力値 */
  currentInput?: Record<string, string>;
  /** 提案値を反映するコールバック */
  onApply: (suggestions: FieldSuggestion[]) => void;
}

export default function HelperChatWidget({ context, currentInput, onApply }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [autoApply, setAutoApply] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [appliedIdx, setAppliedIdx] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const buildHistory = (): HelperMessage[] =>
    messages.map(m => ({ role: m.role, content: m.content }));

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);

    try {
      const res = await apiHelperAsk({
        context,
        question: q,
        history: buildHistory(),
        current_input: currentInput,
      });

      const entry: ChatEntry = {
        role: 'assistant',
        content: res.answer,
        suggestions: res.suggestions ?? undefined,
      };
      setMessages(prev => [...prev, entry]);

      // 自動反映モード
      if (autoApply && res.suggestions && res.suggestions.length > 0) {
        onApply(res.suggestions);
      }
    } catch (e: any) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `エラーが発生しました: ${e.message || e}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopyAll = (idx: number, entry: ChatEntry) => {
    let text = entry.content;
    if (entry.suggestions?.length) {
      text += '\n\n---\n';
      entry.suggestions.forEach(s => {
        text += `${s.label}: ${s.value}\n`;
      });
    }
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const handleCopyField = (value: string) => {
    navigator.clipboard.writeText(value);
  };

  const handleApply = (idx: number, suggestions: FieldSuggestion[]) => {
    onApply(suggestions);
    setAppliedIdx(idx);
    setTimeout(() => setAppliedIdx(null), 2000);
  };

  const handleApplySingle = (suggestion: FieldSuggestion) => {
    onApply([suggestion]);
  };

  const contextLabel =
    context === 'persona' ? 'ペルソナ' :
    context === 'task' ? 'タスク' :
    context === 'rag' ? 'RAG' :
    context === 'patent' ? '特許調査' :
    'セッション設定';

  // ---- 閉じた状態: フローティングボタン ----
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white pl-3 pr-4 py-3 rounded-full shadow-lg transition-all hover:scale-105"
        title={`${contextLabel}の入力をサポート`}
      >
        <MessageCircleQuestion size={20} />
        <span className="text-sm font-medium">ヘルパー</span>
      </button>
    );
  }

  // ---- 開いた状態: チャットパネル ----
  return (
    <div className="fixed bottom-6 right-6 z-50 w-96 max-h-[600px] flex flex-col bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
      {/* ヘッダー */}
      <div className="flex items-center justify-between px-4 py-3 bg-indigo-600 text-white shrink-0">
        <div className="flex items-center gap-2">
          <MessageCircleQuestion size={18} />
          <span className="font-semibold text-sm">{contextLabel}ヘルパー</span>
        </div>
        <div className="flex items-center gap-2">
          {/* 自動反映トグル */}
          <button
            onClick={() => setAutoApply(v => !v)}
            className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium transition-colors ${
              autoApply
                ? 'bg-yellow-400 text-yellow-900'
                : 'bg-indigo-500 text-indigo-200 hover:bg-indigo-400'
            }`}
            title={autoApply ? '自動反映: ON' : '自動反映: OFF'}
          >
            <Zap size={12} />
            {autoApply ? '自動ON' : '自動OFF'}
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1 hover:bg-indigo-500 rounded-lg transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* メッセージ一覧 */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0" style={{ maxHeight: '400px' }}>
        {messages.length === 0 && (
          <div className="text-center text-gray-400 text-sm py-8">
            <MessageCircleQuestion size={32} className="mx-auto mb-2 text-gray-300" />
            <p>{contextLabel}について何でも聞いてください</p>
            <p className="text-xs mt-1 text-gray-300">例:「どんなロールを書けばいい？」</p>
          </div>
        )}

        {messages.map((entry, idx) => (
          <div key={idx} className={`flex ${entry.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {entry.role === 'user' ? (
              // ユーザーメッセージ
              <div className="max-w-[80%] bg-indigo-100 text-indigo-900 rounded-2xl rounded-br-sm px-3 py-2 text-sm">
                {entry.content}
              </div>
            ) : (
              // アシスタントメッセージ
              <div className="max-w-[90%] space-y-2">
                <div className="bg-gray-100 text-gray-800 rounded-2xl rounded-bl-sm px-3 py-2 text-sm">
                  <div className="prose prose-sm prose-gray max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5 [&_table]:text-xs [&_th]:px-2 [&_td]:px-2 [&_code]:text-xs [&_code]:bg-gray-200 [&_code]:px-1 [&_code]:rounded">
                    <ReactMarkdown>{entry.content}</ReactMarkdown>
                  </div>
                  {/* コピーボタン (A) */}
                  <button
                    onClick={() => handleCopyAll(idx, entry)}
                    className="inline-flex items-center gap-1 mt-1 text-xs text-gray-400 hover:text-gray-600"
                    title="コピー"
                  >
                    {copiedIdx === idx ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
                  </button>
                </div>

                {/* 提案カード (B) */}
                {entry.suggestions && entry.suggestions.length > 0 && (
                  <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-3 space-y-2">
                    <p className="text-xs font-semibold text-indigo-600 flex items-center gap-1">
                      <ChevronDown size={12} />
                      提案
                    </p>
                    {entry.suggestions.map((s, si) => (
                      <div key={si} className="flex items-start gap-2 text-sm">
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-medium text-indigo-500">{s.label}</span>
                          <p className="text-gray-800 break-words text-xs mt-0.5">{s.value}</p>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <button
                            onClick={() => handleCopyField(s.value)}
                            className="p-1 text-gray-400 hover:text-indigo-600 hover:bg-indigo-100 rounded transition-colors"
                            title="コピー"
                          >
                            <Copy size={12} />
                          </button>
                          <button
                            onClick={() => handleApplySingle(s)}
                            className="p-1 text-gray-400 hover:text-indigo-600 hover:bg-indigo-100 rounded transition-colors"
                            title="この項目だけ反映"
                          >
                            <ClipboardPaste size={12} />
                          </button>
                        </div>
                      </div>
                    ))}
                    {/* まとめて反映ボタン */}
                    <button
                      onClick={() => handleApply(idx, entry.suggestions!)}
                      className={`w-full mt-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        appliedIdx === idx
                          ? 'bg-green-500 text-white'
                          : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                      }`}
                    >
                      {appliedIdx === idx ? (
                        <><Check size={13} /> 反映しました</>
                      ) : (
                        <><ClipboardPaste size={13} /> まとめて反映</>
                      )}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-2 text-sm text-gray-500">
              <span className="inline-flex gap-1">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 入力エリア */}
      <div className="shrink-0 border-t border-gray-200 px-3 py-2 bg-gray-50">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`${contextLabel}について質問...`}
            rows={1}
            className="flex-1 resize-none border border-gray-300 rounded-xl px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 max-h-24 overflow-y-auto"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="p-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white rounded-xl transition-colors shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
