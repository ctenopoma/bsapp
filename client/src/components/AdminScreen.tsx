import { useEffect, useState } from 'react';
import { Check, X, ShieldCheck, ShieldOff, Users } from 'lucide-react';
import { request } from '../lib/api';

interface UserSummary {
  id: string;
  email: string;
  display_name: string;
  is_approved: boolean;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
}

export default function AdminScreen() {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await request<UserSummary[]>('/api/admin/users');
      setUsers(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const approve = async (id: string) => {
    await request(`/api/admin/users/${id}/approve`, { method: 'POST' });
    await load();
  };

  const reject = async (id: string) => {
    await request(`/api/admin/users/${id}/reject`, { method: 'POST' });
    await load();
  };

  const toggleAdmin = async (id: string) => {
    await request(`/api/admin/users/${id}/toggle-admin`, { method: 'POST' });
    await load();
  };

  return (
    <div className="p-6 max-w-4xl mx-auto flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Users size={24} className="text-blue-600" />
        <h2 className="text-xl font-bold text-gray-900">ユーザー管理</h2>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

      {loading ? (
        <div className="text-sm text-gray-400 py-8 text-center">読み込み中...</div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">ユーザー</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">登録日</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">ステータス</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{u.display_name || u.email}</div>
                    <div className="text-xs text-gray-400">{u.email}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {new Date(u.created_at).toLocaleDateString('ja-JP')}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.is_approved ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {u.is_approved ? <Check size={11} /> : <X size={11} />}
                        {u.is_approved ? '承認済み' : '未承認'}
                      </span>
                      {u.is_admin && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                          <ShieldCheck size={11} />
                          管理者
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      {u.is_approved ? (
                        <button
                          onClick={() => reject(u.id)}
                          className="flex items-center gap-1 px-2 py-1 text-xs rounded-md text-red-600 hover:bg-red-50 transition-colors"
                          title="承認取り消し"
                        >
                          <X size={13} /> 取消
                        </button>
                      ) : (
                        <button
                          onClick={() => approve(u.id)}
                          className="flex items-center gap-1 px-2 py-1 text-xs rounded-md text-green-700 hover:bg-green-50 transition-colors"
                          title="承認"
                        >
                          <Check size={13} /> 承認
                        </button>
                      )}
                      <button
                        onClick={() => toggleAdmin(u.id)}
                        className="flex items-center gap-1 px-2 py-1 text-xs rounded-md text-blue-600 hover:bg-blue-50 transition-colors"
                        title={u.is_admin ? '管理者を解除' : '管理者に設定'}
                      >
                        {u.is_admin ? <ShieldOff size={13} /> : <ShieldCheck size={13} />}
                        {u.is_admin ? '管理者解除' : '管理者にする'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && (
            <div className="text-center text-sm text-gray-400 py-8">ユーザーがいません</div>
          )}
        </div>
      )}
    </div>
  );
}
