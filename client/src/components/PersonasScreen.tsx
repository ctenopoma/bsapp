import { useState, useEffect, useRef } from 'react';
import { Persona, AvailableRagType, RagConfig } from '../types/api';
import { getPersonas, addPersona, updatePersona, deletePersona } from '../lib/db';
import { apiGetRagTypes, apiGetSettings, apiSaveSettings } from '../lib/api';
import { Plus, Trash2, Edit2, Save, X, FileText } from 'lucide-react';

const SELECT_CLS = "w-full border border-gray-300 rounded-lg p-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 bg-white";
const INPUT_CLS = "w-full border border-gray-300 rounded-lg p-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500";

function RagSection({
  ragConfig,
  onChange,
  availableTypes,
  typesLoaded,
}: {
  ragConfig: RagConfig | undefined;
  onChange: (cfg: RagConfig | undefined) => void;
  availableTypes: AvailableRagType[];
  typesLoaded: boolean;
}) {
  const selectedType = ragConfig?.rag_type ?? '';

  const handleTypeChange = (typeId: string) => {
    if (!typeId) {
      onChange(undefined);
    } else {
      onChange({ enabled: true, rag_type: typeId, tag: ragConfig?.tag ?? '' });
    }
  };

  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-gray-50 flex flex-col gap-2">
      <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide">RAG設定</label>
      <select
        value={selectedType}
        onChange={e => handleTypeChange(e.target.value)}
        className={SELECT_CLS}
      >
        <option value="">RAGなし</option>
        {availableTypes.map(t => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
        {!typesLoaded && <option disabled value="">（ホスト未接続 - 選択不可）</option>}
        {typesLoaded && availableTypes.length === 0 && <option disabled value="">（RAG種別未設定）</option>}
      </select>
      {selectedType && (
        <input
          placeholder="RAGコレクションのタグ名"
          value={ragConfig?.tag ?? ''}
          onChange={e => onChange({ enabled: true, rag_type: selectedType, tag: e.target.value })}
          className={INPUT_CLS}
        />
      )}
    </div>
  );
}

export default function PersonasScreen() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<Persona>>({});
  const createRoleRef = useRef<HTMLTextAreaElement | null>(null);
  const editRoleRef = useRef<HTMLTextAreaElement | null>(null);
  const [availableRagTypes, setAvailableRagTypes] = useState<AvailableRagType[]>([]);
  const [ragTypesLoaded, setRagTypesLoaded] = useState(false);

  const [isCreating, setIsCreating] = useState(false);
  const [createForm, setCreateForm] = useState<Partial<Persona>>({ name: '', role: '', pre_info: '' });

  // 要約エージェント
  const [summaryPrompt, setSummaryPrompt] = useState('');
  const [summaryPromptLoaded, setSummaryPromptLoaded] = useState(false);
  const [summaryPromptSaving, setSummaryPromptSaving] = useState(false);
  const [summaryPromptSaved, setSummaryPromptSaved] = useState(false);

  const resizeTextarea = (element: HTMLTextAreaElement | null) => {
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${element.scrollHeight}px`;
  };

  const loadPersonas = async () => {
    try {
      const data = await getPersonas();
      setPersonas(data);
    } catch (e) {
      console.error(e);
    }
  };

  const loadRagTypes = async () => {
    try {
      const res = await apiGetRagTypes();
      setAvailableRagTypes(res.types);
      setRagTypesLoaded(true);
    } catch {
      // ホスト未接続でも graceful に動作する
    }
  };

  const loadSummaryPrompt = async () => {
    try {
      const settings = await apiGetSettings();
      setSummaryPrompt(settings.summary_prompt_template);
      setSummaryPromptLoaded(true);
    } catch {
      // ホスト未接続の場合は非表示のまま
    }
  };

  const handleSaveSummaryPrompt = async () => {
    setSummaryPromptSaving(true);
    try {
      const settings = await apiGetSettings();
      await apiSaveSettings({ ...settings, summary_prompt_template: summaryPrompt });
      setSummaryPromptSaved(true);
      setTimeout(() => setSummaryPromptSaved(false), 2000);
    } catch (e) {
      console.error(e);
    } finally {
      setSummaryPromptSaving(false);
    }
  };

  useEffect(() => {
    loadPersonas();
    loadRagTypes();
    loadSummaryPrompt();
  }, []);

  useEffect(() => {
    resizeTextarea(createRoleRef.current);
    resizeTextarea(editRoleRef.current);
  }, [createForm.role, editForm.role, isCreating, editingId]);

  const handleCreate = async () => {
    if (!createForm.name || !createForm.role) return;
    const newPersona: Persona = {
      id: crypto.randomUUID(),
      name: createForm.name,
      role: createForm.role,
      pre_info: createForm.pre_info ?? '',
      rag_config: createForm.rag_config,
    };
    await addPersona(newPersona);
    setIsCreating(false);
    setCreateForm({ name: '', role: '', pre_info: '' });
    loadPersonas();
  };

  const handleUpdate = async () => {
    if (!editForm.id || !editForm.name || !editForm.role) return;
    await updatePersona(editForm as Persona);
    setEditingId(null);
    loadPersonas();
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this Persona?')) {
      await deletePersona(id);
      loadPersonas();
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Manage Personas</h1>
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium shadow-sm transition-colors"
        >
          <Plus size={18} />
          New Persona
        </button>
      </div>

      {isCreating && (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
          <h2 className="text-lg font-semibold mb-4">Create New Persona</h2>
          <div className="grid gap-4">
            <input
              placeholder="Name (e.g., Critic Engineer)"
              value={createForm.name}
              onChange={e => setCreateForm({...createForm, name: e.target.value})}
              className="w-full border border-gray-300 rounded-lg p-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
            <textarea
              ref={createRoleRef}
              placeholder="Role (e.g., Senior Software Engineer focused on code quality)"
              value={createForm.role}
              onChange={e => {
                setCreateForm({...createForm, role: e.target.value});
                resizeTextarea(e.target);
              }}
              rows={4}
              className="w-full border border-gray-300 rounded-lg p-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-none overflow-hidden"
            />
            <textarea
              placeholder="事前情報（このペルソナのみに与える背景情報・知識・資料）"
              value={createForm.pre_info}
              onChange={e => setCreateForm({...createForm, pre_info: e.target.value})}
              rows={3}
              className="w-full border border-gray-300 rounded-lg p-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-y font-mono text-sm"
            />
            <RagSection
              ragConfig={createForm.rag_config}
              onChange={cfg => setCreateForm({...createForm, rag_config: cfg})}
              availableTypes={availableRagTypes}
              typesLoaded={ragTypesLoaded}
            />
            <div className="flex gap-3 justify-end mt-2">
              <button onClick={() => setIsCreating(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors">Cancel</button>
              <button onClick={handleCreate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors">Save</button>
            </div>
          </div>
        </div>
      )}

      {/* 要約エージェント */}
      {summaryPromptLoaded && (
        <div className="bg-white rounded-xl shadow-sm border border-amber-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <FileText size={18} className="text-amber-600" />
            <h2 className="text-lg font-bold text-gray-900">要約エージェント</h2>
            <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-0.5">固定</span>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            各テーマの議論終了後に要約を生成するエージェントのプロンプトです。
            使用可能な変数: <code className="bg-gray-100 px-1 rounded">{'{theme}'}</code>、
            <code className="bg-gray-100 px-1 rounded">{'{history}'}</code>、
            <code className="bg-gray-100 px-1 rounded">{'{output_format}'}</code>
          </p>
          <textarea
            value={summaryPrompt}
            onChange={e => setSummaryPrompt(e.target.value)}
            rows={8}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 resize-y font-mono"
          />
          <div className="flex justify-end mt-3">
            <button
              onClick={handleSaveSummaryPrompt}
              disabled={summaryPromptSaving}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                summaryPromptSaved
                  ? 'bg-green-600 text-white'
                  : 'bg-amber-600 hover:bg-amber-700 text-white disabled:bg-amber-400'
              }`}
            >
              <Save size={15} />
              {summaryPromptSaved ? '保存しました' : summaryPromptSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        {personas.map(p => (
          <div key={p.id} className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex flex-col gap-3 transition-shadow hover:shadow-md">
            {editingId === p.id ? (
              <div className="grid gap-3">
                <input
                  value={editForm.name}
                  onChange={e => setEditForm({...editForm, name: e.target.value})}
                  className="w-full border border-gray-300 rounded-lg p-2"
                />
                <textarea
                  ref={editRoleRef}
                  value={editForm.role}
                  onChange={e => {
                    setEditForm({...editForm, role: e.target.value});
                    resizeTextarea(e.target);
                  }}
                  rows={4}
                  className="w-full border border-gray-300 rounded-lg p-2 resize-none overflow-hidden"
                />
                <textarea
                  value={editForm.pre_info ?? ''}
                  onChange={e => setEditForm({...editForm, pre_info: e.target.value})}
                  placeholder="事前情報（このペルソナのみに与える背景情報・知識・資料）"
                  rows={3}
                  className="w-full border border-gray-300 rounded-lg p-2 resize-y font-mono text-sm"
                />
                <RagSection
                  ragConfig={editForm.rag_config}
                  onChange={cfg => setEditForm({...editForm, rag_config: cfg})}
                  availableTypes={availableRagTypes}
                  typesLoaded={ragTypesLoaded}
                />
                <div className="flex justify-end gap-2 mt-2">
                  <button onClick={() => setEditingId(null)} className="flex items-center gap-1 text-gray-600 hover:bg-gray-100 px-3 py-1 rounded-md"><X size={16}/> Cancel</button>
                  <button onClick={handleUpdate} className="flex items-center gap-1 text-blue-600 hover:bg-blue-50 px-3 py-1 rounded-md mb-0"><Save size={16}/> Save</button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-xl font-bold text-gray-900">{p.name}</h3>
                    <p className="text-sm font-medium text-blue-600 mt-1">{p.role}</p>
                    {p.pre_info && (
                      <p className="text-xs text-gray-500 mt-2 font-mono whitespace-pre-wrap bg-gray-50 rounded-lg p-2 border border-gray-100">{p.pre_info}</p>
                    )}
                    {p.rag_config?.enabled && p.rag_config.rag_type && (
                      <div className="mt-2 inline-flex items-center gap-1 text-xs text-purple-700 bg-purple-50 border border-purple-200 rounded px-2 py-1">
                        <span className="font-semibold">RAG:</span>
                        <span>{availableRagTypes.find(t => t.id === p.rag_config!.rag_type)?.name ?? p.rag_config.rag_type}</span>
                        {p.rag_config.tag && <span className="text-purple-500">[{p.rag_config.tag}]</span>}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2 ml-4 shrink-0">
                    <button onClick={() => { setEditingId(p.id); setEditForm(p); }} className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"><Edit2 size={18}/></button>
                    <button onClick={() => handleDelete(p.id)} className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"><Trash2 size={18}/></button>
                  </div>
                </div>
              </>
            )}
          </div>
        ))}
        {personas.length === 0 && !isCreating && (
          <div className="text-center py-16 text-gray-500 border-2 border-dashed border-gray-200 rounded-xl">
            No personas created yet. Click "New Persona" to start.
          </div>
        )}
      </div>
    </div>
  );
}
