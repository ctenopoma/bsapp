import { useState, useCallback, useEffect, useRef } from 'react';
import { apiInitRag, apiAddRag, apiGetRagStatus, apiGetRagCollections, apiGetRagChunks, apiDeleteRagChunk, apiSearchRag, apiGetChunkStrategies } from '../lib/api';
import { RagCollectionInfo, RagChunk, RagSearchHit, ChunkStrategy } from '../types/api';
import {
  Database, UploadCloud, RefreshCw, CheckCircle2, AlertCircle,
  Search, ChevronLeft, ChevronRight, Layers, FileText, Trash2, ChevronDown,
  FlaskConical, Zap, Copy, Check,
} from 'lucide-react';

type Tab = 'manage' | 'browse' | 'playground';

// ─── タグ入力コンボボックス ────────────────────────────────────────────
function TagCombobox({ value, onChange, existingTags, disabled }: {
  value: string;
  onChange: (v: string) => void;
  existingTags: string[];
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const filtered = existingTags.filter(t =>
    !value || t.toLowerCase().includes(value.toLowerCase())
  );

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative w-full">
      <div className="flex items-center border border-gray-300 rounded-lg focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 transition-all bg-white overflow-hidden">
        <input
          placeholder="例: ProjectAlpha（既存タグを選択または新規入力）"
          value={value}
          onChange={e => { onChange(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          disabled={disabled}
          className="flex-1 p-3 outline-none font-mono text-sm bg-transparent disabled:bg-gray-50"
        />
        {existingTags.length > 0 && (
          <button
            type="button"
            onMouseDown={e => { e.preventDefault(); setOpen(o => !o); }}
            disabled={disabled}
            className="px-2 py-3 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <ChevronDown size={16} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
          </button>
        )}
      </div>

      {open && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
          {filtered.map(t => (
            <li key={t}>
              <button
                type="button"
                onMouseDown={e => { e.preventDefault(); onChange(t); setOpen(false); }}
                className={`w-full text-left px-4 py-2 text-sm font-mono hover:bg-blue-50 transition-colors ${value === t ? 'text-blue-600 bg-blue-50' : 'text-gray-700'}`}
              >
                {t}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ─── データ管理タブ ─────────────────────────────────────────────────────
const STRATEGY_PARAMS: Record<string, { key: string; label: string; type: 'number'; min: number; max: number; step: number; defaultVal: number }[]> = {
  recursive_semantic: [
    { key: 'chunk_size', label: 'チャンクサイズ（文字数）', type: 'number', min: 200, max: 2000, step: 50, defaultVal: 800 },
    { key: 'overlap', label: 'オーバーラップ（文字数）', type: 'number', min: 0, max: 400, step: 25, defaultVal: 150 },
  ],
  sentence_window: [
    { key: 'window_size', label: 'ウィンドウサイズ（文数）', type: 'number', min: 2, max: 10, step: 1, defaultVal: 5 },
    { key: 'overlap_sentences', label: 'オーバーラップ（文数）', type: 'number', min: 0, max: 5, step: 1, defaultVal: 1 },
  ],
  semantic: [
    { key: 'breakpoint_percentile', label: '境界感度（パーセンタイル）', type: 'number', min: 50, max: 99, step: 1, defaultVal: 85 },
  ],
  structure_aware: [
    { key: 'chunk_size', label: 'セクション最大サイズ（文字数）', type: 'number', min: 200, max: 2000, step: 50, defaultVal: 800 },
    { key: 'overlap', label: 'オーバーラップ（文字数）', type: 'number', min: 0, max: 400, step: 25, defaultVal: 100 },
  ],
};

function ManageTab() {
  const [tag, setTag] = useState('');
  const [text, setText] = useState('');
  const [status, setStatus] = useState<'idle' | 'initializing' | 'processing' | 'completed' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [existingTags, setExistingTags] = useState<string[]>([]);
  const [strategies, setStrategies] = useState<ChunkStrategy[]>([]);
  const [strategy, setStrategy] = useState('recursive_semantic');
  const [params, setParams] = useState<Record<string, number>>({
    chunk_size: 800, overlap: 150, window_size: 5, overlap_sentences: 1, breakpoint_percentile: 85,
  });

  useEffect(() => {
    apiGetRagCollections()
      .then(res => setExistingTags(res.collections.map(c => c.tag)))
      .catch(() => {});
    apiGetChunkStrategies()
      .then(res => setStrategies(res.strategies))
      .catch(() => {});
  }, []);

  const handleInit = async () => {
    if (!tag) return;
    try {
      setStatus('initializing');
      setMessage('コレクションを削除・再作成中...');
      await apiInitRag({ tag });
      setStatus('idle');
      setMessage(`コレクション '${tag}' を初期化しました。`);
    } catch (e: any) {
      setStatus('error');
      setMessage(e.message || 'コレクションの初期化に失敗しました。');
    }
  };

  const handleAddData = async () => {
    if (!tag || !text) return;
    try {
      setStatus('processing');
      setMessage('チャンキング＆ベクトル化を開始しています...');
      const res = await apiAddRag({ tag, text, strategy, ...params });

      const poll = setInterval(async () => {
        try {
          const s = await apiGetRagStatus(res.job_id);
          if (s.status === 'completed') {
            clearInterval(poll);
            setStatus('completed');
            const count = (s as any).chunk_count;
            setMessage(`完了！${count != null ? ` ${count} チャンク` : ''}を保存しました。`);
            setText('');
          } else if (s.status === 'error') {
            clearInterval(poll);
            setStatus('error');
            setMessage(`処理エラー: ${s.error_msg}`);
          }
        } catch {
          clearInterval(poll);
          setStatus('error');
          setMessage('ステータスの取得に失敗しました。');
        }
      }, 2000);
    } catch (e: any) {
      setStatus('error');
      setMessage(e.message || 'ベクトル化ジョブの開始に失敗しました。');
    }
  };

  const busy = status === 'processing' || status === 'initializing';
  const currentStrategyMeta = strategies.find(s => s.id === strategy);
  const currentParams = STRATEGY_PARAMS[strategy] ?? [];

  return (
    <div className="flex flex-col gap-5 flex-1">
      {/* Tag + Init */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-200">
        <h2 className="text-base font-semibold mb-3 text-gray-800">1. 対象タグ（コレクション）</h2>
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">タグ名</label>
            <TagCombobox value={tag} onChange={setTag} existingTags={existingTags} disabled={busy} />
          </div>
          <button
            onClick={handleInit}
            disabled={!tag || busy}
            className="flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-700 px-4 py-3 rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            <RefreshCw size={18} className={status === 'initializing' ? 'animate-spin' : ''} />
            初期化（データ消去）
          </button>
        </div>
      </div>

      {/* Chunking strategy */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-200">
        <h2 className="text-base font-semibold mb-3 text-gray-800">2. チャンキング戦略</h2>
        <div className="grid grid-cols-2 gap-3 mb-3">
          {(strategies.length ? strategies : [{ id: 'recursive_semantic', name: '再帰的意味分割（推奨）', description: '' }]).map(s => (
            <button
              key={s.id}
              onClick={() => setStrategy(s.id)}
              disabled={busy}
              className={`text-left p-3 rounded-lg border-2 transition-colors ${
                strategy === s.id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 bg-white'
              }`}
            >
              <div className={`text-sm font-medium ${strategy === s.id ? 'text-blue-700' : 'text-gray-800'}`}>{s.name}</div>
              <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{s.description}</div>
            </button>
          ))}
        </div>

        {currentParams.length > 0 && (
          <div className="flex flex-wrap gap-4 pt-3 border-t border-gray-100">
            {currentParams.map(p => (
              <div key={p.key} className="flex items-center gap-2">
                <label className="text-xs font-medium text-gray-600 whitespace-nowrap">{p.label}</label>
                <input
                  type="number"
                  min={p.min}
                  max={p.max}
                  step={p.step}
                  value={params[p.key] ?? p.defaultVal}
                  onChange={e => setParams(prev => ({ ...prev, [p.key]: Number(e.target.value) }))}
                  disabled={busy}
                  className="w-20 border border-gray-300 rounded-md px-2 py-1 text-sm outline-none focus:border-blue-500"
                />
              </div>
            ))}
            {strategy === 'semantic' && (
              <p className="text-xs text-amber-600 w-full">
                ※ 意味的チャンキングは文ごとに埋め込みを計算するため、大きなテキストでは処理に時間がかかります。
              </p>
            )}
          </div>
        )}
      </div>

      {/* Text + Submit */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-200 flex flex-col flex-1 min-h-[280px]">
        <h2 className="text-base font-semibold mb-3 text-gray-800">3. ナレッジを追加</h2>
        <textarea
          placeholder="ここにコンテキストドキュメントを貼り付けてください。選択した戦略でチャンキング＆ベクトル化されます..."
          value={text}
          onChange={e => setText(e.target.value)}
          disabled={busy}
          className="w-full flex-1 border border-gray-300 rounded-lg p-4 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-none mb-4 text-sm"
        />
        <div className="flex justify-between items-center">
          <div className="text-sm">
            {status === 'processing' && <span className="flex items-center gap-2 text-blue-600"><RefreshCw className="animate-spin" size={16} />{message}</span>}
            {status === 'completed' && <span className="flex items-center gap-2 text-green-600"><CheckCircle2 size={16} />{message}</span>}
            {status === 'error' && <span className="flex items-center gap-2 text-red-600"><AlertCircle size={16} />{message}</span>}
            {(status === 'idle' || status === 'initializing') && message && <span className="text-gray-600">{message}</span>}
          </div>
          <button
            onClick={handleAddData}
            disabled={!tag || !text || busy}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium shadow-sm transition-colors disabled:opacity-50"
          >
            <UploadCloud size={20} />
            ベクトル化して保存
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── データ確認タブ ─────────────────────────────────────────────────────
const PAGE_SIZE = 10;

function BrowseTab() {
  const [collections, setCollections] = useState<RagCollectionInfo[]>([]);
  const [loadingCollections, setLoadingCollections] = useState(false);
  const [collectionsError, setCollectionsError] = useState('');

  const [selectedTag, setSelectedTag] = useState('');
  const [chunks, setChunks] = useState<RagChunk[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [chunksError, setChunksError] = useState('');
  const [page, setPage] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchCollections = useCallback(async () => {
    setLoadingCollections(true);
    setCollectionsError('');
    try {
      const res = await apiGetRagCollections();
      setCollections(res.collections);
    } catch (e: any) {
      setCollectionsError(e.message || 'コレクション一覧の取得に失敗しました。');
    } finally {
      setLoadingCollections(false);
    }
  }, []);

  const fetchChunks = useCallback(async (tag: string) => {
    setLoadingChunks(true);
    setChunksError('');
    setPage(0);
    setExpandedId(null);
    try {
      const res = await apiGetRagChunks(tag);
      setChunks(res.chunks);
      setTotal(res.total);
      if (res.error) setChunksError(res.error);
    } catch (e: any) {
      setChunksError(e.message || 'チャンクの取得に失敗しました。');
      setChunks([]);
      setTotal(0);
    } finally {
      setLoadingChunks(false);
    }
  }, []);

  const handleDeleteChunk = useCallback(async (tag: string, chunkId: string) => {
    setDeletingId(chunkId);
    try {
      await apiDeleteRagChunk(tag, chunkId);
      setChunks(prev => prev.filter(c => c.id !== chunkId));
      setTotal(prev => prev - 1);
    } catch (e: any) {
      setChunksError(e.message || '削除に失敗しました。');
    } finally {
      setDeletingId(null);
    }
  }, []);

  const handleSelectTag = (tag: string) => {
    setSelectedTag(tag);
    fetchChunks(tag);
  };

  const pageChunks = chunks.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(chunks.length / PAGE_SIZE);

  return (
    <div className="flex gap-6 flex-1 min-h-0">
      {/* Left: collection list */}
      <div className="w-72 flex-shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800 flex items-center gap-2">
            <Layers size={16} className="text-blue-500" />
            コレクション一覧
          </h2>
          <button
            onClick={fetchCollections}
            disabled={loadingCollections}
            className="text-gray-400 hover:text-blue-600 transition-colors"
            title="再読み込み"
          >
            <RefreshCw size={16} className={loadingCollections ? 'animate-spin' : ''} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {collectionsError && (
            <div className="text-xs text-red-500 p-2 flex items-start gap-1">
              <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
              {collectionsError}
            </div>
          )}
          {collections.length === 0 && !loadingCollections && !collectionsError && (
            <div className="text-xs text-gray-400 p-4 text-center">
              「読み込む」ボタンを押してコレクション一覧を取得してください。
            </div>
          )}
          {collections.map(col => (
            <button
              key={col.tag}
              onClick={() => handleSelectTag(col.tag)}
              className={`w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                selectedTag === col.tag
                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                  : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              <div className="font-mono text-sm font-medium truncate">{col.tag}</div>
              <div className="text-xs text-gray-400 mt-0.5">{col.count} チャンク</div>
            </button>
          ))}
        </div>

        <div className="p-3 border-t border-gray-100">
          <button
            onClick={fetchCollections}
            disabled={loadingCollections}
            className="w-full flex items-center justify-center gap-2 bg-gray-50 hover:bg-gray-100 text-gray-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            <Search size={14} />
            {loadingCollections ? '取得中...' : 'コレクションを読み込む'}
          </button>
        </div>
      </div>

      {/* Right: chunk list */}
      <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col min-h-0">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800 flex items-center gap-2">
            <FileText size={16} className="text-blue-500" />
            {selectedTag ? (
              <>
                <span className="font-mono text-blue-600">{selectedTag}</span>
                <span className="text-gray-400 font-normal text-sm">のチャンク</span>
                <span className="ml-1 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{total}</span>
              </>
            ) : (
              <span className="text-gray-400 font-normal">左からコレクションを選択</span>
            )}
          </h2>
          {selectedTag && (
            <button
              onClick={() => fetchChunks(selectedTag)}
              disabled={loadingChunks}
              className="text-gray-400 hover:text-blue-600 transition-colors"
              title="再読み込み"
            >
              <RefreshCw size={16} className={loadingChunks ? 'animate-spin' : ''} />
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loadingChunks && (
            <div className="flex items-center justify-center py-12 text-gray-400">
              <RefreshCw size={20} className="animate-spin mr-2" /> 読み込み中...
            </div>
          )}
          {chunksError && (
            <div className="flex items-start gap-2 text-sm text-red-600 bg-red-50 p-3 rounded-lg">
              <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
              {chunksError}
            </div>
          )}
          {!loadingChunks && !chunksError && selectedTag && chunks.length === 0 && (
            <div className="text-sm text-gray-400 text-center py-12">
              このコレクションにはデータがありません。
            </div>
          )}
          {!loadingChunks && pageChunks.map((chunk, idx) => {
            const isExpanded = expandedId === chunk.id;
            const displayText = isExpanded ? chunk.text : chunk.text.slice(0, 200);
            const needsExpand = chunk.text.length > 200;
            return (
              <div key={chunk.id} className="border border-gray-200 rounded-lg p-3 hover:border-gray-300 transition-colors">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-medium text-gray-400">#{page * PAGE_SIZE + idx + 1}</span>
                  <span className="text-xs text-gray-300 font-mono truncate flex-1">{chunk.id}</span>
                  <span className="text-xs text-gray-400">{chunk.text.length} 文字</span>
                  <button
                    onClick={() => handleDeleteChunk(selectedTag, chunk.id)}
                    disabled={deletingId === chunk.id}
                    className="ml-1 p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
                    title="このチャンクを削除"
                  >
                    {deletingId === chunk.id
                      ? <RefreshCw size={14} className="animate-spin" />
                      : <Trash2 size={14} />}
                  </button>
                </div>
                <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {displayText}
                  {!isExpanded && needsExpand && '…'}
                </p>
                {needsExpand && (
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : chunk.id)}
                    className="mt-1.5 text-xs text-blue-500 hover:text-blue-700 transition-colors"
                  >
                    {isExpanded ? '折りたたむ' : '全文を表示'}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Pagination */}
        {chunks.length > PAGE_SIZE && (
          <div className="p-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-600">
            <span>{page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, chunks.length)} / {chunks.length} 件</span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-40 transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="px-2 py-1">{page + 1} / {totalPages}</span>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-40 transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Playground タブ ────────────────────────────────────────────────────
function PlaygroundTab() {
  const [existingTags, setExistingTags] = useState<string[]>([]);
  const [tag, setTag] = useState('');
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(3);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<RagSearchHit[] | null>(null);
  const [context, setContext] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    apiGetRagCollections()
      .then(res => setExistingTags(res.collections.map(c => c.tag)))
      .catch(() => {});
  }, []);

  const handleSearch = async () => {
    if (!tag || !query) return;
    setLoading(true);
    setError('');
    setResults(null);
    setContext('');
    try {
      const res = await apiSearchRag(tag, query, limit);
      if (res.error) { setError(res.error); return; }
      setResults(res.results);
      setContext(res.context);
    } catch (e: any) {
      setError(e.message || '検索に失敗しました。');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(context);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // スコアを色クラスに変換（0〜1）
  const scoreColor = (score: number) => {
    if (score >= 0.85) return 'text-green-600 bg-green-50 border-green-200';
    if (score >= 0.70) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-gray-500 bg-gray-50 border-gray-200';
  };
  const scoreBarColor = (score: number) => {
    if (score >= 0.85) return 'bg-green-400';
    if (score >= 0.70) return 'bg-yellow-400';
    return 'bg-gray-300';
  };

  return (
    <div className="flex flex-col gap-6 flex-1 min-h-0">
      {/* 説明バナー */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 flex items-start gap-3">
        <FlaskConical size={18} className="text-blue-500 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-blue-700">
          本番と同じ検索処理（ベクトル化 → コサイン類似度検索）を実行します。
          エージェントが実際に受け取るコンテキストを確認できます。
        </p>
      </div>

      {/* 検索フォーム */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex flex-col gap-4">
        <div className="flex gap-4 items-end">
          <div className="w-72 flex-shrink-0">
            <label className="block text-sm font-medium text-gray-700 mb-1">対象タグ</label>
            <TagCombobox value={tag} onChange={setTag} existingTags={existingTags} disabled={loading} />
          </div>
          <div className="flex-shrink-0">
            <label className="block text-sm font-medium text-gray-700 mb-1">取得件数</label>
            <select
              value={limit}
              onChange={e => setLimit(Number(e.target.value))}
              disabled={loading}
              className="border border-gray-300 rounded-lg p-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all text-sm bg-white"
            >
              {[1, 2, 3, 5, 8, 10].map(n => (
                <option key={n} value={n}>{n} 件</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">クエリ（テーマ・質問文）</label>
          <textarea
            placeholder="例: 競合他社との差別化ポイントを教えてください"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSearch(); }}
            disabled={loading}
            rows={3}
            className="w-full border border-gray-300 rounded-lg p-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-none text-sm"
          />
          <p className="text-xs text-gray-400 mt-1">Ctrl+Enter で実行</p>
        </div>

        <div className="flex justify-end">
          <button
            onClick={handleSearch}
            disabled={!tag || !query || loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg font-medium shadow-sm transition-colors disabled:opacity-50"
          >
            {loading
              ? <RefreshCw size={18} className="animate-spin" />
              : <Zap size={18} />}
            {loading ? '検索中...' : '検索実行'}
          </button>
        </div>
      </div>

      {/* エラー */}
      {error && (
        <div className="flex items-start gap-2 text-sm text-red-600 bg-red-50 border border-red-200 p-4 rounded-xl">
          <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {/* 結果 */}
      {results !== null && (
        <div className="flex flex-col gap-4 flex-1 min-h-0">
          {/* ヒット一覧 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
              <Search size={15} className="text-blue-500" />
              <span className="font-semibold text-gray-800 text-sm">
                検索結果
              </span>
              <span className="ml-1 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{results.length} 件</span>
            </div>

            {results.length === 0 ? (
              <div className="p-6 text-sm text-gray-400 text-center">
                該当するチャンクが見つかりませんでした。
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {results.map((hit, idx) => (
                  <div key={hit.id} className="p-4 flex gap-4 items-start">
                    {/* 順位バッジ */}
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center mt-0.5">
                      {idx + 1}
                    </div>

                    {/* テキスト */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{hit.text}</p>
                    </div>

                    {/* スコア */}
                    <div className={`flex-shrink-0 flex flex-col items-end gap-1`}>
                      <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded border ${scoreColor(hit.score)}`}>
                        {hit.score.toFixed(4)}
                      </span>
                      <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${scoreBarColor(hit.score)}`}
                          style={{ width: `${Math.min(hit.score * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* LLMに渡されるコンテキスト */}
          {context && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText size={15} className="text-blue-500" />
                  <span className="font-semibold text-gray-800 text-sm">LLMに渡されるコンテキスト（参考情報 RAG）</span>
                </div>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 transition-colors"
                >
                  {copied ? <Check size={13} className="text-green-500" /> : <Copy size={13} />}
                  {copied ? 'コピー済み' : 'コピー'}
                </button>
              </div>
              <pre className="p-4 text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed overflow-auto max-h-64 bg-gray-50 rounded-b-xl">
                {context}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── メイン画面 ─────────────────────────────────────────────────────────
export default function RagScreen() {
  const [tab, setTab] = useState<Tab>('manage');

  return (
    <div className="p-8 max-w-6xl mx-auto flex flex-col h-full gap-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-2">
          <Database className="text-blue-600" />
          RAG Knowledge Base
        </h1>
        <p className="text-gray-500 mt-1 text-sm">
          ベクトル埋め込みを管理します。タグで知識ベースを分類し、ペルソナごとに参照させることができます。
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200">
        {([
          { id: 'manage', label: 'データ管理' },
          { id: 'browse', label: 'データ確認' },
          { id: 'playground', label: 'Playground' },
        ] as const).map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex flex-col flex-1 min-h-0">
        {tab === 'manage' && <ManageTab />}
        {tab === 'browse' && <BrowseTab />}
        {tab === 'playground' && <PlaygroundTab />}
      </div>
    </div>
  );
}
