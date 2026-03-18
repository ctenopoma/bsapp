/**
 * MSAL (Microsoft Authentication Library) configuration.
 *
 * Set environment variables in .env (or .env.local for dev):
 *   VITE_AZURE_CLIENT_ID   – App registration client ID
 *   VITE_AZURE_TENANT_ID   – Tenant ID  (or "common" for multi-tenant)
 *
 * If VITE_DEV_AUTH_BYPASS=true the MSAL flow is skipped entirely and the
 * server's DEV_AUTH_BYPASS mode is used instead.
 */
import { Configuration, PublicClientApplication, LogLevel } from '@azure/msal-browser';

export const DEV_AUTH_BYPASS = import.meta.env.VITE_DEV_AUTH_BYPASS === 'true';

const CLIENT_ID = import.meta.env.VITE_AZURE_CLIENT_ID ?? '';
const TENANT_ID = import.meta.env.VITE_AZURE_TENANT_ID ?? 'common';

export const msalConfig: Configuration = {
  auth: {
    clientId: CLIENT_ID,
    authority: `https://login.microsoftonline.com/${TENANT_ID}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        if (import.meta.env.DEV) console.log('[MSAL]', message);
      },
      logLevel: LogLevel.Warning,
    },
  },
};

export const loginRequest = {
  scopes: [`api://${CLIENT_ID}/access_as_user`],
};

export const msalInstance = DEV_AUTH_BYPASS
  ? null
  : new PublicClientApplication(msalConfig);
