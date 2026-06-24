// 重要度
export type Importance = '緊急' | '要対応' | '参考' | '通知'

// ヘルス
export interface HealthResponse {
  ok: boolean
  service: string
  version: string
}

// 統計
export interface StatsResponse {
  total: number
  analyzed: number
  by_importance: Record<Importance, number>
  open_tasks: number
  settings_model: string
}

// グループ
export interface Group {
  id: string
  name: string
  color: string
  rule_hint: string
  sort_order: number
}

// メール一覧アイテム
export interface EmailItem {
  id: string
  from_name: string
  from_addr: string
  subject: string
  date: string | null
  has_attachments: boolean
  importance: Importance | null
  group_id: string | null
  group_name: string | null
  summary: string | null
  needs_reply: boolean
  due_date: string | null
  analyzed: boolean
}

export interface EmailsResponse {
  items: EmailItem[]
  count: number
}

// タスク (メール詳細内)
export interface TaskItem {
  id: string
  kind: 'reply_pending' | 'action'
  title: string
  done: boolean
  due_date: string | null
}

// 下書き
export interface DraftItem {
  id: string
  body: string
  status: string
}

// 分析結果
export interface Analysis {
  summary: string
  importance: Importance
  group_id: string | null
  group_name: string | null
  needs_reply: boolean
  due_date: string | null
  suggested_reply: string | null
  pipeline: string | null
}

// メール詳細
export interface EmailDetail {
  id: string
  from_name: string
  from_addr: string
  to_addrs: string[]
  subject: string
  date: string | null
  body_text: string | null
  body_html: string | null
  has_attachments: boolean
  analysis: Analysis | null
  tasks: TaskItem[]
  drafts: DraftItem[]
}

// タスク一覧
export interface TaskListItem {
  id: string
  kind: 'reply_pending' | 'action'
  title: string
  done: boolean
  source: 'ai' | 'manual'
  email_id: string | null
  email_subject: string | null
  due_date: string | null
}

export interface TasksResponse {
  items: TaskListItem[]
  count: number
}

// 分析予測
export interface AnalyzePendingResponse {
  pending: number
  months: number
  estimated_calls: number
  model: string
}

// 設定
export interface SettingsResponse {
  auto_analyze_enabled: boolean
  claude_model: string
  analyze_months: number
}

// SMTP
export interface SmtpResponse {
  configured: boolean
  host: string
  port: number
  secure: boolean
  user: string
  from_name: string
}

// 取り込み
export interface IngestResponse {
  ok: boolean
  profile?: string
  mbox_count?: number
  new_messages?: number
  per_folder?: Record<string, number>
  error?: string
}

// 分析実行
export interface AnalyzeRunResponse {
  ok: boolean
  analyzed: number
  batches: number
}

// 返信整形
export interface FormatReplyResponse {
  formatted: string
}

// 返信送信
export interface SendReplyResponse {
  ok: boolean
  message_id?: string
  detail?: string
}
