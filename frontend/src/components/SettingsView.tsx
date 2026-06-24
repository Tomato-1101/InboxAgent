import { useEffect, useState } from 'react'
import type { SettingsResponse, SmtpResponse } from '../types'
import { api } from '../api'

interface Props {
  onToast: (msg: string, kind?: 'success' | 'error' | 'info') => void
}

export function SettingsView({ onToast }: Props) {
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [smtp, setSmtp] = useState<SmtpResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toggling, setToggling] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, smtp_] = await Promise.all([api.settings(), api.smtp()])
      setSettings(s)
      setSmtp(smtp_)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleAutoAnalyzeToggle = async () => {
    if (!settings) return
    const next = !settings.auto_analyze_enabled
    setToggling(true)
    try {
      const res = await api.setAutoAnalyze(next)
      setSettings({ ...settings, auto_analyze_enabled: res.auto_analyze_enabled })
      onToast(
        res.auto_analyze_enabled ? '自動分析をONにしました' : '自動分析をOFFにしました',
        'success'
      )
    } catch (e: any) {
      onToast(`設定変更に失敗: ${e.message}`, 'error')
    } finally {
      setToggling(false)
    }
  }

  if (loading) return <div className="loading-text">読み込み中…</div>
  if (error) return <div className="error-box" style={{ margin: 20 }}>{error}</div>

  return (
    <div className="settings-view">
      <div className="page-title">設定</div>

      {/* 自動分析 */}
      <div className="settings-card">
        <div className="settings-card-title">自動分析</div>
        <div className="settings-row">
          <span className="settings-key">新着メールを自動でAI分析</span>
          <label className="toggle-switch" style={{ opacity: toggling ? 0.5 : 1 }}>
            <input
              type="checkbox"
              checked={settings?.auto_analyze_enabled ?? false}
              onChange={handleAutoAnalyzeToggle}
              disabled={toggling}
            />
            <span className="toggle-track" />
          </label>
        </div>
        <div className="settings-warn">
          ONにすると新着メールを自動でAI分析します。APIを消費します。デフォルトはOFFです。
        </div>
      </div>

      {/* モデル・分析設定 */}
      {settings && (
        <div className="settings-card">
          <div className="settings-card-title">分析設定（読み取り専用）</div>
          <div className="settings-row">
            <span className="settings-key">使用モデル</span>
            <span className="settings-val">{settings.claude_model}</span>
          </div>
          <div className="settings-row">
            <span className="settings-key">分析対象月数</span>
            <span className="settings-val">{settings.analyze_months} ヶ月</span>
          </div>
        </div>
      )}

      {/* SMTP */}
      <div className="settings-card">
        <div className="settings-card-title">SMTP設定</div>
        {smtp?.configured ? (
          <>
            <div className="settings-row">
              <span className="settings-key">状態</span>
              <span className="settings-val" style={{ color: '#16a34a' }}>設定済み</span>
            </div>
            <div className="settings-row">
              <span className="settings-key">ホスト</span>
              <span className="settings-val">{smtp.host}:{smtp.port}</span>
            </div>
            <div className="settings-row">
              <span className="settings-key">ユーザー</span>
              <span className="settings-val">{smtp.user}</span>
            </div>
            <div className="settings-row">
              <span className="settings-key">送信者名</span>
              <span className="settings-val">{smtp.from_name}</span>
            </div>
            <div className="settings-row">
              <span className="settings-key">パスワード</span>
              <span className="settings-val" style={{ color: '#9ca3af' }}>（非表示）</span>
            </div>
          </>
        ) : (
          <div className="settings-row">
            <span className="settings-key">状態</span>
            <span className="settings-val" style={{ color: '#dc2626' }}>未設定</span>
          </div>
        )}
      </div>
    </div>
  )
}
