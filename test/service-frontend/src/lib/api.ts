const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000';

interface FetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  body?: Record<string, any>;
  headers?: Record<string, string>;
}

async function fetchAPI<T = any>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cochat_token') : null;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = `${API_URL}${endpoint}`;
  const fetchInit: RequestInit = {
    method: options.method || 'GET',
    headers,
  };

  if (options.body) {
    fetchInit.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, fetchInit);

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }

  return response.text() as any;
}

export async function login(email: string, password: string): Promise<{ token: string; user: any }> {
  return fetchAPI('/api/auth/login', {
    method: 'POST',
    body: { email, password },
  });
}

export async function register(email: string, password: string, name: string): Promise<{ token: string; user: any }> {
  return fetchAPI('/api/auth/register', {
    method: 'POST',
    body: { email, password, name },
  });
}

export async function me(): Promise<any> {
  return fetchAPI('/api/auth/me', {
    method: 'GET',
  });
}

export async function listIntegrations(): Promise<any[]> {
  return fetchAPI('/api/integrations', {
    method: 'GET',
  });
}

export async function slackInstallUrl(): Promise<{ url: string }> {
  return fetchAPI('/api/integrations/slack/install-url', {
    method: 'GET',
  });
}

export async function listNotifications(): Promise<any[]> {
  return fetchAPI('/api/notifications', {
    method: 'GET',
  });
}

export async function markRead(notificationId: string): Promise<void> {
  return fetchAPI(`/api/notifications/${notificationId}/read`, {
    method: 'POST',
  });
}

export async function startFocus(durationMinutes?: number): Promise<any> {
  return fetchAPI('/api/focus/start', {
    method: 'POST',
    body: durationMinutes ? { durationMinutes } : {},
  });
}

export async function endFocus(): Promise<any> {
  return fetchAPI('/api/focus/end', {
    method: 'POST',
  });
}

export async function getCurrentFocus(): Promise<any> {
  return fetchAPI('/api/focus/current', {
    method: 'GET',
  });
}

export async function getLatestBriefing(): Promise<any> {
  return fetchAPI('/api/briefings/latest', {
    method: 'GET',
  });
}

export async function postFeedback(feedback: string, type?: string): Promise<void> {
  return fetchAPI('/api/feedback', {
    method: 'POST',
    body: { feedback, type },
  });
}

export function streamNotifications(onMessage: (event: MessageEvent) => void, onError?: (error: Event) => void): EventSource {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cochat_token') : null;
  const url = new URL(`${API_URL}/api/notifications/stream`);
  
  if (token) {
    url.searchParams.append('token', token);
  }

  const eventSource = new EventSource(url.toString());
  eventSource.addEventListener('message', onMessage);
  
  if (onError) {
    eventSource.addEventListener('error', onError);
  }

  return eventSource;
}