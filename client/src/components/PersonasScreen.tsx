import { useState, useEffect } from 'react';
import { Persona } from '../types/api';
import { getPersonas, addPersona, updatePersona, deletePersona } from '../lib/db';
import { Plus, Trash2, Edit2, Save, X } from 'lucide-react';

export default function PersonasScreen() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<Persona>>({});
  
  const [isCreating, setIsCreating] = useState(false);
  const [createForm, setCreateForm] = useState<Partial<Persona>>({ name: '', role: '' });

  const loadPersonas = async () => {
    try {
      const data = await getPersonas();
      setPersonas(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadPersonas();
  }, []);

  const handleCreate = async () => {
    if (!createForm.name || !createForm.role) return;
    const newPersona: Persona = {
      id: crypto.randomUUID(),
      name: createForm.name,
      role: createForm.role
    };
    await addPersona(newPersona);
    setIsCreating(false);
    setCreateForm({ name: '', role: '' });
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
            <input 
              placeholder="Role (e.g., Senior Software Engineer focused on code quality)"
              value={createForm.role}
              onChange={e => setCreateForm({...createForm, role: e.target.value})}
              className="w-full border border-gray-300 rounded-lg p-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
            <div className="flex gap-3 justify-end mt-2">
              <button onClick={() => setIsCreating(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors">Cancel</button>
              <button onClick={handleCreate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors">Save</button>
            </div>
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
                <input 
                  value={editForm.role}
                  onChange={e => setEditForm({...editForm, role: e.target.value})}
                  className="w-full border border-gray-300 rounded-lg p-2"
                />
                <div className="flex justify-end gap-2 mt-2">
                  <button onClick={() => setEditingId(null)} className="flex items-center gap-1 text-gray-600 hover:bg-gray-100 px-3 py-1 rounded-md"><X size={16}/> Cancel</button>
                  <button onClick={handleUpdate} className="flex items-center gap-1 text-blue-600 hover:bg-blue-50 px-3 py-1 rounded-md mb-0"><Save size={16}/> Save</button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">{p.name}</h3>
                    <p className="text-sm font-medium text-blue-600 mt-1">{p.role}</p>
                  </div>
                  <div className="flex gap-2">
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
