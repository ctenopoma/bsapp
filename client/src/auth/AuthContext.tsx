/**
 * AuthContext – provides current user info and auth token to the whole app.
 *
 * In DEV_AUTH_BYPASS mode the token is undefined; the server identifies the
 * user via its own DEV_AUTH_BYPASS mechanism.
 */
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { AccountInfo, InteractionRequiredAuthError } from '@azure/msal-browser';
import { DEV_AUTH_BYPASS, msalInstance, loginRequest } from './msalConfig';

export interface AppUser {
  id: string;
  email: string;
  display_name: string;
  is_approved: boolean;
  is_admin: boolean;
}

interface AuthState {
  ready: boolean;           // MSAL initialised
  user: AppUser | null;     // null = not logged in
  token: string | undefined;
  login: () => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  ready: false,
  user: null,
  token: undefined,
  login: async () => {},
  logout: () => {},
  refreshUser: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

async function fetchMe(token: string | undefined): Promise<AppUser | null> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  try {
    const res = await fetch(`${BASE_URL}/api/auth/me`, { headers });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function callLogin(token: string | undefined): Promise<AppUser | null> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  try {
    const res = await fetch(`${BASE_URL}/api/auth/login`, { method: 'POST', headers });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<AppUser | null>(null);
  const [token, setToken] = useState<string | undefined>(undefined);

  // ── Dev bypass mode ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!DEV_AUTH_BYPASS) return;
    callLogin(undefined).then(u => {
      setUser(u);
      setReady(true);
    });
  }, []);

  // ── MSAL mode ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (DEV_AUTH_BYPASS || !msalInstance) return;
    msalInstance.initialize().then(async () => {
      await msalInstance.handleRedirectPromise();
      const accounts = msalInstance.getAllAccounts();
      if (accounts.length > 0) {
        await _acquireAndLogin(accounts[0]);
      }
      setReady(true);
    });
  }, []);

  async function _acquireAndLogin(account: AccountInfo) {
    if (!msalInstance) return;
    try {
      const result = await msalInstance.acquireTokenSilent({ ...loginRequest, account });
      setToken(result.accessToken);
      const u = await callLogin(result.accessToken);
      setUser(u);
    } catch (e) {
      if (e instanceof InteractionRequiredAuthError) {
        // token expired – force re-login
        setToken(undefined);
        setUser(null);
      }
    }
  }

  const login = useCallback(async () => {
    if (DEV_AUTH_BYPASS || !msalInstance) return;
    const result = await msalInstance.loginPopup(loginRequest);
    setToken(result.accessToken);
    const u = await callLogin(result.accessToken);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    if (DEV_AUTH_BYPASS || !msalInstance) return;
    msalInstance.logoutPopup();
    setUser(null);
    setToken(undefined);
  }, []);

  const refreshUser = useCallback(async () => {
    const u = await fetchMe(token);
    setUser(u);
  }, [token]);

  return (
    <AuthContext.Provider value={{ ready, user, token, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
