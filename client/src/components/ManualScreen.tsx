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

// ページ定義
// parent を指定するとサイドバーで親ページの下にネスト表示される
type Page = {
  id: string;
  file: string;
  title: string;
  parent?: string;
};

const PAGES: Page[] = [
  { id: 'overview',        file: '../manual/00_overview.md',   title: '概要' },
  { id: 'setup',           file: '../manual/01_setup.md',      title: 'New Session' },
  { id: 'setup-strategy',  file: '../manual/01a_strategy.md',  title: 'ストラテジー一覧', parent: 'setup' },
  { id: 'setup-flow',      file: '../manual/01b_flow.md',      title: 'フロー一覧',       parent: 'setup' },
  { id: 'personas',        file: '../manual/02_personas.md',   title: 'Personas' },
  { id: 'tasks',           file: '../manual/03_tasks.md',      title: 'Tasks' },
  { id: 'discussion',      file: '../manual/04_discussion.md', title: 'Discussion' },
  { id: 'rag',             file: '../manual/05_rag.md',        title: 'Data Base (RAG)' },
  { id: 'patent',          file: '../manual/06_patent.md',     title: 'Patent Research' },
  { id: 'settings',        file: '../manual/07_settings.md',   title: 'Settings' },
  { id: 'helper',          file: '../manual/08_helper.md',     title: 'ヘルパー機能' },
];

export default function ManualScreen() {
  const [currentId, setCurrentId] = useState('overview');

  const currentPage = PAGES.find(p => p.id === currentId) ?? PAGES[0];
  const content = manualFiles[currentPage.file] ?? '（ページが見つかりません）';

  // page: リンクをページ遷移に変換するカスタムレンダラー
  const linkRenderer = ({ href, children }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
    if (href?.startsWith('page:')) {
      const targetId = href.slice(5);
      return (
        <button
          onClick={() => setCurrentId(targetId)}
          className="text-indigo-600 hover:text-indigo-800 hover:underline cursor-pointer"
        >
          {children}
        </button>
      );
    }
    return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
  };

  // サイドバーアイテムの描画（親/子で見た目を変える）
  const renderNavItem = (page: Page) => {
    const isActive = currentId === page.id;
    const isChild = !!page.parent;

    return (
      <button
        key={page.id}
        onClick={() => setCurrentId(page.id)}
        className={`flex items-center justify-between text-sm text-left w-full transition-colors ${
          isChild ? 'pl-8 pr-4 py-2' : 'px-4 py-2.5'
        } ${
          isActive
            ? 'bg-indigo-50 text-indigo-700 font-medium border-r-2 border-indigo-500'
            : isChild
            ? 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
        }`}
      >
        <span className={isChild ? 'text-xs' : ''}>{page.title}</span>
        {isActive && <ChevronRight size={14} className="text-indigo-500 shrink-0" />}
      </button>
    );
  };

  return (
    <div className="flex h-full">
      {/* TOCサイドバー */}
      <nav className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col py-4 overflow-y-auto">
        <div className="px-4 mb-3 flex items-center gap-2 text-gray-500 text-xs font-bold uppercase tracking-wider">
          <BookOpen size={14} />
          マニュアル
        </div>
        {PAGES.map(page => renderNavItem(page))}
      </nav>

      {/* コンテンツエリア */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 py-8">
          <article className="prose prose-gray prose-headings:font-semibold prose-h1:text-2xl prose-h2:text-xl prose-h2:border-b prose-h2:border-gray-200 prose-h2:pb-2 prose-table:text-sm prose-code:text-sm prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ a: linkRenderer }}
            >
              {content}
            </ReactMarkdown>
          </article>
        </div>
      </div>
    </div>
  );
}
