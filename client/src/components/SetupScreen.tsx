import { useState, useEffect, useRef } from 'react';
import { generateUUID } from '../lib/uuid';
import { useNavigate } from 'react-router-dom';
import { Persona, TaskModel, ThemeConfig, THEME_STRATEGIES, PROJECT_FLOWS } from '../types/api';
import {
  getPersonas, getTasks, createSession, updateSessionTitle, getThemeEntries, saveThemeEntries,
  getSessionConfig, saveSessionConfig,
  getPresets, createPreset, updatePreset, deletePreset, PresetData,
  getPersonaPresets, PersonaPresetData,
  getTaskPresets, TaskPresetData,
} from '../lib/server-db';
import { apiStartSession, apiGetSettings, apiGenerateTitle } from '../lib/api';
import { Settings, Play, Plus, Trash2, Save, FolderOpen, Users, ListTodo, ArrowUp, ArrowDown } from 'lucide-react';

interface ThemeEntry {
  localId: string;
  text: string;
  personaIds: Set<string>; // 空 = 全ペルソナ参加
  outputFormat: string;
  turnsPerTheme: number | null; // null = セッションのデフォルト値を使用
  preInfo: string; // テーマ固有の事前情報
  themeStrategy: string; // テーマ内ストラテジー（空 = sequential）
  strategyConfig: Record<string, any>; // ストラテジー固有の設定
  personaOrder: string[]; // ペルソナIDの発言順序
  useCustomOrder: boolean; // カスタム順を使用するか
  flowRoleMap: Record<string, string[]>; // フロー役割マッピング（役割名 → ペルソナIDリスト）
  taskAssignment: string; // タスク割り当てモード: random / round_robin / fixed（空=グローバル設定）
  personaTaskMap: Record<string, string>; // fixed時のペルソナID→タスクID
}

function newEntry(): ThemeEntry {
  return { localId: generateUUID(), text: '', personaIds: new Set(), outputFormat: '', turnsPerTheme: null, preInfo: '', themeStrategy: '', strategyConfig: {}, personaOrder: [], useCustomOrder: false, flowRoleMap: {} as Record<string, string[]>, taskAssignment: '', personaTaskMap: {} };
}

// DB形式 <-> UI形式変換
function dbToUi(e: { id: string; text: string; persona_ids: string; output_format: string; turns_per_theme?: number | null; pre_info?: string; theme_strategy?: string; strategy_config?: Record<string, any>; persona_order?: string[]; flow_role_map?: Record<string, string>; task_assignment?: string; persona_task_map?: Record<string, string> }): ThemeEntry {
  const personaOrder = e.persona_order ?? [];
  return {
    localId: e.id,
    text: e.text,
    personaIds: e.persona_ids ? new Set(e.persona_ids.split(',').filter(Boolean)) : new Set(),
    outputFormat: e.output_format ?? '',
    turnsPerTheme: e.turns_per_theme ?? null,
    preInfo: e.pre_info ?? '',
    themeStrategy: e.theme_strategy ?? '',
    strategyConfig: e.strategy_config ?? {},
    personaOrder,
    useCustomOrder: personaOrder.length > 0,
    flowRoleMap: (() => {
      const raw = e.flow_role_map ?? {};
      const result: Record<string, string[]> = {};
      for (const [k, v] of Object.entries(raw)) {
        result[k] = Array.isArray(v) ? v : [v];
      }
      return result;
    })(),
    taskAssignment: e.task_assignment ?? '',
    personaTaskMap: e.persona_task_map ?? {},
  };
}

function uiToDb(e: ThemeEntry, i: number) {
  return {
    id: e.localId,
    text: e.text,
    persona_ids: [...e.personaIds].join(','),
    output_format: e.outputFormat,
    turns_per_theme: e.turnsPerTheme,
    pre_info: e.preInfo,
    theme_strategy: e.themeStrategy,
    strategy_config: e.strategyConfig,
    persona_order: e.useCustomOrder ? e.personaOrder : [],
    flow_role_map: (() => {
      const m: Record<string, string[]> = {};
      for (const [role, pids] of Object.entries(e.flowRoleMap)) {
        if (pids.length > 0) m[role] = pids;
      }
      return Object.keys(m).length > 0 ? m : undefined;
    })(),
    task_assignment: e.taskAssignment || undefined,
    persona_task_map: Object.keys(e.personaTaskMap).length > 0 ? e.personaTaskMap : undefined,
    sort_order: i,
  };
}

export default function SetupScreen() {
  const navigate = useNavigate();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [allTasks, setAllTasks] = useState<TaskModel[]>([]);
  const [themeEntries, setThemeEntries] = useState<ThemeEntry[]>([newEntry()]);
  const themeTextRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  const [activePersonaIds, setActivePersonaIds] = useState<Set<string>>(new Set());
  const [activeTaskIds, setActiveTaskIds] = useState<Set<string>>(new Set());
  const [commonTheme, setCommonTheme] = useState('');
  const [preInfo, setPreInfo] = useState('');
  const [turnsPerTheme, setTurnsPerTheme] = useState(5);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState('');
  const [projectFlow, setProjectFlow] = useState('waterfall');
  const [flowConfig, setFlowConfig] = useState<Record<string, any>>({});
  const [themeTab, setThemeTab] = useState<Record<string, string>>({}); // localId → active tab
  const [flowRoleTab, setFlowRoleTab] = useState(''); // active flow role tab

  // テーマプリセット管理
  const [presets, setPresets] = useState<PresetData[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>('');
  const [presetName, setPresetName] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);

  // ペルソナプリセット・タスクプリセット
  const [personaPresets, setPersonaPresets] = useState<PersonaPresetData[]>([]);
  const [taskPresets, setTaskPresets] = useState<TaskPresetData[]>([]);
  const [selectedPersonaPresetId, setSelectedPersonaPresetId] = useState<string>('');
  const [selectedTaskPresetId, setSelectedTaskPresetId] = useState<string>('');

  const resizeTextarea = (element: HTMLTextAreaElement | null) => {
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${element.scrollHeight}px`;
  };

  useEffect(() => {
    getPersonas().then(p => {
      setPersonas(p);
      setActivePersonaIds(new Set(p.map(x => x.id)));
    }).catch(console.error);
    getTasks().then(tasks => {
      setAllTasks(tasks);
      setActiveTaskIds(new Set(tasks.map(t => t.id)));
    }).catch(console.error);
    // 保存されたテーマを読み込む
    getThemeEntries().then(rows => {
      if (rows.length > 0) {
        setThemeEntries(rows.map(dbToUi));
      }
    }).catch(console.error);
    getSessionConfig('common_theme').then(setCommonTheme).catch(console.error);
    getSessionConfig('pre_info').then(setPreInfo).catch(console.error);
    getSessionConfig('project_flow').then(v => { if (v) setProjectFlow(v); }).catch(console.error);
    getSessionConfig('flow_config').then(v => { if (v) try { setFlowConfig(JSON.parse(v)); } catch {} }).catch(console.error);
    apiGetSettings().then(s => setTurnsPerTheme(s.turns_per_theme)).catch(console.error);
    getPresets().then(setPresets).catch(console.error);
    getPersonaPresets().then(setPersonaPresets).catch(console.error);
    getTaskPresets().then(setTaskPresets).catch(console.error);
  }, []);

  useEffect(() => {
    themeEntries.forEach(entry => {
      resizeTextarea(themeTextRefs.current[entry.localId] ?? null);
    });
  }, [themeEntries]);

  const addTheme = () => setThemeEntries(prev => {
    const next = [...prev, newEntry()];
    saveThemeEntries(next.map(uiToDb)).catch(console.error);
    return next;
  });

  const removeTheme = (localId: string) =>
    setThemeEntries(prev => {
      const next = prev.filter(e => e.localId !== localId);
      saveThemeEntries(next.map(uiToDb)).catch(console.error);
      return next;
    });

  const updateText = (localId: string, text: string) =>
    setThemeEntries(prev => {
      const next = prev.map(e => e.localId === localId ? { ...e, text } : e);
      saveThemeEntries(next.map(uiToDb)).catch(console.error);
      return next;
    });

  const updateOutputFormat = (localId: string, outputFormat: string) =>
    setThemeEntries(prev => {
      const next = prev.map(e => e.localId === localId ? { ...e, outputFormat } : e);
      saveThemeEntries(next.map(uiToDb)).catch(console.error);
      return next;
    });

  const updateThemePreInfo = (localId: string, preInfo: string) =>
    setThemeEntries(prev => {
      const next = prev.map(e => e.localId === localId ? { ...e, preInfo } : e);
      saveThemeEntries(next.map(uiToDb)).catch(console.error);
      return next;
    });

  const togglePersona = (localId: string, personaId: string) => {
    setThemeEntries(prev => {
      const next = prev.map(e => {
        if (e.localId !== localId) return e;
        const pids = new Set(e.personaIds);
        if (pids.size === 0) personas.forEach(p => pids.add(p.id));
        if (pids.has(personaId)) pids.delete(personaId);
        else pids.add(personaId);
        if (pids.size === personas.length) pids.clear();
        // personaOrder から無効なペルソナIDを除去
        const newOrder = e.personaOrder.filter(id => pids.size === 0 || pids.has(id));
        return { ...e, personaIds: pids, personaOrder: newOrder };
      });
      saveThemeEntries(next.map(uiToDb)).catch(console.error);
      return next;
    });
  };

  const isActive = (entry: ThemeEntry, personaId: string) =>
    entry.personaIds.size === 0 || entry.personaIds.has(personaId);

  const loadPersonaPreset = (presetId: string) => {
    setSelectedPersonaPresetId(presetId);
    if (!presetId) {
      setActivePersonaIds(new Set(personas.map(p => p.id)));
      return;
    }
    const preset = personaPresets.find(p => p.id === presetId);
    if (preset) {
      setActivePersonaIds(new Set(preset.persona_ids.split(',').filter(Boolean)));
    }
  };

  const loadTaskPreset = (presetId: string) => {
    setSelectedTaskPresetId(presetId);
    if (!presetId) {
      setActiveTaskIds(new Set(allTasks.map(t => t.id)));
      return;
    }
    const preset = taskPresets.find(p => p.id === presetId);
    if (preset) {
      setActiveTaskIds(new Set(preset.task_ids.split(',').filter(Boolean)));
    }
  };

  // プリセット読み込み
  const loadPreset = (presetId: string) => {
    const preset = presets.find(p => p.id === presetId);
    if (!preset) {
      setSelectedPresetId('');
      return;
    }
    setSelectedPresetId(presetId);
    try {
      const entries = JSON.parse(preset.theme_entries) as Array<{ id: string; text: string; persona_ids: string; output_format: string; turns_per_theme?: number | null; sort_order?: number }>;
      if (entries.length > 0) {
        setThemeEntries(entries.map(dbToUi));
        saveThemeEntries(entries.map((e, i) => ({ ...e, sort_order: e.sort_order ?? i }))).catch(console.error);
      }
    } catch { /* ignore parse error */ }
    setCommonTheme(preset.common_theme);
    saveSessionConfig('common_theme', preset.common_theme).catch(console.error);
    setPreInfo(preset.pre_info);
    saveSessionConfig('pre_info', preset.pre_info).catch(console.error);
    setTurnsPerTheme(preset.turns_per_theme);
    const pf = preset.project_flow ?? 'waterfall';
    setProjectFlow(pf);
    saveSessionConfig('project_flow', pf).catch(console.error);
    const fc = preset.flow_config ?? {};
    setFlowConfig(fc);
    saveSessionConfig('flow_config', JSON.stringify(fc)).catch(console.error);
  };

  // プリセット保存
  const saveCurrentAsPreset = async (name: string) => {
    const data: PresetData = {
      id: selectedPresetId || generateUUID(),
      name,
      theme_entries: JSON.stringify(themeEntries.map(uiToDb)),
      common_theme: commonTheme,
      pre_info: preInfo,
      turns_per_theme: turnsPerTheme,
      project_flow: projectFlow,
      flow_config: flowConfig,
    };
    try {
      if (selectedPresetId && presets.some(p => p.id === selectedPresetId)) {
        await updatePreset(data);
        setPresets(prev => prev.map(p => p.id === data.id ? data : p));
      } else {
        data.id = generateUUID();
        await createPreset(data);
        setPresets(prev => [...prev, data]);
        setSelectedPresetId(data.id);
      }
      setShowSaveDialog(false);
      setPresetName('');
    } catch (e: any) {
      setError(e.message || 'Failed to save preset');
    }
  };

  // プリセット削除
  const handleDeletePreset = async () => {
    if (!selectedPresetId) return;
    const preset = presets.find(p => p.id === selectedPresetId);
    if (!preset || !confirm(`プリセット「${preset.name}」を削除しますか？`)) return;
    try {
      await deletePreset(selectedPresetId);
      setPresets(prev => prev.filter(p => p.id !== selectedPresetId));
      setSelectedPresetId('');
    } catch (e: any) {
      setError(e.message || 'Failed to delete preset');
    }
  };

  const handleStart = async () => {
    const valid = themeEntries.filter(e => e.text.trim());
    if (valid.length === 0) { setError('テーマを1つ以上入力してください。'); return; }

    const usedTasks = allTasks.filter(t => activeTaskIds.has(t.id));
    if (usedTasks.length === 0 && allTasks.length > 0) {
      setError('タスクを1つ以上選択してください。'); return;
    }

    // activePersonaIdsでフィルタした上で、テーマごとのunionを送信
    const activePersonas = personas.filter(p => activePersonaIds.has(p.id));
    if (activePersonas.length === 0) { setError('参加するペルソナを1つ以上選択してください。'); return; }
    const usedIds = new Set<string>();
    valid.forEach(e => {
      if (e.personaIds.size === 0) activePersonas.forEach(p => usedIds.add(p.id));
      else e.personaIds.forEach(id => { if (activePersonaIds.has(id)) usedIds.add(id); });
    });
    const usedPersonas = activePersonas.filter(p => usedIds.has(p.id));
    if (usedPersonas.length === 0) { setError('参加するペルソナがありません。'); return; }

    const themes: ThemeConfig[] = valid.map(e => ({
      theme: e.text.trim(),
      persona_ids: [...e.personaIds],
      output_format: e.outputFormat,
      turns_per_theme: e.turnsPerTheme ?? undefined,
      pre_info: e.preInfo || undefined,
      theme_strategy: e.themeStrategy || undefined,
      strategy_config: Object.keys(e.strategyConfig).length > 0 ? e.strategyConfig : undefined,
      persona_order: e.useCustomOrder && e.personaOrder.length > 0 ? e.personaOrder : undefined,
      flow_role_map: (() => {
        const m: Record<string, string[]> = {};
        for (const [role, pids] of Object.entries(e.flowRoleMap)) {
          if (pids.length > 0) m[role] = pids;
        }
        return Object.keys(m).length > 0 ? m : undefined;
      })(),
      task_assignment: e.taskAssignment || undefined,
      persona_task_map: Object.keys(e.personaTaskMap).length > 0 ? e.personaTaskMap : undefined,
    }));

    try {
      setIsStarting(true);
      setError('');
      const res = await apiStartSession({ themes, personas: usedPersonas, tasks: usedTasks, history: [], common_theme: commonTheme, pre_info: preInfo, turns_per_theme: turnsPerTheme, project_flow: projectFlow || undefined, flow_config: Object.keys(flowConfig).length > 0 ? flowConfig : undefined });
      const sessionId = res.session_id;
      // LLMにタイトルを生成させる（失敗時はフォールバック）
      let title: string;
      try {
        const titleRes = await apiGenerateTitle(themes.map(t => t.theme), commonTheme);
        title = titleRes.title;
      } catch {
        title = themes[0].theme.substring(0, 30) + (themes[0].theme.length > 30 ? '...' : '');
      }
      await createSession(sessionId, title);
      navigate(`/discussion/${sessionId}`);
    } catch (e: any) {
      setError(e.message || 'Failed to start session');
      setIsStarting(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto flex flex-col h-full overflow-y-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-2">
          <Settings className="text-blue-600" />
          Setup Discussion
        </h1>
        <p className="text-gray-600 mt-2">テーマごとに参加するペルソナを設定し、割り当てるタスクを選んでください。</p>
      </div>

      {/* プリセット選択 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex items-center gap-3 flex-wrap">
          <FolderOpen size={16} className="text-gray-500 shrink-0" />
          <label className="text-sm font-bold text-gray-700 shrink-0">プリセット</label>
          <select
            value={selectedPresetId}
            onChange={e => loadPreset(e.target.value)}
            className="flex-1 min-w-[200px] border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 bg-white"
          >
            <option value="">-- 選択してください --</option>
            {presets.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <button
            onClick={() => {
              const current = presets.find(p => p.id === selectedPresetId);
              setPresetName(current?.name || '');
              setShowSaveDialog(true);
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-green-700 bg-green-50 hover:bg-green-100 border border-green-300 rounded-lg transition-colors"
          >
            <Save size={14} />
            {selectedPresetId ? '上書き保存' : '新規保存'}
          </button>
          {selectedPresetId && (
            <button
              onClick={handleDeletePreset}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition-colors"
            >
              <Trash2 size={14} />
              削除
            </button>
          )}
        </div>
        {showSaveDialog && (
          <div className="mt-3 flex items-center gap-2 border-t border-gray-100 pt-3">
            <input
              type="text"
              value={presetName}
              onChange={e => setPresetName(e.target.value)}
              placeholder="プリセット名を入力..."
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              autoFocus
              onKeyDown={e => { if (e.key === 'Enter' && presetName.trim()) saveCurrentAsPreset(presetName.trim()); }}
            />
            <button
              onClick={() => presetName.trim() && saveCurrentAsPreset(presetName.trim())}
              disabled={!presetName.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 rounded-lg transition-colors"
            >
              保存
            </button>
            <button
              onClick={() => { setShowSaveDialog(false); setPresetName(''); }}
              className="px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              キャンセル
            </button>
          </div>
        )}
      </div>

      {/* 共通テーマ & 事前情報 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6 flex flex-col gap-4">
        <div>
          <label className="block text-sm font-bold text-gray-700 mb-1">共通テーマ <span className="text-gray-400 font-normal text-xs">（全テーマに共通する上位テーマ）</span></label>
          <textarea
            value={commonTheme}
            onChange={e => { setCommonTheme(e.target.value); saveSessionConfig('common_theme', e.target.value).catch(console.error); }}
            placeholder="例: 2030年の社会課題"
            rows={3}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y"
          />
        </div>
        <div>
          <label className="block text-sm font-bold text-gray-700 mb-1">事前情報 <span className="text-gray-400 font-normal text-xs">（全エージェントに共有する背景情報・テンプレート変数使用可）</span></label>
          <textarea
            value={preInfo}
            onChange={e => { setPreInfo(e.target.value); saveSessionConfig('pre_info', e.target.value).catch(console.error); }}
            placeholder={"議論の前提となる情報を入力（ファイル内容の貼り付けなど）\nテンプレート変数例: {{theme1_summary}}"}
            rows={4}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y font-mono"
          />
          <p className="text-xs text-gray-400 mt-1">
            変数: <code className="bg-gray-100 px-1 rounded">{`{{themeN_summary}}`}</code> 要約 / <code className="bg-gray-100 px-1 rounded">{`{{themeN_messages}}`}</code> 全発言 / <code className="bg-gray-100 px-1 rounded">{`{{themeN_agent:名前}}`}</code> 特定エージェント（N=テーマ番号, 1始まり）
          </p>
        </div>
        <div>
          <label className="block text-sm font-bold text-gray-700 mb-1">ターン数 <span className="text-gray-400 font-normal text-xs">（1テーマあたり / デフォルトはSettings画面で変更）</span></label>
          <input
            type="number"
            min={1}
            max={50}
            value={turnsPerTheme}
            onChange={e => setTurnsPerTheme(parseInt(e.target.value) || 1)}
            className="w-32 border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-bold text-gray-700 mb-1">プロジェクトフロー <span className="text-gray-400 font-normal text-xs">（テーマ間の進行制御）</span></label>
          <select
            value={projectFlow}
            onChange={e => {
              const v = e.target.value;
              setProjectFlow(v);
              setFlowConfig({});
              saveSessionConfig('project_flow', v).catch(console.error);
              saveSessionConfig('flow_config', '{}').catch(console.error);
            }}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 bg-white"
          >
            {PROJECT_FLOWS.map(f => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>
          <p className="text-xs text-gray-400 mt-1">
            {PROJECT_FLOWS.find(f => f.id === projectFlow)?.description}
          </p>
          {/* フロー固有の設定フィールド */}
          {(() => {
            const flow = PROJECT_FLOWS.find(f => f.id === projectFlow);
            if (!flow || flow.configFields.length === 0) return null;
            return (
              <div className="mt-2 flex flex-wrap gap-3">
                {flow.configFields.map(field => (
                  <div key={field.key} className={`flex gap-2 ${field.type === 'slot_prompts' ? 'w-full items-start' : 'items-center'} ${field.type === 'text' ? 'w-full' : ''}`}>
                    <label className="text-xs text-gray-500 shrink-0">{field.label}:</label>
                    {field.type === 'number' && (
                      <input
                        type="number"
                        min={field.min}
                        max={field.max}
                        value={flowConfig[field.key] ?? field.default}
                        onChange={ev => {
                          const val = parseInt(ev.target.value);
                          const v = isNaN(val) ? field.default : val;
                          const next = { ...flowConfig, [field.key]: v };
                          setFlowConfig(next);
                          saveSessionConfig('flow_config', JSON.stringify(next)).catch(console.error);
                        }}
                        className="w-20 border border-gray-300 rounded-lg px-2 py-1 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                      />
                    )}
                    {field.type === 'text' && (
                      <input
                        type="text"
                        value={flowConfig[field.key] ?? field.default}
                        placeholder={field.placeholder ?? ''}
                        onChange={ev => {
                          const next = { ...flowConfig, [field.key]: ev.target.value };
                          setFlowConfig(next);
                          saveSessionConfig('flow_config', JSON.stringify(next)).catch(console.error);
                        }}
                        className="flex-1 border border-gray-300 rounded-lg px-2 py-1 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                      />
                    )}
                    {field.type === 'slot_prompts' && (() => {
                      const slotPrompts: Record<string, { stance_prompt?: string }> = flowConfig[field.key] ?? {};
                      const availableRoles = field.roles ?? [];
                      if (availableRoles.length === 0) return null;
                      return (
                        <div className="w-full mt-1 space-y-2">
                          {availableRoles.map(role => (
                            <div key={role} className="flex items-start gap-2">
                              <span className="text-xs text-gray-600 w-28 shrink-0 pt-1 font-medium">{role}</span>
                              <textarea
                                value={slotPrompts[role]?.stance_prompt ?? ''}
                                onChange={ev => {
                                  const text = ev.target.value;
                                  const newSlotPrompts = { ...slotPrompts };
                                  if (text.trim()) {
                                    newSlotPrompts[role] = { stance_prompt: text };
                                  } else {
                                    delete newSlotPrompts[role];
                                  }
                                  const next = { ...flowConfig, [field.key]: newSlotPrompts };
                                  setFlowConfig(next);
                                  saveSessionConfig('flow_config', JSON.stringify(next)).catch(console.error);
                                }}
                                placeholder={`${role} の立場・ミッションを記述（省略可）`}
                                rows={2}
                                className="flex-1 border border-gray-300 rounded-lg px-2 py-1 text-xs outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y"
                              />
                            </div>
                          ))}
                        </div>
                      );
                    })()}
                  </div>
                ))}
              </div>
            );
          })()}
          {/* 単一ペルソナ役割の割当（フロー設定にインライン） */}
          {(() => {
            const flow = PROJECT_FLOWS.find(f => f.id === projectFlow);
            const singleRoles = (flow?.flowRoles ?? []).filter(r => !r.multi);
            if (singleRoles.length === 0) return null;
            return (
              <div className="mt-3 space-y-2">
                <p className="text-xs font-medium text-gray-500">役割担当ペルソナ（全テーマ共通）</p>
                {singleRoles.map(role => {
                  // flowConfig に保存: flow_role_defaults = { role_name: persona_id }
                  const defaults: Record<string, string> = flowConfig._role_defaults ?? {};
                  return (
                    <div key={role.name} className="flex items-center gap-2">
                      <label className="text-xs text-gray-500 w-36 shrink-0">{role.name}:</label>
                      <select
                        value={defaults[role.name] ?? ''}
                        onChange={ev => {
                          const pid = ev.target.value;
                          const newDefaults = { ...defaults };
                          if (pid) { newDefaults[role.name] = pid; } else { delete newDefaults[role.name]; }
                          const next = { ...flowConfig, _role_defaults: Object.keys(newDefaults).length > 0 ? newDefaults : undefined };
                          if (!next._role_defaults) delete next._role_defaults;
                          setFlowConfig(next);
                          saveSessionConfig('flow_config', JSON.stringify(next)).catch(console.error);
                        }}
                        className="border border-gray-300 rounded-lg px-2 py-1 text-xs outline-none focus:border-blue-500 bg-white"
                      >
                        <option value="">（自動 / インデックス指定）</option>
                        {personas.filter(p => activePersonaIds.has(p.id)).map(p => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>
      </div>

      {/* テーマ設定セクション（フロー役割タブ統合） */}
      {(() => {
        const flow = PROJECT_FLOWS.find(f => f.id === projectFlow);
        const multiRoles = (flow?.flowRoles ?? []).filter(r => r.multi);
        const hasMultiRoles = multiRoles.length > 0;
        const activeRole = hasMultiRoles
          ? (flowRoleTab && multiRoles.some(r => r.name === flowRoleTab) ? flowRoleTab : multiRoles[0].name)
          : '';
        return (
          <>
            {/* グループ役割タブ（陣営など複数ペルソナの役割のみ） */}
            {hasMultiRoles && (
              <div className="flex border-b border-gray-200 mt-4 mb-0">
                {multiRoles.map(role => (
                  <button
                    key={role.name}
                    onClick={() => setFlowRoleTab(role.name)}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                      activeRole === role.name
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-400 hover:text-gray-600'
                    }`}
                  >
                    {role.name}
                  </button>
                ))}
              </div>
            )}

            {/* テーマカード一覧 */}
            <div className="flex flex-col gap-3 mt-3">
              {themeEntries.map((entry, idx) => {
                // フロー役割タブが有効な場合、このテーマ×役割に割り当てられたペルソナIDリスト
                const rolePersonaIds: string[] = hasMultiRoles ? (entry.flowRoleMap[activeRole] ?? []) : [];
                return (
                  <div key={entry.localId} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
                    {/* テーマ入力行 */}
                    <div className="flex items-start gap-3 mb-3">
                      <span className="text-xs font-bold text-gray-400 uppercase tracking-wide w-16 shrink-0 pt-2">
                        Theme {idx + 1}
                      </span>
                      <textarea
                        ref={element => {
                          themeTextRefs.current[entry.localId] = element;
                        }}
                        value={entry.text}
                        onChange={e => {
                          updateText(entry.localId, e.target.value);
                          resizeTextarea(e.target);
                        }}
                        placeholder="テーマを入力..."
                        rows={3}
                        className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none overflow-hidden"
                      />
                      <button
                        onClick={() => removeTheme(entry.localId)}
                        disabled={themeEntries.length === 1}
                        className="mt-1.5 p-1.5 text-gray-300 hover:text-red-500 disabled:opacity-20 transition-colors"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>

                    {/* ペルソナ選択 */}
                    <div className="flex items-center gap-2 flex-wrap mb-3">
                      {hasMultiRoles ? (
                        /* グループ役割: チップで複数選択 */
                        <>
                          <span className="text-xs text-gray-400">{activeRole}:</span>
                          {personas.filter(p => activePersonaIds.has(p.id) && isActive(entry, p.id)).length === 0 ? (
                            <span className="text-xs text-red-400">ペルソナが選択されていません</span>
                          ) : (
                            personas.filter(p => activePersonaIds.has(p.id) && isActive(entry, p.id)).map(p => {
                              const assigned = rolePersonaIds.includes(p.id);
                              return (
                                <button
                                  key={p.id}
                                  onClick={() => {
                                    setThemeEntries(prev => {
                                      const next = prev.map(t => {
                                        if (t.localId !== entry.localId) return t;
                                        const newMap = { ...t.flowRoleMap };
                                        const current = newMap[activeRole] ?? [];
                                        if (assigned) {
                                          newMap[activeRole] = current.filter(id => id !== p.id);
                                        } else {
                                          newMap[activeRole] = [...current, p.id];
                                        }
                                        if (newMap[activeRole].length === 0) delete newMap[activeRole];
                                        return { ...t, flowRoleMap: newMap };
                                      });
                                      saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                      return next;
                                    });
                                  }}
                                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                                    assigned
                                      ? 'bg-blue-100 border-blue-400 text-blue-700'
                                      : 'bg-gray-100 border-gray-200 text-gray-400'
                                  }`}
                                >
                                  {p.name}
                                </button>
                              );
                            })
                          )}
                        </>
                      ) : (
                        <>
                          <span className="text-xs text-gray-400">参加:</span>
                          {personas.filter(p => activePersonaIds.has(p.id)).length === 0 ? (
                            <span className="text-xs text-red-400">ペルソナが選択されていません</span>
                          ) : (
                            personas.filter(p => activePersonaIds.has(p.id)).map(p => {
                              const active = isActive(entry, p.id);
                              return (
                                <button
                                  key={p.id}
                                  onClick={() => togglePersona(entry.localId, p.id)}
                                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                                    active
                                      ? 'bg-blue-100 border-blue-400 text-blue-700'
                                      : 'bg-gray-100 border-gray-200 text-gray-400 line-through'
                                  }`}
                                >
                                  {p.name}
                                </button>
                              );
                            })
                          )}
                        </>
                      )}
                    </div>

                    {/* テーマ設定タブ */}
                    {(() => {
                      const activeTab = themeTab[entry.localId] ?? 'basic';
                      const tabs = [
                        { id: 'basic', label: '基本設定' },
                        { id: 'strategy', label: 'ストラテジー' },
                        { id: 'order', label: '発言順' },
                      ];
                      return (
                        <>
                          <div className="flex border-b border-gray-200 mb-3 -mx-4 px-4">
                            {tabs.map(tab => (
                              <button
                                key={tab.id}
                                onClick={() => setThemeTab(prev => ({ ...prev, [entry.localId]: tab.id }))}
                                className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
                                  activeTab === tab.id
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-400 hover:text-gray-600'
                                }`}
                              >
                                {tab.label}
                              </button>
                            ))}
                          </div>

                          {/* 基本設定タブ */}
                          {activeTab === 'basic' && (
                            <div>
                              <div className="flex items-start gap-3 mb-3">
                                <span className="text-xs font-bold text-gray-400 uppercase tracking-wide w-16 shrink-0 pt-2">Format</span>
                                <textarea
                                  value={entry.outputFormat}
                                  onChange={e => updateOutputFormat(entry.localId, e.target.value)}
                                  placeholder="出力フォーマットを指定（空=デフォルト）"
                                  rows={2}
                                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y font-mono"
                                />
                              </div>
                              <div className="flex items-start gap-3 mb-3">
                                <span className="text-xs font-bold text-gray-400 uppercase tracking-wide w-16 shrink-0 pt-2">Pre-Info</span>
                                <div className="flex-1">
                                  <textarea
                                    value={entry.preInfo}
                                    onChange={e => updateThemePreInfo(entry.localId, e.target.value)}
                                    placeholder="テーマ固有の事前情報（テンプレート変数使用可）"
                                    rows={2}
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y font-mono"
                                  />
                                  <p className="text-xs text-gray-400 mt-1">
                                    変数: <code className="bg-gray-100 px-1 rounded">{`{{theme1_summary}}`}</code> <code className="bg-gray-100 px-1 rounded">{`{{theme1_messages}}`}</code> <code className="bg-gray-100 px-1 rounded">{`{{theme1_agent:名前}}`}</code> （番号は1始まり）
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-3 mb-3">
                                <span className="text-xs font-bold text-gray-400 uppercase tracking-wide w-16 shrink-0">Turns</span>
                                <input
                                  type="number"
                                  min={1}
                                  max={50}
                                  value={entry.turnsPerTheme ?? ''}
                                  onChange={e => {
                                    const v = e.target.value === '' ? null : parseInt(e.target.value) || 1;
                                    setThemeEntries(prev => {
                                      const next = prev.map(t => t.localId === entry.localId ? { ...t, turnsPerTheme: v } : t);
                                      saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                      return next;
                                    });
                                  }}
                                  placeholder={String(turnsPerTheme)}
                                  className="w-24 border border-gray-300 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                />
                                <span className="text-xs text-gray-400">（空=デフォルト {turnsPerTheme}）</span>
                              </div>
                              {/* タスク割り当てモード */}
                              {allTasks.filter(t => activeTaskIds.has(t.id)).length > 0 && (
                                <div className="mt-3 pt-3 border-t border-gray-100">
                                  <div className="flex items-center gap-3 mb-2">
                                    <span className="text-xs font-bold text-gray-400 uppercase tracking-wide w-16 shrink-0">Task</span>
                                    <select
                                      value={entry.taskAssignment}
                                      onChange={e => {
                                        const mode = e.target.value;
                                        setThemeEntries(prev => {
                                          const next = prev.map(t => t.localId === entry.localId
                                            ? { ...t, taskAssignment: mode, personaTaskMap: mode === 'fixed' ? t.personaTaskMap : {} }
                                            : t
                                          );
                                          saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                          return next;
                                        });
                                      }}
                                      className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm outline-none focus:border-blue-500 bg-white"
                                    >
                                      <option value="">デフォルト（ラウンドロビン）</option>
                                      <option value="random">ランダム</option>
                                      <option value="round_robin">ラウンドロビン</option>
                                      <option value="fixed">固定割り当て</option>
                                    </select>
                                  </div>
                                  {entry.taskAssignment === 'fixed' && (() => {
                                    const activeTasks = allTasks.filter(t => activeTaskIds.has(t.id));
                                    const themePersonas = personas.filter(p =>
                                      activePersonaIds.has(p.id) && isActive(entry, p.id)
                                    );
                                    return (
                                      <div className="ml-2 pl-2 border-l-2 border-gray-100 space-y-1.5">
                                        {themePersonas.map(p => (
                                          <div key={p.id} className="flex items-center gap-2">
                                            <span className="text-xs text-gray-500 w-28 shrink-0 truncate">{p.name}:</span>
                                            <select
                                              value={entry.personaTaskMap[p.id] ?? ''}
                                              onChange={ev => {
                                                const tid = ev.target.value;
                                                setThemeEntries(prev => {
                                                  const next = prev.map(t => {
                                                    if (t.localId !== entry.localId) return t;
                                                    const newMap = { ...t.personaTaskMap };
                                                    if (tid) { newMap[p.id] = tid; } else { delete newMap[p.id]; }
                                                    return { ...t, personaTaskMap: newMap };
                                                  });
                                                  saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                                  return next;
                                                });
                                              }}
                                              className="border border-gray-300 rounded-lg px-2 py-1 text-xs outline-none focus:border-blue-500 bg-white flex-1 min-w-0"
                                            >
                                              <option value="">（ランダム）</option>
                                              {activeTasks.map(t => (
                                                <option key={t.id} value={t.id}>{t.description.substring(0, 40)}{t.description.length > 40 ? '...' : ''}</option>
                                              ))}
                                            </select>
                                          </div>
                                        ))}
                                      </div>
                                    );
                                  })()}
                                </div>
                              )}
                              {/* 単一役割のテーマ個別オーバーライド */}
                              {(() => {
                                const singleRoles = (flow?.flowRoles ?? []).filter(r => !r.multi);
                                if (singleRoles.length === 0) return null;
                                const defaults: Record<string, string> = flowConfig._role_defaults ?? {};
                                const hasOverride = singleRoles.some(r => (entry.flowRoleMap[r.name] ?? []).length > 0);
                                return (
                                  <details className="mt-2 mb-1" open={hasOverride}>
                                    <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 select-none">
                                      役割の個別設定
                                    </summary>
                                    <div className="mt-2 space-y-1.5 pl-2 border-l-2 border-gray-100">
                                      {singleRoles.map(role => {
                                        const overrideIds = entry.flowRoleMap[role.name] ?? [];
                                        const overrideId = overrideIds[0] ?? '';
                                        const defaultPersona = defaults[role.name]
                                          ? personas.find(p => p.id === defaults[role.name])
                                          : null;
                                        return (
                                          <div key={role.name} className="flex items-center gap-2">
                                            <label className="text-xs text-gray-500 w-36 shrink-0">{role.name}:</label>
                                            <select
                                              value={overrideId}
                                              onChange={ev => {
                                                const pid = ev.target.value;
                                                setThemeEntries(prev => {
                                                  const next = prev.map(t => {
                                                    if (t.localId !== entry.localId) return t;
                                                    const newMap = { ...t.flowRoleMap };
                                                    if (pid) {
                                                      newMap[role.name] = [pid];
                                                    } else {
                                                      delete newMap[role.name];
                                                    }
                                                    return { ...t, flowRoleMap: newMap };
                                                  });
                                                  saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                                  return next;
                                                });
                                              }}
                                              className="border border-gray-300 rounded-lg px-2 py-1 text-xs outline-none focus:border-blue-500 bg-white"
                                            >
                                              <option value="">
                                                {defaultPersona
                                                  ? `（共通: ${defaultPersona.name}）`
                                                  : '（共通設定を使用）'}
                                              </option>
                                              {personas.filter(p => activePersonaIds.has(p.id)).map(p => (
                                                <option key={p.id} value={p.id}>{p.name}</option>
                                              ))}
                                            </select>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </details>
                                );
                              })()}
                            </div>
                          )}

                          {/* ストラテジータブ */}
                          {activeTab === 'strategy' && (
                            <div>
                              <select
                                value={entry.themeStrategy || 'sequential'}
                                onChange={e => {
                                  const strategyId = e.target.value;
                                  setThemeEntries(prev => {
                                    const next = prev.map(t => t.localId === entry.localId
                                      ? { ...t, themeStrategy: strategyId, strategyConfig: {} }
                                      : t
                                    );
                                    saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                    return next;
                                  });
                                }}
                                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 bg-white"
                              >
                                {THEME_STRATEGIES.map(s => (
                                  <option key={s.id} value={s.id}>{s.name}</option>
                                ))}
                              </select>
                              <p className="text-xs text-gray-400 mt-1 mb-2">
                                {THEME_STRATEGIES.find(s => s.id === (entry.themeStrategy || 'sequential'))?.description}
                              </p>
                              {(() => {
                                const strategy = THEME_STRATEGIES.find(s => s.id === (entry.themeStrategy || 'sequential'));
                                if (!strategy || strategy.configFields.length === 0) return null;
                                return (
                                  <div className="flex flex-wrap gap-3">
                                    {strategy.configFields.map(field => (
                                      <div key={field.key} className={`flex gap-2 ${field.type === 'slot_prompts' || field.type === 'role_map' ? 'w-full items-start' : 'items-center'} ${field.type === 'text' ? 'w-full' : ''}`}>
                                        <label className="text-xs text-gray-500 shrink-0">{field.label}:</label>
                                        {field.type === 'number' && (
                                          <input
                                            type="number"
                                            min={field.min}
                                            max={field.max}
                                            value={entry.strategyConfig[field.key] ?? field.default}
                                            onChange={ev => {
                                              const val = parseInt(ev.target.value);
                                              const v = isNaN(val) ? field.default : val;
                                              setThemeEntries(prev => {
                                                const next = prev.map(t => t.localId === entry.localId
                                                  ? { ...t, strategyConfig: { ...t.strategyConfig, [field.key]: v } }
                                                  : t
                                                );
                                                saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                                return next;
                                              });
                                            }}
                                            className="w-20 border border-gray-300 rounded-lg px-2 py-1 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                          />
                                        )}
                                        {field.type === 'text' && (
                                          <input
                                            type="text"
                                            value={entry.strategyConfig[field.key] ?? field.default}
                                            placeholder={field.placeholder ?? ''}
                                            onChange={ev => {
                                              const val = ev.target.value;
                                              setThemeEntries(prev => {
                                                const next = prev.map(t => t.localId === entry.localId
                                                  ? { ...t, strategyConfig: { ...t.strategyConfig, [field.key]: val } }
                                                  : t
                                                );
                                                saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                                return next;
                                              });
                                            }}
                                            className="flex-1 border border-gray-300 rounded-lg px-2 py-1 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                          />
                                        )}
                                        {field.type === 'role_map' && (() => {
                                          const roleMap: Record<string, string> = entry.strategyConfig[field.key] ?? {};
                                          const availableRoles = field.roles ?? [];
                                          const themePersonas = personas.filter(p =>
                                            activePersonaIds.has(p.id) && isActive(entry, p.id)
                                          );
                                          if (themePersonas.length === 0) return null;
                                          return (
                                            <div className="w-full mt-1 space-y-1">
                                              {themePersonas.map(p => (
                                                <div key={p.id} className="flex items-center gap-2">
                                                  <span className="text-xs text-gray-600 w-32 truncate" title={p.name}>{p.name}</span>
                                                  <select
                                                    value={roleMap[p.id] ?? ''}
                                                    onChange={ev => {
                                                      const role = ev.target.value;
                                                      setThemeEntries(prev => {
                                                        const next = prev.map(t => {
                                                          if (t.localId !== entry.localId) return t;
                                                          const newRoleMap = { ...roleMap };
                                                          if (role) { newRoleMap[p.id] = role; } else { delete newRoleMap[p.id]; }
                                                          return { ...t, strategyConfig: { ...t.strategyConfig, [field.key]: newRoleMap } };
                                                        });
                                                        saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                                        return next;
                                                      });
                                                    }}
                                                    className="border border-gray-300 rounded px-2 py-0.5 text-xs outline-none focus:border-blue-500 bg-white"
                                                  >
                                                    <option value="">（自動）</option>
                                                    {availableRoles.map(r => (<option key={r} value={r}>{r}</option>))}
                                                  </select>
                                                </div>
                                              ))}
                                            </div>
                                          );
                                        })()}
                                        {field.type === 'slot_prompts' && (() => {
                                          const slotPrompts: Record<string, { stance_prompt?: string }> = entry.strategyConfig[field.key] ?? {};
                                          const availableRoles = field.roles ?? [];
                                          if (availableRoles.length === 0) return null;
                                          return (
                                            <div className="w-full mt-1 space-y-2">
                                              {availableRoles.map(role => (
                                                <div key={role} className="flex items-start gap-2">
                                                  <span className="text-xs text-gray-600 w-24 shrink-0 pt-1 font-medium">{role}</span>
                                                  <textarea
                                                    value={slotPrompts[role]?.stance_prompt ?? ''}
                                                    onChange={ev => {
                                                      const text = ev.target.value;
                                                      setThemeEntries(prev => {
                                                        const next = prev.map(t => {
                                                          if (t.localId !== entry.localId) return t;
                                                          const newSlotPrompts = { ...slotPrompts };
                                                          if (text.trim()) { newSlotPrompts[role] = { stance_prompt: text }; } else { delete newSlotPrompts[role]; }
                                                          return { ...t, strategyConfig: { ...t.strategyConfig, [field.key]: newSlotPrompts } };
                                                        });
                                                        saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                                        return next;
                                                      });
                                                    }}
                                                    placeholder={`${role} の立場・ミッションを記述（省略可）`}
                                                    rows={2}
                                                    className="flex-1 border border-gray-300 rounded-lg px-2 py-1 text-xs outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y"
                                                  />
                                                </div>
                                              ))}
                                            </div>
                                          );
                                        })()}
                                      </div>
                                    ))}
                                  </div>
                                );
                              })()}
                            </div>
                          )}

                          {/* 発言順タブ */}
                          {activeTab === 'order' && (
                            <div>
                              <label className="flex items-center gap-2 cursor-pointer mb-2">
                                <input
                                  type="checkbox"
                                  checked={entry.useCustomOrder}
                                  onChange={e => {
                                    const enabled = e.target.checked;
                                    setThemeEntries(prev => {
                                      const next = prev.map(t => {
                                        if (t.localId !== entry.localId) return t;
                                        const initOrder = enabled && t.personaOrder.length === 0
                                          ? personas
                                              .filter(p => activePersonaIds.has(p.id) && isActive(t, p.id))
                                              .map(p => p.id)
                                          : t.personaOrder;
                                        return { ...t, useCustomOrder: enabled, personaOrder: initOrder };
                                      });
                                      saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                      return next;
                                    });
                                  }}
                                  className="w-3.5 h-3.5 accent-blue-600"
                                />
                                <span className="text-xs text-gray-600">カスタム順を使用</span>
                              </label>
                              {entry.useCustomOrder && (
                                <div className="flex flex-col gap-1">
                                  {entry.personaOrder
                                    .map(pid => personas.find(p => p.id === pid))
                                    .filter((p): p is typeof personas[0] => p !== undefined)
                                    .map((p, i, arr) => (
                                      <div key={p.id} className="flex items-center gap-2">
                                        <span className="text-xs text-gray-400 w-5 text-right">{i + 1}.</span>
                                        <span className="text-xs font-medium text-gray-700 flex-1 bg-gray-50 border border-gray-200 rounded px-2 py-1">
                                          {p.name}
                                        </span>
                                        <button
                                          disabled={i === 0}
                                          onClick={() => {
                                            setThemeEntries(prev => {
                                              const next = prev.map(t => {
                                                if (t.localId !== entry.localId) return t;
                                                const order = [...t.personaOrder];
                                                [order[i - 1], order[i]] = [order[i], order[i - 1]];
                                                return { ...t, personaOrder: order };
                                              });
                                              saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                              return next;
                                            });
                                          }}
                                          className="p-1 text-gray-400 hover:text-blue-600 disabled:opacity-20 transition-colors"
                                        >
                                          <ArrowUp size={12} />
                                        </button>
                                        <button
                                          disabled={i === arr.length - 1}
                                          onClick={() => {
                                            setThemeEntries(prev => {
                                              const next = prev.map(t => {
                                                if (t.localId !== entry.localId) return t;
                                                const order = [...t.personaOrder];
                                                [order[i], order[i + 1]] = [order[i + 1], order[i]];
                                                return { ...t, personaOrder: order };
                                              });
                                              saveThemeEntries(next.map(uiToDb)).catch(console.error);
                                              return next;
                                            });
                                          }}
                                          className="p-1 text-gray-400 hover:text-blue-600 disabled:opacity-20 transition-colors"
                                        >
                                          <ArrowDown size={12} />
                                        </button>
                                      </div>
                                    ))}
                                  {entry.personaOrder.length === 0 && (
                                    <p className="text-xs text-gray-400 mt-1">ペルソナが選択されていません</p>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                );
              })}
            </div>

            <button
              onClick={addTheme}
              className="mt-3 flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium self-start transition-colors"
            >
              <Plus size={15} /> テーマを追加
            </button>
          </>
        );
      })()}

      {/* ペルソナプリセット選択 */}
      <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-3">
          <Users size={16} className="text-blue-600" />
          <h2 className="text-lg font-bold text-gray-800">ペルソナプリセット</h2>
        </div>
        {personaPresets.length === 0 ? (
          <p className="text-sm text-gray-500">Personas画面でプリセットを作成してください。</p>
        ) : (
          <>
            <select
              value={selectedPersonaPresetId}
              onChange={e => loadPersonaPreset(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 bg-white mb-3"
            >
              <option value="">-- 全ペルソナを使用 --</option>
              {personaPresets.map(pp => (
                <option key={pp.id} value={pp.id}>{pp.name}</option>
              ))}
            </select>
            <div className="flex flex-wrap gap-1.5">
              {personas.map(p => (
                <span
                  key={p.id}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                    activePersonaIds.has(p.id)
                      ? 'bg-blue-100 border-blue-400 text-blue-700'
                      : 'bg-gray-100 border-gray-200 text-gray-300'
                  }`}
                >
                  {p.name}
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      {/* タスクプリセット選択 */}
      <div className="mt-4 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-3">
          <ListTodo size={16} className="text-purple-600" />
          <h2 className="text-lg font-bold text-gray-800">タスクプリセット</h2>
        </div>
        {taskPresets.length === 0 ? (
          <p className="text-sm text-gray-500">Tasks画面でプリセットを作成してください。</p>
        ) : (
          <>
            <select
              value={selectedTaskPresetId}
              onChange={e => loadTaskPreset(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 bg-white mb-3"
            >
              <option value="">-- 全タスクを使用 --</option>
              {taskPresets.map(tp => (
                <option key={tp.id} value={tp.id}>{tp.name}</option>
              ))}
            </select>
            <div className="flex flex-wrap gap-1.5">
              {allTasks.map(t => (
                <span
                  key={t.id}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                    activeTaskIds.has(t.id)
                      ? 'bg-purple-100 border-purple-400 text-purple-700'
                      : 'bg-gray-100 border-gray-200 text-gray-300'
                  }`}
                >
                  {t.description.length > 30 ? t.description.substring(0, 30) + '...' : t.description}
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      {error && (
        <div className="mt-6 bg-red-50 text-red-700 p-4 rounded-lg border border-red-200">
          <span className="font-medium">{error}</span>
        </div>
      )}

      <div className="mt-8 flex justify-end">
        <button
          onClick={handleStart}
          disabled={isStarting || activePersonaIds.size === 0}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-md transition-all transform hover:scale-[1.02]"
        >
          <Play size={24} />
          {isStarting ? 'Starting...' : 'Start Discussion'}
        </button>
      </div>
    </div>
  );
}
