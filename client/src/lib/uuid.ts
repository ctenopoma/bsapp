/**
 * crypto.randomUUID() のフォールバック付きラッパー。
 * HTTP + IPアドレスアクセス (非セキュアコンテキスト) では
 * crypto.randomUUID が使えないため Math.random ベースの実装にフォールバックする。
 */
export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // 非セキュアコンテキスト向けフォールバック (RFC 4122 v4)
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}
