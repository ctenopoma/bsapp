import { useState } from 'react';
import { apiInitRag, apiAddRag, apiGetRagStatus } from '../lib/api';
import { Database, UploadCloud, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';

export default function RagScreen() {
  const [tag, setTag] = useState('');
  const [text, setText] = useState('');
  const [status, setStatus] = useState<'idle' | 'initializing' | 'processing' | 'completed' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const handleInit = async () => {
    if (!tag) return;
    try {
      setStatus('initializing');
      setMessage('Deleting and recreating collection...');
      await apiInitRag({ tag });
      setStatus('idle');
      setMessage(`Collection '${tag}' initialized successfully.`);
    } catch (e: any) {
      setStatus('error');
      setMessage(e.message || 'Failed to initialize collection.');
    }
  };

  const handleAddData = async () => {
    if (!tag || !text) return;
    try {
      setStatus('processing');
      setMessage('Sending data to host...');
      const res = await apiAddRag({ tag, text });
      
      const poll = setInterval(async () => {
        try {
          const statusRes = await apiGetRagStatus(res.job_id);
          if (statusRes.status === 'completed') {
            clearInterval(poll);
            setStatus('completed');
            setMessage('Data vectorized and stored successfully!');
            setText('');
          } else if (statusRes.status === 'error') {
            clearInterval(poll);
            setStatus('error');
            setMessage(`Error during processing: ${statusRes.error_msg}`);
          }
        } catch (e) {
          clearInterval(poll);
          setStatus('error');
          setMessage('Failed to poll status.');
        }
      }, 2000);
      
    } catch (e: any) {
      setStatus('error');
      setMessage(e.message || 'Failed to start vectorization job.');
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto flex flex-col h-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-2">
          <Database className="text-blue-600" />
          RAG Knowledge Base
        </h1>
        <p className="text-gray-600 mt-2">Manage vector embeddings for discussion contexts. Tags allow specific themes to have custom contexts.</p>
      </div>

      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6 flex-shrink-0">
        <h2 className="text-lg font-semibold mb-4 text-gray-800">1. Target Tag (Collection)</h2>
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Tag Name</label>
            <input 
              placeholder="e.g. 'Project Alpha Specs'"
              value={tag}
              onChange={e => setTag(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono text-sm"
            />
          </div>
          <button 
            onClick={handleInit}
            disabled={!tag || status === 'initializing' || status === 'processing'}
            className="flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-700 px-4 py-3 rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            <RefreshCw size={18} className={status === 'initializing' ? 'animate-spin' : ''} />
            Initialize (Clear Data)
          </button>
        </div>
      </div>

      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex flex-col flex-1 min-h-[400px]">
        <h2 className="text-lg font-semibold mb-4 text-gray-800">2. Add Knowledge</h2>
        <textarea 
          placeholder="Paste context document here to be chunked and vectorized..."
          value={text}
          onChange={e => setText(e.target.value)}
          className="w-full flex-1 border border-gray-300 rounded-lg p-4 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-none mb-4"
        />
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            {status === 'processing' && <span className="flex items-center gap-2 text-blue-600 font-medium whitespace-pre-wrap"><RefreshCw className="animate-spin" size={18}/> {message}</span>}
            {status === 'completed' && <span className="flex items-center gap-2 text-green-600 font-medium whitespace-pre-wrap"><CheckCircle2 size={18}/> {message}</span>}
            {status === 'error' && <span className="flex items-center gap-2 text-red-600 font-medium whitespace-pre-wrap"><AlertCircle size={18}/> {message}</span>}
            {(status === 'idle' || status === 'initializing') && message && <span className="text-gray-600 whitespace-pre-wrap">{message}</span>}
          </div>

          <button 
            onClick={handleAddData}
            disabled={!tag || !text || status === 'processing' || status === 'initializing'}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium shadow-sm transition-colors disabled:opacity-50"
          >
            <UploadCloud size={20} />
            Vectorize & Store
          </button>
        </div>
      </div>
    </div>
  );
}
