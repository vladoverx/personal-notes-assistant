import { API_BASE_URL } from '../config.js';
import { EventSourcePolyfill } from '../lib/eventsource.js';

const TOKEN_KEY = 'authToken';
const REFRESH_TOKEN_KEY = 'authRefreshToken';
const EXPIRES_AT_KEY = 'authTokenExpiresAt';

export class ApiError extends Error {
  constructor(message, status, headers) {
    super(message || 'Request failed');
    this.name = 'ApiError';
    this.status = status || 0;
    this.headers = headers || null;
    const retry = headers && typeof headers.get === 'function' ? headers.get('Retry-After') : null;
    const retryNum = retry != null ? parseInt(retry, 10) : null;
    this.retryAfter = Number.isFinite(retryNum) ? retryNum : null;
  }
}

export function getAuthToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export function setAuthToken(token) {
  try { if (token) localStorage.setItem(TOKEN_KEY, token); } catch { /* ignore */ }
}

export function clearAuthToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}

export function getRefreshToken() {
  try { return localStorage.getItem(REFRESH_TOKEN_KEY); } catch { return null; }
}

export function setRefreshToken(token) {
  try {
    if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
    else localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch { /* ignore */ }
}

export function getTokenExpiresAt() {
  try {
    const v = localStorage.getItem(EXPIRES_AT_KEY);
    return v ? parseInt(v, 10) : null;
  } catch { return null; }
}

export function setTokenExpiresAt(ts) {
  try {
    if (Number.isFinite(ts)) localStorage.setItem(EXPIRES_AT_KEY, String(ts));
    else localStorage.removeItem(EXPIRES_AT_KEY);
  } catch { /* ignore */ }
}

export function clearSession() {
  clearAuthToken();
  try { localStorage.removeItem(REFRESH_TOKEN_KEY); } catch { /* ignore */ }
  try { localStorage.removeItem(EXPIRES_AT_KEY); } catch { /* ignore */ }
}

export function setSession(session) {
  if (!session) return;
  setAuthToken(session.access_token);
  setRefreshToken(session.refresh_token || null);
  const now = Date.now();
  const skewMs = 5000; // refresh a few seconds before expiry
  const expiresInSec = Number(session.expires_in || 0);
  if (Number.isFinite(expiresInSec) && expiresInSec > 0) {
    setTokenExpiresAt(now + expiresInSec * 1000 - skewMs);
  } else {
    setTokenExpiresAt(null);
  }
}

function authHeaders(extra = {}) {
  const token = getAuthToken();
  const headers = { ...extra };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

let refreshPromise = null;

function dispatchUnauthorized(reason) {
  try {
    const evt = new CustomEvent('auth-unauthorized', { detail: { reason } });
    window.dispatchEvent(evt);
  } catch { /* ignore */ }
}

async function attemptTokenRefresh() {
  if (refreshPromise) return refreshPromise;
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    clearSession();
    dispatchUnauthorized('missing_refresh_token');
    throw new Error('Missing refresh token');
  }
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        throw new Error('Refresh failed');
      }
      const data = await response.json();
      setSession(data);
      return data;
    } catch (e) {
      clearSession();
      dispatchUnauthorized('refresh_failed');
      throw e;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

async function ensureFreshTokenIfNeeded() {
  const expiresAt = getTokenExpiresAt();
  if (!expiresAt) return; // unknown; skip proactive refresh
  if (Date.now() >= expiresAt) {
    await attemptTokenRefresh();
  }
}

// Expose for modules that need to ensure session freshness before long-lived requests (e.g., SSE)
export async function ensureSessionFresh() {
  await ensureFreshTokenIfNeeded();
}

async function jsonFetch(path, { method = 'GET', body, headers } = {}) {
  await ensureFreshTokenIfNeeded();
  const doRequest = async () => fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: authHeaders({ 'Content-Type': 'application/json', 'Accept': 'application/json', ...headers }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let response = await doRequest();
  if (response.status === 401) {
    try {
      await attemptTokenRefresh();
      response = await doRequest();
    } catch (e) {
      const error = new ApiError('Unauthorized', 401, response?.headers);
      error.payload = null;
      throw error;
    }
  }
  if (!response.ok) {
    let detail = 'Request failed';
    let payload = null;
    try {
      payload = await response.json();
      detail = payload?.detail || payload?.message || detail;
    } catch { /* ignore */ }
    const error = new ApiError(detail, response.status, response.headers);
    error.payload = payload;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

// Auth
export async function signIn(email, password) {
  return jsonFetch('/auth/signin', { method: 'POST', body: { email, password } });
}

export async function signUp(email, password) {
  return jsonFetch('/auth/signup', { method: 'POST', body: { email, password } });
}

export async function validateToken() {
  return jsonFetch('/auth/validate', { method: 'GET' });
}

export async function signOut() {
  return jsonFetch('/auth/signout', { method: 'POST' });
}

// Notes
export async function listNotes(limit = 200) {
  const params = new URLSearchParams({});
  if (limit) params.set('limit', String(limit));
  const qs = params.toString();
  return jsonFetch(`/notes/${qs ? `?${qs}` : ''}`, { method: 'GET' });
}

export async function getNote(noteId) {
  return jsonFetch(`/notes/${noteId}`, { method: 'GET' });
}

export async function createNote(note) {
  return jsonFetch('/notes/', { method: 'POST', body: note });
}

export async function updateNote(noteId, note) {
  return jsonFetch(`/notes/${noteId}`, { method: 'PATCH', body: note });
}

export async function deleteNote(noteId) {
  await jsonFetch(`/notes/${noteId}`, { method: 'DELETE' });
  return true;
}

// Chat streaming (SSE via polyfill)
export function streamChat({ message, previousResponseId }) {
  const url = new URL(`${API_BASE_URL}/chat/stream`);
  const payload = { message, previous_response_id: previousResponseId };
  return new EventSourcePolyfill(url, {
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    method: 'POST',
    payload: JSON.stringify(payload),
  });
}

// Search
export async function searchNotes({ query = null, tags = null, match_all_tags = false, note_type = null, is_archived = null, limit = 20 } = {}) {
  const body = {
    query: query || null,
    tags: Array.isArray(tags) ? tags : (tags ? [tags] : null),
    match_all_tags: Boolean(match_all_tags),
    note_type: note_type || null,
    is_archived: is_archived === null || is_archived === undefined ? null : Boolean(is_archived),
    limit: Math.max(1, Math.min(Number(limit) || 20, 200)),
  };
  return jsonFetch('/notes/search', { method: 'POST', body });
}

// Metadata (taxonomy and note types)
export async function getNoteTypes() {
  return jsonFetch('/metadata/note-types', { method: 'GET' });
}

export async function getUserTaxonomy() {
  return jsonFetch('/metadata/taxonomy', { method: 'GET' });
}


