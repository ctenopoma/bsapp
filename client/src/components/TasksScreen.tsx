import { useState, useEffect } from 'react';
import { TaskModel } from '../types/api';
import { getTasks, addTask, updateTask, deleteTask, getTaskPresets, createTaskPreset, updateTaskPreset, deleteTaskPreset, TaskPresetData } from '../lib/server-db';
import { Plus, Trash2, Edit2, Save, X, FolderOpen } from 'lucide-react';

export default function TasksScreen() {
  const [tasks, setTasks] = useState<TaskModel[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<TaskModel>>({});

  const [isCreating, setIsCreating] = useState(false);
  const [createForm, setCreateForm] = useState<Partial<TaskModel>>({ description: '' });

  // プリセット管理
  const [taskPresets, setTaskPresets] = useState<TaskPresetData[]>([]);
  const [presetName, setPresetName] = useState('');
  const [presetSelectedIds, setPresetSelectedIds] = useState<Set<string>>(new Set());
  const [editingPresetId, setEditingPresetId] = useState<string | null>(null);
  const [showPresetForm, setShowPresetForm] = useState(false);

  const loadTasks = async () => {
    try {
      const data = await getTasks();
      setTasks(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadTasks();
    getTaskPresets().then(setTaskPresets).catch(console.error);
  }, []);

  const handleCreate = async () => {
    if (!createForm.description) return;
    const newTask: TaskModel = {
      id: crypto.randomUUID(),
      description: createForm.description
    };
    await addTask(newTask);
    setIsCreating(false);
    setCreateForm({ description: '' });
    loadTasks();
  };

  const handleUpdate = async () => {
    if (!editForm.id || !editForm.description) return;
    await updateTask(editForm as TaskModel);
    setEditingId(null);
    loadTasks();
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this Task?')) {
      await deleteTask(id);
      loadTasks();
    }
  };

  const openPresetForm = (preset?: TaskPresetData) => {
    if (preset) {
      setEditingPresetId(preset.id);
      setPresetName(preset.name);
      setPresetSelectedIds(new Set(preset.task_ids.split(',').filter(Boolean)));
    } else {
      setEditingPresetId(null);
      setPresetName('');
      setPresetSelectedIds(new Set(tasks.map(t => t.id)));
    }
    setShowPresetForm(true);
  };

  const handleSavePreset = async () => {
    if (!presetName.trim()) return;
    const data: TaskPresetData = {
      id: editingPresetId || crypto.randomUUID(),
      name: presetName.trim(),
      task_ids: [...presetSelectedIds].join(','),
    };
    try {
      if (editingPresetId) {
        await updateTaskPreset(data);
        setTaskPresets(prev => prev.map(p => p.id === data.id ? data : p));
      } else {
        await createTaskPreset(data);
        setTaskPresets(prev => [...prev, data]);
      }
      setShowPresetForm(false);
    } catch (e: any) {
      console.error(e);
    }
  };

  const handleDeletePreset = async (id: string) => {
    const preset = taskPresets.find(p => p.id === id);
    if (!preset || !confirm(`プリセット「${preset.name}」を削除しますか？`)) return;
    await deleteTaskPreset(id);
    setTaskPresets(prev => prev.filter(p => p.id !== id));
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Manage Tasks</h1>
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium shadow-sm transition-colors"
        >
          <Plus size={18} />
          New Task
        </button>
      </div>

      {/* タスクプリセット */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <FolderOpen size={16} className="text-purple-600" />
          <h2 className="text-lg font-bold text-gray-900">タスクプリセット</h2>
          <span className="text-xs text-gray-400">（タスクのセットを保存してNew Sessionで選択）</span>
        </div>
        {taskPresets.length === 0 && !showPresetForm && (
          <p className="text-sm text-gray-500 mb-3">プリセットはまだありません。</p>
        )}
        {taskPresets.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {taskPresets.map(tp => {
              const ids = tp.task_ids.split(',').filter(Boolean);
              return (
                <div key={tp.id} className="flex items-center gap-1 bg-purple-50 border border-purple-200 rounded-lg px-3 py-1.5">
                  <span className="text-sm font-medium text-purple-800">{tp.name}</span>
                  <span className="text-xs text-purple-500 ml-1">({ids.length}件)</span>
                  <button onClick={() => openPresetForm(tp)} className="ml-1 p-0.5 text-purple-400 hover:text-purple-600"><Edit2 size={13} /></button>
                  <button onClick={() => handleDeletePreset(tp.id)} className="p-0.5 text-purple-400 hover:text-red-500"><Trash2 size={13} /></button>
                </div>
              );
            })}
          </div>
        )}
        {showPresetForm ? (
          <div className="border border-purple-200 rounded-lg p-4 bg-purple-50/50">
            <input
              type="text"
              value={presetName}
              onChange={e => setPresetName(e.target.value)}
              placeholder="プリセット名..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 mb-3"
              autoFocus
            />
            <p className="text-xs text-gray-500 mb-2">含めるタスクを選択:</p>
            <div className="flex flex-wrap gap-2 mb-3">
              {tasks.map(t => (
                <button
                  key={t.id}
                  onClick={() => setPresetSelectedIds(prev => {
                    const next = new Set(prev);
                    if (next.has(t.id)) next.delete(t.id); else next.add(t.id);
                    return next;
                  })}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                    presetSelectedIds.has(t.id)
                      ? 'bg-purple-100 border-purple-400 text-purple-700'
                      : 'bg-gray-100 border-gray-200 text-gray-400'
                  }`}
                >
                  {t.description.length > 40 ? t.description.substring(0, 40) + '...' : t.description}
                </button>
              ))}
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowPresetForm(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">キャンセル</button>
              <button onClick={handleSavePreset} disabled={!presetName.trim() || presetSelectedIds.size === 0}
                className="px-3 py-1.5 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 rounded-lg">保存</button>
            </div>
          </div>
        ) : (
          <button onClick={() => openPresetForm()} className="flex items-center gap-1.5 text-sm text-purple-600 hover:text-purple-800 font-medium">
            <Plus size={15} /> 新規プリセット
          </button>
        )}
      </div>

      {isCreating && (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
          <h2 className="text-lg font-semibold mb-4">Create New Task</h2>
          <div className="grid gap-4">
            <textarea
              placeholder="Task Description (e.g., Please critique the code style and find any logical bugs...)"
              value={createForm.description}
              onChange={e => setCreateForm({...createForm, description: e.target.value})}
              rows={3}
              className="w-full border border-gray-300 rounded-lg p-3 outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all resize-none"
            />
            <div className="flex gap-3 justify-end mt-2">
              <button onClick={() => setIsCreating(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors">Cancel</button>
              <button onClick={handleCreate} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors">Save</button>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        {tasks.map(t => (
          <div key={t.id} className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex flex-col gap-3 transition-shadow hover:shadow-md">
            {editingId === t.id ? (
              <div className="grid gap-3">
                <textarea
                  value={editForm.description}
                  onChange={e => setEditForm({...editForm, description: e.target.value})}
                  className="w-full border border-gray-300 rounded-lg p-2 resize-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none"
                  rows={3}
                />
                <div className="flex justify-end gap-2 mt-2">
                  <button onClick={() => setEditingId(null)} className="flex items-center gap-1 text-gray-600 hover:bg-gray-100 px-3 py-1 rounded-md"><X size={16}/> Cancel</button>
                  <button onClick={handleUpdate} className="flex items-center gap-1 text-purple-600 hover:bg-purple-50 px-3 py-1 rounded-md mb-0"><Save size={16}/> Save</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between items-start gap-4">
                <p className="text-gray-800 flex-1 whitespace-pre-wrap">{t.description}</p>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => { setEditingId(t.id); setEditForm(t); }} className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"><Edit2 size={18}/></button>
                  <button onClick={() => handleDelete(t.id)} className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"><Trash2 size={18}/></button>
                </div>
              </div>
            )}
          </div>
        ))}
        {tasks.length === 0 && !isCreating && (
          <div className="text-center py-16 text-gray-500 border-2 border-dashed border-gray-200 rounded-xl">
            No tasks created yet. Click "New Task" to start.
          </div>
        )}
      </div>
    </div>
  );
}
