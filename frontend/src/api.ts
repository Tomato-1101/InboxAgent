import type {
  HealthResponse,
  StatsResponse,
  EmailsResponse,
  EmailDetail,
  Group,
  TasksResponse,
  AnalyzePendingResponse,
  AnalyzeRunResponse,
  SettingsResponse,
  SmtpResponse,
  IngestResponse,
  FormatReplyResponse,
  SendReplyResponse,
} from './types'

const BASE = ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? JSON.stringify(body)
    } catch (_) {}
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  stats: () => request<StatsResponse>('/api/stats'),

  emails: (params?: {
    group_id?: string
    importance?: string
    q?: string
    needs_reply?: boolean
    limit?: number
  }) => {
    const p = new URLSearchParams()
    if (params?.group_id) p.set('group_id', params.group_id)
    if (params?.importance) p.set('importance', params.importance)
    if (params?.q) p.set('q', params.q)
    if (params?.needs_reply != null) p.set('needs_reply', String(params.needs_reply))
    if (params?.limit != null) p.set('limit', String(params.limit))
    const qs = p.toString()
    return request<EmailsResponse>(`/api/emails${qs ? '?' + qs : ''}`)
  },

  email: (id: string) => request<EmailDetail>(`/api/emails/${id}`),

  groups: () =>
    request<{ items: Group[] }>('/api/groups').then((r) => r.items),

  createGroup: (body: Omit<Group, 'id'>) =>
    request<{ id: string }>('/api/groups', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateGroup: (id: string, body: Omit<Group, 'id'>) =>
    request<{ ok: boolean }>(`/api/groups/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteGroup: (id: string) =>
    request<{ ok: boolean }>(`/api/groups/${id}`, { method: 'DELETE' }),

  tasks: (done?: boolean) => {
    const p = new URLSearchParams()
    if (done != null) p.set('done', String(done))
    const qs = p.toString()
    return request<TasksResponse>(`/api/tasks${qs ? '?' + qs : ''}`)
  },

  toggleTask: (id: string) =>
    request<{ ok: boolean; done: boolean }>(`/api/tasks/${id}/toggle`, {
      method: 'POST',
    }),

  formatReply: (email_id: string, draft: string) =>
    request<FormatReplyResponse>('/api/reply/format', {
      method: 'POST',
      body: JSON.stringify({ email_id, draft }),
    }),

  sendReply: (body: {
    email_id: string
    to: string
    subject: string
    body: string
  }) =>
    request<SendReplyResponse>('/api/reply/send', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  smtp: () => request<SmtpResponse>('/api/smtp'),

  ingest: () =>
    request<IngestResponse>('/api/ingest', { method: 'POST' }),

  analyzePending: (months?: number) => {
    const p = new URLSearchParams()
    if (months != null) p.set('months', String(months))
    return request<AnalyzePendingResponse>(
      `/api/analyze/pending${p.toString() ? '?' + p.toString() : ''}`
    )
  },

  analyzeRun: (opts?: { months?: number; max_emails?: number; model?: string }) =>
    request<AnalyzeRunResponse>('/api/analyze/run', {
      method: 'POST',
      body: JSON.stringify(opts ?? {}),
    }),

  settings: () => request<SettingsResponse>('/api/settings'),

  setAutoAnalyze: (enabled: boolean) =>
    request<{ ok: boolean; auto_analyze_enabled: boolean }>(
      '/api/settings/auto-analyze',
      {
        method: 'POST',
        body: JSON.stringify({ auto_analyze_enabled: enabled }),
      }
    ),
}
