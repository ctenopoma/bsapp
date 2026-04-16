/**
 * AuthContext – Windowsユーザー名を唯一の識別子として使用する。
 * Azure AD / MSAL は使用しない。
 */
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { initAuth } from '../lib/api';

export interface AppUser {
  id: string;
  email: string;
  display_name: string;
  is_approved: boolean;
  is_admin: boolean;
}

interface AuthState {
  ready: boolean;
  user: AppUser | null;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  ready: false,
  user: null,
  refreshUser: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

async function callLogin(): Promise<AppUser | null> {
  const { buildRequestHeaders } = await import('../lib/api');
  const headers = buildRequestHeaders();
  try {
    const res = await fetch(`${BASE_URL}/api/auth/login`, { method: 'POST', headers });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchMe(): Promise<AppUser | null> {
  const { buildRequestHeaders } = await import('../lib/api');
  const headers = buildRequestHeaders();
  try {
    const res = await fetch(`${BASE_URL}/api/auth/me`, { headers });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<AppUser | null>(null);

  useEffect(() => {
    initAuth()
      .catch(() => {})
      .then(() => callLogin())
      .then(u => {
        if (!u) {
          console.error(
            '[Auth] /api/auth/login failed. ' +
            'バックエンドが DEV_AUTH_BYPASS=true で起動しているか確認してください。'
          );
        }
        setUser(u);
        setReady(true);
      });
  }, []);

  const refreshUser = useCallback(async () => {
    const u = await fetchMe();
    setUser(u);
  }, []);

  return (
    <AuthContext.Provider value={{ ready, user, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
