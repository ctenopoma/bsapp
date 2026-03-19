import { useState, useEffect, useRef } from 'react';
import { generateUUID } from '../lib/uuid';
import { FlaskConical, Upload, CheckSquare, Square, Play, Copy, Trash2, ChevronDown, ChevronUp, FileText, BookOpen } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { apiGetSettings, apiPatentAnalyze, apiPatentSummary } from '../lib/api';
import {
  createPatentSession,
  getPatentSessions,
  deletePatentSession,
  addPatentReport,
  getPatentReports,
  savePatentSummary,
  getPatentSummary,
  getSessionConfig,
  saveSessionConfig,
  PatentSessionData,
  PatentReportData,
} from '../lib/server-db';
import { AppSettings, PatentAnalyzeResponse } from '../types/api';

// -------------------------------------------------------------------
// CSV パーサー (UTF-8 / Shift-JIS 対応、クォート内改行対応)
// -------------------------------------------------------------------

/**
 * RFC 4180 準拠の CSV パーサー。
 * クォートで囲まれたフィールド内の改行 (J-PlatPat の出願人欄など) を正しく処理する。
 */
function parseCSV(text: string): Record<string, string>[] {
  const rows = _parseCSVRaw(text);
  if (rows.length < 2) return [];
  const headers = rows[0].map(h => h.trim());
  const result: Record<string, string>[] = [];
  for (let i = 1; i < rows.length; i++) {
    const cols = rows[i];
    if (cols.every(c => c.trim() === '')) continue;
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => { row[h] = (cols[idx] ?? '').trim(); });
    result.push(row);
  }
  return result;
}

function _parseCSVRaw(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let inQuotes = false;
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { cell += '"'; i += 2; }  // エスケープ済みクォート
        else { inQuotes = false; i++; }                     // クォート終了
      } else {
        cell += ch; i++;                                     // クォート内の任意文字 (改行含む)
      }
    } else {
      if (ch === '"') { inQuotes = true; i++; }
      else if (ch === ',') { row.push(cell); cell = ''; i++; }
      else if (ch === '\r' && text[i + 1] === '\n') { row.push(cell); cell = ''; rows.push(row); row = []; i += 2; }
      else if (ch === '\n') { row.push(cell); cell = ''; rows.push(row); row = []; i++; }
      else { cell += ch; i++; }
    }
  }
  row.push(cell);
  if (row.length > 1 || row[0] !== '') rows.push(row);
  return rows;
}

async function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const buf = e.target?.result as ArrayBuffer;
      // UTF-8 を試みて、Shift-JIS にフォールバック
      try {
        const utf8 = new TextDecoder('utf-8', { fatal: true }).decode(buf);
        resolve(utf8);
      } catch {
        try {
          resolve(new TextDecoder('shift-jis').decode(buf));
        } catch {
          reject(new Error('文字コードを判別できませんでした。UTF-8またはShift-JISのCSVを使用してください。'));
        }
      }
    };
    reader.onerror = () => reject(new Error('ファイルの読み込みに失敗しました'));
    reader.readAsArrayBuffer(file);
  });
}

// -------------------------------------------------------------------
// 型定義
// -------------------------------------------------------------------
interface CompanyCount {
  company: string;
  count: number;
}

interface ReportEntry {
  company: string;
  report: string;
  status: 'pending' | 'analyzing' | 'done' | 'error';
  error?: string;
}

const INPUT_CLS = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500';
const TEXTAREA_CLS = `${INPUT_CLS} resize-y font-mono`;

// -------------------------------------------------------------------
// メインコンポーネント
// -------------------------------------------------------------------
export default function PatentResearchScreen() {
  const [tab, setTab] = useState<'new' | 'history'>('new');
  const [settings, setSettings] = useState<AppSettings | null>(null);

  // 分析設定 (クライアントローカル)
  const [analyzeSystemPrompt, setAnalyzeSystemPrompt] = useState('');
  const [analyzeOutputFormat, setAnalyzeOutputFormat] = useState('');
  const [summarySystemPrompt, setSummarySystemPrompt] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);

  // CSV・企業
  const [csvRows, setCsvRows] = useState<Record<string, string>[]>([]);
  const [companies, setCompanies] = useState<CompanyCount[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [csvError, setCsvError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 分析状態
  const [status, setStatus] = useState<'idle' | 'analyzing' | 'done' | 'error'>('idle');
  const [reports, setReports] = useState<ReportEntry[]>([]);
  const [summary, setSummary] = useState('');
  const [summaryStatus, setSummaryStatus] = useState<'idle' | 'analyzing' | 'done' | 'error'>('idle');
  const [globalError, setGlobalError] = useState('');

  // 履歴
  const [sessions, setSessions] = useState<PatentSessionData[]>([]);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [historyReports, setHistoryReports] = useState<Record<string, PatentReportData[]>>({});
  const [historySummaries, setHistorySummaries] = useState<Record<string, string>>({});

  // 初期読み込み
  useEffect(() => {
    apiGetSettings().then(setSettings).catch(() => {});
    getSessionConfig('patent_analyze_system_prompt').then(setAnalyzeSystemPrompt);
    getSessionConfig('patent_analyze_output_format').then(setAnalyzeOutputFormat);
    getSessionConfig('patent_summary_system_prompt').then(setSummarySystemPrompt);
    loadSessions();
  }, []);

  const loadSessions = async () => {
    const data = await getPatentSessions();
    setSessions(data);
  };

  // -------------------------------------------------------------------
  // 設定の保存
  // -------------------------------------------------------------------
  const saveLocalSettings = async () => {
    await saveSessionConfig('patent_analyze_system_prompt', analyzeSystemPrompt);
    await saveSessionConfig('patent_analyze_output_format', analyzeOutputFormat);
    await saveSessionConfig('patent_summary_system_prompt', summarySystemPrompt);
  };

  // -------------------------------------------------------------------
  // CSV 読み込み
  // -------------------------------------------------------------------
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCsvError('');
    setCompanies([]);
    setSelected(new Set());
    setCsvRows([]);
    try {
      const text = await readFileAsText(file);
      const rows = parseCSV(text);
      if (rows.length === 0) { setCsvError('CSVにデータがありません'); return; }

      const companyCol = settings?.patent_company_column ?? '出願人';
      if (!rows[0].hasOwnProperty(companyCol)) {
        setCsvError(`列名 "${companyCol}" が見つかりません。Settingsで列名を確認してください。`);
        return;
      }

      // 企業ごとの件数カウント
      const counts: Record<string, number> = {};
      for (const row of rows) {
        const co = (row[companyCol] ?? '').trim();
        if (co) counts[co] = (counts[co] ?? 0) + 1;
      }
      const sorted = Object.entries(counts)
        .map(([company, count]) => ({ company, count }))
        .sort((a, b) => b.count - a.count);

      setCsvRows(rows);
      setCompanies(sorted);
    } catch (err: any) {
      setCsvError(err.message ?? 'CSVの読み込みに失敗しました');
    }
  };

  const toggleCompany = (company: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(company) ? next.delete(company) : next.add(company);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === companies.length) { setSelected(new Set()); }
    else { setSelected(new Set(companies.map(c => c.company))); }
  };

  // -------------------------------------------------------------------
  // 分析実行
  // -------------------------------------------------------------------
  const handleStart = async () => {
    if (selected.size === 0) return;
    await saveLocalSettings();
    setStatus('analyzing');
    setGlobalError('');
    setSummary('');
    setSummaryStatus('idle');

    const contentCol = settings?.patent_content_column ?? '発明の名称';
    const dateCol = settings?.patent_date_column ?? '出願日';
    const companyCol = settings?.patent_company_column ?? '出願人';

    const orderedCompanies = companies.filter(c => selected.has(c.company));
    const initialReports: ReportEntry[] = orderedCompanies.map(c => ({
      company: c.company, report: '', status: 'pending',
    }));
    setReports(initialReports);

    // セッション作成
    const sessionId = generateUUID();
    const title = `${orderedCompanies.map(c => c.company).slice(0, 3).join('・')}${orderedCompanies.length > 3 ? '...' : ''} (${new Date().toLocaleDateString('ja-JP')})`;
    await createPatentSession(sessionId, title);

    const completedReports: PatentAnalyzeResponse[] = [];

    for (let i = 0; i < orderedCompanies.length; i++) {
      const { company } = orderedCompanies[i];

      // 該当企業の特許を日付降順で最大10件取得
      const companyRows = csvRows
        .filter(r => (r[companyCol] ?? '').trim() === company)
        .sort((a, b) => {
          const da = a[dateCol] ?? '';
          const db_ = b[dateCol] ?? '';
          return db_.localeCompare(da);
        })
        .slice(0, 10);

      const patents = companyRows.map(r => ({
        content: r[contentCol] ?? '',
        date: r[dateCol] ?? '',
      })).filter(p => p.content);

      // analyzing に変更
      setReports(prev => prev.map((r, idx) =>
        idx === i ? { ...r, status: 'analyzing' } : r
      ));

      try {
        const res = await apiPatentAnalyze({
          company,
          patents,
          system_prompt: analyzeSystemPrompt,
          output_format: analyzeOutputFormat,
        });

        setReports(prev => prev.map((r, idx) =>
          idx === i ? { ...r, report: res.report, status: 'done' } : r
        ));
        await addPatentReport(sessionId, company, res.report, i);
        completedReports.push(res);
      } catch (err: any) {
        const msg = err.message ?? 'エラーが発生しました';
        setReports(prev => prev.map((r, idx) =>
          idx === i ? { ...r, status: 'error', error: msg } : r
        ));
      }
    }

    // 総括
    if (completedReports.length > 0) {
      setSummaryStatus('analyzing');
      try {
        const res = await apiPatentSummary({
          company_reports: completedReports,
          system_prompt: summarySystemPrompt,
        });
        setSummary(res.summary);
        setSummaryStatus('done');
        await savePatentSummary(sessionId, res.summary);
      } catch (err: any) {
        setSummaryStatus('error');
        setGlobalError(err.message ?? '総括の生成に失敗しました');
      }
    }

    setStatus('done');
    await loadSessions();

    // デスクトップ通知
    try {
      if ('Notification' in window) {
        if (Notification.permission === 'default') {
          await Notification.requestPermission();
        }
        if (Notification.permission === 'granted') {
          new Notification('文献調査が完了しました', {
            body: `${orderedCompanies.length}社の特許分析と総括が完了しました。`,
          });
        }
      }
    } catch { /* 通知は非必須のため無視 */ }
  };

  // -------------------------------------------------------------------
  // コピー
  // -------------------------------------------------------------------
  const handleCopy = (reps: ReportEntry[], sum: string) => {
    const text = [
      ...reps.filter(r => r.status === 'done').map(r => `## ${r.company}\n${r.report}`),
      sum ? `## 総括\n${sum}` : '',
    ].filter(Boolean).join('\n\n---\n\n');
    navigator.clipboard.writeText(text);
  };

  // -------------------------------------------------------------------
  // 履歴操作
  // -------------------------------------------------------------------
  const handleExpandSession = async (id: string) => {
    if (expandedSession === id) { setExpandedSession(null); return; }
    setExpandedSession(id);
    if (!historyReports[id]) {
      const [reps, sum] = await Promise.all([getPatentReports(id), getPatentSummary(id)]);
      setHistoryReports(prev => ({ ...prev, [id]: reps }));
      setHistorySummaries(prev => ({ ...prev, [id]: sum }));
    }
  };

  const handleDeleteSession = async (id: string) => {
    if (!confirm('このレポートを削除しますか？')) return;
    await deletePatentSession(id);
    setHistoryReports(prev => { const n = { ...prev }; delete n[id]; return n; });
    setHistorySummaries(prev => { const n = { ...prev }; delete n[id]; return n; });
    if (expandedSession === id) setExpandedSession(null);
    await loadSessions();
  };

  const handleCopyHistory = async (id: string) => {
    const reps = historyReports[id] ?? await getPatentReports(id);
    const sum = historySummaries[id] ?? await getPatentSummary(id);
    const text = [
      ...reps.map(r => `## ${r.company}\n${r.report}`),
      sum ? `## 総括\n${sum}` : '',
    ].filter(Boolean).join('\n\n---\n\n');
    navigator.clipboard.writeText(text);
  };

  // -------------------------------------------------------------------
  // 描画
  // -------------------------------------------------------------------
  return (
    <div className="p-6 max-w-4xl mx-auto flex flex-col gap-6">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <FlaskConical className="text-blue-600" size={26} />
          Patent Research
        </h1>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {(['new', 'history'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${tab === t ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-800'}`}>
              {t === 'new' ? '新規調査' : '履歴'}
            </button>
          ))}
        </div>
      </div>

      {/* ======= 新規調査タブ ======= */}
      {tab === 'new' && (
        <div className="flex flex-col gap-5">

          {/* 分析設定 */}
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <button
              onClick={() => setSettingsOpen(v => !v)}
              className="w-full flex items-center justify-between px-5 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span>分析設定</span>
              {settingsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {settingsOpen && (
              <div className="px-5 pb-5 flex flex-col gap-4 border-t border-gray-100 pt-4">
                <p className="text-xs text-gray-400">
                  ホスト側の列名設定 (Settings画面): 企業列=<code className="bg-gray-100 px-1 rounded">{settings?.patent_company_column ?? '...'}</code>、
                  内容列=<code className="bg-gray-100 px-1 rounded">{settings?.patent_content_column ?? '...'}</code>、
                  日付列=<code className="bg-gray-100 px-1 rounded">{settings?.patent_date_column ?? '...'}</code>
                </p>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">企業別分析 システムプロンプト</label>
                  <textarea className={TEXTAREA_CLS} rows={4} value={analyzeSystemPrompt}
                    onChange={e => setAnalyzeSystemPrompt(e.target.value)}
                    placeholder="（空の場合はデフォルトプロンプトを使用）" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">企業別分析 出力フォーマット</label>
                  <textarea className={TEXTAREA_CLS} rows={5} value={analyzeOutputFormat}
                    onChange={e => setAnalyzeOutputFormat(e.target.value)}
                    placeholder="（空の場合はデフォルトフォーマットを使用）" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">総括 システムプロンプト</label>
                  <textarea className={TEXTAREA_CLS} rows={3} value={summarySystemPrompt}
                    onChange={e => setSummarySystemPrompt(e.target.value)}
                    placeholder="（空の場合はデフォルトプロンプトを使用）" />
                </div>
                <button onClick={saveLocalSettings}
                  className="self-end px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
                  設定を保存
                </button>
              </div>
            )}
          </section>

          {/* CSV 選択 */}
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Upload size={15} /> CSVファイル選択
            </h2>
            <div className="flex items-center gap-3">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={status === 'analyzing'}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors border border-gray-200 disabled:opacity-50"
              >
                ファイルを選択
              </button>
              {csvRows.length > 0 && (
                <span className="text-sm text-gray-500">{csvRows.length.toLocaleString()} 件読み込み済み</span>
              )}
            </div>
            <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
            {csvError && <p className="text-xs text-red-500">{csvError}</p>}
          </section>

          {/* 企業選択 */}
          {companies.length > 0 && (
            <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700">企業選択</h2>
                <button onClick={toggleAll} className="text-xs text-blue-600 hover:text-blue-800">
                  {selected.size === companies.length ? '全解除' : '全選択'}
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto flex flex-col gap-1 pr-1">
                {companies.map(({ company, count }) => {
                  const checked = selected.has(company);
                  return (
                    <button key={company} onClick={() => toggleCompany(company)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors text-left ${checked ? 'bg-blue-50 text-blue-800' : 'hover:bg-gray-50 text-gray-700'}`}
                    >
                      {checked ? <CheckSquare size={15} className="text-blue-600 shrink-0" /> : <Square size={15} className="text-gray-400 shrink-0" />}
                      <span className="flex-1 truncate">{company}</span>
                      <span className="text-xs text-gray-400 shrink-0">{count.toLocaleString()}件</span>
                    </button>
                  );
                })}
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                <span className="text-xs text-gray-500">{selected.size}社選択中</span>
                <button
                  onClick={handleStart}
                  disabled={selected.size === 0 || status === 'analyzing'}
                  className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-semibold transition-colors shadow-sm"
                >
                  <Play size={14} />
                  {status === 'analyzing' ? '分析中...' : '分析開始'}
                </button>
              </div>
            </section>
          )}

          {/* 結果 */}
          {reports.length > 0 && (
            <section className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700">分析結果</h2>
                {status === 'done' && (
                  <button onClick={() => handleCopy(reports, summary)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors">
                    <Copy size={13} /> 全てコピー
                  </button>
                )}
              </div>

              {reports.map(r => (
                <div key={r.company} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                  <div className={`px-5 py-3 flex items-center gap-2 border-b border-gray-100 ${
                    r.status === 'analyzing' ? 'bg-blue-50' :
                    r.status === 'done' ? 'bg-green-50' :
                    r.status === 'error' ? 'bg-red-50' : 'bg-gray-50'
                  }`}>
                    <FileText size={15} className="text-gray-500 shrink-0" />
                    <span className="font-semibold text-gray-800 flex-1">{r.company}</span>
                    <span className="text-xs text-gray-400">
                      {r.status === 'pending' ? '待機中' :
                       r.status === 'analyzing' ? '分析中...' :
                       r.status === 'done' ? '完了' : 'エラー'}
                    </span>
                  </div>
                  <div className="px-5 py-4">
                    {r.status === 'analyzing' && (
                      <div className="flex items-center gap-2 text-sm text-blue-600 animate-pulse">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
                        LLMが分析中...
                      </div>
                    )}
                    {r.status === 'done' && (
                      <div className="prose prose-sm max-w-none text-gray-700">
                        <ReactMarkdown>{r.report}</ReactMarkdown>
                      </div>
                    )}
                    {r.status === 'error' && (
                      <p className="text-sm text-red-600">{r.error}</p>
                    )}
                  </div>
                </div>
              ))}

              {/* 総括 */}
              {(summaryStatus !== 'idle') && (
                <div className="bg-white rounded-xl border border-blue-200 shadow-sm overflow-hidden">
                  <div className={`px-5 py-3 flex items-center gap-2 border-b border-blue-100 ${summaryStatus === 'analyzing' ? 'bg-blue-50' : 'bg-blue-50'}`}>
                    <BookOpen size={15} className="text-blue-600 shrink-0" />
                    <span className="font-semibold text-blue-800 flex-1">総括</span>
                    <span className="text-xs text-blue-400">
                      {summaryStatus === 'analyzing' ? '生成中...' : summaryStatus === 'done' ? '完了' : 'エラー'}
                    </span>
                  </div>
                  <div className="px-5 py-4">
                    {summaryStatus === 'analyzing' && (
                      <div className="flex items-center gap-2 text-sm text-blue-600 animate-pulse">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
                        総括を生成中...
                      </div>
                    )}
                    {summaryStatus === 'done' && (
                      <div className="prose prose-sm max-w-none text-gray-700">
                        <ReactMarkdown>{summary}</ReactMarkdown>
                      </div>
                    )}
                    {summaryStatus === 'error' && (
                      <p className="text-sm text-red-600">{globalError}</p>
                    )}
                  </div>
                </div>
              )}
            </section>
          )}

          {globalError && status !== 'analyzing' && (
            <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200 text-sm">{globalError}</div>
          )}
        </div>
      )}

      {/* ======= 履歴タブ ======= */}
      {tab === 'history' && (
        <div className="flex flex-col gap-3">
          {sessions.length === 0 ? (
            <div className="text-center py-16 text-gray-400 text-sm">まだ調査履歴がありません</div>
          ) : (
            sessions.map(s => (
              <div key={s.id} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3">
                  <button
                    onClick={() => handleExpandSession(s.id)}
                    className="flex items-center gap-2 flex-1 text-left hover:text-blue-700 transition-colors"
                  >
                    <BookOpen size={15} className="text-gray-400 shrink-0" />
                    <span className="text-sm font-medium text-gray-800 flex-1">{s.title}</span>
                    <span className="text-xs text-gray-400 shrink-0">
                      {new Date(s.created_at).toLocaleString('ja-JP')}
                    </span>
                    {expandedSession === s.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  <div className="flex items-center gap-1 ml-3">
                    <button onClick={() => handleCopyHistory(s.id)}
                      className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors" title="コピー">
                      <Copy size={14} />
                    </button>
                    <button onClick={() => handleDeleteSession(s.id)}
                      className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors" title="削除">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {expandedSession === s.id && (
                  <div className="border-t border-gray-100 px-4 py-4 flex flex-col gap-4">
                    {(historyReports[s.id] ?? []).map(r => (
                      <div key={r.id}>
                        <p className="text-xs font-semibold text-gray-500 mb-1">{r.company}</p>
                        <div className="prose prose-sm max-w-none text-gray-700 bg-gray-50 rounded-lg p-3">
                          <ReactMarkdown>{r.report}</ReactMarkdown>
                        </div>
                      </div>
                    ))}
                    {historySummaries[s.id] && (
                      <div>
                        <p className="text-xs font-semibold text-blue-600 mb-1">総括</p>
                        <div className="prose prose-sm max-w-none text-gray-700 bg-blue-50 rounded-lg p-3">
                          <ReactMarkdown>{historySummaries[s.id]}</ReactMarkdown>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
