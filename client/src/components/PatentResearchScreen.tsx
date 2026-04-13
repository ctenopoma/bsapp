import { useState, useEffect, useRef } from 'react';
import { generateUUID } from '../lib/uuid';
import {
  FlaskConical, Upload, CheckSquare, Square, Play, Copy, Trash2,
  ChevronDown, ChevronUp, FileText, BookOpen, AlertTriangle, Minimize2,
  Save, FolderOpen, Check, BarChart2,
} from 'lucide-react';
import { writeText } from '@tauri-apps/plugin-clipboard-manager';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiGetSettings, apiPatentAnalyze, apiPatentCompress, apiPatentAnalyzeChunked, apiPatentStats, apiPatentStatsProcessors } from '../lib/api';
import {
  createPatentSession,
  getPatentSessions,
  deletePatentSession,
  addPatentReport,
  getPatentReports,
  getSessionConfig,
  saveSessionConfig,
  PatentSessionData,
  PatentReportData,
  getPatentPresets,
  createPatentPreset,
  updatePatentPreset,
  deletePatentPreset,
  uploadPatentCsv,
  listPatentCsvs,
  getPatentCsvRows,
  deletePatentCsv,
  PatentCsvMeta,
} from '../lib/server-db';
import { AppSettings, FieldSuggestion, PatentCompressMode, PatentItem, PatentPresetData, StatProcessorInfo, StatProcessorConfig, StatTableResult } from '../types/api';

// 分析戦略の型
type AnalysisStrategy = 'bulk' | 'bulk_per_patent' | 'bulk_per_company' | 'chunked';
import HelperChatWidget from './HelperChatWidget';

// -------------------------------------------------------------------
// CSV パーサー (UTF-8 / Shift-JIS 対応、クォート内改行対応)
// -------------------------------------------------------------------
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
        if (text[i + 1] === '"') { cell += '"'; i += 2; }
        else { inQuotes = false; i++; }
      } else { cell += ch; i++; }
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
      try {
        resolve(new TextDecoder('utf-8', { fatal: true }).decode(buf));
      } catch {
        try { resolve(new TextDecoder('shift-jis').decode(buf)); }
        catch { reject(new Error('文字コードを判別できませんでした。UTF-8またはShift-JISのCSVを使用してください。')); }
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

// トークン超過エラーかどうか判定
function isTokenLimitError(msg: string): boolean {
  const lower = msg.toLowerCase();
  return (
    lower.includes('token_limit_exceeded') ||
    lower.includes('context_length_exceeded') ||
    lower.includes('context length') ||
    lower.includes('maximum context') ||
    lower.includes('too long') ||
    lower.includes('reduce the length')
  );
}

const INPUT_CLS = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500';
const TEXTAREA_CLS = `${INPUT_CLS} resize-y font-mono`;

// クライアント側上限デフォルト
const DEFAULT_MAX_COMPANIES = 20;
const DEFAULT_MAX_TOTAL_PATENTS = 100;

// -------------------------------------------------------------------
// メインコンポーネント
// -------------------------------------------------------------------
export default function PatentResearchScreen() {
  const [tab, setTab] = useState<'new' | 'history'>('new');
  const [settings, setSettings] = useState<AppSettings | null>(null);

  // CSV・企業
  const [csvRows, setCsvRows] = useState<Record<string, string>[]>([]);
  const [csvName, setCsvName] = useState('');
  const [savedCsvId, setSavedCsvId] = useState('');
  const [savedCsvs, setSavedCsvs] = useState<PatentCsvMeta[]>([]);
  const [companies, setCompanies] = useState<CompanyCount[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [csvError, setCsvError] = useState('');
  const [csvSaving, setCsvSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 上限設定
  const [maxCompanies, setMaxCompanies] = useState(DEFAULT_MAX_COMPANIES);
  const [maxTotalPatents, setMaxTotalPatents] = useState(DEFAULT_MAX_TOTAL_PATENTS);
  const [patentsPerCompany, setPatentsPerCompany] = useState(10);

  // 分析設定（既存LLM分析）
  const [analyzeSystemPrompt, setAnalyzeSystemPrompt] = useState('');
  const [analyzeOutputFormat, setAnalyzeOutputFormat] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [strategy, setStrategy] = useState<AnalysisStrategy>('bulk');
  const [chunkSize, setChunkSize] = useState(20);

  // 統計処理設定
  const [statsOpen, setStatsOpen] = useState(false);
  const [availableProcessors, setAvailableProcessors] = useState<StatProcessorInfo[]>([]);
  // processorId → config
  const [processorConfigs, setProcessorConfigs] = useState<Record<string, StatProcessorConfig>>({});
  const [finalLlmPrompt, setFinalLlmPrompt] = useState('');

  // 統計実行状態
  const [statsStatus, setStatsStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [statsTables, setStatsTables] = useState<StatTableResult[]>([]);
  const [statsLlmResult, setStatsLlmResult] = useState('');
  const [statsError, setStatsError] = useState('');

  // 分析状態（既存LLM分析）
  const [status, setStatus] = useState<'idle' | 'compressing' | 'analyzing' | 'done' | 'error'>('idle');
  const [report, setReport] = useState('');
  const [globalError, setGlobalError] = useState('');
  const [isTokenError, setIsTokenError] = useState(false);
  const [compressInfo, setCompressInfo] = useState<{ original: number; compressed: number } | null>(null);
  const [chunkInfo, setChunkInfo] = useState<{ current: number; total: number } | null>(null);

  // 警告ダイアログ
  const [warning, setWarning] = useState<{ message: string; onConfirm: () => void } | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // プリセット管理
  const [presets, setPresets] = useState<PatentPresetData[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState('');
  const [presetName, setPresetName] = useState('');
  const [showSavePresetDialog, setShowSavePresetDialog] = useState(false);

  // 履歴
  const [sessions, setSessions] = useState<PatentSessionData[]>([]);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [historyReports, setHistoryReports] = useState<Record<string, PatentReportData[]>>({});

  // 初期読み込み
  useEffect(() => {
    apiGetSettings().then(setSettings).catch(() => {});
    getSessionConfig('patent_analyze_system_prompt').then(setAnalyzeSystemPrompt);
    getSessionConfig('patent_analyze_output_format').then(setAnalyzeOutputFormat);
    getSessionConfig('patent_max_companies').then(v => { if (v) setMaxCompanies(parseInt(v) || DEFAULT_MAX_COMPANIES); });
    getSessionConfig('patent_max_total_patents').then(v => { if (v) setMaxTotalPatents(parseInt(v) || DEFAULT_MAX_TOTAL_PATENTS); });
    getSessionConfig('patent_patents_per_company').then(v => { if (v) setPatentsPerCompany(parseInt(v) || 10); });
    getSessionConfig('patent_strategy').then(v => { if (v) setStrategy(v as AnalysisStrategy); });
    getSessionConfig('patent_chunk_size').then(v => { if (v) setChunkSize(parseInt(v) || 20); });
    loadSessions();
    getPatentPresets().then(setPresets).catch(console.error);
    listPatentCsvs().then(setSavedCsvs).catch(console.error);
    apiPatentStatsProcessors().then(procs => {
      setAvailableProcessors(procs);
      // デフォルト: 全プロセッサを有効・LLMなしで初期化
      const defaultConfigs: Record<string, StatProcessorConfig> = {};
      for (const p of procs) {
        defaultConfigs[p.id] = { processor_id: p.id, enabled: true, param_prompt: '', variable_name: '', ipc_col: '' };
      }
      setProcessorConfigs(defaultConfigs);
    }).catch(console.error);
  }, []);

  const loadSessions = async () => {
    const data = await getPatentSessions();
    setSessions(data);
  };

  // -------------------------------------------------------------------
  // 設定の保存
  // -------------------------------------------------------------------
  const saveLocalSettings = async () => {
    await Promise.all([
      saveSessionConfig('patent_analyze_system_prompt', analyzeSystemPrompt),
      saveSessionConfig('patent_analyze_output_format', analyzeOutputFormat),
      saveSessionConfig('patent_max_companies', String(maxCompanies)),
      saveSessionConfig('patent_max_total_patents', String(maxTotalPatents)),
      saveSessionConfig('patent_patents_per_company', String(patentsPerCompany)),
      saveSessionConfig('patent_strategy', strategy),
      saveSessionConfig('patent_chunk_size', String(chunkSize)),
    ]);
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
    setSavedCsvId('');
    try {
      const text = await readFileAsText(file);
      const rows = parseCSV(text);
      if (rows.length === 0) { setCsvError('CSVにデータがありません'); return; }

      const companyCol = settings?.patent_company_column ?? '出願人';
      if (!Object.prototype.hasOwnProperty.call(rows[0], companyCol)) {
        setCsvError(`列名 "${companyCol}" が見つかりません。Settingsで列名を確認してください。`);
        return;
      }

      const counts: Record<string, number> = {};
      for (const row of rows) {
        const co = (row[companyCol] ?? '').trim();
        if (co) counts[co] = (counts[co] ?? 0) + 1;
      }
      const sorted = Object.entries(counts)
        .map(([company, count]) => ({ company, count }))
        .sort((a, b) => b.count - a.count);

      setCsvRows(rows);
      setCsvName(file.name);
      setCompanies(sorted);

      // サーバーに自動保存
      setCsvSaving(true);
      try {
        const meta = await uploadPatentCsv(generateUUID(), file.name, rows);
        setSavedCsvId(meta.id);
        setSavedCsvs(prev => [meta, ...prev]);
      } catch (err) {
        console.error('CSV保存失敗:', err);
      } finally {
        setCsvSaving(false);
      }
    } catch (err: any) {
      setCsvError(err.message ?? 'CSVの読み込みに失敗しました');
    }
  };

  // サーバー保存済みCSVを読み込む
  const handleLoadSavedCsv = async (csvMeta: PatentCsvMeta) => {
    setCsvError('');
    try {
      const { rows } = await getPatentCsvRows(csvMeta.id);
      const companyCol = settings?.patent_company_column ?? '出願人';
      const counts: Record<string, number> = {};
      for (const row of rows) {
        const co = (row[companyCol] ?? '').trim();
        if (co) counts[co] = (counts[co] ?? 0) + 1;
      }
      const sorted = Object.entries(counts)
        .map(([company, count]) => ({ company, count }))
        .sort((a, b) => b.count - a.count);
      setCsvRows(rows);
      setCsvName(csvMeta.name);
      setSavedCsvId(csvMeta.id);
      setCompanies(sorted);
      setSelected(new Set());
    } catch (err: any) {
      setCsvError(err.message ?? 'CSV読み込みに失敗しました');
    }
  };

  const handleDeleteSavedCsv = async (csvId: string) => {
    if (!confirm('このCSVを削除しますか？')) return;
    await deletePatentCsv(csvId);
    setSavedCsvs(prev => prev.filter(c => c.id !== csvId));
    if (savedCsvId === csvId) { setSavedCsvId(''); setCsvRows([]); setCompanies([]); setSelected(new Set()); }
  };

  const toggleCompany = (company: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(company) ? next.delete(company) : next.add(company);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === companies.length) setSelected(new Set());
    else setSelected(new Set(companies.map(c => c.company)));
  };

  // -------------------------------------------------------------------
  // バリデーション
  // -------------------------------------------------------------------
  const getValidationWarning = (): string | null => {
    const orderedCompanies = companies.filter(c => selected.has(c.company));
    if (orderedCompanies.length > maxCompanies) {
      return `選択企業数 (${orderedCompanies.length}社) が上限 (${maxCompanies}社) を超えています。企業数を減らすか、上限を変更してください。`;
    }
    const totalPatents = orderedCompanies.reduce((sum, c) => sum + Math.min(c.count, patentsPerCompany), 0);
    if (totalPatents > maxTotalPatents) {
      return `合計特許数 (${totalPatents}件) が上限 (${maxTotalPatents}件) を超えています。企業数・件数を減らすか、圧縮モードまたはチャンク分割Reduceを使用してください。`;
    }
    return null;
  };

  // -------------------------------------------------------------------
  // 分析実行
  // -------------------------------------------------------------------
  const doAnalyze = async () => {
    await saveLocalSettings();
    setStatus('analyzing');
    setReport('');
    setGlobalError('');
    setIsTokenError(false);
    setCompressInfo(null);
    setChunkInfo(null);

    const contentCol = settings?.patent_content_column ?? '発明の名称';
    const dateCol = settings?.patent_date_column ?? '出願日';
    const companyCol = settings?.patent_company_column ?? '出願人';
    const orderedCompanies = companies.filter(c => selected.has(c.company));

    // 全企業の特許を収集
    const patentsByCompany: { company: string; patents: PatentItem[] }[] = [];
    for (const { company } of orderedCompanies) {
      const rows = csvRows
        .filter(r => (r[companyCol] ?? '').trim() === company)
        .sort((a, b) => (b[dateCol] ?? '').localeCompare(a[dateCol] ?? ''))
        .slice(0, patentsPerCompany);
      const patents: PatentItem[] = rows
        .map(r => ({ content: r[contentCol] ?? '', date: r[dateCol] ?? '' }))
        .filter(p => p.content);
      if (patents.length > 0) patentsByCompany.push({ company, patents });
    }

    const companyLabel = orderedCompanies.map(c => c.company).slice(0, 3).join('・')
      + (orderedCompanies.length > 3 ? '...' : '');

    const sessionId = generateUUID();
    const title = `${companyLabel} (${new Date().toLocaleDateString('ja-JP')})`;
    await createPatentSession(sessionId, title);

    try {
      let finalReport = '';

      if (strategy === 'chunked') {
        // --- チャンク分割Reduce ---
        const allPatents: PatentItem[] = patentsByCompany.flatMap(({ company, patents }) =>
          patents.map(p => ({ ...p, content: `[${company}] ${p.content}` }))
        );
        const totalChunks = Math.ceil(allPatents.length / chunkSize);
        setChunkInfo({ current: 0, total: totalChunks });

        const res = await apiPatentAnalyzeChunked({
          company: companyLabel,
          patents: allPatents,
          system_prompt: analyzeSystemPrompt,
          output_format: analyzeOutputFormat,
          chunk_size: chunkSize,
          max_prompt_tokens: settings?.patent_max_prompt_tokens ?? 0,
        });
        setChunkInfo({ current: res.chunk_count, total: res.chunk_count });
        finalReport = res.report;

      } else {
        // --- 圧縮 or 一括 ---
        let allPatents: PatentItem[];
        const compressMode: PatentCompressMode | null =
          strategy === 'bulk_per_patent' ? 'per_patent' :
          strategy === 'bulk_per_company' ? 'per_company' : null;

        if (compressMode) {
          setStatus('compressing');
          let totalOriginal = 0;
          let totalCompressed = 0;
          const compressedPatents: PatentItem[] = [];

          for (const { company, patents } of patentsByCompany) {
            totalOriginal += patents.length;
            try {
              const res = await apiPatentCompress({ patents, mode: compressMode, company });
              for (const p of res.patents) {
                compressedPatents.push({ ...p, content: `[${company}] ${p.content}` });
              }
              totalCompressed += res.compressed_count;
            } catch {
              for (const p of patents) {
                compressedPatents.push({ ...p, content: `[${company}] ${p.content}` });
              }
              totalCompressed += patents.length;
            }
          }
          allPatents = compressedPatents;
          setCompressInfo({ original: totalOriginal, compressed: totalCompressed });
          setStatus('analyzing');
        } else {
          allPatents = patentsByCompany.flatMap(({ company, patents }) =>
            patents.map(p => ({ ...p, content: `[${company}] ${p.content}` }))
          );
        }

        const res = await apiPatentAnalyze({
          company: companyLabel,
          patents: allPatents,
          system_prompt: analyzeSystemPrompt,
          output_format: analyzeOutputFormat,
          max_prompt_tokens: settings?.patent_max_prompt_tokens ?? 0,
        });
        finalReport = res.report;
      }

      setReport(finalReport);
      setStatus('done');
      await addPatentReport(sessionId, companyLabel, finalReport, 0);

    } catch (err: any) {
      const msg = err.message ?? 'エラーが発生しました';
      setGlobalError(msg);
      setIsTokenError(isTokenLimitError(msg));
      setStatus('error');
    }

    await loadSessions();

    try {
      if ('Notification' in window) {
        if (Notification.permission === 'default') await Notification.requestPermission();
        if (Notification.permission === 'granted') {
          new Notification('文献調査が完了しました', {
            body: `${orderedCompanies.length}社の特許分析が完了しました。`,
          });
        }
      }
    } catch { /* 通知は非必須のため無視 */ }
  };

  const handleStart = async () => {
    if (selected.size === 0) return;
    const validationWarn = getValidationWarning();
    if (validationWarn) {
      setWarning({
        message: validationWarn,
        onConfirm: () => { setWarning(null); doAnalyze(); },
      });
      return;
    }
    await doAnalyze();
  };

  // -------------------------------------------------------------------
  // プリセット管理
  // -------------------------------------------------------------------
  const _buildPresetData = (id: string, name: string): PatentPresetData => ({
    id,
    name,
    system_prompt: analyzeSystemPrompt,
    output_format: analyzeOutputFormat,
    strategy,
    chunk_size: chunkSize,
    max_companies: maxCompanies,
    max_total_patents: maxTotalPatents,
    patents_per_company: patentsPerCompany,
    csv_id: savedCsvId,
    selected_companies: Array.from(selected),
    stats_processors: Object.values(processorConfigs),
    final_llm_prompt: finalLlmPrompt,
  });

  const loadPreset = (presetId: string) => {
    setSelectedPresetId(presetId);
    if (!presetId) return;
    const preset = presets.find(p => p.id === presetId);
    if (!preset) return;
    setAnalyzeSystemPrompt(preset.system_prompt);
    setAnalyzeOutputFormat(preset.output_format);
    setStrategy(preset.strategy as AnalysisStrategy);
    setChunkSize(preset.chunk_size);
    setMaxCompanies(preset.max_companies);
    setMaxTotalPatents(preset.max_total_patents);
    setPatentsPerCompany(preset.patents_per_company);
    setFinalLlmPrompt(preset.final_llm_prompt || '');
    // 統計プロセッサ設定を復元
    if (preset.stats_processors?.length) {
      const restored: Record<string, StatProcessorConfig> = {};
      for (const sp of preset.stats_processors) {
        restored[sp.processor_id] = sp;
      }
      // 新しいプロセッサがあればデフォルト追加
      for (const p of availableProcessors) {
        if (!restored[p.id]) {
          restored[p.id] = { processor_id: p.id, enabled: false, param_prompt: '', variable_name: '', ipc_col: '' };
        }
      }
      setProcessorConfigs(restored);
    }
    // CSV復元
    if (preset.csv_id && preset.csv_id !== savedCsvId) {
      const csvMeta = savedCsvs.find(c => c.id === preset.csv_id);
      if (csvMeta) handleLoadSavedCsv(csvMeta);
    }
    // 企業選択を復元
    if (preset.selected_companies?.length) {
      setSelected(new Set(preset.selected_companies));
    }
  };

  const handleSavePreset = async () => {
    if (!presetName.trim()) return;
    const existing = presets.find(p => p.id === selectedPresetId);
    if (existing) {
      const updated = _buildPresetData(existing.id, presetName);
      const saved = await updatePatentPreset(updated);
      setPresets(prev => prev.map(p => p.id === saved.id ? saved : p));
    } else {
      const newPreset = _buildPresetData(generateUUID(), presetName);
      const saved = await createPatentPreset(newPreset);
      setPresets(prev => [...prev, saved]);
      setSelectedPresetId(saved.id);
    }
    setPresetName('');
    setShowSavePresetDialog(false);
  };

  const handleDeletePreset = async (id: string) => {
    if (!confirm('このプリセットを削除しますか？')) return;
    await deletePatentPreset(id);
    setPresets(prev => prev.filter(p => p.id !== id));
    if (selectedPresetId === id) setSelectedPresetId('');
  };

  // -------------------------------------------------------------------
  // コピー
  // -------------------------------------------------------------------
  const safeCopy = async (text: string, key: string) => {
    const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
    try {
      if (isTauri) {
        await writeText(text);
      } else {
        await navigator.clipboard.writeText(text);
      }
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    } catch (e) {
      console.error('Copy failed:', e);
    }
  };

  const handleCopy = (text: string) => safeCopy(text, 'report');

  // -------------------------------------------------------------------
  // 履歴操作
  // -------------------------------------------------------------------
  const handleExpandSession = async (id: string) => {
    if (expandedSession === id) { setExpandedSession(null); return; }
    setExpandedSession(id);
    if (!historyReports[id]) {
      const reps = await getPatentReports(id);
      setHistoryReports(prev => ({ ...prev, [id]: reps }));
    }
  };

  const handleDeleteSession = async (id: string) => {
    if (!confirm('このレポートを削除しますか？')) return;
    await deletePatentSession(id);
    setHistoryReports(prev => { const n = { ...prev }; delete n[id]; return n; });
    if (expandedSession === id) setExpandedSession(null);
    await loadSessions();
  };

  const handleCopyHistory = async (id: string) => {
    const reps = historyReports[id] ?? await getPatentReports(id);
    const session = sessions.find(s => s.id === id);
    const title = session?.title ?? '特許分析';
    const sections = [`# ${title}`];
    for (const r of reps) {
      sections.push(`## ${r.company}\n\n${r.report}`);
    }
    await safeCopy(sections.join('\n\n---\n\n'), `history:${id}`);
  };

  // -------------------------------------------------------------------
  // ヘルパー
  // -------------------------------------------------------------------
  const handleHelperApply = (suggestions: FieldSuggestion[]) => {
    for (const s of suggestions) {
      if (s.field === 'analyze_system_prompt') setAnalyzeSystemPrompt(s.value);
      if (s.field === 'analyze_output_format') setAnalyzeOutputFormat(s.value);
    }
  };

  // -------------------------------------------------------------------
  // 統計処理実行
  // -------------------------------------------------------------------
  const handleRunStats = async () => {
    if (csvRows.length === 0) return;
    const enabledIds = Object.values(processorConfigs).filter(c => c.enabled).map(c => c.processor_id);
    if (enabledIds.length === 0) return;

    setStatsStatus('running');
    setStatsTables([]);
    setStatsLlmResult('');
    setStatsError('');

    const displayMode = finalLlmPrompt ? 'llm' : 'table';
    const filteredRows = selected.size > 0
      ? csvRows.filter(r => selected.has((r[settings?.patent_company_column ?? '出願人'] ?? '').trim()))
      : csvRows;

    try {
      const res = await apiPatentStats({
        rows: filteredRows,
        processor_ids: enabledIds,
        display_mode: displayMode,
        llm_prompt: finalLlmPrompt,
        company_col: settings?.patent_company_column,
        date_col: settings?.patent_date_column,
        content_col: settings?.patent_content_column,
      });
      setStatsTables(res.tables);
      setStatsLlmResult(res.llm_result);
      setStatsStatus('done');
    } catch (err: any) {
      setStatsError(err.message ?? '統計処理でエラーが発生しました');
      setStatsStatus('error');
    }
  };

  const updateProcessorConfig = (id: string, patch: Partial<StatProcessorConfig>) => {
    setProcessorConfigs(prev => ({
      ...prev,
      [id]: { ...prev[id], ...patch },
    }));
  };

  // -------------------------------------------------------------------
  // 描画ヘルパー
  // -------------------------------------------------------------------
  const orderedSelected = companies.filter(c => selected.has(c.company));
  const estimatedTotal = orderedSelected.reduce((sum, c) => sum + Math.min(c.count, patentsPerCompany), 0);
  const companyOverLimit = orderedSelected.length > maxCompanies;
  const patentOverLimit = estimatedTotal > maxTotalPatents;
  const hasWarning = companyOverLimit || patentOverLimit;

  const isRunning = status === 'compressing' || status === 'analyzing';

  // -------------------------------------------------------------------
  // 描画
  // -------------------------------------------------------------------
  return (
    <div className="p-6 w-full flex flex-col gap-6">
      {/* 警告ダイアログ */}
      {warning && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 flex flex-col gap-4">
            <div className="flex items-start gap-3">
              <AlertTriangle size={20} className="text-amber-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-gray-800 text-sm">上限超過の警告</p>
                <p className="text-sm text-gray-600 mt-1">{warning.message}</p>
              </div>
            </div>
            <p className="text-xs text-gray-500">このまま続行しますか？コンテキスト長超過でエラーになる可能性があります。</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setWarning(null)}
                className="px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors">
                キャンセル
              </button>
              <button onClick={warning.onConfirm}
                className="px-4 py-1.5 text-sm bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-medium transition-colors">
                続行
              </button>
            </div>
          </div>
        </div>
      )}

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

          {/* プリセット管理 */}
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <FolderOpen size={15} className="text-gray-500" />
              <h2 className="text-sm font-semibold text-gray-700">プリセット</h2>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <select
                value={selectedPresetId}
                onChange={e => loadPreset(e.target.value)}
                className="flex-1 min-w-0 border border-gray-300 rounded-lg px-2 py-1.5 text-sm outline-none focus:border-blue-500"
              >
                <option value="">— プリセットを選択 —</option>
                {presets.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  setPresetName(presets.find(p => p.id === selectedPresetId)?.name ?? '');
                  setShowSavePresetDialog(v => !v);
                }}
                className="flex items-center gap-1 px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-gray-700"
              >
                <Save size={13} />
                {selectedPresetId ? '更新/別名保存' : '名前を付けて保存'}
              </button>
              {selectedPresetId && (
                <button
                  type="button"
                  onClick={() => handleDeletePreset(selectedPresetId)}
                  className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg border border-transparent hover:border-red-200 transition-colors"
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>
            {showSavePresetDialog && (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="プリセット名"
                  value={presetName}
                  onChange={e => setPresetName(e.target.value)}
                  className="flex-1 border border-gray-300 rounded-lg px-2 py-1 text-sm outline-none focus:border-blue-500"
                  onKeyDown={e => { if (e.key === 'Enter') handleSavePreset(); if (e.key === 'Escape') setShowSavePresetDialog(false); }}
                  autoFocus
                />
                <button type="button" onClick={handleSavePreset}
                  className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors">
                  保存
                </button>
                <button type="button" onClick={() => setShowSavePresetDialog(false)}
                  className="px-3 py-1 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                  キャンセル
                </button>
              </div>
            )}
          </section>

          {/* 統計処理設定 */}
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <button
              onClick={() => setStatsOpen(v => !v)}
              className="w-full flex items-center justify-between px-5 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span className="flex items-center gap-2">
                <BarChart2 size={15} className="text-indigo-500" />
                統計処理設定
              </span>
              {statsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {statsOpen && (
              <div className="px-5 pb-5 flex flex-col gap-4 border-t border-gray-100 pt-4">
                <p className="text-xs text-gray-400">
                  統計処理を選択し、各処理ごとにLLMがパラメータ（企業・期間等）を生成するプロンプトを設定できます。
                  プロンプトが空の場合は全データを機械的に処理します。
                  最終LLMプロンプトに変数（例: <code className="bg-gray-100 px-1 rounded">&#123;&#123;yearly_count&#125;&#125;</code>）を入れるとその統計結果が差し込まれます。
                </p>

                {/* 統計プロセッサ一覧 */}
                <div className="flex flex-col gap-3">
                  {availableProcessors.map(proc => {
                    const cfg = processorConfigs[proc.id];
                    if (!cfg) return null;
                    return (
                      <div key={proc.id} className={`border rounded-lg overflow-hidden transition-colors ${
                        cfg.enabled ? 'border-indigo-300' : 'border-gray-200'
                      }`}>
                        {/* ヘッダー行 */}
                        <div className={`flex items-center gap-2 px-3 py-2 ${cfg.enabled ? 'bg-indigo-50' : 'bg-gray-50'}`}>
                          <input
                            type="checkbox"
                            checked={cfg.enabled}
                            onChange={e => updateProcessorConfig(proc.id, { enabled: e.target.checked })}
                            className="shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-sm font-medium text-gray-700">{proc.title}</span>
                            <span className="ml-2 text-xs text-gray-400">{proc.description}</span>
                          </div>
                          <code className="text-xs text-indigo-500 bg-white border border-indigo-200 px-1.5 py-0.5 rounded shrink-0">
                            &#123;&#123;{cfg.variable_name || proc.id}&#125;&#125;
                          </code>
                        </div>

                        {/* 詳細設定（有効時のみ） */}
                        {cfg.enabled && (
                          <div className="px-3 py-3 flex flex-col gap-3 border-t border-indigo-100 bg-white">
                            {/* LLMパラメータ生成プロンプト */}
                            <div>
                              <label className="block text-xs font-semibold text-gray-600 mb-1">
                                パラメータ生成プロンプト
                                <span className="ml-1 font-normal text-gray-400">（空=全データを機械処理、入力時=LLMがフィルター条件を生成）</span>
                              </label>
                              <textarea
                                className={TEXTAREA_CLS}
                                rows={3}
                                value={cfg.param_prompt}
                                onChange={e => updateProcessorConfig(proc.id, { param_prompt: e.target.value })}
                                placeholder="例: 前の議論で言及された企業を対象に分析してください。対象企業をJSONで出力: {&quot;companies&quot;: [...], &quot;year_from&quot;: 2020}"
                              />
                            </div>
                            {/* 変数名・IPC列 */}
                            <div className="flex gap-3">
                              <div className="flex-1">
                                <label className="block text-xs font-semibold text-gray-600 mb-1">
                                  変数名
                                  <span className="ml-1 font-normal text-gray-400">（空の場合は processor_id を使用）</span>
                                </label>
                                <input
                                  type="text"
                                  className={INPUT_CLS}
                                  value={cfg.variable_name}
                                  onChange={e => updateProcessorConfig(proc.id, { variable_name: e.target.value })}
                                  placeholder={proc.id}
                                />
                              </div>
                              {proc.id === 'ipc_distribution' && (
                                <div className="flex-1">
                                  <label className="block text-xs font-semibold text-gray-600 mb-1">
                                    IPC列名
                                    <span className="ml-1 font-normal text-gray-400">（空=自動検出）</span>
                                  </label>
                                  <input
                                    type="text"
                                    className={INPUT_CLS}
                                    value={cfg.ipc_col}
                                    onChange={e => updateProcessorConfig(proc.id, { ipc_col: e.target.value })}
                                    placeholder="IPC分類"
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* 最終LLMプロンプト */}
                <div className="border-t border-gray-100 pt-3">
                  <label className="block text-xs font-semibold text-gray-600 mb-1">
                    最終LLMプロンプト
                    <span className="ml-2 font-normal text-gray-400">
                      変数例: <code className="bg-gray-100 px-1 rounded">&#123;&#123;company_count&#125;&#125;</code>、<code className="bg-gray-100 px-1 rounded">&#123;&#123;yearly_count&#125;&#125;</code>、<code className="bg-gray-100 px-1 rounded">&#123;&#123;stats_all&#125;&#125;</code>（全統計）
                    </span>
                    <span className="ml-2 font-normal text-gray-400">（空=統計テーブルをそのまま表示）</span>
                  </label>
                  <textarea
                    className={TEXTAREA_CLS}
                    rows={4}
                    value={finalLlmPrompt}
                    onChange={e => setFinalLlmPrompt(e.target.value)}
                    placeholder={`以下の特許統計データを分析し、技術動向と競争状況をまとめてください。\n\n{{stats_all}}`}
                  />
                </div>

                {/* 実行ボタン */}
                <div className="flex items-center justify-between border-t border-gray-100 pt-3">
                  <span className="text-xs text-gray-400">
                    {csvRows.length > 0
                      ? `${csvRows.length.toLocaleString()}件のデータ${selected.size > 0 ? `（${selected.size}社選択中）` : ''}`
                      : 'CSVをアップロードすると統計処理を実行できます'}
                  </span>
                  <button
                    onClick={handleRunStats}
                    disabled={csvRows.length === 0 || Object.values(processorConfigs).every(c => !c.enabled) || statsStatus === 'running'}
                    className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white rounded-lg text-sm font-semibold transition-colors"
                  >
                    <BarChart2 size={13} />
                    {statsStatus === 'running' ? '処理中...' : '統計実行'}
                  </button>
                </div>

                {/* 統計結果 */}
                {statsStatus !== 'idle' && (
                  <div className="border-t border-gray-100 pt-3 flex flex-col gap-3">
                    <h3 className="text-xs font-semibold text-gray-600">統計結果</h3>

                    {statsStatus === 'running' && (
                      <div className="flex items-center gap-2 text-sm text-indigo-600 animate-pulse">
                        <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" />
                        統計処理中...
                      </div>
                    )}

                    {statsStatus === 'error' && (
                      <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">
                        {statsError}
                      </div>
                    )}

                    {statsStatus === 'done' && (
                      <div className="flex flex-col gap-4">
                        {statsLlmResult ? (
                          <>
                            <div className="bg-gray-50 rounded-lg p-3">
                              <div className="prose prose-sm max-w-none text-gray-700">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{statsLlmResult}</ReactMarkdown>
                              </div>
                            </div>
                            <details className="text-xs">
                              <summary className="cursor-pointer text-gray-400 hover:text-gray-600">統計テーブルを表示</summary>
                              <div className="mt-2 flex flex-col gap-3">
                                {statsTables.filter(t => !t.is_empty).map(t => (
                                  <div key={t.processor_id} className="bg-gray-50 rounded-lg p-3 overflow-x-auto">
                                    <div className="prose prose-sm max-w-none text-gray-700">
                                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.markdown}</ReactMarkdown>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </details>
                          </>
                        ) : (
                          <>
                            {statsTables.filter(t => !t.is_empty).map(t => (
                              <div key={t.processor_id} className="bg-gray-50 rounded-lg p-3 overflow-x-auto">
                                <div className="prose prose-sm max-w-none text-gray-700">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.markdown}</ReactMarkdown>
                                </div>
                              </div>
                            ))}
                            {statsTables.every(t => t.is_empty) && (
                              <p className="text-xs text-gray-400">統計データが取得できませんでした。CSV列名の設定を確認してください。</p>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>

          {/* LLM分析設定 */}
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <button
              onClick={() => setSettingsOpen(v => !v)}
              className="w-full flex items-center justify-between px-5 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span>LLM分析設定</span>
              {settingsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {settingsOpen && (
              <div className="px-5 pb-5 flex flex-col gap-4 border-t border-gray-100 pt-4">
                <p className="text-xs text-gray-400">
                  ホスト側の列名設定 (Settings画面): 企業列=<code className="bg-gray-100 px-1 rounded">{settings?.patent_company_column ?? '...'}</code>、
                  内容列=<code className="bg-gray-100 px-1 rounded">{settings?.patent_content_column ?? '...'}</code>、
                  日付列=<code className="bg-gray-100 px-1 rounded">{settings?.patent_date_column ?? '...'}</code>
                </p>

                {/* プロンプト設定 */}
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">システムプロンプト</label>
                  <textarea className={TEXTAREA_CLS} rows={4} value={analyzeSystemPrompt}
                    onChange={e => setAnalyzeSystemPrompt(e.target.value)}
                    placeholder="（空の場合はデフォルトプロンプトを使用）" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">出力フォーマット</label>
                  <textarea className={TEXTAREA_CLS} rows={5} value={analyzeOutputFormat}
                    onChange={e => setAnalyzeOutputFormat(e.target.value)}
                    placeholder="（空の場合はデフォルトフォーマットを使用）" />
                </div>

                {/* 上限設定 */}
                <div className="border-t border-gray-100 pt-3">
                  <p className="text-xs font-semibold text-gray-600 mb-2">上限設定</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">最大企業数</label>
                      <input type="number" min="1" className={INPUT_CLS}
                        value={maxCompanies} onChange={e => setMaxCompanies(parseInt(e.target.value) || 1)} />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">企業ごとの最大件数</label>
                      <input type="number" min="1" max="100" className={INPUT_CLS}
                        value={patentsPerCompany} onChange={e => setPatentsPerCompany(parseInt(e.target.value) || 1)} />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">合計最大特許数</label>
                      <input type="number" min="1" className={INPUT_CLS}
                        value={maxTotalPatents} onChange={e => setMaxTotalPatents(parseInt(e.target.value) || 1)} />
                    </div>
                  </div>
                </div>

                {/* 分析戦略 */}
                <div className="border-t border-gray-100 pt-3">
                  <p className="text-xs font-semibold text-gray-600 mb-2">分析戦略</p>
                  <div className="flex flex-col gap-1.5">
                    {([
                      ['bulk',            '一括分析',               '全特許を1回のLLMに渡す。高速だが特許数が多いとコンテキスト超過のリスクあり'],
                      ['bulk_per_patent', '一括（特許個別要約）',    '各特許を事前に1〜2文へ要約してからまとめて渡す。トークンを削減'],
                      ['bulk_per_company','一括（企業別まとめ要約）','企業ごとの特許群をまとめて要約してから渡す。さらにトークンを削減'],
                      ['chunked',         'チャンク分割Reduce',      '特許をN件ずつ分割して個別分析し、最後に統合。大量特許でも安定動作'],
                    ] as [AnalysisStrategy, string, string][]).map(([val, label, desc]) => (
                      <label key={val} className={`flex items-start gap-2 px-3 py-2 rounded-lg cursor-pointer border transition-colors ${
                        strategy === val ? 'border-blue-300 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'
                      }`}>
                        <input type="radio" name="strategy" value={val}
                          checked={strategy === val}
                          onChange={() => setStrategy(val)}
                          className="mt-0.5 shrink-0" />
                        <div className="flex-1">
                          <span className="text-sm font-medium text-gray-700">{label}</span>
                          <p className="text-xs text-gray-400">{desc}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                  {strategy === 'chunked' && (
                    <div className="mt-2 flex items-center gap-2">
                      <label className="text-xs text-gray-500 shrink-0">チャンクサイズ（件/チャンク）</label>
                      <input type="number" min="1" max="200" className="w-24 border border-gray-300 rounded-lg px-2 py-1 text-sm outline-none focus:border-blue-500"
                        value={chunkSize} onChange={e => setChunkSize(parseInt(e.target.value) || 20)} />
                      <span className="text-xs text-gray-400">
                        → 推定 {estimatedTotal > 0 ? Math.ceil(estimatedTotal / chunkSize) : '?'} チャンク
                      </span>
                    </div>
                  )}
                  <p className="mt-2 text-xs text-gray-400">
                    圧縮・Reduceプロンプトは Settings画面で編集できます。
                  </p>
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
              <Upload size={15} /> CSVファイル
            </h2>

            {/* アップロード */}
            <div className="flex items-center gap-3 flex-wrap">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isRunning}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors border border-gray-200 disabled:opacity-50"
              >
                ファイルを選択
              </button>
              {csvRows.length > 0 && (
                <span className="text-sm text-gray-600">
                  <span className="font-medium">{csvName}</span>
                  <span className="text-gray-400 ml-1">({csvRows.length.toLocaleString()} 件)</span>
                  {csvSaving && <span className="ml-2 text-xs text-blue-500">保存中...</span>}
                  {savedCsvId && !csvSaving && <span className="ml-2 text-xs text-green-500">サーバー保存済み</span>}
                </span>
              )}
            </div>
            <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
            {csvError && <p className="text-xs text-red-500">{csvError}</p>}

            {/* 保存済みCSV一覧 */}
            {savedCsvs.length > 0 && (
              <div className="border-t border-gray-100 pt-3">
                <p className="text-xs font-semibold text-gray-600 mb-2">サーバー保存済みCSV</p>
                <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
                  {savedCsvs.map(csv => (
                    <div
                      key={csv.id}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm border transition-colors ${
                        savedCsvId === csv.id
                          ? 'border-blue-300 bg-blue-50'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <button
                        className="flex-1 text-left text-gray-700 truncate"
                        onClick={() => handleLoadSavedCsv(csv)}
                      >
                        <span className="font-medium truncate">{csv.name}</span>
                        <span className="ml-2 text-xs text-gray-400">{csv.row_count.toLocaleString()}件</span>
                      </button>
                      <button
                        onClick={() => handleDeleteSavedCsv(csv.id)}
                        className="p-1 text-gray-400 hover:text-red-500 transition-colors shrink-0"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
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

              {/* ステータスバー */}
              <div className="flex items-center justify-between pt-2 border-t border-gray-100 flex-wrap gap-2">
                <div className="flex items-center gap-3 text-xs flex-wrap">
                  <span className={companyOverLimit ? 'text-amber-600 font-semibold' : 'text-gray-500'}>
                    {orderedSelected.length}社選択中
                    {companyOverLimit && ` (上限: ${maxCompanies}社)`}
                  </span>
                  <span className={patentOverLimit ? 'text-amber-600 font-semibold' : 'text-gray-500'}>
                    推定 {estimatedTotal.toLocaleString()}件
                    {patentOverLimit && ` (上限: ${maxTotalPatents}件)`}
                  </span>
                  {hasWarning && (
                    <span className="flex items-center gap-1 text-amber-600">
                      <AlertTriangle size={12} /> 上限超過 — 続行時は警告が表示されます
                    </span>
                  )}
                  {strategy !== 'bulk' && (
                    <span className="flex items-center gap-1 text-blue-600">
                      <Minimize2 size={12} />
                      {strategy === 'bulk_per_patent' ? '特許個別要約' :
                       strategy === 'bulk_per_company' ? '企業別まとめ要約' :
                       `チャンク分割Reduce (${chunkSize}件/chunk)`}
                    </span>
                  )}
                </div>
                <button
                  onClick={handleStart}
                  disabled={selected.size === 0 || isRunning}
                  className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-semibold transition-colors shadow-sm"
                >
                  <Play size={14} />
                  {status === 'compressing' ? '圧縮中...' : status === 'analyzing' ? '分析中...' : '分析開始'}
                </button>
              </div>
            </section>
          )}

          {/* 結果 */}
          {(status !== 'idle') && (
            <section className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700">分析結果</h2>
                {status === 'done' && (
                  <button onClick={() => handleCopy(report)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                      copiedKey === 'report'
                        ? 'bg-green-50 text-green-700 border-green-200'
                        : 'text-gray-600 hover:bg-gray-100 border-gray-200'
                    }`}>
                    {copiedKey === 'report' ? <Check size={13} /> : <Copy size={13} />}
                    {copiedKey === 'report' ? 'コピーしました' : 'MDコピー'}
                  </button>
                )}
              </div>

              {/* 圧縮情報 */}
              {compressInfo && (
                <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 rounded-lg text-xs text-blue-700 border border-blue-200">
                  <Minimize2 size={13} />
                  圧縮完了: {compressInfo.original}件 → {compressInfo.compressed}件
                  （{Math.round((1 - compressInfo.compressed / compressInfo.original) * 100)}%削減）
                </div>
              )}

              {/* チャンク進捗情報 */}
              {chunkInfo && (
                <div className="flex items-center gap-2 px-3 py-2 bg-purple-50 rounded-lg text-xs text-purple-700 border border-purple-200">
                  <FileText size={13} />
                  {status === 'done'
                    ? `チャンク分割Reduce完了: ${chunkInfo.total}チャンクを統合`
                    : `チャンク分割Reduce実行中... (全${chunkInfo.total}チャンク)`}
                </div>
              )}

              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className={`px-5 py-3 flex items-center gap-2 border-b border-gray-100 ${
                  isRunning ? 'bg-blue-50' :
                  status === 'done' ? 'bg-green-50' : 'bg-red-50'
                }`}>
                  <FileText size={15} className="text-gray-500 shrink-0" />
                  <span className="font-semibold text-gray-800 flex-1">特許分析レポート</span>
                  <span className="text-xs text-gray-400">
                    {status === 'compressing' ? '圧縮中...' :
                     status === 'analyzing' ? '分析中...' :
                     status === 'done' ? '完了' : 'エラー'}
                  </span>
                </div>
                <div className="px-5 py-4">
                  {isRunning && (
                    <div className="flex items-center gap-2 text-sm text-blue-600 animate-pulse">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
                      {status === 'compressing'
                        ? '特許テキストを圧縮中...'
                        : strategy === 'chunked'
                          ? `チャンク分割分析中... Map → Reduce（サーバー側で処理中）`
                          : 'LLMが分析中...'}
                    </div>
                  )}
                  {status === 'done' && (
                    <div className="prose prose-sm max-w-none text-gray-700">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                    </div>
                  )}
                  {status === 'error' && (
                    <div className={`rounded-lg p-3 text-sm ${isTokenError ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
                      {isTokenError && (
                        <div className="flex items-center gap-2 font-semibold mb-1">
                          <AlertTriangle size={14} className="shrink-0" />
                          トークン数超過
                        </div>
                      )}
                      <p>{globalError}</p>
                      {isTokenError && (
                        <p className="mt-2 text-xs">
                          対処法: 企業数・件数を減らす / 圧縮モードを使用する / Settings でトークン上限を見直す
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}
        </div>
      )}

      <HelperChatWidget
        context="patent"
        currentInput={{
          analyze_system_prompt: analyzeSystemPrompt,
          analyze_output_format: analyzeOutputFormat,
        }}
        onApply={handleHelperApply}
      />

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
                      <div key={r.id} className="prose prose-sm max-w-none text-gray-700 bg-gray-50 rounded-lg p-3">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.report}</ReactMarkdown>
                      </div>
                    ))}
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
