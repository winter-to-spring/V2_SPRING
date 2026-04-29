import { Notification, FocusSession, Briefing, Integration } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

interface ApiError extends Error {
  status: number;
  data?: unknown;
}

async function api<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = new URL(path, API_BASE).toString();
  
  const token = typeof window !== 'undefined' 
    ? localStorage.getItem('cochat_token')
    : null;

  const headers = new Headers(init?.headers || {});
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const error: ApiError = new Error(
      `API error: ${response.status}`,
    ) as ApiError;
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return response.json();
}

// Notification endpoints
export async function listNotifications(
  workspaceId: string,
  limit?: number,
): Promise<Notification[]> {
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());
  const path = `/api/v1/workspaces/${workspaceId}/notifications${
    params.toString() ? '?' + params.toString() : ''
  }`;
  return api<Notification[]>(path);
}

export async function patchNotification(
  workspaceId: string,
  notificationId: string,
  payload: { read?: boolean },
): Promise<Notification> {
  const path = `/api/v1/workspaces/${workspaceId}/notifications/${notificationId}`;
  return api<Notification>(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

// Focus endpoints
export async function startFocus(
  workspaceId: string,
  payload: { duration_minutes: number },
): Promise<FocusSession> {
  const path = `/api/v1/workspaces/${workspaceId}/focus/start`;
  return api<FocusSession>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function endFocus(
  workspaceId: string,
): Promise<FocusSession> {
  const path = `/api/v1/workspaces/${workspaceId}/focus/end`;
  return api<FocusSession>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function getCurrentFocus(
  workspaceId: string,
): Promise<FocusSession | null> {
  const path = `/api/v1/workspaces/${workspaceId}/focus/current`;
  return api<FocusSession | null>(path);
}

// Briefing endpoints
export async function generateBriefing(
  workspaceId: string,
): Promise<Briefing> {
  const path = `/api/v1/workspaces/${workspaceId}/briefings/generate`;
  return api<Briefing>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function getLatestBriefing(
  workspaceId: string,
): Promise<Briefing | null> {
  const path = `/api/v1/workspaces/${workspaceId}/briefings/latest`;
  return api<Briefing | null>(path);
}

// Integration endpoints
export async function listIntegrations(
  workspaceId: string,
): Promise<Integration[]> {
  const path = `/api/v1/workspaces/${workspaceId}/integrations`;
  return api<Integration[]>(path);
}

export async function getSlackInstallUrl(
  workspaceId: string,
): Promise<{ url: string }> {
  const path = `/api/v1/workspaces/${workspaceId}/integrations/slack/install-url`;
  return api<{ url: string }>(path);
}

export { api };
