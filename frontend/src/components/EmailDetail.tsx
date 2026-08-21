import { useEffect, useState, useCallback } from 'react'
import type { EmailDetail as EmailDetailType, Importance } from '../types'
import { api } from '../api'
import { ConfirmDialog } from './ConfirmDialog'

const IMP_COLOR: Record<Importance, string> = {
  '緊急': '#dc2626',
  '要対応': '#d97706',
  '参考': '#2563eb',
  '通知': '#64748b',
}

const IMP_BG: Record<Importance, string> = {
  '緊急': '#fef2f2',
  '要対応': '#fffbeb',
  '参考': '#eff6ff',
  '通知': '#f8fafc',
}

function reSubject(subject: string): string {
  if (subject.startsWith('Re:') || subject.startsWith('RE:')) return subject
  return `Re: ${subject}`
}

// メールは未信頼の外部コンテンツ。HTML を生描画せず、DOMParser でテキストだけ
// 取り出して表示する（script/onerror 等は実行されない＝XSS を構造的に防ぐ）。
function htmlToText(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  return (doc.body?.textContent || '').replace(/\n{3,}/g, '\n\n').trim()
}

interface Props {
  emailId: string | null
  onToast: (msg: string, kind?: 'success' | 'error' | 'info') => void
  onEmailSelect?: (id: string) => void
}

export function EmailDetail({ emailId, onToast, onEmailSelect }: Props) {
  const [detail, setDetail] = useState<EmailDetailType | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 返信フォーム
  const [replyTo, setReplyTo] = useState('')
  const [replySubject, setReplySubject] = useState('')
  const [replyBody, setReplyBody] = useState('')
  const [formatting, setFormatting] = useState(false)
  const [sending, setSending] = useState(false)
  const [smtpConfigured, setSmtpConfigured] = useState(true)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const loadSmtp = useCallback(async () => {
    try {
      const s = await api.smtp()
      setSmtpConfigured(s.configured)
    } catch (_) {
      setSmtpConfigured(false)
    }
  }, [])

  useEffect(() => {
    loadSmtp()
  }, [loadSmtp])

  useEffect(() => {
    if (!emailId) {
      setDetail(null)
      return
    }
    setLoading(true)
    setError(null)
    api.email(emailId)
      .then((d) => {
        setDetail(d)
        // 返信フォームの初期値設定
        setReplyTo(d.from_addr)
        setReplySubject(reSubject(d.subject))
        // AI下書きがあれば差し込む（送信済みの下書きは再投入しない）
        const suggested =
          d.drafts?.find((x) => x.status === '候補')?.body ??
          d.analysis?.suggested_reply ??
          ''
        setReplyBody(suggested)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [emailId])

  if (!emailId) {
    return (
      <div className="email-detail-pane">
        <div className="email-detail-empty">メールを選択してください</div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="email-detail-pane">
        <div className="loading-text">読み込み中…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="email-detail-pane">
        <div className="error-box" style={{ margin: 16 }}>{error}</div>
      </div>
    )
  }

  if (!detail) return null

  const analysis = detail.analysis
  const hasDraft = !!(
    detail.drafts?.find((x) => x.status === '候補')?.body || analysis?.suggested_reply
  )

  const handleFormat = async () => {
    setFormatting(true)
    try {
      const res = await api.formatReply(detail.id, replyBody)
      setReplyBody(res.formatted)
      onToast('AIで整形しました', 'success')
    } catch (e: any) {
      onToast(`整形エラー: ${e.message}`, 'error')
    } finally {
      setFormatting(false)
    }
  }

  const handleSendConfirm = () => {
    setConfirmOpen(true)
  }

  const handleSend = async () => {
    setConfirmOpen(false)
    setSending(true)
    try {
      const res = await api.sendReply({
        email_id: detail.id,
        to: replyTo,
        subject: replySubject,
        body: replyBody,
      })
      if (res.ok) {
        onToast(`送信しました (ID: ${res.message_id ?? '-'})`, 'success')
      } else {
        onToast(`送信失敗: ${res.detail ?? '不明なエラー'}`, 'error')
      }
    } catch (e: any) {
      onToast(`送信エラー: ${e.message}`, 'error')
    } finally {
      setSending(false)
    }
  }

  const actionTasks = detail.tasks.filter((t) => t.kind === 'action')
  const bodyContent = detail.body_text || ''

  return (
    <>
      <div className="email-detail-pane">
        <div className="email-detail-scroll">
          {/* ヘッダメタ */}
          <div className="detail-meta">
            <div className="detail-subject">{detail.subject}</div>
            <div className="detail-meta-row">
              <span className="detail-meta-label">差出人</span>
              <span className="detail-meta-val">
                {detail.from_name ? `${detail.from_name} <${detail.from_addr}>` : detail.from_addr}
              </span>
            </div>
            <div className="detail-meta-row">
              <span className="detail-meta-label">宛先</span>
              <span className="detail-meta-val">{detail.to_addrs}</span>
            </div>
            {detail.date && (
              <div className="detail-meta-row">
                <span className="detail-meta-label">日時</span>
                <span className="detail-meta-val">
                  {new Date(detail.date).toLocaleString('ja-JP')}
                </span>
              </div>
            )}
          </div>

          {/* AI分析結果 */}
          {analysis && (
            <>
              <div className="detail-section">
                <div className="detail-section-title">AI要約</div>
                <div className="detail-summary">{analysis.summary}</div>
              </div>

              <div className="detail-section">
                <div className="detail-section-title">分類</div>
                <div className="detail-badges">
                  {analysis.importance && (
                    <span
                      className="badge"
                      style={{
                        background: IMP_BG[analysis.importance],
                        color: IMP_COLOR[analysis.importance],
                        border: `1px solid ${IMP_COLOR[analysis.importance]}40`,
                        fontWeight: 600,
                      }}
                    >
                      {analysis.importance}
                    </span>
                  )}
                  {analysis.group_name && (
                    <span className="badge badge-group">{analysis.group_name}</span>
                  )}
                  {analysis.needs_reply && (
                    <span className="badge badge-needs-reply">要返信</span>
                  )}
                  {analysis.due_date && (
                    <span className="badge" style={{ background: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0' }}>
                      期日: {new Date(analysis.due_date).toLocaleDateString('ja-JP')}
                    </span>
                  )}
                </div>
              </div>
            </>
          )}

          {/* アクション項目 */}
          {actionTasks.length > 0 && (
            <div className="detail-section">
              <div className="detail-section-title">アクション項目</div>
              <div className="task-list">
                {actionTasks.map((t) => (
                  <div key={t.id} className={`task-item ${t.done ? 'done-item' : ''}`}>
                    <span>{t.done ? '✓' : '○'}</span>
                    <span>{t.title}</span>
                    {t.due_date && (
                      <span className="task-due" style={{ marginLeft: 'auto', fontSize: 11, color: '#9ca3af' }}>
                        {new Date(t.due_date).toLocaleDateString('ja-JP')}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 本文 */}
          {bodyContent && (
            <div className="detail-section">
              <div className="detail-section-title">本文</div>
              <div className="body-text">{bodyContent}</div>
            </div>
          )}
          {!bodyContent && detail.body_html && (
            <div className="detail-section">
              <div className="detail-section-title">本文（HTMLをテキスト表示）</div>
              <div className="body-text">{htmlToText(detail.body_html)}</div>
            </div>
          )}
        </div>

        {/* 返信エリア */}
        <div className="reply-area">
          <div className="reply-area-title">返信</div>

          {hasDraft && (
            <div className="ai-draft-notice">
              AIが定型返信案を用意しました（編集可能です）
            </div>
          )}

          {!smtpConfigured && (
            <div className="smtp-notice">
              SMTP未設定（会社PCで設定してください）。送信は無効です。
            </div>
          )}

          <div className="reply-field">
            <label>宛先</label>
            <input
              className="reply-input"
              value={replyTo}
              onChange={(e) => setReplyTo(e.target.value)}
            />
          </div>
          <div className="reply-field">
            <label>件名</label>
            <input
              className="reply-input"
              value={replySubject}
              onChange={(e) => setReplySubject(e.target.value)}
            />
          </div>
          <div className="reply-field">
            <label>本文</label>
            <textarea
              className="reply-input reply-textarea"
              value={replyBody}
              onChange={(e) => setReplyBody(e.target.value)}
              rows={4}
            />
          </div>

          <div className="reply-actions">
            <button
              className="btn-secondary btn btn-sm"
              onClick={handleFormat}
              disabled={formatting || sending || !replyBody}
            >
              {formatting ? (
                <>
                  <span className="spinning">⟳</span> 整形中…
                </>
              ) : (
                'AIで整形'
              )}
            </button>
            <button
              className="btn-primary btn btn-sm"
              onClick={handleSendConfirm}
              disabled={!smtpConfigured || sending || formatting || !replyTo || !replyBody}
            >
              {sending ? (
                <>
                  <span className="spinning">⟳</span> 送信中…
                </>
              ) : (
                '送信'
              )}
            </button>
          </div>
        </div>
      </div>

      {confirmOpen && (
        <ConfirmDialog
          title="この内容で送信しますか？"
          body={`宛先: ${replyTo}\n件名: ${replySubject}\n文字数: ${replyBody.length} 文字`}
          preview={replyBody}
          onConfirm={handleSend}
          onCancel={() => setConfirmOpen(false)}
          confirmLabel="送信"
        />
      )}
    </>
  )
}
