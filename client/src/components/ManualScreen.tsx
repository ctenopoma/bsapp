import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BookOpen, ChevronRight } from 'lucide-react';

// マニュアルファイルを一括インポート
const manualFiles = import.meta.glob<string>('../manual/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
});

// ページ定義（順序・タイトル・ファイルパスを管理）
const PAGES = [
  { id: 'overview',    file: '../manual/00_overview.md',  title: '概要' },
  { id: 'setup',       file: '../manual/01_setup.md',     title: 'New Session' },
  { id: 'personas',    file: '../manual/02_personas.md',  title: 'Personas' },
  { id: 'tasks',       file: '../manual/03_tasks.md',     title: 'Tasks' },
  { id: 'discussion',  file: '../manual/04_discussion.md', title: 'Discussion' },
  { id: 'rag',         file: '../manual/05_rag.md',       title: 'Data Base (RAG)' },
  { id: 'patent',      file: '../manual/06_patent.md',    title: 'Patent Research' },
  { id: 'settings',    file: '../manual/07_settings.md',  title: 'Settings' },
  { id: 'helper',      file: '../manual/08_helper.md',    title: 'ヘルパー機能' },
] as const;

type PageId = typeof PAGES[number]['id'];

export default function ManualScreen() {
  const [currentId, setCurrentId] = useState<PageId>('overview');

  const currentPage = PAGES.find(p => p.id === currentId)!;
  const content = manualFiles[currentPage.file] ?? '（ページが見つかりません）';

  return (
    <div className="flex h-full">
      {/* TOCサイドバー */}
      <nav className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col py-4">
        <div className="px-4 mb-3 flex items-center gap-2 text-gray-500 text-xs font-bold uppercase tracking-wider">
          <BookOpen size={14} />
          マニュアル
        </div>
        {PAGES.map(page => (
          <button
            key={page.id}
            onClick={() => setCurrentId(page.id)}
            className={`flex items-center justify-between px-4 py-2.5 text-sm text-left transition-colors ${
              currentId === page.id
                ? 'bg-indigo-50 text-indigo-700 font-medium border-r-2 border-indigo-500'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <span>{page.title}</span>
            {currentId === page.id && <ChevronRight size={14} className="text-indigo-500" />}
          </button>
        ))}
      </nav>

      {/* コンテンツエリア */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 py-8">
          <article className="prose prose-gray prose-headings:font-semibold prose-h1:text-2xl prose-h2:text-xl prose-h2:border-b prose-h2:border-gray-200 prose-h2:pb-2 prose-table:text-sm prose-code:text-sm prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </article>
        </div>
      </div>
    </div>
  );
}
