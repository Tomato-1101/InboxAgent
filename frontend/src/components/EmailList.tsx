import type { EmailItem, Importance } from '../types'

const IMP_COLOR: Record<Importance, string> = {
  '緊急': '#dc2626',
  '要対応': '#d97706',
  '参考': '#2563eb',
  '通知': '#64748b',
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000)
  if (diffDays === 0) {
    return d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
  }
  if (diffDays < 7) {
    return d.toLocaleDateString('ja-JP', { weekday: 'short' })
  }
  return d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' })
}

interface Props {
  emails: EmailItem[]
  selectedId: string | null
  onSelect: (id: string) => void
  loading: boolean
  error: string | null
}

export function EmailList({ emails, selectedId, onSelect, loading, error }: Props) {
  if (loading) {
    return <div className="loading-text">読み込み中…</div>
  }
  if (error) {
    return <div className="error-box">{error}</div>
  }

  return (
    <div className="email-list-scroll">
      {emails.length === 0 && (
        <div className="empty-state">メールがありません</div>
      )}
      {emails.map((email) => (
        <div
          key={email.id}
          className={`email-row ${selectedId === email.id ? 'selected' : ''} ${
            !email.analyzed ? 'unanalyzed' : ''
          }`}
          onClick={() => onSelect(email.id)}
        >
          <div
            className="email-importance-bar"
            style={{
              background: email.importance
                ? IMP_COLOR[email.importance]
                : '#e5e7eb',
            }}
          />
          <div className="email-row-content">
            <div className="email-row-top">
              <span className="email-from">
                {email.from_name || email.from_addr}
              </span>
              <span className="email-date">{formatDate(email.date)}</span>
            </div>
            <div className="email-subject">{email.subject}</div>
            {email.summary && (
              <div className="email-summary">{email.summary}</div>
            )}
            <div className="email-row-meta">
              {!email.analyzed && (
                <span className="badge badge-unanalyzed">未分析</span>
              )}
              {email.group_name && (
                <span className="badge badge-group">{email.group_name}</span>
              )}
              {email.needs_reply && (
                <span className="badge badge-needs-reply">要返信</span>
              )}
              {email.has_attachments && (
                <span className="badge badge-attachment">添付</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
