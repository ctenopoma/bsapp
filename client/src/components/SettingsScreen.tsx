import { useState } from 'react';
import { AppSettings, HealthResponse } from '../types/api';
import { apiGetSettings, apiSaveSettings, apiGetHealth } from '../lib/api';
import { SlidersHorizontal, Save, RotateCcw, CheckCircle, XCircle, RefreshCw } from 'lucide-react';

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-semibold text-gray-700 mb-1">
        {label}
        {hint && <span className="ml-2 text-xs text-gray-400 font-normal">{hint}</span>}
      </label>
      {children}
    </div>
  );
}

const INPUT_CLS = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500";
const TEXTAREA_CLS = `${INPUT_CLS} resize-y font-mono`;

type HealthStatus = 'idle' | 'checking' | 'done';

const DEFAULT_FORM: AppSettings = {
  turns_per_theme: 5,
  default_output_format: "【発言者】{name}\n【主張】(1〜2文で主張を述べる)\n【根拠】(根拠や補足を1〜2文で)\n300字以内で記述してください。",
  agent_prompt_template: "",
  summary_prompt_template: "",
  max_history_tokens: 50000,
  recent_history_count: 5,
  available_rag_types: [],
  patent_company_column: '出願人',
  patent_content_column: '発明の名称',
  patent_date_column: '出願日',
};

function getErrorMessage(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : String(error);

  if (message.includes('[Fetch Failed]')) {
    return `${fallback} ホストが起動しているか確認してから再試行してください。`;
  }

  return message.replace(/^Error:\s*/, '') || fallback;
}

export default function SettingsScreen() {
  const [form, setForm] = useState<AppSettings>(DEFAULT_FORM);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus>('idle');
  const [healthError, setHealthError] = useState('');
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const set = (key: keyof AppSettings, value: string | number) =>
    setForm(prev => ({ ...prev, [key]: value }));

  const loadSettings = async () => {
    setLoadingSettings(true);
    setError('');
    try {
      const settings = await apiGetSettings();
      setForm(settings);
      setSettingsLoaded(true);
    } catch (e: unknown) {
      setSettingsLoaded(false);
      setError(getErrorMessage(e, 'ホスト設定の読込に失敗しました。'));
    } finally {
      setLoadingSettings(false);
    }
  };

  const handleSave = async () => {
    try {
      setError('');
      const updated = await apiSaveSettings(form);
      setForm(updated);
      setSettingsLoaded(true);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setError(getErrorMessage(e, '保存に失敗しました。'));
    }
  };

  const handleHealthCheck = async () => {
    setHealthStatus('checking');
    setHealthError('');
    setHealth(null);
    try {
      const result = await apiGetHealth();
      setHealth(result);
      await loadSettings();
      setHealthStatus('done');
    } catch (e: unknown) {
      setHealthError(getErrorMessage(e, '接続確認に失敗しました。'));
      setHealthStatus('done');
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto flex flex-col gap-8 overflow-y-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-2">
          <SlidersHorizontal className="text-blue-600" />
          Settings
        </h1>
        <p className="text-gray-500 mt-2 text-sm">変更はサーバー再起動後も settings.json に保存されます。</p>
        <p className="text-xs text-gray-500 mt-2">
          {settingsLoaded
            ? 'ホスト設定を読み込み済みです。'
            : '初回表示ではホストへ自動接続しません。接続確認またはリロードでホスト設定を読み込みます。'}
        </p>
      </div>

      {/* 接続確認 */}
      <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex flex-col gap-4">
        <h2 className="text-lg font-bold text-gray-800 border-b border-gray-100 pb-2">接続確認</h2>
        <p className="text-xs text-gray-500">LLM接続設定はサーバー側 (.env) で管理されています。</p>
        <div className="flex items-center gap-4">
          <button
            onClick={handleHealthCheck}
            disabled={healthStatus === 'checking' || loadingSettings}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <RefreshCw size={15} className={healthStatus === 'checking' || loadingSettings ? 'animate-spin' : ''} />
            {healthStatus === 'checking' || loadingSettings ? '確認中...' : '接続確認'}
          </button>
          {healthStatus === 'done' && (
            <div className="flex flex-col gap-2 text-sm">
              {healthError ? (
                <StatusRow label="サーバー" ok={false} detail={healthError} />
              ) : (
                <>
                  <StatusRow label="サーバー" ok={true} />
                  <StatusRow label="LLM" ok={health?.llm === 'ok'} detail={health?.llm_error} />
                </>
              )}
            </div>
          )}
        </div>
      </section>

      {/* セッションデフォルト */}
      <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex flex-col gap-4">
        <h2 className="text-lg font-bold text-gray-800 border-b border-gray-100 pb-2">セッションデフォルト</h2>
        <Field label="1テーマあたりのターン数">
          <input className={INPUT_CLS} type="number" min="1" max="50"
            value={form.turns_per_theme}
            onChange={e => set('turns_per_theme', parseInt(e.target.value) || 5)} />
        </Field>
        <Field label="デフォルト出力フォーマット" hint="（テーマ・ペルソナ未指定時に使用）">
          <textarea className={TEXTAREA_CLS} rows={4} value={form.default_output_format}
            onChange={e => set('default_output_format', e.target.value)} />
        </Field>
      </section>

      {/* 会話履歴設定 */}
      <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex flex-col gap-4">
        <h2 className="text-lg font-bold text-gray-800 border-b border-gray-100 pb-2">会話履歴設定</h2>
        <p className="text-xs text-gray-500">
          エージェントに渡す会話履歴のトークン上限と、圧縮しない直近の件数を設定します。
          上限を超えた古い履歴はLLMで要約圧縮され、チャット画面に通知が表示されます（0=無制限）。
        </p>
        <p className="text-xs text-amber-600">
          サーバー側で <code className="bg-amber-50 px-1 rounded">MAX_HISTORY_TOKENS_LIMIT</code>（.env）が設定されている場合、
          その値を超える設定は保存時にエラーになります。また実行時も自動的に上限でキャップされます。
        </p>
        <Field label="会話履歴の最大トークン数" hint="（0=サーバー上限で自動制限）">
          <input className={INPUT_CLS} type="number" min="0"
            value={form.max_history_tokens}
            onChange={e => set('max_history_tokens', parseInt(e.target.value) || 0)} />
        </Field>
        <Field label="圧縮しない直近の会話数" hint="（この件数より前の履歴を圧縮対象にする）">
          <input className={INPUT_CLS} type="number" min="1" max="200"
            value={form.recent_history_count}
            onChange={e => set('recent_history_count', parseInt(e.target.value) || 5)} />
        </Field>
      </section>

      {/* 特許調査設定 */}
      <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex flex-col gap-4">
        <h2 className="text-lg font-bold text-gray-800 border-b border-gray-100 pb-2">特許調査 CSV列名設定</h2>
        <p className="text-xs text-gray-500">Patent Research画面で使用するCSVの列名を設定します。</p>
        <Field label="企業名列" hint="（出願人など）">
          <input className={INPUT_CLS} type="text" value={form.patent_company_column ?? ''}
            onChange={e => set('patent_company_column', e.target.value)} />
        </Field>
        <Field label="特許内容列" hint="（発明の名称など）">
          <input className={INPUT_CLS} type="text" value={form.patent_content_column ?? ''}
            onChange={e => set('patent_content_column', e.target.value)} />
        </Field>
        <Field label="日付列" hint="（出願日など / 最新10件の抽出に使用）">
          <input className={INPUT_CLS} type="text" value={form.patent_date_column ?? ''}
            onChange={e => set('patent_date_column', e.target.value)} />
        </Field>
      </section>

      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200 text-sm">{error}</div>
      )}

      <div className="flex justify-end gap-3 pb-8">
        <button
          onClick={loadSettings}
          disabled={loadingSettings}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors border border-gray-200"
        >
          <RotateCcw size={16} className={loadingSettings ? 'animate-spin' : ''} />
          {loadingSettings ? '読込中...' : 'リロード'}
        </button>
        <button
          onClick={handleSave}
          disabled={!settingsLoaded}
          className={`flex items-center gap-2 px-6 py-2 rounded-lg font-semibold transition-colors shadow-sm ${
            saved
              ? 'bg-green-600 text-white'
              : 'bg-blue-600 hover:bg-blue-700 text-white disabled:bg-blue-300 disabled:hover:bg-blue-300'
          }`}
        >
          <Save size={16} /> {saved ? '保存しました' : '保存'}
        </button>
      </div>
    </div>
  );
}

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail?: string | null }) {
  return (
    <div className="flex items-center gap-2">
      {ok
        ? <CheckCircle size={16} className="text-green-500 shrink-0" />
        : <XCircle size={16} className="text-red-500 shrink-0" />}
      <span className={ok ? 'text-green-700' : 'text-red-700'}>
        {label}: {ok ? 'OK' : 'エラー'}
      </span>
      {!ok && detail && <span className="text-gray-500 text-xs ml-1 truncate max-w-xs" title={detail}>{detail}</span>}
    </div>
  );
}
