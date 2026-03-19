import { useState } from 'react';
import { MessageSquare, LogIn, Clock } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { DEV_AUTH_BYPASS } from '../auth/msalConfig';

interface Props {
  pending?: boolean; // user exists but not yet approved
}

export default function LoginScreen({ pending = false }: Props) {
  const { login, refreshUser } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      await login();
    } catch (e: any) {
      setError(e.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-lg p-8 flex flex-col gap-6">
        <div className="flex items-center gap-3">
          <MessageSquare className="text-blue-600" size={32} />
          <h1 className="text-2xl font-bold text-gray-900">AI Discuss</h1>
        </div>

        {pending ? (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2 text-amber-700 bg-amber-50 rounded-lg px-4 py-3">
              <Clock size={18} className="shrink-0" />
              <span className="text-sm font-medium">アカウントは承認待ちです</span>
            </div>
            <p className="text-sm text-gray-500">
              管理者がアカウントを承認すると利用できるようになります。しばらくお待ちください。
            </p>
            <button
              onClick={() => refreshUser()}
              className="w-full py-2 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
            >
              状態を再確認
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-gray-600">
              {DEV_AUTH_BYPASS
                ? '開発モード: 認証はバイパスされています'
                : 'Microsoftアカウントでサインインしてください'}
            </p>
            {DEV_AUTH_BYPASS && (
              <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                バックエンドへの接続に失敗しました。<br />
                サーバーが起動しているか、<code>host/.env</code> に{' '}
                <code>DEV_AUTH_BYPASS=true</code> が設定されているか確認してください。
              </div>
            )}
            {error && (
              <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>
            )}
            <button
              onClick={handleLogin}
              disabled={loading || DEV_AUTH_BYPASS}
              className="flex items-center justify-center gap-2 w-full py-3 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <LogIn size={18} />
              {loading ? 'サインイン中...' : 'Microsoftでサインイン'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
