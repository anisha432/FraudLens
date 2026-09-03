// Production: use env vars. Dev fallback: localhost:8000 (via Vite proxy or direct)
const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE = (import.meta as any).env?.VITE_WS_URL || 'ws://localhost:8000';

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('fraudlens_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchJSON(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...authHeaders(), ...options?.headers } });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Auth
export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Invalid credentials');
  }
  return res.json();
}

export async function register(name: string, email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password, confirm_password: password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Registration failed');
  }
  return res.json();
}

export async function getMe() {
  return fetchJSON('/auth/me');
}

export async function logout() {
  try { await fetchJSON('/auth/logout', { method: 'POST' }); } catch {}
  localStorage.removeItem('fraudlens_token');
}

export function setAuthToken(token: string) {
  localStorage.setItem('fraudlens_token', token);
}

export function getAuthToken(): string | null {
  return localStorage.getItem('fraudlens_token');
}

export function clearAuthToken() {
  localStorage.removeItem('fraudlens_token');
}

export async function uploadDataset(file: File) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/upload/dataset`, { method: 'POST', body: form, headers: authHeaders() });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function trainModel(datasetId: string, useSmote = true) {
  return fetchJSON('/train', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, use_smote: useSmote }),
  });
}

export async function getDashboardSummary() { return fetchJSON('/dashboard/summary'); }
export async function getAnalytics() { return fetchJSON('/dashboard/analytics'); }
export async function getTransactions(params: Record<string, string | number> = {}) {
  const qs = new URLSearchParams(params as any).toString();
  return fetchJSON(`/transactions?${qs}`);
}
export async function getTransaction(id: string) { return fetchJSON(`/transactions/${id}`); }
export async function getAlerts(params: Record<string, string | number> = {}) {
  const qs = new URLSearchParams(params as any).toString();
  return fetchJSON(`/alerts?${qs}`);
}
export async function updateAlert(alertId: string, data: { status?: string; notes?: string }) {
  return fetchJSON(`/alerts/${alertId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}
export async function getModels() { return fetchJSON('/models'); }
export async function getModelComparison() { return fetchJSON('/models/compare'); }
export async function getFeatureImportance() { return fetchJSON('/models/feature-importance'); }
export async function getThresholdAnalysis(modelName = 'xgboost') {
  return fetchJSON('/models/threshold', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_name: modelName }),
  });
}
export async function getExplanation(txId: string) { return fetchJSON(`/explanations/${txId}`); }
export async function getGlobalExplanation() { return fetchJSON('/explanations/global'); }
export async function getEDA() { return fetchJSON('/eda'); }
export async function getExecutiveAnalytics(params: Record<string, string | number> = {}) {
  const qs = new URLSearchParams(params as any).toString();
  return fetchJSON(`/analytics/executive${qs ? '?' + qs : ''}`);
}
export async function getHealth() { return fetchJSON('/health'); }
export function createWS() {
  const token = localStorage.getItem('fraudlens_token') || '';
  return new WebSocket(`${WS_BASE}/ws/live?token=${token}`);
}
export async function getActivityLog(params: Record<string, string | number> = {}) {
  const qs = new URLSearchParams(params as any).toString();
  return fetchJSON(`/auth/activity${qs ? '?' + qs : ''}`);
}

export async function generateDemo() {
  return fetchJSON('/demo/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
}

export async function getDatasets() { return fetchJSON('/datasets'); }

export async function getSystemStatus() {
  try {
    const health = await getHealth();
    const datasets = await getDatasets();
    // A dataset is considered loaded only if the CURRENT USER has their own datasets.
    // Do NOT check global health.models_loaded — that counts ALL users' models.
    const hasDataset = (datasets.datasets || []).length > 0;
    return {
      healthy: health.status === 'healthy',
      modelsLoaded: health.models_loaded || 0,
      hasDataset,
      datasets: datasets.datasets || [],
    };
  } catch {
    return { healthy: false, modelsLoaded: 0, hasDataset: false, datasets: [] };
  }
}
