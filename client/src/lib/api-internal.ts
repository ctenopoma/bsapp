/**
 * Shared internal fetch utility.
 * Exported as `request` for use by server-db.ts.
 * The token is kept in api.ts via setAuthToken().
 */
export { request } from './api';
